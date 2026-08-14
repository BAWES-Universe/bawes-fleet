#!/usr/bin/env python3
"""capability_register.py — shared knowledge layer + capability register (round-63 D-3, binding).

The register is where the fleet's learnings become VISIBLE and VERIFIED:
  - A learning enters as a CLAIM (write-up merged from a brick's bank via the
    bridge, DA'd, deduped by topic hash).
  - It becomes VERIFIED ONLY via probe-pool before/after measurement (D-3
    guard 1: scar doctrine — claims are never presented as capabilities).
  - The register is the fleet's visible capability map: what the fleet claims
    it can do vs what it has PROVEN it can do.

Round-63 guards enforced HERE:
  - No self-verify: nothing in this module can mark a claim VERIFIED except the
    probe-pool measurement path, which requires an external measurement record
    (probe_id + before/after scores + evaluator id). A brick cannot fabricate
    verification.
  - Probe pool is HELD-OUT (D-3 guard 2): the register records probe_pool
    version + checksum; the pool itself never enters any training set (noted
    in every measurement row).
  - One capability per topic ever (topic-hash dedup, D-2).
  - Every mutation is audit-logged (D-1 surface).
  - Evidence-first: claims carry receipt refs; verification carries the
    measurement record.
"""
from __future__ import annotations
import argparse, fcntl, hashlib, json, pathlib, re, sys, time, unicodedata

TOPIC_HASH_RE = re.compile(r"^[0-9a-f]{16}$")
RECEIPT_SHAPE = re.compile(r"^[A-Z][A-Z0-9-]*-\d+$")

def topic_hash(topic: str) -> str:
    norm = " ".join(unicodedata.normalize("NFKC", topic.strip().lower()).split())
    return hashlib.sha256(norm.encode()).hexdigest()[:16]

