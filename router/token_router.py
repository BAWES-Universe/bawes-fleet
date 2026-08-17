#!/usr/bin/env python3
"""token_router.py — the FLEET TOKEN ROUTER (T-UNIVERSE-013, khalid spec).

The marketplace where every AI lane registers and every task gets routed:
  - Any brick hosting an AI endpoint REGISTERS it: endpoint URL + model +
    capacity + cost/task + quality tier + auth secret (vaulted, never served).
  - Requests carry a quality need: routine -> cheapest capable registered lane;
    audit/high-value -> advanced lane; fallback -> a designated default lane.
  - CREDENTIALS NEVER SHARED (khalid's core rule): a lane's API key stays in
    the router's vault (mode-600 secret files); consumers get scoped per-brick
    tokens and the router proxies the call — the consumer never sees the key.
  - Every SERVED task is billed once (invoke() is the only meter).
  - Revocation is instant. Fail-open doctrine: degrade, never crash.

Hostile-DA hardened (all 12 findings closed):
  1. SSRF: endpoints validated at register AND invoke — private/loopback/
     link-local/metadata ranges rejected; redirects NOT followed (each hop
     would need re-validation, so we refuse); DNS rebinding blocked by
     resolving to IP and checking every candidate address.
  2. Secret exfil: invoke() masks echoed Authorization headers in upstream
     responses (the vaulted key can never round-trip to a consumer).
  3. Ledger privacy: /ledger always scoped to the CALLER's brick.
  4. Routing policy: cost floor (>= COST_FLOOR) + quality floor (audit is
     never served by a routine lane) + default_lane fallback wired.
  5. Bill once: route() PICKs without debiting; invoke() is the only meter.
  6. Schema: _read validates types; corrupt rows counted, never crash.
  7. Vault hygiene: os.open(0o600) atomic create, vault dir 0700,
     secret unlinked before lane rewrite (no orphans on failure).
  8. Response cap: upstream body streamed, capped at 1MB, aborted beyond.
  9. Token lookup: single index file (token -> brick), no per-request scan.
  10. Audit-before-mutation everywhere.
  11. route()/lanes() never expose endpoints (invoke by lane_id only).
  12. CI: hostile probes for HTTP matrix, SSRF, reflection, billing.

round-138 card 6 (AGI access for every human's bricks): tokens are issued ONLY
by the sudo-gated, registry-checked token_issue.py (refuses unregistered
brick_ids, audits issue/revoke); the tokens dir is root:root 0700 (non-root
file-drop closed; ubuntu keeps read-only ACLs so brain clients keep working);
invoke() enforces per-token lane_scope fail-closed + spend cap; revoke =
delete + forced reindex + audit row. GLM stays AGI-brainstorming-only (scope),
gpt-4o stays disabled (lane active:false).

round-139 card 8 (transparency surface — F-19): invoke() measures latency_ms
around every lane call and appends one measurement row
{ts, brick_id, lane, model, latency_ms, cost_usd, tokens, billed} to
--measurements-path (default <state-dir>/measurements.jsonl) — the feed that
drives the per-brick status card. tokens comes from the lane's usage object
(OpenAI/DeepSeek/OpenRouter shape) when parseable, else null (honest
"unknown"); cost_usd is the BILLED lane price (0.0 on failed attempts — the
ledger still bills once, only on 2xx, finding DA-3). Router auth, billing,
and the ledger are unchanged.
"""
from __future__ import annotations
import argparse, fcntl, hashlib, ipaddress, json, os, pathlib, re, socket, sys, time
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

LANE_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
BRICK_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
QUALITY_TIERS = {"routine", "audit", "advanced"}
COST_FLOOR = 0.0005          # cheaper than this = suspicious (poisoned free lane)
MAX_RESPONSE_BYTES = 1_000_000
SECRET_MIN = 16

# ---- round-146 item 3&4: allowance meter + escape paths ----
# The meter lives in the register dir; allowance_meter.py is the only writer.
sys.path.insert(0, "/srv/bricks/ovh-server-001")
sys.path.insert(0, "/srv/bricks/orchestrator")  # banana_spend.py (T-026 sink)
import allowance_meter  # noqa: E402
from banana_spend import BananaSpend, beyond_cap_price  # noqa: E402
SPEND_LEDGER = pathlib.Path("/srv/bricks/register/spend.jsonl")
ALLOWANCE_NOTIFIER = "/srv/bricks/ovh-server-001/allowance_notifier.py"
# C2 (round-143b): user keys attach ONLY to fleet-allowlisted provider
# endpoints — NO user-supplied endpoints; the SSRF class is removed by
# construction. _validate_endpoint stays as defense-in-depth.
FLEET_BYOK_ALLOWLIST = {
    "deepseek":   ("https://api.deepseek.com/chat/completions",
                   "deepseek-v4-flash", 0.002),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions",
                   "z-ai/glm-5.2", 0.03),
    "openai":     ("https://api.openai.com/v1/chat/completions",
                   "gpt-4o-mini", 0.0015),
}

# ---- round-139 card 5 (genius brick, AGI ruling ratified): MANDATORY
# context envelope at EVERY call. Three fields, no turn completes without
# them: retrieved_docs (top-k vector chunks, explicit [] if none),
# capability_card (brick_id/lanes/caps/limits from the caller's token
# record), honesty_fallback (exact no-context template). ----
VECTOR_STORE_PATH = pathlib.Path("/srv/bricks/orchestrator/vector-store.json")
REGISTRY_PATH = pathlib.Path("/srv/bricks/register/registry.jsonl")
MAX_RETRIEVED_DOCS = 3
HONESTY_FALLBACK = ("I don't have memory of that — I can only answer from "
                    "verified fleet knowledge. Ask differently or I'll route "
                    "this to the fleet queue.")
STOPWORDS = frozenset("""a an and are as at be by for from has have how i in is it
its of on or that the this to was what when where which who will with you your
we our they their can could would should do does did not no yes about into
over under than then there here out up down more most some any all each
tell me what the about fleet brain answer question""".split())

