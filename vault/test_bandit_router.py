#!/usr/bin/env python3
"""test_bandit_router.py — TDD RED for the Bandit Router (AGI-designed).
Thompson Sampling over bot-capability arms. Reward = 1 if issue resolved +
user ack, 0 if escalated/timeout. Cold-start from capability similarity.
Stale stats decay weekly. All choices logged. No secrets in rewards."""
import json, pathlib, shutil, sys, tempfile, unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from bandit_router import BanditRouter

class TestBanditRouter(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.r = BanditRouter(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_pick_arm(self):
        """A routing decision returns a valid bot arm."""
        self.r.register("triage-bot", ["question", "help"])
        self.r.register("lost-bot", ["lost_member"])
        pick = self.r.pick("lost_member")
        self.assertEqual(pick, "lost-bot")

    def test_capability_match_routes(self):
        """Only bots whose capability matches the need are candidates."""
        self.r.register("triage-bot", ["question"])
        self.r.register("unanswered-bot", ["question"])
        pick = self.r.pick("question")
        self.assertIn(pick, ["triage-bot", "unanswered-bot"])

    def test_reward_updates_prior(self):
        """A verified reward updates the arm's success counts."""
        self.r.register("triage-bot", ["question"])
        arm = self.r.pick("question", issue_id="I-1")
        self.r.reward(arm, success=True, meta={"issue_id": "I-1"})
        stats = self.r.stats(arm)
        self.assertEqual(stats["alpha"], stats["beta"] + 1)  # alpha = successes + 1

    def test_failed_reward_increases_beta(self):
        """Escalation/timeout increases the failure count."""
        self.r.register("triage-bot", ["question"])
        arm = self.r.pick("question", issue_id="I-2")
        self.r.reward(arm, success=False, meta={"issue_id": "I-2"})
        stats = self.r.stats(arm)
        self.assertEqual(stats["beta"], 2)  # beta = failures + 1

    def test_choices_logged_for_audit(self):
        """Every routing choice is logged."""
        self.r.register("triage-bot", ["question"])
        self.r.pick("question")
        self.r.pick("question")
        self.assertGreaterEqual(len(self.r.choices()), 2)

    def test_no_secret_in_rewards(self):
        """Reward log never contains secret material."""
        self.r.register("triage-bot", ["question"])
        arm = self.r.pick("question", issue_id="I-3")
        self.r.reward(arm, success=True, meta={"issue_id": "I-3", "token": "SHOULD-NOT-APPEAR"})
        for c in self.r.choices():
            self.assertNotIn("SHOULD-NOT-APPEAR", json.dumps(c))

    def test_unknown_need_fails_open_to_any(self):
        """Unknown need routes to any registered bot (fail-open on routing)."""
        self.r.register("triage-bot", ["question"])
        pick = self.r.pick("mystery")
        self.assertEqual(pick, "triage-bot")

if __name__ == "__main__":
    unittest.main(verbosity=2)