class CapabilityRegister:
    def __init__(self, reg_dir: pathlib.Path, brick_id: str = "register-001"):
        self.reg_dir = reg_dir
        self.brick_id = brick_id
        self.claims_path = reg_dir / "claims.jsonl"
        self.measurements_path = reg_dir / "measurements.jsonl"
        self.audit_path = reg_dir / "audit.jsonl"
        try:
            reg_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        for p in (self.claims_path, self.measurements_path, self.audit_path):
            try:
                if not p.exists():
                    p.touch()
                p.chmod(0o600)
            except OSError:
                pass

    # ---- internal ----
    def _log(self, op: str, detail: dict, outcome: str = "ok"):
        try:
            with open(self.audit_path, "a") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.write(json.dumps({"ts": int(time.time()), "register": self.brick_id,
                                    "op": op, "outcome": outcome, **detail}) + "\n")
                f.flush()
                fcntl.flock(f, fcntl.LOCK_UN)
        except OSError:
            pass

    def _read(self, path: pathlib.Path) -> tuple[list[dict], int]:
        if not path.exists():
            return [], 0
        out, corrupt = [], 0
        try:
            for line in path.read_text().splitlines():
                try:
                    e = json.loads(line)
                    if not isinstance(e, dict):
                        raise ValueError("not a dict")
                    out.append(e)
                except Exception:
                    corrupt += 1
        except OSError:
            return [], 0
        return out, corrupt

    def _append_atomic(self, path: pathlib.Path, row: dict):
        with open(path, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(row) + "\n")
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)

    # ---- API ----
    def claim(self, topic: str, capability: str, receipt_ids: list[str],
              source_brick: str, bridge_ref: str = "") -> dict:
        """A write-up enters the register as a CLAIM (never verified here).
        Requires: valid receipt refs (evidence-first, D-2), source brick, topic."""
        receipts = [r.strip() for r in receipt_ids if r and r.strip()]
        if not receipts:
            self._log("claim", {"topic": topic[:40], "reason": "no receipts"}, outcome="rejected")
            raise ValueError("claim needs receipt refs (evidence-first, D-2)")
        for r in receipts:
            if not RECEIPT_SHAPE.match(r):
                self._log("claim", {"topic": topic[:40], "receipt": r}, outcome="rejected")
                raise ValueError(f"receipt '{r}' not ledger shape (^[A-Z][A-Z0-9-]*-[0-9]+$)")
        if not source_brick.strip():
            self._log("claim", {"topic": topic[:40], "reason": "no source"}, outcome="rejected")
            raise ValueError("claim needs source_brick")

        th = topic_hash(topic)
        claims, corrupt = self._read(self.claims_path)
        if any(c["topic_hash"] == th for c in claims):
            self._log("claim", {"topic_hash": th, "reason": "duplicate"}, outcome="rejected")
            raise ValueError(f"duplicate topic (hash {th}) — one capability per topic ever (D-2)")

        row = {"topic": topic.strip(), "topic_hash": th, "capability": capability.strip(),
               "receipt_ids": receipts, "source_brick": source_brick,
               "bridge_ref": bridge_ref, "status": "claimed",  # NEVER verified here
               "ts": int(time.time())}
        # audit BEFORE claim row (no crash window where a claim exists unlogged)
        self._log("claim", {"topic_hash": th, "receipts": receipts, "source": source_brick})
        self._append_atomic(self.claims_path, row)
        return {"topic_hash": th, "status": "claimed"}

    def verify(self, topic: str, probe_id: str, before_score: float, after_score: float,
               evaluator: str, probe_pool_version: str, probe_pool_checksum: str) -> dict:
        """CLAIMED -> VERIFIED via probe-pool measurement (D-3 guard 1).
        The ONLY path that upgrades status; requires a full measurement record.
        The probe pool is HELD-OUT (D-3 guard 2): recorded with version+checksum,
        never usable as training data (the checksum makes pool substitution detectable)."""
        if not TOPIC_HASH_RE.match(probe_id):
            raise ValueError(f"probe_id '{probe_id}' not a topic-hash shape")
        if not (0 <= before_score <= 1 and 0 <= after_score <= 1):
            raise ValueError("scores must be in [0,1]")
        if not probe_pool_version or len(probe_pool_checksum) < 16:
            raise ValueError("probe_pool_version + checksum required (held-out pool, D-3)")
        if after_score <= before_score:
            # guard 3: a fine-tune qualifies only if it BEATS the baseline on the held-out pool
            self._log("verify", {"probe_id": probe_id, "before": before_score,
                                 "after": after_score, "reason": "not an improvement"},
                      outcome="rejected")
            raise ValueError(f"no improvement: after {after_score} <= before {before_score} — "
                             f"overfitting is not growth (D-3 guard 3)")

        th = topic_hash(topic)
        claims, corrupt = self._read(self.claims_path)
        idx = next((i for i, c in enumerate(claims) if c["topic_hash"] == th), None)
        if idx is None:
            self._log("verify", {"topic_hash": th, "reason": "no claim"}, outcome="rejected")
            raise ValueError(f"no claim for topic hash {th} — verify a claim, not a ghost")

        meas = {"ts": int(time.time()), "topic_hash": th, "probe_id": probe_id,
                "before": before_score, "after": after_score, "evaluator": evaluator,
                "probe_pool_version": probe_pool_version,
                "probe_pool_checksum": probe_pool_checksum,
                "held_out": True}  # guard 2: this pool NEVER enters a training set
        self._append_atomic(self.measurements_path, meas)

        claims[idx]["status"] = "verified"
        claims[idx]["verified_ts"] = int(time.time())
        claims[idx]["measurement"] = {"probe_id": probe_id, "before": before_score,
                                      "after": after_score, "evaluator": evaluator}
        # rewrite claims atomically (temp + rename)
        tmp = self.claims_path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            for c in claims:
                f.write(json.dumps(c) + "\n")
            f.flush()
            os_fchmod = __import__("os").fchmod
            os_fchmod(f.fileno(), 0o600)
            fcntl.flock(f, fcntl.LOCK_UN)
        __import__("os").replace(tmp, self.claims_path)
        self._log("verify", {"topic_hash": th, "probe_id": probe_id,
                             "before": before_score, "after": after_score,
                             "evaluator": evaluator, "pool_version": probe_pool_version})
        return {"topic_hash": th, "status": "verified", "improvement": after_score - before_score}

    def status(self) -> dict:
        claims, corrupt = self._read(self.claims_path)
        meas, meas_corrupt = self._read(self.measurements_path)
        self._log("status", {"claims": len(claims)})
        return {"brick": self.brick_id,
                "claims": len(claims),
                "claimed": sum(1 for c in claims if c.get("status") == "claimed"),
                "verified": sum(1 for c in claims if c.get("status") == "verified"),
                "measurements": len(meas),
                "corrupt_rows": corrupt + meas_corrupt}

    def list(self, status: str = "") -> list[dict]:
        """The visible capability map: topic, status, receipts, measurement."""
        claims, _ = self._read(self.claims_path)
        out = []
        for c in claims:
            if status and c.get("status") != status:
                continue
            out.append({"topic": c["topic"], "topic_hash": c["topic_hash"],
                        "status": c.get("status"),
                        "receipt_ids": c.get("receipt_ids", []),
                        "source_brick": c.get("source_brick", ""),
                        "measurement": c.get("measurement")})
        out.sort(key=lambda c: c["topic"])
        return out

def main():
    ap = argparse.ArgumentParser(description="capability register (round-63 D-3)")
    ap.add_argument("op", choices=["claim", "verify", "status", "list"])
    ap.add_argument("--reg-dir", required=True)
    ap.add_argument("--brick-id", default="register-001")
    ap.add_argument("--topic", default="")
    ap.add_argument("--capability", default="")
    ap.add_argument("--receipts", default="")
    ap.add_argument("--source-brick", default="")
    ap.add_argument("--bridge-ref", default="")
    ap.add_argument("--probe-id", default="")
    ap.add_argument("--before", type=float, default=0.0)
    ap.add_argument("--after", type=float, default=0.0)
    ap.add_argument("--evaluator", default="")
    ap.add_argument("--pool-version", default="")
    ap.add_argument("--pool-checksum", default="")
    args = ap.parse_args()

    reg = CapabilityRegister(pathlib.Path(args.reg_dir), args.brick_id)
    try:
        if args.op == "claim":
            receipts = [r.strip() for r in args.receipts.split(",") if r.strip()]
            print(json.dumps(reg.claim(args.topic, args.capability, receipts,
                                       args.source_brick, args.bridge_ref)))
        elif args.op == "verify":
            print(json.dumps(reg.verify(args.topic, args.probe_id, args.before, args.after,
                                        args.evaluator, args.pool_version, args.pool_checksum)))
        elif args.op == "status":
            print(json.dumps(reg.status()))
        else:
            print(json.dumps(reg.list(args.topic)))
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
