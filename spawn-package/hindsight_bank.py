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

Round-63 guards enforced HERE (not just CI):
  - status is CLAMPED to "claimed" in retain(): a brick can NEVER self-verify
    (D-3 guard 1); verification only via the register phase with external proof.
  - receipt IDs must match ledger shape (^[A-Z]+-[0-9]+$ or ^T-...$) — realness,
    not presence (D-2).
  - bank data files are mode 0600 (D-5 privacy at the FS level).
  - retain() is atomic: exclusive flock around check+append (no TOCTOU dupes).
  - corrupt JSONL rows are counted + surfaced (never silently fail-open).
  - rejections are logged in the audit, and audit rows are written BEFORE the
    entry (no crash window where an entry exists without its audit line).
"""
from __future__ import annotations
import argparse, fcntl, hashlib, json, pathlib, re, sys, time, unicodedata

RECEIPT_SHAPE = re.compile(r"^[A-Z][A-Z0-9-]*-\d+$")  # e.g. T-UNIVERSE-008, K1-42
VALID_STATUS = {"claimed"}  # nothing else is writable by a brick

class BankRejection(Exception):
    """Business-rule rejection — a brick catches this; it never kills the worker."""

class HindsightBank:
    def __init__(self, bank_dir: pathlib.Path, brick_id: str):
        self.bank_dir = bank_dir
        self.brick_id = brick_id
        self.entries_path = bank_dir / "entries.jsonl"
        self.audit_path = bank_dir / "audit.jsonl"
        bank_dir.mkdir(parents=True, exist_ok=True)
        self._secure()

    # ---- internal ----
    def _secure(self):
        """D-5 privacy at FS level: bank data files are 0600."""
        for p in (self.entries_path, self.audit_path):
            if not p.exists():
                p.touch()
            p.chmod(0o600)

    def _append(self, path: pathlib.Path, row: dict):
        with open(path, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(row) + "\n")
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)

    def _log(self, op: str, detail: dict, outcome: str = "ok"):
        self._append(self.audit_path, {"ts": int(time.time()), "brick": self.brick_id,
                                       "op": op, "outcome": outcome, **detail})

    def _read_entries(self) -> tuple[list, int]:
        """Returns (entries, corrupt_count). Corrupt rows are counted, never hidden."""
        if not self.entries_path.exists():
            return [], 0
        out, corrupt = [], 0
        for line in self.entries_path.read_text().splitlines():
            try:
                e = json.loads(line)
                if not isinstance(e, dict) or "topic_hash" not in e:
                    raise ValueError("missing topic_hash")
                out.append(e)
            except Exception:
                corrupt += 1
        return out, corrupt

    @staticmethod
    def topic_hash(topic: str) -> str:
        # NFKC + whitespace-normalize: "Python  Memory" == "Python Memory"
        norm = " ".join(unicodedata.normalize("NFKC", topic.strip().lower()).split())
        return hashlib.sha256(norm.encode()).hexdigest()[:16]

    # ---- API ----
    def retain(self, topic: str, learning: str, receipt_ids: list[str]) -> dict:
        """Store a learning. ALWAYS status='claimed' — self-verify is impossible (D-3)."""
        receipts = [r for r in receipt_ids if r and r.strip()]
        for r in receipts:
            if not RECEIPT_SHAPE.match(r.strip()):
                self._log("retain", {"topic": topic[:40], "receipts": receipts,
                                     "reason": "bad receipt shape"}, outcome="rejected")
                raise BankRejection(f"receipt '{r}' does not match ledger shape "
                                    f"(^[A-Z][A-Z0-9-]*-[0-9]+$), D-2 realness")
        if not receipts:
            self._log("retain", {"topic": topic[:40], "reason": "no receipts"},
                      outcome="rejected")
            raise BankRejection("no receipt refs — an entry without receipts is a blog post (D-2)")

        th = self.topic_hash(topic)
        entry = {"brick": self.brick_id, "ts": int(time.time()), "topic": topic.strip(),
                 "topic_hash": th, "learning": learning, "receipt_ids": receipts,
                 "status": "claimed"}  # clamped — NEVER user-supplied

        # atomic check+append (no TOCTOU dupes)
        with open(self.entries_path, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            existing, corrupt = [], 0
            if self.entries_path.stat().st_size > 0:
                existing, corrupt = self._read_entries()
            if any(e["topic_hash"] == th for e in existing):
                fcntl.flock(f, fcntl.LOCK_UN)
                self._log("retain", {"topic_hash": th, "reason": "duplicate"}, outcome="rejected")
                raise BankRejection(f"duplicate topic (hash {th}) — one learning per topic ever (D-2)")
            # audit row FIRST (no crash window where entry exists without audit)
            self._append(self.audit_path, {"ts": int(time.time()), "brick": self.brick_id,
                                           "op": "retain", "outcome": "ok",
                                           "topic_hash": th, "receipt_ids": receipts})
            f.write(json.dumps(entry) + "\n")
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)
        return {"retained": th, "status": "claimed"}

    def recall(self, query: str, top_k: int = 5) -> dict:
        """Search OWN bank only (private by default, D-5). Request is LOGGED (D-1)."""
        q = query.strip().lower()
        entries, corrupt = self._read_entries()
        hits = []
        for e in entries:
            score = 0
            if q in e.get("topic", "").lower():
                score += 3
            if q in e.get("learning", "").lower():
                score += 1
            if score:
                hits.append({"topic": e.get("topic"), "topic_hash": e.get("topic_hash"),
                             "status": e.get("status"), "receipt_ids": e.get("receipt_ids", []),
                             "learning": e.get("learning", "")[:300], "score": score})
        hits.sort(key=lambda h: h["score"], reverse=True)
        self._log("recall", {"query": query, "hits": len(hits), "corrupt_rows": corrupt})
        return {"brick": self.brick_id, "query": query, "hits": hits[:top_k],
                "corrupt_rows": corrupt}

    def reflect(self, topic: str) -> dict:
        """Synthesize what THIS brick knows (private). Logged."""
        th = self.topic_hash(topic)
        entries, corrupt = self._read_entries()
        mine = [e for e in entries if e.get("topic_hash") == th]
        self._log("reflect", {"topic": topic, "entries": len(mine), "corrupt_rows": corrupt})
        if not mine:
            return {"brick": self.brick_id, "topic": topic, "summary": "no entries",
                    "corrupt_rows": corrupt}
        summary = " | ".join(f"[{e.get('status')}] {e.get('learning', '')[:200]}" for e in mine)
        return {"brick": self.brick_id, "topic": topic, "entries": len(mine),
                "summary": summary, "corrupt_rows": corrupt,
                "receipt_ids": [r for e in mine for r in e.get("receipt_ids", [])]}

    def status(self) -> dict:
        entries, corrupt = self._read_entries()
        audit_rows = 0
        if self.audit_path.exists():
            for line in self.audit_path.read_text().splitlines():
                if line.strip():
                    audit_rows += 1
        self._log("status", {"entries": len(entries), "corrupt_rows": corrupt})
        return {"brick": self.brick_id, "entries": len(entries), "corrupt_rows": corrupt,
                "claimed": sum(1 for e in entries if e.get("status") == "claimed"),
                "verified": sum(1 for e in entries if e.get("status") == "verified"),
                "audit_rows": audit_rows}

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
    try:
        if args.op == "retain":
            receipts = [r.strip() for r in args.receipts.split(",") if r.strip()]
            print(json.dumps(bank.retain(args.topic, args.learning, receipts)))
        elif args.op == "recall":
            print(json.dumps(bank.recall(args.topic)))
        elif args.op == "reflect":
            print(json.dumps(bank.reflect(args.topic)))
        else:
            print(json.dumps(bank.status()))
    except BankRejection as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
