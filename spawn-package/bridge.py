#!/usr/bin/env python3
"""bridge.py — the HINDSIGHT BRIDGE between per-brick banks (round-63 ruling, binding).

Connects banks: any brick can ask the bridge "has anyone learned X?" and get
AGGREGATED recall across banks.

Round-63 D-1/D-2/D-5 constraints enforced HERE (hostile-DA hardened):
  - METADATA-ONLY at WRITE: index rows pass a strict field whitelist; ANY other
    field (learning, body, content, nested) is REJECTED. The bridge never holds
    raw content, not even at rest.
  - D-5 privacy at FS level: index + audit files are mode 0600.
  - AUTH FAIL-CLOSED: a token is REQUIRED. Tokens live in a tokens/ dir
    (mode-600 per file); each token is bound to a brick_id at registration —
    a caller's brick_id is derived from ITS token, never from the request body
    (impersonation impossible). No token configured => bridge refuses to serve.
  - Server-side dedup (D-2): topic_hash is RECOMPUTED from the topic with the
    bank's normalization (NFKC + whitespace) — brick-supplied hashes are
    ignored. Intra-call dupes rejected too. One learning per topic, ever.
  - FAIL-OPEN (D-5): bricks work without the bridge. Any degradation returns a
    real HTTP 503 (distinguishable from "no data"), and status() degrades
    exactly like recall() — never crashes.
  - AUDIT (D-1): every op — recall, index, status, 401, 404, rejections — is
    logged with outcome.
  - Concurrency: flock + temp-file + atomic rename around index writes.
"""
from __future__ import annotations
import argparse, fcntl, hashlib, json, os, pathlib, re, sys, time, unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

# strict whitelist — metadata only, nothing else can land on disk (DA-4)
ALLOWED_INDEX_FIELDS = {"brick", "topic", "topic_hash", "status", "receipt_ids", "ts"}
ALLOWED_STATUS = {"claimed", "verified"}
BRICK_ID_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

def topic_hash(topic: str) -> str:
    # NFKC + whitespace-normalize: "Python  Memory" == "Python Memory" (bank parity)
    norm = " ".join(unicodedata.normalize("NFKC", topic.strip().lower()).split())
    return hashlib.sha256(norm.encode()).hexdigest()[:16]

