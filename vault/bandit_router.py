#!/usr/bin/env python3
"""bandit_router.py — Bandit Router (AGI design, DA-hardened rounds 1-3).
Thompson Sampling over bot-capability arms.
Round 3 fixes (deleg_68e37e71): issue_id REQUIRED for reward (no unbounded
inflation), picks+rewards PERSISTED in HMAC'd state (no restart reset),
bandit state HMAC integrity (no silent tamper)."""
import hashlib, hmac, json, os, pathlib, random, time

class BanditRouter:
    def __init__(self, base_dir: str):
        self.base = pathlib.Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)
        self.state_file = self.base / "bandit_state.json"
        self.choice_file = self.base / "choices.jsonl"
        self.integrity_key = os.environ.get("BANDIT_INTEGRITY_KEY", "")
        self.arms = {}
        self._picks = {}      # issue_id -> arm picked
        self._rewarded = {}   # issue_id -> set of rewarded arms
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
                raise RuntimeError("bandit state integrity check failed (tampered)")
        st = data.get("state", {})
        self.arms = st.get("arms", {})
        self._picks = st.get("picks", {})
        self._rewarded = {k: set(v) for k, v in st.get("rewarded", {}).items()}

    def _save(self):
        state = {"arms": self.arms, "picks": self._picks,
                 "rewarded": {k: sorted(v) for k, v in self._rewarded.items()}}
        doc = {"state": state}
        if self.integrity_key:
            doc["_hmac"] = self._hmac(json.dumps(state, sort_keys=True))
        fd = os.open(self.state_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(doc, indent=2))

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
        # F7 (round 3): issue_id REQUIRED — empty rewards were unbounded inflation
        if not issue_id:
            raise PermissionError("reward requires a non-empty issue_id")
        if arm_id not in self.arms:
            raise KeyError(arm_id)
        # F7: reward requires this arm was picked for the issue
        if self._picks.get(issue_id) != arm_id:
            raise PermissionError("reward rejected: arm was not picked for this issue")
        # F7: dedup — each issue rewarded once per arm (persisted)
        rewarded = self._rewarded.setdefault(issue_id, set())
        if arm_id in rewarded:
            return  # already counted, no inflation
        rewarded.add(arm_id)
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
