#!/usr/bin/env python3
"""test_round3.py — TDD RED for DA round 3 findings (deleg_68e37e71).
1. F4 regression: store-overwrite must fail-closed when admin env unset
2. F5 bypass: no key_ref constant fallback — raw reads fail-closed without env
3. F8: access() requires vault key (no unauthenticated quota-burn)
4. F7: reward without issue_id rejected (no unbounded inflation)
5. F7: picks+rewards persisted across restarts
6. F3: bandit state HMAC integrity"""
import json, os, pathlib, shutil, sys, tempfile, unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from vault_bot import VaultBot
from bandit_router import BanditRouter

class TestF4_FailClosedStore(unittest.TestCase):
    def setUp(self):
        os.environ["VAULTBOT_KEY"] = "ENV-KEY"
        self.dir = tempfile.mkdtemp()
        self.v = VaultBot(self.dir)

    def tearDown(self):
        os.environ.pop("VAULTBOT_KEY", None)
        os.environ.pop("VAULTBOT_ADMIN_KEY", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_store_overwrite_fail_closed_without_admin_env(self):
        """No admin env configured = overwriting an existing service DENIED."""
        self.v.store("cloudflare", "REAL", owner="khalid")  # first store ok
        with self.assertRaises(PermissionError):
            self.v.store("cloudflare", "POISON", owner="khalid")  # no admin env

class TestF5_NoKeyRefFallback(unittest.TestCase):
    def setUp(self):
        os.environ["VAULTBOT_KEY"] = "ENV-KEY"
        self.dir = tempfile.mkdtemp()
        self.v = VaultBot(self.dir)
        self.v.store("cloudflare", "SUPER-SECRET", owner="khalid")

    def tearDown(self):
        os.environ.pop("VAULTBOT_KEY", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_raw_read_fail_closed_without_env(self):
        """Restart without VAULTBOT_KEY = all raw reads DENIED (no constant fallback)."""
        os.environ.pop("VAULTBOT_KEY", None)
        v2 = VaultBot(self.dir)
        with self.assertRaises(PermissionError):
            v2.get_raw("cloudflare", agent="relay", vault_key="env:VAULTBOT_KEY")

class TestF8_AccessAuthz(unittest.TestCase):
    def setUp(self):
        os.environ["VAULTBOT_KEY"] = "ENV-KEY"
        self.dir = tempfile.mkdtemp()
        self.v = VaultBot(self.dir)
        self.v.store("cloudflare", "CF", owner="khalid", quota=2)

    def tearDown(self):
        os.environ.pop("VAULTBOT_KEY", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_access_requires_key(self):
        """access() without the vault key is rejected (no quota-burn)."""
        with self.assertRaises(PermissionError):
            self.v.access("cloudflare", agent="attacker", capability="dns")

    def test_access_with_key_ok(self):
        self.v.access("cloudflare", agent="relay", capability="dns", vault_key="ENV-KEY")
        self.assertEqual(self.v.quota_breached("cloudflare"), False)

class TestF7_IssueIdRequired(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.r = BanditRouter(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_reward_without_issue_id_rejected(self):
        """reward() without issue_id is rejected (no unbounded inflation)."""
        self.r.register("triage-bot", ["question"])
        self.r.pick("question", issue_id="I-1")
        with self.assertRaises(PermissionError):
            self.r.reward("triage-bot", success=True, meta={})

class TestF7_PersistedAcrossRestart(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.r = BanditRouter(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_pick_and_reward_survive_restart(self):
        """Same issue cannot be re-picked+re-rewarded after a restart."""
        self.r.register("triage-bot", ["question"])
        arm = self.r.pick("question", issue_id="I-1")
        self.r.reward(arm, success=True, meta={"issue_id": "I-1"})
        alpha_after_first = self.r.stats("triage-bot")["alpha"]
        # restart — dedup state persists, no inflation
        r2 = BanditRouter(self.dir)
        r2.reward("triage-bot", success=True, meta={"issue_id": "I-1"})
        self.assertEqual(r2.stats("triage-bot")["alpha"], alpha_after_first)

class TestF3_BanditHMAC(unittest.TestCase):
    def test_tampered_bandit_state_fails_closed(self):
        """bandit_state.json tampering (alpha=999) detected at load."""
        os.environ["BANDIT_INTEGRITY_KEY"] = "BIK"
        d = tempfile.mkdtemp()
        try:
            r = BanditRouter(d)
            r.register("triage-bot", ["question"])
            r.pick("question", issue_id="I-1")
            p = pathlib.Path(d) / "bandit_state.json"
            data = json.loads(p.read_text())
            data["state"]["arms"]["triage-bot"]["alpha"] = 999
            p.write_text(json.dumps(data))
            with self.assertRaises(RuntimeError):
                BanditRouter(d)
        finally:
            os.environ.pop("BANDIT_INTEGRITY_KEY", None)
            shutil.rmtree(d, ignore_errors=True)

if __name__ == "__main__":
    unittest.main(verbosity=2)
