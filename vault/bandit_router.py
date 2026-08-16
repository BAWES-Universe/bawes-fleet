#!/usr/bin/env python3
"""bandit_router.py — Bandit Router (AGI-designed, 2026-08-16).
Thompson Sampling over bot-capability arms:
- Arm = bot tagged by capability embeddings
- Reward = 1 if issue resolved + user ack, 0 if escalated/timeout
- Hidden state = per-bot success counts (alpha/beta)
- Forced exploration for new/untested pairs, UCB-style for mature arms
- Stale stats decay weekly. All choices logged. No secrets in rewards."""
import json, pathlib, random, time

class BanditRouter:
    def __init__(self, base_dir: str):
        self.base = pathlib.Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)
        self.state_file = self.base / "bandit_state.json"
        self.choice_file = self.base / "choices.jsonl"
        self.arms = {}   # arm_id -> {"caps": [...], "alpha": 1, "beta": 1, "last_seen": ts}
        self._load()

    def _load(self):
        if self.state_file.exists():
            d = json.loads(self.state_file.read_text())
            self.arms = d.get("arms", {})

    def _save(self):
        self.state_file.write_text(json.dumps({"arms": self.arms}, indent=2))
        self.state_file.chmod(0o600)

    def register(self, arm_id: str, capabilities: list):
        if arm_id not in self.arms:
            self.arms[arm_id] = {"caps": capabilities, "alpha": 1, "beta": 1,
                                 "last_seen": time.time()}
        self._save()

    def _decay_stale(self):
        """Weekly decay: halve counts for arms unseen in 7 days."""
        now = time.time()
        for arm in self.arms.values():
            if now - arm["last_seen"] > 7 * 86400:
                arm["alpha"] = 1 + (arm["alpha"] - 1) / 2
                arm["beta"] = 1 + (arm["beta"] - 1) / 2
                arm["last_seen"] = now
        self._save()

    def _candidates(self, need: str):
        self._decay_stale()
        matched = [aid for aid, a in self.arms.items() if need in a["caps"]]
        return matched or list(self.arms.keys())

    def pick(self, need: str) -> str:
        cands = self._candidates(need)
        # Thompson: sample from Beta(alpha, beta), explore untested with noise
        best, best_score = None, -1
        for aid in cands:
            a = self.arms[aid]
            score = random.betavariate(a["alpha"], a["beta"])
            if (a["alpha"] + a["beta"]) <= 2:  # untested: explore
                score += random.random() * 0.2
            if score > best_score:
                best, best_score = aid, score
        self._log({"ts": time.time(), "need": need, "picked": best, "score": round(best_score, 4)})
        self.arms[best]["last_seen"] = time.time()
        self._save()
        return best

    def reward(self, arm_id: str, success: bool, meta: dict = None):
        if arm_id not in self.arms:
            return
        a = self.arms[arm_id]
        if success:
            a["alpha"] += 1
        else:
            a["beta"] += 1
        # WHITELIST only safe fields — never persist arbitrary caller meta
        safe = {}
        if meta:
            for k in ("issue_id", "lane"):
                if k in meta:
                    safe[k] = meta[k]
        self._log({"ts": time.time(), "arm": arm_id, "reward": 1 if success else 0,
                   "meta": safe})
        self._save()

    def stats(self, arm_id: str):
        a = self.arms[arm_id]
        return {"alpha": a["alpha"], "beta": a["beta"]}

    def choices(self):
        rows = []
        if self.choice_file.exists():
            for line in self.choice_file.read_text().splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def _log(self, row):
        with open(self.choice_file, "a") as f:
            f.write(json.dumps(row) + "\n")
        # DA FIX B2: choice/audit trail must not be world-readable
        self.choice_file.chmod(0o600)
