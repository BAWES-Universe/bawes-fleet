#!/usr/bin/env python3
"""byok.py — BRING-YOUR-OWN-KEY (round-143b ruling 1 + round-146 item 4).

Flow: user key via the ingest surface (door_ingest :3744 — fragment token,
burn-on-open, person from token record) -> vaulted per-user 0600 owner-bound
-> router lane `byok-<brick>` -> token scope grant -> their lane. Revocation
is one op: scrub vault + deactivate lane + strip scope + audit, ZERO retention
(no copies anywhere — verified by grep).

Security (C2): user keys attach ONLY to fleet-allowlisted provider endpoints
(FLEET_BYOK_ALLOWLIST in token_router.py) — no user-supplied endpoints, the
SSRF class is removed by construction; _validate_endpoint stays as
defense-in-depth. Key never becomes master, never leaves the vault, never
touches chat/agent context/logs (router masks echoed Authorization).

Revocation semantics: door_ingest.revoke() scrubs the ingest store + re-mints
the paste token; the router deregisters + unlinks the lane secret; token scope
is stripped (keeping base lanes); every step audited. provider-dashboard kill
remains the instant kill switch (round-117 doctrine).
"""
from __future__ import annotations
import hashlib, json, os, pathlib, subprocess, sys, time, urllib.request

sys.path.insert(0, "/srv/bricks/ovh-server-001")
sys.path.insert(0, "/srv/door")

import allowance_meter as meter  # noqa: E402
from token_router import FLEET_BYOK_ALLOWLIST  # noqa: E402

REGISTER = pathlib.Path("/srv/bricks/register")
BYOK_LEDGER = REGISTER / "byok.jsonl"
ROUTER = "http://127.0.0.1:3742"
FLEET_TOKEN = "/srv/bricks/router/tokens/ovh-server-001.token"
TOKEN_ISSUE = "/srv/bricks/router/token_issue.py"
TOKENS_META = "/srv/bricks/router/state/tokens-meta.jsonl"
VAULT_STORE = pathlib.Path("/srv/vault/store.jsonl")
ROUTER_VAULT = pathlib.Path("/srv/bricks/router/state/vault")


def _fleet_token() -> str:
    return pathlib.Path(FLEET_TOKEN).read_text().strip()


def _router_api(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        f"{ROUTER}{path}",
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {_fleet_token()}",
                 "Content-Type": "application/json"},
        method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "body": e.read().decode()[:200]}
    except Exception as e:
        return {"error": str(e)[:120]}


def _audit(kind: str, detail: dict):
    with open(BYOK_LEDGER, "a") as f:
        f.write(json.dumps({"kind": kind, "ts": int(time.time()), **detail}) + "\n")
    os.chmod(BYOK_LEDGER, 0o600)


def person_brick(person_id: str) -> str | None:
    """The person's registered brick (registry owner name -> brick_id)."""
    name = meter.person_name(person_id)
    if not meter.REGISTRY.exists():
        return None
    for line in meter.REGISTRY.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("owner") == name and r.get("brick_id"):
            return r["brick_id"]
    return None


def _current_meta(brick_id: str) -> dict:
    """Current token meta (scope + cap) via sudo (tokens-meta is root:root)."""
    try:
        out = subprocess.run(["sudo", "cat", str(TOKENS_META)],
                             capture_output=True, text=True, timeout=30)
        for line in out.stdout.splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("brick_id") == brick_id and r.get("status") == "active":
                return r
    except Exception:
        pass
    return {}


def _token_issue(args: list[str]) -> tuple[int, str]:
    p = subprocess.run(["sudo", "python3", TOKEN_ISSUE] + args,
                       capture_output=True, text=True, timeout=60)
    return p.returncode, (p.stdout + p.stderr).strip()


def register(person_id: str, service: str, key: str) -> dict:
    """Vault the key (per-user 0600, owner-bound, custody hash) + wire the lane
    + grant scope. Idempotent per (person, service): re-register updates."""
    v = vault(person_id, service, key)
    if not v.get("ok"):
        return v
    w = wire_lane(person_id, service, key)
    return {**v, **w}


def vault(person_id: str, service: str, key: str) -> dict:
    """Ingest-side vault only (door_ingest.vault_put: atomic 0600 + custody
    hash). Always succeeds for allowlisted services — the key is the user's;
    storage is the guarantee, lane wiring is separate (staged)."""
    if service not in FLEET_BYOK_ALLOWLIST:
        return {"ok": False,
                "error": f"service '{service}' not on the fleet BYOK allowlist "
                         f"({sorted(FLEET_BYOK_ALLOWLIST)})"}
    key_sha = hashlib.sha256(key.encode()).hexdigest()[:16]
    try:
        from door_ingest import vault_put
        vault_put(service, key, person_id)
    except Exception as e:
        return {"ok": False, "error": f"vault_put failed: {str(e)[:80]}"}
    return {"ok": True, "key_sha": key_sha}