# SSRF blocklist superset (finding DA-4): Python flags + ranges Python misses
def _is_blocked_ip(ip) -> bool:
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved \
       or ip.is_multicast or ip.is_unspecified:
        return True
    # manual superset: CGNAT 100.64/10, 6to4 relay 192.88.99/24
    if ip.version == 4:
        b = int(ip)
        return (b >> 24) == 100 or (b >> 16) == 0xC058
    return False

class NoRedirect(urllib.request.HTTPRedirectHandler):
    """REFUSE all 3xx (finding DA-1 CRIT): urllib's default handler follows
    302 cross-host without re-validation — that is the SSRF hole."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused (SSRF guard)", headers, fp)

def _blocked_target(host: str) -> bool:
    """SSRF guard: reject private/loopback/link-local/metadata/reserved IPs.
    DNS-rebind-safe: resolve ALL addresses; ANY private hit blocks."""
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return True
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_blocked_ip(ip):
            return True
    return False

def _validate_endpoint(endpoint: str) -> str:
    """Reject non-http(s), private targets, and path weirdness. Returns host."""
    if not endpoint.startswith(("http://", "https://")):
        raise ValueError("endpoint must be http(s)://")
    p = urlparse(endpoint)
    if not p.hostname:
        raise ValueError("endpoint needs a hostname")
    host = p.hostname.rstrip(".")
    # literal IP fast-path (no DNS involved)
    try:
        ip = ipaddress.ip_address(host)
        if _is_blocked_ip(ip):
            raise ValueError("endpoint targets a blocked address range (private/loopback/metadata)")
    except ValueError:
        if _blocked_target(host):
            raise ValueError("endpoint resolves to a blocked address range "
                             "(private/loopback/metadata) — SSRF guard")
    return host

def _retrieve_docs(query: str, k: int = MAX_RETRIEVED_DOCS) -> list[dict]:
    """round-139 genius standard (retrieval-first): keyword-match the fleet
    vector store for the user's question. Returns top-k docs
    {sha, topic, text, receipt, score}. EXPLICIT [] when the store is
    unreadable or nothing matches — never a partial/guessed answer."""
    if not query:
        return []
    try:
        store = json.loads(VECTOR_STORE_PATH.read_text())
    except Exception:
        return []
    docs = store.get("docs") if isinstance(store, dict) else None
    if not isinstance(docs, list):
        return []
    terms = [t for t in re.findall(r"[a-z0-9]{3,}", query.lower())
             if t not in STOPWORDS]
    if not terms:
        return []
    scored = []
    for d in docs:
        if not isinstance(d, dict):
            continue
        hay = f"{d.get('text') or ''} {d.get('topic') or ''}".lower()
        hits = sum(hay.count(t) for t in terms)
        if hits > 0:
            scored.append((hits, d))
    scored.sort(key=lambda x: -x[0])
    # relevance floor: a single incidental keyword (e.g. 'results') must not
    # surface an irrelevant doc; short distinctive queries keep recall 1
    min_hits = 1 if len(terms) <= 2 else 2
    keep = [x for x in scored if x[0] >= min_hits]
    return [{"sha": d.get("sha"), "topic": d.get("topic"),
             "text": (d.get("text") or "")[:400],
             "receipt": d.get("receipt"), "score": s}
            for s, d in keep[:k]]

def _capability_card(token_record: dict | None, consumer: str) -> dict:
    """Per-brick capability card — brick_id, lanes, caps, limits — derived
    from the caller's token record (round-138 gate) enriched best-effort
    with the brick's registered skills (functions)."""
    rec = token_record or {}
    card = {
        "brick_id": rec.get("brick_id") or consumer,
        "owner": rec.get("owner", ""),
        "lanes": rec.get("lane_scope") or [],
        "spend_cap_usd": rec.get("spend_cap_usd"),
        "status": rec.get("status", "active"),
        "functions": [],
        "limits": ["answers grounded in retrieved_docs only",
                   "empty retrieval -> honesty fallback, never fabrication",
                   "lane_scope enforced at invoke",
                   "spend cap enforced at invoke"],
    }
    try:
        for line in REGISTRY_PATH.read_text().splitlines():
            r = json.loads(line)
            if isinstance(r, dict) and r.get("brick_id") == card["brick_id"]:
                card["functions"] = r.get("skills") or []
                if r.get("role"):
                    card["role"] = r["role"]
                break
    except Exception:
        pass
    return card