class Bridge:
    def __init__(self, index_dir: pathlib.Path, tokens_dir: pathlib.Path | None = None,
                 brick_id: str = "bridge-001"):
        self.index_dir = index_dir
        self.tokens_dir = tokens_dir
        self.brick_id = brick_id
        self.audit_path = index_dir / "audit.jsonl"
        try:
            index_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # fail-open: bridge degrades, never dies (D-5)
        try:
            if self.audit_path.exists():
                self.audit_path.chmod(0o600)
            else:
                self.audit_path.touch()
                self.audit_path.chmod(0o600)
        except OSError:
            pass  # fail-open: audit hardening failure never breaks the bridge

    # ---- auth (fail-closed, token-bound identity) ----
    def _token_to_brick(self, token: str) -> str | None:
        """Resolve a bearer token to its bound brick_id. Mode-600 per file."""
        if not self.tokens_dir or not token:
            return None
        td = pathlib.Path(self.tokens_dir)
        if not td.is_dir():
            return None
        try:
            for p in td.iterdir():
                if not p.is_file() or (p.stat().st_mode & 0o777) != 0o600:
                    continue
                if p.read_text().strip() == token:
                    return p.name.replace(".token", "")
        except OSError:
            return None
        return None

    # ---- internal ----
    def _log(self, op: str, detail: dict, outcome: str = "ok"):
        try:
            with open(self.audit_path, "a") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.write(json.dumps({"ts": int(time.time()), "bridge": self.brick_id,
                                    "op": op, "outcome": outcome, **detail}) + "\n")
                f.flush()
                fcntl.flock(f, fcntl.LOCK_UN)
        except OSError:
            pass  # fail-open: audit failure never breaks recall (D-5)

    def _read_index(self) -> tuple[list[dict], int] | None:
        """Read all brick index files. Returns (rows, corrupt_count), or None
        when the index dir is structurally broken (path exists but isn't a dir)
        — the caller returns 503. A missing-but-creatable dir = empty index."""
        if self.index_dir.exists() and not self.index_dir.is_dir():
            return None  # structurally broken -> degraded (DA-6)
        if not self.index_dir.is_dir():
            return [], 0
        rows, corrupt = [], 0
        try:
            files = sorted(self.index_dir.glob("index-*.jsonl"))
        except OSError:
            return [], 0
        for p in files:
            brick = p.name.replace("index-", "").replace(".jsonl", "")
            try:
                lines = p.read_text().splitlines()
            except OSError:
                continue
            for line in lines:
                try:
                    e = json.loads(line)
                    if not isinstance(e, dict):
                        raise ValueError("not a dict")
                    row = {k: e[k] for k in ALLOWED_INDEX_FIELDS if k in e}
                    if "topic_hash" not in row or "topic" not in row:
                        raise ValueError("missing topic/topic_hash")
                    row["brick"] = brick  # attribution from FILENAME, never body
                    rows.append(row)
                except Exception:
                    corrupt += 1
        return rows, corrupt

    def _atomic_write_index(self, brick: str, rows: list[dict]):
        out = self.index_dir / f"index-{brick}.jsonl"
        tmp = self.index_dir / f".index-{brick}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.flush()
            os.fchmod(f.fileno(), 0o600)  # D-5 privacy at rest
            fcntl.flock(f, fcntl.LOCK_UN)
        os.replace(tmp, out)  # atomic: readers never see a torn file
        os.chmod(out, 0o600)

    # ---- API ----
    def index(self, brick: str, rows: list[dict]) -> dict:
        """A brick registers its index (metadata only, D-5).
        brick_id comes from the AUTHENTICATED token, not the body — but we also
        validate the body brick_id matches (defense in depth)."""
        if not BRICK_ID_SHAPE.match(brick):
            self._log("index", {"brick": brick, "reason": "invalid brick_id"}, outcome="rejected")
            raise ValueError(f"invalid brick_id '{brick}' (DA-9)")
        clean = []
        for r in rows:
            if not isinstance(r, dict):
                self._log("index", {"brick": brick, "reason": "row not an object"}, outcome="rejected")
                raise ValueError("index row must be an object")
            extra = set(r.keys()) - ALLOWED_INDEX_FIELDS
            if extra:
                self._log("index", {"brick": brick, "rejected_fields": sorted(extra)},
                          outcome="rejected")
                raise ValueError(f"index rows are metadata-only; rejected fields: {sorted(extra)} (D-5)")
            if "topic" not in r or "receipt_ids" not in r:
                self._log("index", {"brick": brick, "reason": "missing topic/receipts"},
                          outcome="rejected")
                raise ValueError("index row needs topic + receipt_ids")
            # SERVER-SIDE hash + normalized topic: never trust the brick (DA-3)
            th = topic_hash(r["topic"])
            norm_topic = " ".join(unicodedata.normalize("NFKC", r["topic"].strip()).split())
            status = r.get("status", "claimed")
            if status not in ALLOWED_STATUS:
                self._log("index", {"brick": brick, "status": status}, outcome="rejected")
                raise ValueError(f"status must be claimed|verified, got '{status}'")
            clean.append({"brick": brick, "topic": norm_topic[:80], "topic_hash": th,
                          "status": status,
                          "receipt_ids": [x for x in r.get("receipt_ids", []) if isinstance(x, str)],
                          "ts": int(r.get("ts", 0))})

        # flock around read-check-append-write (no lost rows, no TOCTOU dupes)
        lock_path = self.index_dir / ".index.lock"
        with open(lock_path, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                res = self._read_index()
                if res is None:
                    raise ValueError("index dir structurally broken — refusing to write")
                existing, corrupt = res
                # intra-call dedup: same hash twice in ONE registration (DA-3)
                seen_in_call = set()
                kept, dupes = [], 0
                for row in clean:
                    if row["topic_hash"] in seen_in_call:
                        dupes += 1
                        continue
                    seen_in_call.add(row["topic_hash"])
                    if row["topic_hash"] in {e["topic_hash"] for e in existing}:
                        dupes += 1
                        continue
                    kept.append(row)
                # preserve other bricks' rows + this brick's existing rows
                others = [e for e in existing if e["brick"] != brick]
                mine = [e for e in existing if e["brick"] == brick]
                all_rows = others + mine + kept
                if corrupt:
                    self._log("index", {"brick": brick, "corrupt_rows": corrupt}, outcome="partial")
                self._atomic_write_index(brick, mine + kept)
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)
        self._log("index", {"brick": brick, "rows": len(kept), "dupes": dupes})
        return {"brick": brick, "indexed": len(kept), "dupes_skipped": dupes, "corrupt_rows": corrupt}

    def recall(self, query: str, top_k: int = 10) -> dict | int:
        """Aggregated recall — metadata + receipts only. Returns int 503 on degrade."""
        if not query.strip():
            return 503  # empty query rejected (DA-10)
        q = query.strip().lower()
        try:
            res = self._read_index()
        except Exception:
            self._log("recall", {"query": query, "reason": "index unreadable"}, outcome="error")
            return 503
        if res is None:
            self._log("recall", {"query": query, "reason": "index dir broken"}, outcome="error")
            return 503
        rows, corrupt = res
        hits = []
        for e in rows:
            score = 0
            if q in e["topic"].lower():
                score += 3
            if any(q in r.lower() for r in e["receipt_ids"]):
                score += 1
            if score:
                hits.append({**e, "score": score})
        hits.sort(key=lambda h: h["score"], reverse=True)
        self._log("recall", {"query": query, "hits": len(hits), "corrupt_rows": corrupt})
        return {"query": query, "hits": hits[:top_k],
                "bricks_indexed": len(set(h["brick"] for h in rows)),
                "corrupt_rows": corrupt}

    def status(self) -> dict | int:
        """Degrades exactly like recall() — never crashes (DA-6)."""
        try:
            res = self._read_index()
            if res is None:
                self._log("status", {"reason": "index dir broken"}, outcome="error")
                return 503
            rows, corrupt = res
            audit_rows = 0
            if self.audit_path.exists():
                for line in self.audit_path.read_text().splitlines():
                    if line.strip():
                        audit_rows += 1
            self._log("status", {"bricks_indexed": len(set(r["brick"] for r in rows)),
                                 "index_rows": len(rows), "corrupt_rows": corrupt})
            return {"brick": self.brick_id, "bricks_indexed": len(set(r["brick"] for r in rows)),
                    "index_rows": len(rows), "corrupt_rows": corrupt, "audit_rows": audit_rows}
        except Exception:
            self._log("status", {"reason": "degraded"}, outcome="error")
            return 503

