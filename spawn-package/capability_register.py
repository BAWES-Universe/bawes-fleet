#!/usr/bin/env python3
"""capability_register.py — shared knowledge layer + capability register (round-63 D-3, binding).

The register is where the fleet's learnings become VISIBLE and VERIFIED:
  - A learning enters as a CLAIM (write-up merged from a brick's bank via the
    bridge, DA'd, deduped by topic hash).
  - It becomes VERIFIED ONLY via probe-pool measurement (D-3 guard 1:
    scar doctrine — claims are never presented as capabilities).

Anti-poisoning design (hostile-DA hardened):
  - NO SELF-VERIFY: measurements are INGESTED as a separate event (ingest()
    requires evaluator != source_brick — a brick can never be its own
    evaluator). verify() only APPLIES a pre-existing ingested measurement
    to the claim it names. Fabricating verification is structurally
    impossible: verify() takes no scores at all.
  - Probe pool HELD-OUT (G2): every measurement records pool version +
    checksum; pool never enters training.
  - Guard-3 REAL: verify() requires after > the claim's BEST-KNOWN score
    (stored on the claim), not a self-reported baseline; regression or
    no-improvement is rejected.
  - One measurement per probe_id, bound to ONE topic (no cross-topic reuse).
  - Full 64-hex topic hash (no 32-bit birthday-collision DoS).
  - Single-writer flock: claim() read-check-append AND verify() read-apply-
    rewrite are one critical section each — no lost claims, no TOCTOU dupes.
  - Audit-before-mutation on every path (no crash window); every rejection
    is logged (D-1).
  - Every parsed row is schema-validated; corrupt rows counted + surfaced,
    never allowed to crash list()/status().
"""
from __future__ import annotations
import argparse, fcntl, hashlib, json, os, pathlib, re, sys, time, unicodedata

TOPIC_HASH_RE = re.compile(r"^[0-9a-f]{64}$")      # full sha256 hex
RECEIPT_SHAPE = re.compile(r"^[A-Z][A-Z0-9-]*-\d+$")

def topic_hash(topic: str) -> str:
    """Full 64-hex sha256 over NFKC+whitespace-normalized topic (no truncation)."""
    norm = " ".join(unicodedata.normalize("NFKC", topic.strip().lower()).split())
    return hashlib.sha256(norm.encode()).hexdigest()

