#!/usr/bin/env python3
"""hindsight_bank.py — per-brick hindsight bank (round-63 ruling, binding).

Every brick ships a private long-term memory bank:
  - retain(entry): store a verified learning (receipt-ref'd, topic-hash deduped)
  - recall(query): search OWN bank (private by default)
  - reflect(topic): synthesize what this brick knows about a topic
  - The bank is namespaced by brick_id; content is private to its brick.
  - Recall/reflect requests are LOGGED (the bank is an audit surface, D-1).
  - Topic-hash dedup: one learning per topic ever (D-2 sharpening 2).
  - Evidence-first: every entry carries ledger receipt IDs (D-2 sharpening 1);
    an entry with no receipt refs is a blog post, not a learning.

Round-63 guards that apply here:
  - Write-ups merge into the SHARED layer only via the DA gate (bridge phase);
    this module is the per-brick store, not the shared layer.
  - CLAIMED vs VERIFIED: entries carry status "claimed" until probe-pool
    measurement upgrades them (the register does that; the bank records it).
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, sys, time

class HindsightBank:
    def __init__(self, bank_dir: pathlib.Path, brick_id: str):
        self.bank_dir = bank_dir
        self.brick_id = brick_id
        self.entries_path = bank_dir / "entries.jsonl"
        self.audit_path = bank_dir / "audit.jsonl"
        bank_dir.mkdir(parents=True, exist_ok=True)

    # ---- internal ----
    def _append(self, path: pathlib.Path, row: dict):
        with open(path, "a") as f:
            f.write(json.dumps(row) + "\n")

    def _log(self, op: str, detail: dict):
        self._append(self.audit_path, {"ts": int(time.time()), "brick": self.brick_id,
                                       "op": op, **detail})

    def _read_entries(self) -> list:
        if not self.entries_path.exists():
            return []
        out = []
        for line in self.entries_path.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out

    @staticmethod
    def topic_hash(topic: str) -> str:
        return hashlib.sha256(topic.strip().lower().encode()).hexdigest()[:16]

    # ---- API ----
    def retain(self, topic: str, learning: str, receipt_ids: list[str],
               status: str = "claimed") -> dict:
        """Store a verified learning. REJECTED if no receipt refs (D-2)."""
        if not receipt_ids:
            raise SystemExit("REJECTED: no receipt refs — an entry without receipts is a blog post (round-63 D-2)")
        th = self.topic_hash(topic)
        existing = [e for e in self._read_entries() if e["topic_hash"] == th]
        if existing:
            raise SystemExit(f"REJECTED: duplicate topic (hash {th}) — one learning per topic ever (D-2)")
        entry = {"brick": self.brick_id, "ts": int(time.time()), "topic": topic.strip(),
                 "topic_hash": th, "learning": learning, "receipt_ids": receipt_ids,
                 "status": status}  # claimed until probe-pool measurement
        self._append(self.entries_path, entry)
        self._log("retain", {"topic_hash": th, "receipt_ids": receipt_ids})
        return {"retained": th, "status": status}

    def recall(self, query: str, top_k: int = 5) -> dict:
        """Search OWN bank only (private by default, D-5). Request is LOGGED (D-1)."""
        q = query.strip().lower()
        hits = []
        for e in self._read_entries():
            score = 0
            if q in e["topic"].lower():
                score += 3
            if q in e["learning"].lower():
                score += 1
            if score:
                hits.append({"topic": e["topic"], "topic_hash": e["topic_hash"],
                             "status": e["status"], "receipt_ids": e["receipt_ids"],
                             "learning": e["learning"][:300], "score": score})
        hits.sort(key=lambda h: h["score"], reverse=True)
        self._log("recall", {"query": query, "hits": len(hits)})
        return {"brick": self.brick_id, "query": query, "hits": hits[:top_k]}

    def reflect(self, topic: str) -> dict:
        """Synthesize what THIS brick knows (private). Logged."""
        th = self.topic_hash(topic)
        mine = [e for e in self._read_entries() if e["topic_hash"] == th]
        self._log("reflect", {"topic": topic, "entries": len(mine)})
        if not mine:
            return {"brick": self.brick_id, "topic": topic, "summary": "no entries"}
        summary = " | ".join(f"[{e['status']}] {e['learning'][:200]}" for e in mine)
        return {"brick": self.brick_id, "topic": topic, "entries": len(mine),
                "summary": summary, "receipt_ids": [r for e in mine for r in e["receipt_ids"]]}

    def status(self) -> dict:
        entries = self._read_entries()
        return {"brick": self.brick_id, "entries": len(entries),
                "claimed": sum(1 for e in entries if e["status"] == "claimed"),
                "verified": sum(1 for e in entries if e["status"] == "verified"),
                "audit_rows": sum(1 for _ in self.audit_path.open()) if self.audit_path.exists() else 0}

def main():
    ap = argparse.ArgumentParser(description="per-brick hindsight bank (round-63)")
    ap.add_argument("op", choices=["retain", "recall", "reflect", "status"])
    ap.add_argument("--bank-dir", required=True)
    ap.add_argument("--brick-id", required=True)
    ap.add_argument("--topic", default="")
    ap.add_argument("--learning", default="")
    ap.add_argument("--receipts", default="", help="comma-separated ledger receipt IDs")
    args = ap.parse_args()

    bank = HindsightBank(pathlib.Path(args.bank_dir), args.brick_id)
    if args.op == "retain":
        print(json.dumps(bank.retain(args.topic, args.learning,
                                     [r.strip() for r in args.receipts.split(",") if r.strip()])))
    elif args.op == "recall":
        print(json.dumps(bank.recall(args.topic)))
    elif args.op == "reflect":
        print(json.dumps(bank.reflect(args.topic)))
    else:
        print(json.dumps(bank.status()))

if __name__ == "__main__":
    main()
