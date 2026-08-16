#!/usr/bin/env python3
"""spread.py — Failure-Spread Orchestrator (AGI design, DA-hardened).
Failed tests spread across bricks: bandit picks top-k by capability +
solve rate, each brick declares ONE attack workspace (pair protocol),
parallel hypotheses, first verified fix -> pair-DA hostile review ->
merge. DA hardening (deleg_38939fca): F1 register_da admin-gated,
F2 winner must be a solver, F3 state HMAC integrity."""
import hashlib, hmac, json, os, pathlib, time

class SpreadOrchestrator:
    def __init__(self, base_dir: str, integrity_key: str = ""):
        self.base = pathlib.Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)
        self.state_file = self.base / "spread_state.json"
        self.integrity_key = integrity_key or os.environ.get("SPREAD_INTEGRITY_KEY", "")
        self.state = {"bricks": {}, "failures": {}, "workspaces": {}, "da_keys": {}}
        self._load()

    def _hmac(self, payload: str) -> str:
        return hmac.new(self.integrity_key.encode(), payload.encode(), hashlib.sha256).hexdigest()

    def _load(self):
        if not self.state_file.exists():
            return
        raw = self.state_file.read_text()
        data = json.loads(raw)
        if self.integrity_key:
            if data.get("_hmac") != self._hmac(json.dumps(data.get("state", {}), sort_keys=True)):
                raise RuntimeError("spread state integrity check failed (tampered)")
        self.state = data.get("state", self.state)

    def _save(self):
        doc = {"state": self.state}
        if self.integrity_key:
            doc["_hmac"] = self._hmac(json.dumps(self.state, sort_keys=True))
        fd = os.open(self.state_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(doc, indent=2))

    def register_da(self, reviewer_id: str, da_key: str, admin_key: str = ""):
        """F1: DA keys are minted ONLY by the relay admin — caller-asserted
        reviewer identity is no longer proof of anything. Fail-closed: no
        configured admin key = deny all registrations."""
        expected = os.environ.get("SPREAD_ADMIN_KEY", "")
        if not expected or admin_key != expected:
            raise PermissionError("DA registration requires the admin key (relay only)")
        if reviewer_id in self.state["da_keys"]:
            raise PermissionError("DA key already registered — rotation requires admin ceremony")
        self.state["da_keys"][reviewer_id] = da_key
        self._save()

    def register(self, brick_id: str, capabilities: list):
        self.state["bricks"].setdefault(brick_id, {
            "caps": capabilities, "solves": 0, "exploration": 0, "tries": 0})
        self._save()

    def _capability_score(self, brick, failure_text):
        score = 0
        for c in brick["caps"]:
            if c.lower() in failure_text.lower():
                score += 2
        if brick["tries"] > 0:
            score += 0.5 * (brick["solves"] / brick["tries"])
        else:
            score += 0.7
        return score

    def spread(self, failure_text: str, k: int = 2) -> list:
        fid = f"failure-{len(self.state['failures']) + 1}"
        ranked = sorted(self.state["bricks"].items(),
                        key=lambda kv: -self._capability_score(kv[1], failure_text))
        solvers = [bid for bid, _ in ranked[:k]]
        self.state["failures"][fid] = {
            "text": failure_text, "solvers": solvers, "winner": None,
            "da_approved": False, "merged": False, "ts": time.time()}
        for bid in solvers:
            self.state["bricks"][bid]["tries"] += 1
            self.state["workspaces"][f"{fid}:{bid}"] = {
                "owner": bid, "failure": fid, "status": "attacking"}
        self._save()
        return solvers

    def workspaces(self):
        return {k: v for k, v in self.state["workspaces"].items()}

    def verify_fix(self, brick_id: str, failure_id: str, passed: bool):
        f = self.state["failures"][failure_id]
        # F2: only a PICKED SOLVER can claim the win
        if brick_id not in f["solvers"]:
            raise PermissionError("only a picked solver can verify a fix")
        ws = self.state["workspaces"].get(f"{failure_id}:{brick_id}")
        if passed and f["winner"] is None:
            f["winner"] = brick_id
            self.state["bricks"][brick_id]["solves"] += 1
            if ws:
                ws["status"] = "fix-verified"
        self._save()

    def da_approve(self, failure_id: str, reviewer: str, da_key: str = ""):
        f = self.state["failures"][failure_id]
        if f["winner"] is None:
            raise RuntimeError("no verified fix to review")
        if not da_key or self.state["da_keys"].get(reviewer) != da_key:
            raise PermissionError("DA approval requires the registered reviewer key")
        f["da_approved"] = True
        f["da_reviewer"] = reviewer
        self._save()

    def merge(self, failure_id: str):
        f = self.state["failures"][failure_id]
        if not f["da_approved"]:
            raise RuntimeError("DA review required before merge")
        f["merged"] = True
        self._save()

    def exploration_credit(self, brick_id: str, failure_id: str):
        self.state["bricks"][brick_id]["exploration"] += 1
        self._save()

    def winner(self, failure_id: str):
        return self.state["failures"][failure_id].get("winner")

    def exploration(self, brick_id: str):
        return self.state["bricks"][brick_id]["exploration"]

    def solver_credit(self, brick_id: str):
        return self.state["bricks"][brick_id]["solves"]