class TokenRouter:
    def __init__(self, state_dir: pathlib.Path, tokens_dir: pathlib.Path,
                 brick_id: str = "router-001", default_lane: str = "",
                 measurements_path: pathlib.Path | None = None):
        self.state_dir = state_dir
        self.tokens_dir = tokens_dir
        self.brick_id = brick_id
        self.default_lane = default_lane      # WIRED: fallback when no tier match
        self.lanes_path = state_dir / "lanes.jsonl"
        self.ledger_path = state_dir / "ledger.jsonl"
        self.audit_path = state_dir / "audit.jsonl"
        self.lock_path = state_dir / ".router.lock"
        self.tokens_meta_path = state_dir / "tokens-meta.jsonl"
        self.vault_dir = state_dir / "vault"
        # round-139 card 8: transparency feed (per-invoke latency/cost/tokens)
        self.measurements_path = measurements_path or (state_dir / "measurements.jsonl")
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
            self.vault_dir.mkdir(mode=0o700, exist_ok=True)   # finding 7: dir 0700
            os.chmod(self.vault_dir, 0o700)
        except OSError:
            pass
        for p in (self.lanes_path, self.ledger_path, self.audit_path,
                  self.tokens_meta_path, self.measurements_path):
            try:
                if not p.exists():
                    p.touch()
                p.chmod(0o600)
            except OSError:
                pass

    # ---- auth: token -> brick, constant-time via index file ----
    def _rebuild_token_index(self):
        """Build tokens/index.jsonl (token_hash -> brick). Called at init and
        whenever a token file changes. Lookup is O(1), not O(N)."""
        idx = {}
        if self.tokens_dir and pathlib.Path(self.tokens_dir).is_dir():
            for p in pathlib.Path(self.tokens_dir).iterdir():
                if not p.is_file() or not p.name.endswith(".token"):
                    continue
                try:
                    # round-138: token files are root:root 0600 + a read-only
                    # ACL for the service user (u:ubuntu:r--). An ACL mask is
                    # reflected in st_mode's GROUP bits (0640 display), so the
                    # strict 0600 check would reject every ACL'd token. The
                    # security property is: no world perms, no group write/exec
                    # (a write-granting ACL shows group-write in the mask and
                    # is rejected here). Writes stay root-only via the 0700 dir.
                    if (p.stat().st_mode & 0o027) != 0:
                        continue                    # world/group-write tokens ignored
                    idx[hashlib.sha256(p.read_text().strip().encode()).hexdigest()] = \
                        p.name.replace(".token", "")
                except OSError:
                    continue
        try:
            (self.state_dir / "tokens-index.jsonl").write_text(
                json.dumps(idx) + "\n")
            os.chmod(self.state_dir / "tokens-index.jsonl", 0o600)
        except OSError:
            pass

    def _token_to_brick(self, token: str) -> str | None:
        if not token:
            return None
        idx = {}
        try:
            line = (self.state_dir / "tokens-index.jsonl").read_text().splitlines()
            idx = json.loads(line[0]) if line else {}
        except OSError:
            idx = {}   # missing/unreadable index — rebuild below (round-138:
                       # token_issue.py force-reindexes by deleting the file)
        hit = idx.get(hashlib.sha256(token.strip().encode()).hexdigest())
        if hit is None:
            # finding DA-5: stale index — rebuild once (new token files)
            self._rebuild_token_index()
            try:
                line = (self.state_dir / "tokens-index.jsonl").read_text().splitlines()
                idx = json.loads(line[0]) if line else {}
            except OSError:
                idx = {}
            hit = idx.get(hashlib.sha256(token.strip().encode()).hexdigest())
        return hit

    # ---- round-138 card 6: per-token records (lane_scope + spend cap) ----
    def _load_token_meta(self) -> dict:
        """tokens-meta.jsonl: one record per line, keyed by token sha256.
        Records are written ONLY by the sudo-gated token_issue.py (registry
        check at issue; revoke removes the record). Missing record = unknown
        token = fail closed at invoke."""
        out = {}
        try:
            for line in self.tokens_meta_path.read_text().splitlines():
                try:
                    r = json.loads(line)
                    if isinstance(r, dict) and r.get("token_hash"):
                        out[r["token_hash"]] = r
                except Exception:
                    continue
        except OSError:
            return out
        return out

    def _token_record(self, token: str) -> dict | None:
        """Full token record (brick, owner, lane_scope, spend_cap_usd) or None.
        round-138: invoke() gates on this record — lane_scope fail-closed and
        per-token spend cap live HERE, not in the bare hash->brick index."""
        if not token:
            return None
        h = hashlib.sha256(token.strip().encode()).hexdigest()
        rec = self._load_token_meta().get(h)
        if rec is None or rec.get("status") != "active":
            return None
        return rec

    def _spend_used(self, consumer: str) -> float:
        """Sum of billed ledger cost for this consumer. One token per brick,
        so consumer-sum == per-token spend (round-138 card 6)."""
        rows, _ = self._read(self.ledger_path, "ledger")
        return sum(float(r.get("cost", 0.0) or 0.0) for r in rows
                   if r.get("consumer") == consumer)

    # ---- internal ----
    def _log(self, op: str, detail: dict, outcome: str = "ok"):
        try:
            with open(self.audit_path, "a") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.write(json.dumps({"ts": int(time.time()), "router": self.brick_id,
                                    "op": op, "outcome": outcome, **detail}) + "\n")
                f.flush()
                fcntl.flock(f, fcntl.LOCK_UN)
        except OSError:
            pass

    def _read(self, path: pathlib.Path, schema: str = "") -> tuple[list[dict], int]:
        """Type-validated read (finding 6). schema='lanes' enforces lane-row
        types; 'ledger' requires consumer/lane; '' = any dict with no checks."""
        if not path.exists():
            return [], 0
        out, corrupt = [], 0
        try:
            for line in path.read_text().splitlines():
                try:
                    e = json.loads(line)
                    if not isinstance(e, dict):
                        raise ValueError("not a dict")
                    if schema == "lanes":
                        need = ("lane_id", "owner", "endpoint", "model",
                                "capacity", "cost_per_task", "quality")
                        if any(not isinstance(e.get(k), str) for k in
                               ("lane_id", "owner", "endpoint", "model", "capacity", "quality")):
                            raise ValueError("bad lane row shape (missing str key)")
                        if not isinstance(e.get("cost_per_task"), (int, float)):
                            raise ValueError("cost not numeric")
                    elif schema == "ledger":
                        if not isinstance(e.get("consumer"), str) or not isinstance(e.get("lane"), str):
                            raise ValueError("bad ledger row shape")
                    out.append(e)
                except Exception:
                    corrupt += 1
        except OSError:
            return [], 0
        return out, corrupt

    def _lock(self):
        lf = open(self.lock_path, "w")
        fcntl.flock(lf, fcntl.LOCK_EX)
        return lf

    def _append_atomic(self, path: pathlib.Path, row: dict):
        with open(path, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(row) + "\n")
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)

    def _measure(self, brick_id: str, lane_id: str, model: str,
                 latency_ms: float, cost_usd: float, tokens: int | None,
                 billed: bool):
        """round-139 card 8: one transparency row per invoke attempt.
        cost_usd is the BILLED lane price (0.0 when the call failed and the
        ledger was not debited); tokens is the lane-reported usage when
        parseable, else null (honest 'unknown'). Never touches the ledger."""
        try:
            self._append_atomic(self.measurements_path, {
                "ts": int(time.time()), "brick_id": brick_id, "lane": lane_id,
                "model": model, "latency_ms": round(float(latency_ms), 1),
                "cost_usd": round(float(cost_usd), 6), "tokens": tokens,
                "billed": billed})
        except OSError:
            pass

    def _vault_put(self, lane_id: str, secret: str) -> pathlib.Path:
        """Atomic 0600 create (finding 7): os.open with mode — no 0644 window."""
        p = self.vault_dir / f"{lane_id}.secret"
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, secret.encode())
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(p, 0o600)
        return p

    # ---- API ----
    def register(self, owner_brick: str, lane_id: str, endpoint: str, model: str,
                 capacity: str, cost_per_task: float, quality: str,
                 auth_type: str = "", auth_secret: str = "") -> dict:
        """A brick registers its AI endpoint as a routable lane."""
        if not LANE_SHAPE.match(lane_id):
            raise ValueError(f"invalid lane_id '{lane_id}'")
        _validate_endpoint(endpoint)                    # SSRF guard (finding 1)
        if quality not in QUALITY_TIERS:
            raise ValueError(f"quality must be one of {sorted(QUALITY_TIERS)}")
        if not (0 < cost_per_task <= 1000):
            raise ValueError("cost_per_task must be in (0, 1000]")
        if cost_per_task < COST_FLOOR:                  # finding 4: cost floor
            raise ValueError(f"cost_per_task {cost_per_task} below floor {COST_FLOOR} — "
                             f"suspicious lane, floor enforced")
        if auth_type and not auth_secret:
            raise ValueError("auth_secret required when auth_type set")

        lf = self._lock()
        try:
            lanes, _ = self._read(self.lanes_path, "lanes")
            for l in lanes:
                if l["lane_id"] == lane_id:
                    if l["owner"] != owner_brick:
                        self._log("register", {"lane": lane_id, "owner": owner_brick,
                                               "reason": "not owner"}, outcome="rejected")
                        raise ValueError(f"lane {lane_id} owned by {l['owner']} — only owner can register/update")
                    lanes = [x for x in lanes if x["lane_id"] != lane_id]

            # audit BEFORE mutation (finding 10)
            self._log("register", {"lane": lane_id, "owner": owner_brick,
                                   "model": model, "quality": quality,
                                   "cost": cost_per_task})
            if auth_secret:
                self._vault_put(lane_id, auth_secret)   # atomic 0600
            row = {"ts": int(time.time()), "lane_id": lane_id, "owner": owner_brick,
                   "endpoint": endpoint, "model": model, "capacity": capacity,
                   "cost_per_task": float(cost_per_task), "quality": quality,
                   "auth_type": auth_type, "active": True}
            tmp = self.lanes_path.with_name(f".lanes.{os.getpid()}.tmp")
            with open(tmp, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                for l in lanes:
                    f.write(json.dumps(l) + "\n")
                f.write(json.dumps(row) + "\n")
                f.flush()
                os.fchmod(f.fileno(), 0o600)
                fcntl.flock(f, fcntl.LOCK_UN)
            os.replace(tmp, self.lanes_path)
            os.chmod(self.lanes_path, 0o600)
            return {"lane_id": lane_id, "status": "registered", "quality": quality,
                    "cost_per_task": cost_per_task}
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN); lf.close()

    def deregister(self, owner_brick: str, lane_id: str) -> dict:
        lf = self._lock()
        try:
            lanes, _ = self._read(self.lanes_path, "lanes")
            keep = [l for l in lanes if l["lane_id"] != lane_id]
            if len(keep) == len(lanes):
                raise ValueError(f"lane {lane_id} not found")
            for l in lanes:
                if l["lane_id"] == lane_id and l["owner"] != owner_brick:
                    self._log("deregister", {"lane": lane_id, "owner": owner_brick,
                                             "reason": "not owner"}, outcome="rejected")
                    raise ValueError(f"lane {lane_id} owned by {l['owner']} — only owner can deregister")
            # audit BEFORE mutation, secret unlinked before rewrite (finding 7+10)
            self._log("deregister", {"lane": lane_id, "owner": owner_brick})
            try:
                (self.vault_dir / f"{lane_id}.secret").unlink()
            except OSError:
                pass
            tmp = self.lanes_path.with_name(f".lanes.{os.getpid()}.tmp")
            with open(tmp, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                for l in keep:
                    f.write(json.dumps(l) + "\n")
                f.flush()
                os.fchmod(f.fileno(), 0o600)
                fcntl.flock(f, fcntl.LOCK_UN)
            os.replace(tmp, self.lanes_path)
            os.chmod(self.lanes_path, 0o600)
            return {"lane_id": lane_id, "status": "deregistered"}
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN); lf.close()

    def lanes(self) -> dict:
        """Metadata-only lane map — NO endpoints exposed (finding 11)."""
        lanes, corrupt = self._read(self.lanes_path, "lanes")
        return {"lanes": [{"lane_id": l["lane_id"], "owner": l["owner"], "model": l["model"],
                           "capacity": l.get("capacity", ""),
                           "cost_per_task": l["cost_per_task"],
                           "quality": l["quality"], "active": l.get("active", True)}
                          for l in lanes],
                "corrupt_rows": corrupt}

    def route(self, consumer: str, quality: str = "routine",
              lane_scope: list | None = None) -> dict:
        """PICK a lane WITHOUT debiting (finding 5: route is not a meter).
        Returns a route receipt id; invoke() consumes it and is the ONLY meter.
        Quality floor (finding 4): audit never served by routine lanes.
        round-138: when lane_scope is given (per-token allowlist), only lanes
        inside the caller's scope are eligible — fail-closed (empty scope =
        no lane = 503)."""
        if quality not in QUALITY_TIERS:
            raise ValueError(f"quality must be one of {sorted(QUALITY_TIERS)}")
        lanes, corrupt = self._read(self.lanes_path, "lanes")
        active = [l for l in lanes if l.get("active", True)]
        if lane_scope is not None:
            active = [l for l in active if l["lane_id"] in lane_scope]
        tier = [l for l in active if l["quality"] == quality]
        # quality floor: audit/advanced only served by audit/advanced lanes
        if not tier and quality in ("audit", "advanced"):
            tier = [l for l in active if l["quality"] in ("audit", "advanced")]
        # default_lane fallback (WIRED, finding 4)
        if not tier and self.default_lane:
            tier = [l for l in active if l["lane_id"] == self.default_lane]
        # NO bare fallback to any lane: quality floor means audit never
        # served by routine (finding 4) — no tier match = 503
        if not tier:
            self._log("route", {"consumer": consumer, "quality": quality,
                                "reason": "no lane for quality tier"}, outcome="error")
            return {"status": 503, "error": f"no registered lane for quality tier '{quality}'"}

        pick = min(tier, key=lambda l: l["cost_per_task"])
        # route receipt: NOT a ledger entry, just a pick
        receipt = hashlib.sha256(f"{consumer}|{pick['lane_id']}|{time.time()}"
                                 .encode()).hexdigest()[:16]
        self._log("route", {"consumer": consumer, "lane": pick["lane_id"],
                            "quality": quality, "receipt": receipt})
        return {"status": 200, "lane": pick["lane_id"], "owner": pick["owner"],
                "model": pick["model"], "cost": pick["cost_per_task"],
                "quality": pick["quality"], "route_receipt": receipt,
                "corrupt_rows": corrupt,
                "note": "invoke via /invoke with route_receipt — billed once at invoke"}

    def _inject_envelope(self, payload: dict, consumer: str,
                         token_record: dict | None, lane_id: str) -> dict:
        """round-139 card 5 (genius brick, ratified): EVERY call forwarded to
        a lane carries the MANDATORY context envelope — retrieved_docs (top-k
        vector chunks, explicit [] if none), capability_card (brick_id/lanes/
        caps/limits from the token record), honesty_fallback (exact no-context
        template). No turn completes without all three: injected HERE in the
        router, so direct invokes AND brick-local prompts (brain.py, door,
        loops) all inherit it. Chat-shaped payloads only; non-chat payloads
        are logged and passed through untouched."""
        if not isinstance(payload, dict) or not isinstance(payload.get("messages"), list):
            self._log("envelope", {"consumer": consumer, "lane": lane_id,
                                   "reason": "non-chat payload — no messages to envelop"},
                      outcome="skipped")
            return payload
        query = ""
        for m in reversed(payload["messages"]):
            if isinstance(m, dict) and m.get("role") == "user" \
               and isinstance(m.get("content"), str):
                query = m["content"]
                break
        docs = _retrieve_docs(query)
        card = _capability_card(token_record, consumer)
        envelope = {"retrieved_docs": docs, "capability_card": card,
                    "honesty_fallback": HONESTY_FALLBACK}
        system_content = (
            "[MANDATORY CONTEXT ENVELOPE — round-139 genius standard. This "
            "turn carries all three fields; obey them.]\n"
            "RETRIEVED_DOCS (when non-empty, answer ONLY from these and cite "
            "the doc topic):\n" + json.dumps(docs, ensure_ascii=False) + "\n\n"
            "CAPABILITY_CARD (your identity, permissions, functions, limits):\n"
            + json.dumps(card, ensure_ascii=False) + "\n\n"
            "HONESTY_FALLBACK (when RETRIEVED_DOCS is empty and the user asks "
            "for facts, reply with EXACTLY this text — never invent):\n"
            + HONESTY_FALLBACK
        )
        out = dict(payload)
        out["messages"] = ([{"role": "system", "content": system_content}]
                           + list(payload["messages"]))
        # proof of injection: digest of the OUTBOUND payload envelope (never
        # the raw payload — callers' text stays out of the audit trail)
        self._log("envelope_injected", {
            "consumer": consumer, "lane": lane_id,
            "brick_id": card.get("brick_id"), "docs": len(docs),
            "doc_topics": [d.get("topic") for d in docs],
            "doc_shas": [d.get("sha") for d in docs],
            "capability_card_fields": sorted(card.keys()),
            "honesty_fallback_chars": len(HONESTY_FALLBACK),
        })
        return out

    def invoke(self, consumer: str, lane_id: str, payload: dict,
               route_receipt: str = "", token_record: dict | None = None) -> dict:
        """PROXY a call — THE ONLY METER (finding 5). The lane's vaulted secret
        is attached by the router and never returned; echoed Authorization in
        upstream bodies is MASKED (finding 2).
        round-138 card 6: per-token gates — lane_scope fail-closed and spend
        cap. A token without a record (file-dropped, revoked, or issued
        outside the registry gate) is DENIED."""
        lanes, _ = self._read(self.lanes_path, "lanes")
        pick = next((l for l in lanes if l["lane_id"] == lane_id and l.get("active", True)), None)
        if not pick:
            return {"status": 404, "error": f"lane {lane_id} not active"}
        # ---- round-138 per-token gates (before ANY proxying) ----
        if token_record is None:
            self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                 "reason": "no token record — revoked or unissued"},
                      outcome="rejected")
            return {"status": 403,
                    "error": "token revoked or not issued via registry gate"}
        scope = token_record.get("lane_scope") or []
        if not scope:
            self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                 "reason": "token has no lane scope — fail closed"},
                      outcome="rejected")
            return {"status": 403, "error": "token has no lane scope — fail closed"}
        if lane_id not in scope:
            self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                 "reason": "lane outside token scope", "scope": scope},
                      outcome="rejected")
            return {"status": 403,
                    "error": f"lane '{lane_id}' outside token scope {scope}"}
        cap = token_record.get("spend_cap_usd")
        if cap is not None:
            used = self._spend_used(consumer)
            if used + float(pick["cost_per_task"]) > float(cap):
                self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                     "used": round(used, 4), "cap": cap},
                          outcome="rejected")
                return {"status": 403,
                        "error": f"token spend cap exceeded "
                                 f"(used ${used:.4f} + ${pick['cost_per_task']} > cap ${cap})"}
        # ---- end round-138 gates ----
        # ---- round-146 item 3: allowance meter (R1.3: check + reservation
        # debit under one flock, immediately after the spend-cap check,
        # before the upstream call). Only human-owned bricks are metered;
        # fleet ops (ovh-server-001, earn-loop, roles) are exempt (R1.4). ----
        person = self._meter_person(consumer)
        meter_debit = None
        pay_with = (payload or {}).get("pay_with") if isinstance(payload, dict) else ""
        if person:
            if pay_with == "bananas":
                # Escape path 3: spend bananas at cost+20% (earned-only,
                # no self-pay). The router (never the brick) writes the spend
                # row; paid overage does not consume the free allowance.
                spend = self._banana_pay(person, float(pick["cost_per_task"]),
                                         consumer, lane_id, pick.get("model", ""))
                if not spend.get("ok"):
                    self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                         "reason": "banana pay refused: "
                                                   + str(spend.get("error"))},
                              outcome="rejected")
                    return {"status": 403, "error": spend.get("error"),
                            "price_bananas": spend.get("price"),
                            "balance": spend.get("balance")}
                meter_debit = allowance_meter.debit(
                    person, consumer, lane_id, card_id=route_receipt,
                    invoke_ts=int(time.time()),
                    lane_cost=float(pick["cost_per_task"]),
                    payer="user-bananas")
            else:
                meter_debit = allowance_meter.debit(
                    person, consumer, lane_id, card_id=route_receipt,
                    invoke_ts=int(time.time()),
                    lane_cost=float(pick["cost_per_task"]),
                    payer="sponsored")
                if not meter_debit.get("ok"):
                    # STOP path (R4/R6): durable alert row FIRST (fsync'd by
                    # the meter), delivery attempt second, stop third. The
                    # stop NEVER waits on the notifier (spawned, not awaited).
                    name = allowance_meter.person_name(person)
                    alert = allowance_meter.open_alert(
                        person, consumer, name=name, rung="100",
                        cost_usd=self._spend_used(consumer))
                    if alert.get("new"):
                        self._spawn_notifier(alert["alert_id"])
                    self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                         "person": person,
                                         "reason": "allowance_exhausted",
                                         "usage": meter_debit.get("usage"),
                                         "allowance": meter_debit.get("allowance")},
                              outcome="rejected")
                    return {"status": 403, "error": "allowance_exhausted",
                            "month": meter_debit.get("month"),
                            "usage": meter_debit.get("usage"),
                            "allowance": meter_debit.get("allowance"),
                            "next_window_ts": allowance_meter.next_window_ts(
                                meter_debit.get("month", "")),
                            "degraded": "retrieval-only",
                            "message": allowance_meter.degraded_reply(
                                name, meter_debit.get("usage", 0),
                                meter_debit.get("allowance", allowance_meter.BASE_ALLOWANCE),
                                self._banana_balance(person),
                                beyond_cap_price(float(pick["cost_per_task"])))}
        # ---- end round-146 meter ----
        # SSRF guard at invoke too (finding 1: endpoints may be re-validated)
        try:
            _validate_endpoint(pick["endpoint"])
        except ValueError:
            return {"status": 403, "error": "lane endpoint blocked (SSRF guard)"}

        secret = ""
        sp = self.vault_dir / f"{lane_id}.secret"
        if sp.exists():
            try:
                secret = sp.read_text().strip()
            except OSError:
                secret = ""
        headers = {"Content-Type": "application/json"}
        if pick.get("auth_type") == "bearer" and secret:
            headers["Authorization"] = f"Bearer {secret}"

        # audit BEFORE the call (finding 10) — a served call must be auditable
        self._log("invoke", {"consumer": consumer, "lane": lane_id,
                             "receipt": route_receipt or "direct"})

        # round-139 card 5: MANDATORY context envelope on EVERY outbound call
        # (retrieved_docs + capability_card + honesty_fallback). Injected here
        # so no turn reaches a lane without all three fields.
        payload = self._inject_envelope(payload, consumer, token_record, lane_id)

        opener = urllib.request.build_opener(NoRedirect)   # finding DA-1: refuse 3xx
        t0 = time.monotonic()            # round-139 card 8: latency meter
        try:
            req = urllib.request.Request(pick["endpoint"], data=json.dumps(payload).encode(),
                                         headers=headers, method="POST")
            with opener.open(req, timeout=15) as resp:
                body = resp.read(MAX_RESPONSE_BYTES + 1)   # finding 8: cap
            latency_ms = (time.monotonic() - t0) * 1000
            if len(body) > MAX_RESPONSE_BYTES:
                body = body[:MAX_RESPONSE_BYTES]
                self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                     "reason": "response capped"}, outcome="partial")
            text = body.decode(errors="replace")
            # finding 2: mask any echoed Authorization so the vaulted key can
            # never round-trip to a consumer
            if secret:
                text = text.replace(f"Bearer {secret}", "Bearer [REDACTED]")
                text = text.replace(secret, "[REDACTED]")
            # round-139 card 8: usage tokens from the lane response when
            # present (OpenAI/DeepSeek/OpenRouter shape); null = unknown.
            tokens = None
            try:
                if text.lstrip().startswith("{"):
                    usage = json.loads(text).get("usage")
                    if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
                        tokens = usage["total_tokens"]
            except Exception:
                tokens = None
            # BILL ONLY ON 2xx (finding DA-3): a failed call is not a served task
            payer = "user-bananas" if pay_with == "bananas" else (
                "user-key" if lane_id.startswith("byok-") else "sponsored")
            entry = {"ts": int(time.time()), "consumer": consumer, "lane": lane_id,
                     "owner": pick["owner"], "quality": pick["quality"],
                     "cost": pick["cost_per_task"], "model": pick["model"],
                     "route_receipt": route_receipt, "payer": payer}
            self._append_atomic(self.ledger_path, entry)
            self._measure(consumer, lane_id, pick["model"], latency_ms,
                          pick["cost_per_task"], tokens, billed=True)
            # round-146 item 3: post-invoke ladder evaluator (80/95/100) —
            # warnings + the proactive 100% alert when the 50th completes.
            if person and pay_with != "bananas":
                self._ladder_eval(person, consumer)
            return {"status": 200, "response": text[:16000]}  # was 4000 — reasoning models burn the cap on reasoning_content before emitting content (AGI-consensus fix 2026-08-16)
        except urllib.error.HTTPError as e:
            latency_ms = (time.monotonic() - t0) * 1000
            self._measure(consumer, lane_id, pick["model"], latency_ms, 0.0,
                          None, billed=False)
            # round-146: a failed call is not a served task — return the
            # reservation (billed-only counting, R1.4)
            if person and meter_debit and meter_debit.get("ok"):
                allowance_meter.refund(person, consumer, lane_id, meter_debit.get("ref"))
            if 300 <= e.code < 400:
                self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                     "status": e.code,
                                     "reason": "redirect refused (SSRF guard)"}, outcome="error")
                return {"status": 502, "error": f"lane returned redirect {e.code} — refused (SSRF guard)"}
            self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                 "status": e.code, "reason": "upstream error"}, outcome="error")
            return {"status": 502, "error": f"lane returned {e.code}"}
        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            self._measure(consumer, lane_id, pick["model"], latency_ms, 0.0,
                          None, billed=False)
            if person and meter_debit and meter_debit.get("ok"):
                allowance_meter.refund(person, consumer, lane_id, meter_debit.get("ref"))
            self._log("invoke", {"consumer": consumer, "lane": lane_id,
                                 "reason": str(e)[:80]}, outcome="error")
            return {"status": 503, "error": f"lane unreachable: {str(e)[:80]}"}

    def ledger(self, consumer: str = "") -> dict:
        """The meter, CALLER-SCOPED at the HTTP layer (finding 3)."""
        rows, corrupt = self._read(self.ledger_path, "ledger")
        if consumer:
            rows = [r for r in rows if r.get("consumer") == consumer]
        return {"entries": rows[-100:], "count": len(rows), "corrupt_rows": corrupt}

    # ---- round-146 item 3&4 helpers ----
    def _meter_person(self, brick_id: str) -> str | None:
        """None = not metered (fleet ops / roles / khalid's own brick)."""
        try:
            return allowance_meter.person_of_brick(brick_id)
        except Exception:
            return None

    def _banana_balance(self, person_id: str) -> float:
        try:
            return BananaSpend(SPEND_LEDGER).balance(person_id)["available"]
        except Exception:
            return 0.0

    def _banana_pay(self, person_id: str, lane_cost: float, brick_id: str,
                    lane_id: str, model: str) -> dict:
        """Escape path 3: spend bananas at cost+20% — earned-only, no
        self-pay (the router writes the spend row; the brick never can)."""
        try:
            s = BananaSpend(SPEND_LEDGER)
            price = beyond_cap_price(lane_cost)
            bal = s.balance(person_id)
            if bal["earned"] <= 0:
                return {"ok": False, "price": price, "balance": bal,
                        "error": "beyond-cap spend is earned-only — no "
                                 "verified earnings yet (earn first, BYOK, or wait)"}
            if bal["available"] < price:
                return {"ok": False, "price": price, "balance": bal,
                        "error": "insufficient bananas (earning-first)"}
            return s.spend(person_id, "beyond_cap",
                           f"allowance-overage-{int(time.time())}",
                           {"lane": lane_id, "brick": brick_id,
                            "model": model, "cost_usd": lane_cost,
                            "reason": "round-146 beyond-cap escape, cost+20%"})
        except Exception as e:
            return {"ok": False, "error": f"banana spend path error: {str(e)[:80]}"}

    def _spawn_notifier(self, alert_id: str):
        """Fire-and-forget: the STOP never waits on the notifier (R6). The
        watchdog (root cron) retries anything still open."""
        try:
            import subprocess
            subprocess.Popen([sys.executable, ALLOWANCE_NOTIFIER,
                              "--alert-id", alert_id],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _ladder_eval(self, person: str, brick_id: str):
        """Post-invoke evaluator: 80/95 warnings for the user, the 95% khalid
        heads-up, and the proactive 100% alert the moment the 50th completes
        (khalid learns BEFORE the stop — the strong reading of his directive)."""
        try:
            m = allowance_meter.month()
            allowance_meter.maybe_warning(person, brick_id, m)
            b = allowance_meter.bucket(person, m)
            if b["usage"] >= b["allowance"]:
                alert = allowance_meter.open_alert(
                    person, brick_id, name=allowance_meter.person_name(person),
                    rung="100", cost_usd=self._spend_used(brick_id))
                if alert.get("new"):
                    self._spawn_notifier(alert["alert_id"])
            elif b["usage"] >= allowance_meter._rung_thresholds(
                    b["allowance"])[1]:  # >= 95%
                alert = allowance_meter.open_alert(
                    person, brick_id, name=allowance_meter.person_name(person),
                    rung="95", cost_usd=self._spend_used(brick_id))
                if alert.get("new"):
                    self._spawn_notifier(alert["alert_id"])
        except Exception:
            pass

    # ---- round-146 item 4: BYOK lanes (C2/C3) ----
    def register_byok(self, person_brick: str, service: str,
                      auth_secret: str) -> dict:
        """User key attaches ONLY to a fleet-allowlisted endpoint (C2) and is
        owner-bound to the person's registered brick (C3). The key transits
        loopback only and is vaulted by register() (_vault_put, 0600)."""
        if service not in FLEET_BYOK_ALLOWLIST:
            raise ValueError(
                f"service '{service}' not on the fleet BYOK allowlist "
                f"({sorted(FLEET_BYOK_ALLOWLIST)}) — no user-supplied endpoints")
        if not BRICK_SHAPE.match(person_brick):
            raise ValueError("invalid person brick id")
        if len(auth_secret or "") < SECRET_MIN:
            raise ValueError("auth_secret too short")
        lane_id = f"byok-{person_brick}"
        if not LANE_SHAPE.match(lane_id) or len(lane_id) > 64:
            raise ValueError(f"invalid byok lane id '{lane_id}'")
        if self._meter_person(person_brick) is None:
            raise ValueError(
                f"{person_brick} is not a registered human-owned brick")
        endpoint, model, cost = FLEET_BYOK_ALLOWLIST[service]
        return self.register(person_brick, lane_id, endpoint, model,
                             "unlimited", cost, "routine", "bearer",
                             auth_secret)

    def deregister_byok(self, lane_id: str) -> dict:
        """BYOK revoke: owner = the person brick embedded in the lane id;
        deregister() deactivates the lane AND unlinks the vault secret
        (zero-retention)."""
        if not lane_id.startswith("byok-"):
            raise ValueError("not a byok lane")
        person_brick = lane_id[len("byok-"):]
        return self.deregister(person_brick, lane_id)

    def status(self) -> dict:
        lanes, lcorrupt = self._read(self.lanes_path, "lanes")
        led, dcorrupt = self._read(self.ledger_path, "ledger")
        self._log("status", {"lanes": len(lanes)})
        return {"brick": self.brick_id, "lanes": len(lanes),
                "active_lanes": sum(1 for l in lanes if l.get("active", True)),
                "ledger_entries": len(led), "corrupt_rows": lcorrupt + dcorrupt}

# ---- HTTP surface ----
class RouterHandler(BaseHTTPRequestHandler):
    router = None

    def _json(self, code: int, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _caller_token(self) -> str:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return ""
        return auth[7:].strip()

    def _caller(self) -> str | None:
        tok = self._caller_token()
        if not tok:
            return None
        return self.router._token_to_brick(tok)

    def _read_body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode()) if n else {}

    def _auth(self, path: str):
        caller = self._caller()
        if not caller:
            self.router._log("auth", {"path": path}, outcome="rejected")
            self._json(401, {"error": "unauthorized"})
            return None
        return caller

    def do_GET(self):
        caller = self._auth(self.path)
        if caller is None:
            return
        parsed = urlparse(self.path)
        if parsed.path == "/lanes":
            self._json(200, self.router.lanes())
        elif parsed.path == "/ledger":
            self._json(200, self.router.ledger(caller))   # finding 3: caller-scoped
        elif parsed.path == "/status":
            self._json(200, self.router.status())
        else:
            self.router._log("404", {"path": self.path}, outcome="rejected")
            self._json(404, {"error": "not found"})

    def do_POST(self):
        caller = self._auth(self.path)
        if caller is None:
            return
        parsed = urlparse(self.path)
        try:
            body = self._read_body()
            if parsed.path == "/register":
                if body.get("byok"):
                    # BYOK bridge: the fleet control brick (door ingest) may
                    # register a lane owned by a PERSON's brick, endpoint from
                    # the allowlist only (C2). Any other caller: 403.
                    if caller != "ovh-server-001":
                        self.router._log("register", {"byok": True,
                                                      "authed": caller},
                                         outcome="rejected")
                        self._json(403, {"error": "byok register requires the "
                                                  "fleet control token"})
                        return
                    res = self.router.register_byok(
                        body.get("person_brick", ""), body.get("service", ""),
                        body.get("auth_secret", ""))
                    self._json(200, res)
                    return
                if body.get("owner") != caller:
                    self.router._log("register", {"claimed": body.get("owner"),
                                                  "authed": caller}, outcome="rejected")
                    self._json(403, {"error": "you can only register lanes you own"})
                    return
                res = self.router.register(caller, body.get("lane_id", ""),
                                           body.get("endpoint", ""), body.get("model", ""),
                                           body.get("capacity", ""),
                                           float(body.get("cost_per_task", 0)),
                                           body.get("quality", ""),
                                           body.get("auth_type", ""),
                                           body.get("auth_secret", ""))
                self._json(200, res)
            elif parsed.path == "/deregister":
                if body.get("byok"):
                    if caller != "ovh-server-001":
                        self.router._log("deregister", {"byok": True,
                                                        "authed": caller},
                                         outcome="rejected")
                        self._json(403, {"error": "byok deregister requires "
                                                  "the fleet control token"})
                        return
                    self._json(200, self.router.deregister_byok(
                        body.get("lane_id", "")))
                    return
                if body.get("owner") != caller:
                    self._json(403, {"error": "you can only deregister lanes you own"})
                    return
                self._json(200, self.router.deregister(caller, body.get("lane_id", "")))
            elif parsed.path == "/route":
                rec = self.router._token_record(self._caller_token())
                if rec is None:
                    self.router._log("route", {"consumer": caller,
                                               "reason": "no token record"},
                                     outcome="rejected")
                    self._json(403, {"error": "token revoked or not issued via registry gate"})
                    return
                res = self.router.route(caller, body.get("quality", "routine"),
                                        lane_scope=rec.get("lane_scope") or [])
                code = 200 if res.get("status") == 200 else res.get("status", 500)
                self._json(code, res)
            elif parsed.path == "/invoke":
                rec = self.router._token_record(self._caller_token())
                res = self.router.invoke(caller, body.get("lane_id", ""),
                                         body.get("payload", {}),
                                         body.get("route_receipt", ""),
                                         token_record=rec)
                code = 200 if res.get("status") == 200 else res.get("status", 500)
                self._json(code, res)
            else:
                self.router._log("404", {"path": self.path}, outcome="rejected")
                self._json(404, {"error": "not found"})
        except ValueError as e:
            self.router._log("api", {"path": self.path, "reason": str(e)}, outcome="rejected")
            self._json(400, {"error": str(e)})
        except Exception as e:
            self.router._log("api", {"path": self.path, "reason": str(e)[:80]}, outcome="error")
            self._json(500, {"error": str(e)[:80]})

    def log_message(self, *a):
        pass

def main():
    ap = argparse.ArgumentParser(description="fleet token router (T-UNIVERSE-013)")
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--tokens-dir", required=True)
    ap.add_argument("--brick-id", default="router-001")
    ap.add_argument("--default-lane", default="")
    ap.add_argument("--measurements-path", default="",
                    help="round-139 card 8 transparency feed; default <state-dir>/measurements.jsonl")
    ap.add_argument("--port", type=int, default=3742)
    ap.add_argument("--bind", default="127.0.0.1")
    args = ap.parse_args()
    r = TokenRouter(pathlib.Path(args.state_dir), pathlib.Path(args.tokens_dir),
                    args.brick_id, args.default_lane,
                    pathlib.Path(args.measurements_path) if args.measurements_path else None)
    r._rebuild_token_index()
    RouterHandler.router = r
    srv = ThreadingHTTPServer((args.bind, args.port), RouterHandler)
    print(f"[router] {args.brick_id} on {args.bind}:{args.port} "
          f"(lanes register, secrets vaulted, billed once at invoke)")
    srv.serve_forever()

if __name__ == "__main__":
    main()
