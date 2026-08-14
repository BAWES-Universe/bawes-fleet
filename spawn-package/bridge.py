#!/usr/bin/env python3
"""bridge.py — the HINDSIGHT BRIDGE between per-brick banks (round-63 ruling, binding).

Connects banks: any brick can ask the bridge "has anyone learned X?" and get
AGGREGATED recall across banks.

Round-63 D-1/D-5 constraints enforced HERE:
  - METADATA-ONLY index: the bridge indexes what each bank contains (topic,
    topic_hash, status, receipt_ids, brick_id, ts) — NEVER the raw learning text.
  - Aggregated recall returns metadata + receipt refs; the requesting brick
    fetches the full learning from the owning brick via A2A if authorized.
  - Recall requests are LOGGED (the bridge is an audit surface, D-1).
  - FAIL-OPEN: bricks work without the bridge; losing it degrades collective
    recall, never function (D-5). Bridge down = recall endpoint 503, bricks
    continue.
  - Topic-hash dedup at index time (D-2): one learning per topic ever.
  - The bridge itself holds NO bank content — only index rows. Raw content
    stays in the owning brick's private bank (mode-600).

Wiring: banks expose their index (topics only) via their local A2A endpoint;
the bridge pulls index rows (not content) on a cadence and serves /recall
aggregations. For phase (b) the bridge reads index files written by bricks
to a shared index dir OR is fed via the registry — implementation below uses
explicit index-file registration so it works before A2A mesh is fully wired.
"""
from __future__ import annotations
import argparse, json, pathlib, sys, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VALID_OPS = {"recall", "index", "status"}

class Bridge:
    def __init__(self, index_dir: pathlib.Path, brick_id: str = "bridge-001"):
        self.index_dir = index_dir
        self.brick_id = brick_id
        self.audit_path = index_dir / "audit.jsonl"
        try:
            index_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # fail-open: bridge degrades, never dies (D-5)

    # ---- internal ----
    def _log(self, op: str, detail: dict, outcome: str = "ok"):
        try:
            with open(self.audit_path, "a") as f:
                f.write(json.dumps({"ts": int(time.time()), "bridge": self.brick_id,
                                    "op": op, "outcome": outcome, **detail}) + "\n")
        except OSError:
            pass  # fail-open: audit failure never breaks recall (D-5)

    def _read_index(self) -> list[dict]:
        """Read all brick index files. Index rows = metadata ONLY (no learning text)."""
        rows = []
        if not self.index_dir.exists():
            return rows
        for p in sorted(self.index_dir.glob("index-*.jsonl")):
            brick = p.name.replace("index-", "").replace(".jsonl", "")
            for line in p.read_text().splitlines():
                try:
                    e = json.loads(line)
                    if "topic_hash" not in e or "topic" not in e:
                        continue
                    # enforce metadata-only: strip any raw content field if present
                    rows.append({"brick": brick, "topic": e["topic"][:80],
                                 "topic_hash": e["topic_hash"],
                                 "status": e.get("status", "claimed"),
                                 "receipt_ids": e.get("receipt_ids", []),
                                 "ts": e.get("ts", 0)})
                except Exception:
                    continue
        return rows

    # ---- API ----
    def recall(self, query: str, top_k: int = 10) -> dict:
        """Aggregated recall across registered bricks — metadata + receipts only.
        Returns 503 if index_dir unreadable (fail-open: caller treats as no-answer)."""
        try:
            rows = self._read_index()
        except Exception:
            self._log("recall", {"query": query, "reason": "index unreadable"}, outcome="error")
            return {"error": "bridge degraded", "status": 503}
        q = query.strip().lower()
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
        self._log("recall", {"query": query, "hits": len(hits)})
        return {"query": query, "hits": hits[:top_k], "bricks_indexed": len(set(h["brick"] for h in rows))}

    def index(self, brick: str, rows: list[dict]) -> dict:
        """A brick registers its index (metadata only). REJECTED if any row
        contains a raw 'learning' field (bridge never ingests content, D-5)."""
        for r in rows:
            if "learning" in r:
                self._log("index", {"brick": brick, "reason": "content rejected"}, outcome="rejected")
                raise ValueError("bridge ingests INDEX ONLY — no raw learning content (D-5)")
            if "topic_hash" not in r or "topic" not in r:
                raise ValueError("index row needs topic + topic_hash")
        # topic-hash dedup at index time: keep existing rows, append only new hashes
        existing_rows = self._read_index()
        existing = {r["topic_hash"] for r in existing_rows}
        dupes = [r for r in rows if r["topic_hash"] in existing]
        kept = [r for r in rows if r["topic_hash"] not in existing]
        if dupes:
            self._log("index", {"brick": brick, "dupes": len(dupes)}, outcome="partial")
        out = self.index_dir / f"index-{brick}.jsonl"
        # write existing rows + new rows (never truncate the index)
        all_rows = [r for r in existing_rows if r["brick"] == brick] + kept
        with open(out, "w") as f:
            for r in all_rows:
                f.write(json.dumps(r) + "\n")
        self._log("index", {"brick": brick, "rows": len(kept), "dupes": len(dupes)})
        return {"brick": brick, "indexed": len(kept), "dupes_skipped": len(dupes)}

    def status(self) -> dict:
        rows = self._read_index()
        audit_rows = sum(1 for _ in self.audit_path.open()) if self.audit_path.exists() else 0
        return {"brick": self.brick_id, "bricks_indexed": len(set(r["brick"] for r in rows)),
                "index_rows": len(rows), "audit_rows": audit_rows}

# ---- HTTP surface (local A2A-style, read-only + index registration) ----
class BridgeHandler(BaseHTTPRequestHandler):
    bridge = None  # set by caller

    def _json(self, code: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        auth = self.headers.get("Authorization", "")
        tok = getattr(self.bridge, "token", None)
        if not tok:
            return True  # no token configured — local-only bind expected
        return auth == f"Bearer {tok}"

    def do_GET(self):
        if not self._authed():
            self._json(401, {"error": "unauthorized"})
            return
        if self.path.startswith("/recall?q="):
            q = self.path.split("q=", 1)[1][:200]
            self._json(200, self.bridge.recall(q))
        elif self.path == "/status":
            self._json(200, self.bridge.status())
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self._authed():
            self._json(401, {"error": "unauthorized"})
            return
        if self.path == "/index":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode())
                brick = body.get("brick", "")
                rows = body.get("rows", [])
                if not brick or not isinstance(rows, list):
                    self._json(400, {"error": "need brick + rows"})
                    return
                self._json(200, self.bridge.index(brick, rows))
            except ValueError as e:
                self._json(400, {"error": str(e)})
            except Exception as e:
                self._json(500, {"error": str(e)})
        else:
            self._json(404, {"error": "not found"})

    def log_message(self, *a):
        pass  # silence default logging (audit handled by bridge)

def main():
    ap = argparse.ArgumentParser(description="hindsight bridge (round-63)")
    ap.add_argument("--index-dir", required=True)
    ap.add_argument("--brick-id", default="bridge-001")
    ap.add_argument("--port", type=int, default=3740)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--token", default="", help="bearer token (empty = local-only bind)")
    args = ap.parse_args()

    b = Bridge(pathlib.Path(args.index_dir), args.brick_id)
    b.token = args.token
    BridgeHandler.bridge = b
    srv = ThreadingHTTPServer((args.bind, args.port), BridgeHandler)
    print(f"[bridge] {args.brick_id} serving on {args.bind}:{args.port} (metadata-only index, fail-open)")
    srv.serve_forever()

if __name__ == "__main__":
    main()