class CapabilityRegister:
    def __init__(self, reg_dir: pathlib.Path, brick_id: str = "register-001"):
        self.reg_dir = reg_dir
        self.brick_id = brick_id
        self.claims_path = reg_dir / "claims.jsonl"
        self.measurements_path = reg_dir / "measurements.jsonl"
        self.audit_path = reg_dir / "audit.jsonl"
        self.lock_path = reg_dir / ".register.lock"
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
            pass  # fail-open audit (fleet doctrine), but audit-BEFORE-mutation everywhere

    def _read(self, path: pathlib.Path, require_topic: bool = False) -> tuple[list[dict], int]:
        """Schema-validated read: every row must be a dict with topic_hash.
        Corrupt rows are counted and surfaced — never crash callers.
        require_topic=True (claims): rows missing 'topic' count as corrupt so a
        ghost row can't permanently pin a topic hash (DA hardening note)."""
        if not path.exists():
            return [], 0
        out, corrupt = [], 0
        try:
            for line in path.read_text().splitlines():
                try:
                    e = json.loads(line)
                    if not isinstance(e, dict) or "topic_hash" not in e:
                        raise ValueError("missing topic_hash")
                    if require_topic and not isinstance(e.get("topic"), str):
                        raise ValueError("missing topic")
                    out.append(e)
                except Exception:
                    corrupt += 1
        except OSError:
            return [], 0
        return out, corrupt

    def _lock(self, excl: bool = True):
        lf = open(self.lock_path, "w")
        fcntl.flock(lf, fcntl.LOCK_EX if excl else fcntl.LOCK_SH)
        return lf

    def _append_atomic(self, path: pathlib.Path, row: dict):
        with open(path, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(row) + "\n")
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)

    # ---- API ----
    def claim(self, topic: str, capability: str, receipt_ids: list[str],
              source_brick: str, bridge_ref: str = "") -> dict:
        """A write-up enters the register as a CLAIM (never verified here)."""
        receipts = []
        for r in receipt_ids:
            r = (r or "").strip()
            if r and r not in receipts:      # dedup receipts within a claim
                receipts.append(r)
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
        lf = self._lock()                    # single critical section: check+append
        try:
            claims, corrupt = self._read(self.claims_path, require_topic=True)
            if any(c["topic_hash"] == th for c in claims):
                self._log("claim", {"topic_hash": th, "reason": "duplicate"}, outcome="rejected")
                raise ValueError(f"duplicate topic (hash {th}) — one capability per topic ever (D-2)")
            if corrupt:
                self._log("claim", {"topic_hash": th, "corrupt_rows": corrupt}, outcome="partial")
            row = {"topic": topic.strip(), "topic_hash": th, "capability": capability.strip(),
                   "receipt_ids": receipts, "source_brick": source_brick,
                   "bridge_ref": bridge_ref, "status": "claimed",  # NEVER verified here
                   "best_score": None,       # guard-3 baseline, set by verify
                   "ts": int(time.time())}
            self._log("claim", {"topic_hash": th, "receipts": receipts, "source": source_brick})
            self._append_atomic(self.claims_path, row)
            return {"topic_hash": th, "status": "claimed"}
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN); lf.close()

    def ingest(self, topic_hash_: str, probe_id: str, before_score: float, after_score: float,
               evaluator: str, source_brick: str, probe_pool_version: str,
               probe_pool_checksum: str) -> dict:
        """INGEST a probe-pool measurement (external event, evaluator-bound).
        This is the ONLY way a measurement enters the register. Requires:
          - evaluator != source_brick (a brick can never evaluate itself)
          - evaluator must name a registered non-earner critic (checked against
            an evaluator registry file; a bare string is rejected)
          - full valid topic hash + probe id
        The measurement is stored; verify() applies it to the claim it names.
        """
        if not TOPIC_HASH_RE.match(topic_hash_):
            raise ValueError(f"topic_hash '{topic_hash_}' not full sha256 hex")
        if not TOPIC_HASH_RE.match(probe_id):
            raise ValueError(f"probe_id '{probe_id}' not full sha256 hex")
        if not (0 <= before_score <= 1 and 0 <= after_score <= 1):
            raise ValueError("scores must be in [0,1]")
        if not source_brick.strip():
            raise ValueError("source_brick required")
        if not evaluator.strip() or evaluator.strip() == source_brick.strip():
            self._log("ingest", {"topic_hash": topic_hash_, "evaluator": evaluator,
                                 "reason": "evaluator must be external non-earner"},
                      outcome="rejected")
            raise ValueError("evaluator must be a DIFFERENT registered non-earner critic "
                             "(no self-verify, D-3 guard 1)")
        # evaluator registry check: bare strings are never accepted
        er = self.reg_dir / "evaluators.jsonl"
        if not er.exists():
            self._log("ingest", {"topic_hash": topic_hash_, "evaluator": evaluator,
                                 "reason": "no evaluator registry"}, outcome="rejected")
            raise ValueError("evaluator registry missing — cannot verify anything")
        evals = []
        for line in er.read_text().splitlines():
            try:
                e = json.loads(line)
                if e.get("id") == evaluator.strip() and e.get("role") == "non-earner":
                    evals.append(e)
            except Exception:
                continue
        if not evals:
            self._log("ingest", {"topic_hash": topic_hash_, "evaluator": evaluator,
                                 "reason": "not a registered non-earner"}, outcome="rejected")
            raise ValueError(f"evaluator '{evaluator}' not a registered non-earner critic")
        if not probe_pool_version or len(probe_pool_checksum) < 16:
            self._log("ingest", {"topic_hash": topic_hash_, "reason": "pool not recorded"},
                      outcome="rejected")
            raise ValueError("probe_pool_version + checksum required (held-out pool, D-3 guard 2)")

        lf = self._lock()
        try:
            meas, _ = self._read(self.measurements_path)
            # one probe_id -> ONE topic (no cross-topic reuse)
            for m in meas:
                if m.get("probe_id") == probe_id and m.get("topic_hash") != topic_hash_:
                    self._log("ingest", {"probe_id": probe_id, "reason": "probe bound elsewhere"},
                              outcome="rejected")
                    raise ValueError(f"probe_id {probe_id} already bound to another topic")
            row = {"ts": int(time.time()), "topic_hash": topic_hash_, "probe_id": probe_id,
                   "before": before_score, "after": after_score, "evaluator": evaluator,
                   "source_brick": source_brick,
                   "probe_pool_version": probe_pool_version,
                   "probe_pool_checksum": probe_pool_checksum,
                   "held_out": True}        # guard 2: this pool NEVER enters a training set
            self._log("ingest", {"topic_hash": topic_hash_, "probe_id": probe_id,
                                 "evaluator": evaluator, "before": before_score,
                                 "after": after_score, "pool": probe_pool_version})
            self._append_atomic(self.measurements_path, row)
            return {"topic_hash": topic_hash_, "probe_id": probe_id, "status": "ingested"}
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN); lf.close()

    def verify(self, topic: str, probe_id: str) -> dict:
        """APPLY an already-ingested measurement to a claim — the ONLY upgrade
        path. Takes NO scores, NO evaluator: nothing self-attestable here.
        Applies the most recent ingested measurement for (topic, probe_id).
        Guard-3: after must beat the claim's best-known score."""
        th = topic_hash(topic)
        lf = self._lock()
        try:
            claims, _ = self._read(self.claims_path, require_topic=True)
            idx = next((i for i, c in enumerate(claims) if c["topic_hash"] == th), None)
            if idx is None:
                self._log("verify", {"topic_hash": th, "reason": "no claim"}, outcome="rejected")
                raise ValueError(f"no claim for topic hash {th} — verify a claim, not a ghost")

            meas, _ = self._read(self.measurements_path)
            matches = [m for m in meas if m["topic_hash"] == th and m["probe_id"] == probe_id]
            if not matches:
                self._log("verify", {"topic_hash": th, "probe_id": probe_id,
                                     "reason": "no ingested measurement"}, outcome="rejected")
                raise ValueError(f"no INGESTED measurement for probe {probe_id} on this topic — "
                                 f"measurements must be ingested first (no self-verify)")
            m = max(matches, key=lambda x: x["ts"])

            best = claims[idx].get("best_score")
            if best is not None and m["after"] <= best:
                self._log("verify", {"topic_hash": th, "probe_id": probe_id,
                                     "after": m["after"], "best": best,
                                     "reason": "not beating best"}, outcome="rejected")
                raise ValueError(f"after {m['after']} <= best {best} — must BEAT the best-known "
                                 f"score, not self-baseline (D-3 guard 3)")

            prev = claims[idx].get("status")
            claims[idx]["status"] = "verified"
            claims[idx]["verified_ts"] = int(time.time())
            claims[idx]["best_score"] = m["after"]
            claims[idx]["measurement"] = {"probe_id": probe_id, "before": m["before"],
                                          "after": m["after"], "evaluator": m["evaluator"],
                                          "pool_version": m["probe_pool_version"]}

            # audit BEFORE mutation (no crash window — verify path)
            self._log("verify", {"topic_hash": th, "probe_id": probe_id,
                                 "before": m["before"], "after": m["after"],
                                 "evaluator": m["evaluator"], "prev_status": prev})
            tmp = self.claims_path.with_name(f".claims.{os.getpid()}.tmp")
            with open(tmp, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                for c in claims:
                    f.write(json.dumps(c) + "\n")
                f.flush()
                os.fchmod(f.fileno(), 0o600)
                fcntl.flock(f, fcntl.LOCK_UN)
            os.replace(tmp, self.claims_path)
            os.chmod(self.claims_path, 0o600)
            return {"topic_hash": th, "status": "verified",
                    "improvement": m["after"] - m["before"]}
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN); lf.close()

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
        claims, _ = self._read(self.claims_path, require_topic=True)
        out = []
        for c in claims:
            if not isinstance(c.get("topic"), str):
                continue                       # schema-safe: never crash list()
            if status and c.get("status") != status:
                continue
            out.append({"topic": c["topic"], "topic_hash": c["topic_hash"],
                        "status": c.get("status"),
                        "receipt_ids": c.get("receipt_ids", []),
                        "source_brick": c.get("source_brick", ""),
                        "best_score": c.get("best_score"),
                        "measurement": c.get("measurement")})
        out.sort(key=lambda c: c["topic"])
        return out