# ---- HTTP surface ----
class BridgeHandler(BaseHTTPRequestHandler):
    bridge = None  # set by caller

    def _json(self, code: int, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _caller_brick(self) -> str | None:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        return self.bridge._token_to_brick(auth[7:].strip())

    def do_GET(self):
        caller = self._caller_brick()
        if not caller:
            self.bridge._log("auth", {"path": self.path, "outcome": "401"}, outcome="rejected")
            self._json(401, {"error": "unauthorized"})
            return
        parsed = urlparse(self.path)
        if parsed.path == "/recall":
            q = unquote(parsed.query[2:]) if parsed.query.startswith("q=") else ""
            res = self.bridge.recall(q)
            if res == 503:
                self._json(503, {"error": "bridge degraded"})
            else:
                self._json(200, res)
        elif parsed.path == "/status":
            res = self.bridge.status()
            if res == 503:
                self._json(503, {"error": "bridge degraded"})
            else:
                self._json(200, res)
        else:
            self.bridge._log("404", {"path": self.path}, outcome="rejected")
            self._json(404, {"error": "not found"})

    def do_POST(self):
        caller = self._caller_brick()
        if not caller:
            self.bridge._log("auth", {"path": self.path, "outcome": "401"}, outcome="rejected")
            self._json(401, {"error": "unauthorized"})
            return
        parsed = urlparse(self.path)
        if parsed.path == "/index":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode())
                body_brick = body.get("brick", "")
                rows = body.get("rows", [])
                # brick_id MUST match the token-bound identity (DA-5 impersonation)
                if body_brick != caller:
                    self.bridge._log("index", {"claimed": body_brick, "authed": caller,
                                               "outcome": "rejected"}, outcome="rejected")
                    self._json(403, {"error": f"brick_id '{body_brick}' != token identity '{caller}'"})
                    return
                if not isinstance(rows, list):
                    self._json(400, {"error": "rows must be a list"})
                    return
                self._json(200, self.bridge.index(caller, rows))
            except ValueError as e:
                self.bridge._log("index", {"reason": str(e)}, outcome="rejected")
                self._json(400, {"error": str(e)})
            except Exception as e:
                self.bridge._log("index", {"reason": str(e)}, outcome="error")
                self._json(500, {"error": str(e)})
        else:
            self.bridge._log("404", {"path": self.path}, outcome="rejected")
            self._json(404, {"error": "not found"})

    def log_message(self, *a):
        pass  # audit handled by bridge

def main():
    ap = argparse.ArgumentParser(description="hindsight bridge (round-63)")
    ap.add_argument("--index-dir", required=True)
    ap.add_argument("--tokens-dir", required=True, help="dir of mode-600 <brick>.token files")
    ap.add_argument("--brick-id", default="bridge-001")
    ap.add_argument("--port", type=int, default=3740)
    ap.add_argument("--bind", default="127.0.0.1")
    args = ap.parse_args()

    b = Bridge(pathlib.Path(args.index_dir), pathlib.Path(args.tokens_dir), args.brick_id)
    BridgeHandler.bridge = b
    srv = ThreadingHTTPServer((args.bind, args.port), BridgeHandler)
    print(f"[bridge] {args.brick_id} on {args.bind}:{args.port} "
          f"(token-auth required, metadata-only, fail-open 503)")
    srv.serve_forever()

if __name__ == "__main__":
    main()
