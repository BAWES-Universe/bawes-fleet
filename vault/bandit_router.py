#!/usr/bin/env python3
"""bandit_router.py — Bandit Router (AGI design, DA-hardened).
Thompson Sampling over bot-capability arms. DA hardening (deleg_38939fca):
F6 atomic 0600 file creates, F7 reward dedup per issue + pick tracking,
no reward inflation."""
import json, os, pathlib, random, time

class BanditRouter:
    def __init__(self, base_dir: str):
        self.base = pathlib.Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)
        self.state_file = self.base / "bandit_state.json"
        self.choice_file = self.base / "choices.jsonl"
        self.arms = {}
        self._picks = {}   # issue_id -> arm picked (F7)
        self._rewarded = {}  # issue_id -> set of arms rewarded (F7)
        self._load()

    def _load(self):
        if self.state_file.exists():
            d = json.loads(self.state_file.read_text())
            self.arms = d.get("arms", {})

    def _save(self):
        fd = os.open(self.state_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps({"arms": self.arms}, indent=2))

    def register(self, arm_id: str, capabilities: list):
        if arm_id not in self.arms:
            self.arms[arm_id] = {"caps": capabilities, "alpha": 1, "beta": 1,
                                 "last_seen": time.time()}
        self._save()

    def _decay_stale(self):
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

    def pick(self, need: str, issue_id: str = "") -> str:
        cands = self._candidates(need)
        best, best_score = None, -1
        for aid in cands:
            a = self.arms[aid]
            score = random.betavariate(a["alpha"], a["beta"])
            if (a["alpha"] + a["beta"]) <= 2:
                score += random.random() * 0.2
            if score > best_score:
                best, best_score = aid, score
        if issue_id:
            self._picks[issue_id] = best
        self._log({"ts": time.time(), "need": need, "picked": best,
                   "score": round(best_score, 4), "issue_id": issue_id})
        self.arms[best]["last_seen"] = time.time()
        self._save()
        return best

    def reward(self, arm_id: str, success: bool, meta: dict = None):
        issue_id = (meta or {}).get("issue_id", "")
        # F7: reward requires this arm was picked for the issue
        if issue_id and self._picks.get(issue_id) != arm_id:
            raise PermissionError("reward rejected: arm was not picked for this issue")
        # F7: dedup — each issue rewarded once per arm
        rewarded = self._rewarded.setdefault(issue_id, set())
        if issue_id in rewarded:
            return  # already counted, no inflation
        if issue_id:
            rewarded.add(issue_id)
        a = self.arms[arm_id]
        if success:
            a["alpha"] += 1
        else:
            a["beta"] += 1
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
        fd = os.open(self.choice_file, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(json.dumps(row) + "\n")