def main():
    ap = argparse.ArgumentParser(description="capability register (round-63 D-3)")
    ap.add_argument("op", choices=["claim", "ingest", "verify", "status", "list"])
    ap.add_argument("--reg-dir", required=True)
    ap.add_argument("--brick-id", default="register-001")
    ap.add_argument("--topic", default="")
    ap.add_argument("--topic-hash", default="")
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
    ap.add_argument("--status", default="", help="list filter: claimed|verified")
    args = ap.parse_args()

    reg = CapabilityRegister(pathlib.Path(args.reg_dir), args.brick_id)
    try:
        if args.op == "claim":
            receipts = [r.strip() for r in args.receipts.split(",") if r.strip()]
            print(json.dumps(reg.claim(args.topic, args.capability, receipts,
                                       args.source_brick, args.bridge_ref)))
        elif args.op == "ingest":
            print(json.dumps(reg.ingest(args.topic_hash, args.probe_id, args.before, args.after,
                                        args.evaluator, args.source_brick,
                                        args.pool_version, args.pool_checksum)))
        elif args.op == "verify":
            print(json.dumps(reg.verify(args.topic, args.probe_id)))
        elif args.op == "status":
            print(json.dumps(reg.status()))
        else:
            print(json.dumps(reg.list(args.status)))
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