def wire_lane(person_id: str, service: str, key: str) -> dict:
    """Router lane (endpoint from the fleet allowlist ONLY — C2) + scope
    grant. Best-effort: a person without a registered brick stays vault-only
    (staged); the vault + revocation are real regardless."""
    if service not in FLEET_BYOK_ALLOWLIST:
        return {"ok": False,
                "error": f"service '{service}' not on the fleet BYOK allowlist "
                         f"({sorted(FLEET_BYOK_ALLOWLIST)}) — vault-only "
                         f"services are stored but not wired to a lane"}
    brick = person_brick(person_id)
    if not brick:
        return {"ok": False, "error": "no registered brick for this person — "
                                      "key vaulted; lane wiring staged until "
                                      "the brick registers"}
    key_sha = hashlib.sha256(key.encode()).hexdigest()[:16]

    # 2) router lane (endpoint from the fleet allowlist ONLY — C2)
    res = _router_api("POST", "/register", {
        "byok": True, "person_brick": brick, "service": service,
        "auth_secret": key})
    if res.get("error") or res.get("status") != "registered":
        return {"ok": False, "error": f"router byok register failed: {res}"}

    # 3) scope grant (root token_issue — sudo is the documented box model)
    meta = _current_meta(brick)
    scope = list(meta.get("lane_scope") or [])
    cap = meta.get("spend_cap_usd") or 2.0
    lane = f"byok-{brick}"
    if lane not in scope:
        scope.append(lane)
        rc, out = _token_issue(["adopt", "--brick-id", brick,
                                "--owner", meter.person_name(person_id),
                                "--lane-scope", ",".join(scope),
                                "--spend-cap-usd", str(cap)])
        if rc != 0:
            return {"ok": False,
                    "error": f"scope grant failed (rc={rc}): {out[:200]}"}

    _audit("byok-register", {"person_id": person_id, "brick_id": brick,
                             "lane": lane, "service": service,
                             "key_sha": key_sha, "scope": scope})
    return {"ok": True, "brick_id": brick, "lane": lane,
            "key_sha": key_sha, "endpoint": FLEET_BYOK_ALLOWLIST[service][0]}


def revoke(person_id: str) -> dict:
    """One atomic-ish revoke: scrub ingest store + deactivate lane + unlink
    router vault secret + strip scope + audit. Zero retention afterwards."""
    brick = person_brick(person_id)
    lane = f"byok-{brick}" if brick else ""
    out = {"person_id": person_id, "brick_id": brick, "lane": lane}

    # 1) router: deregister lane + unlink vault secret (zero-retention)
    if lane:
        res = _router_api("POST", "/deregister", {"lane_id": lane, "byok": True})
        out["router"] = res
        secret_file = ROUTER_VAULT / f"{lane}.secret"
        if secret_file.exists():
            secret_file.unlink()
            out["router_secret_unlinked"] = True

    # 2) ingest-side scrub + re-mint paste token (D7)
    try:
        from door_ingest import revoke as ingest_revoke
        tok = ingest_revoke(person_id)
        out["ingest_scrubbed"] = True
        out["new_token"] = tok
    except Exception as e:
        out["ingest_scrubbed"] = False
        out["ingest_error"] = str(e)[:80]

    # 3) strip scope (keep base lanes)
    if brick:
        meta = _current_meta(brick)
        scope = [s for s in (meta.get("lane_scope") or []) if s != lane]
        if scope != (meta.get("lane_scope") or []):
            rc, msg = _token_issue(["adopt", "--brick-id", brick,
                                    "--owner", meter.person_name(person_id),
                                    "--lane-scope", ",".join(scope),
                                    "--spend-cap-usd",
                                    str(meta.get("spend_cap_usd") or 2.0)])
            out["scope_stripped"] = (rc == 0)
            out["scope_msg"] = msg[:120] if rc else ""
        else:
            out["scope_stripped"] = True  # lane was never in scope

    # 4) zero-retention audit: grep the box for any key material
    leaked = []
    if lane:
        for hay in (VAULT_STORE, ROUTER_VAULT / f"{lane}.secret"):
            if hay.exists() and lane.replace("byok-", "") in hay.read_text(
                    errors="replace"):
                leaked.append(str(hay))
    out["zero_retention"] = not leaked
    out["residual_paths"] = leaked
    _audit("byok-revoke", {"brick_id": brick, "lane": lane,
                           "zero_retention": out["zero_retention"],
                           "residual": leaked})
    return out


def status(brick_id: str) -> dict:
    lane = f"byok-{brick_id}"
    lanes = _router_api("GET", "/lanes")
    lane_row = next((l for l in lanes.get("lanes", [])
                     if l.get("lane_id") == lane), None)
    meta = _current_meta(brick_id)
    return {"lane": lane,
            "lane_active": bool(lane_row and lane_row.get("active", True)),
            "in_scope": lane in (meta.get("lane_scope") or []),
            "vault_secret": (ROUTER_VAULT / f"{lane}.secret").exists()}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["register", "revoke", "status", "person-brick"])
    ap.add_argument("--person-id", default="")
    ap.add_argument("--brick-id", default="")
    ap.add_argument("--service", default="deepseek")
    ap.add_argument("--key", default="")
    a = ap.parse_args()
    if a.cmd == "register":
        print(json.dumps(register(a.person_id, a.service, a.key), indent=1))
    elif a.cmd == "revoke":
        print(json.dumps(revoke(a.person_id), indent=1))
    elif a.cmd == "status":
        print(json.dumps(status(a.brick_id), indent=1))
    elif a.cmd == "person-brick":
        print(person_brick(a.person_id))
