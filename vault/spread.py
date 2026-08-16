#!/usr/bin/env python3
"""spread.py — Failure-Spread Orchestrator (AGI design, 2026-08-16).
Failed tests spread across bricks:
1. Failure broadcast to bandit router with capability match + solve rates
2. Top-k bricks selected (UCB exploration/exploitation)
3. Pair protocol: each brick declares ONE attack workspace (no double-own)
4. All k attack the same failure as parallel hypotheses
5. First verified fix -> pair-DA hostile review -> merge
6. Winner = solver credit; losers = exploration credit (feed router priors)"""
import json, pathlib, random, time

class SpreadOrchestrator:
    def __init__(self, base_dir: str):
        self.base = pathlib.Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)
        self.state_file = self.base / "spread_state.json"
        self.state = {"bricks": {}, "failures": {}, "workspaces": {}}
        self._load()

    def _load(self):
        if self.state_file.exists():
            self.state = json.loads(self.state_file.read_text())

    def _save(self):
        self.state_file.write_text(json.dumps(self.state, indent=2))
        self.state_file.chmod(0o600)

    def register(self, brick_id: str, capabilities: list):
        self.state["bricks"].setdefault(brick_id, {
            "caps": capabilities, "solves": 0, "exploration": 0, "tries": 0})
        self._save()

    def _capability_score(self, brick, failure_text):
        score = 0
        for c in brick["caps"]:
            if c.lower() in failure_text.lower():
                score += 2
        # UCB: exploit solve rate, explore untested
        if brick["tries"] > 0:
            score += 0.5 * (brick["solves"] / brick["tries"])
        else:
            score += 0.7  # exploration bonus for untested
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
            # pair protocol: ONE workspace per solver, never double-owned
            self.state["workspaces"][f"{fid}:{bid}"] = {
                "owner": bid, "failure": fid, "status": "attacking"}
        self._save()
        return solvers

    def workspaces(self):
        return {k: v for k, v in self.state["workspaces"].items()}

    def verify_fix(self, brick_id: str, failure_id: str, passed: bool):
        f = self.state["failures"][failure_id]
        if passed and f["winner"] is None:
            f["winner"] = brick_id
            self.state["bricks"][brick_id]["solves"] += 1
            ws = self.state["workspaces"].get(f"{failure_id}:{brick_id}")
            if ws:
                ws["status"] = "fix-verified"
        self._save()

    def da_approve(self, failure_id: str, reviewer: str):
        f = self.state["failures"][failure_id]
        if f["winner"] is None:
            raise RuntimeError("no verified fix to review")
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
        """Non-winner gets exploration credit (feeds router priors)."""
        self.state["bricks"][brick_id]["exploration"] += 1
        self._save()

    def winner(self, failure_id: str):
        return self.state["failures"][failure_id].get("winner")

    def exploration(self, brick_id: str):
        return self.state["bricks"][brick_id]["exploration"]

    def solver_credit(self, brick_id: str):
        return self.state["bricks"][brick_id]["solves"]
