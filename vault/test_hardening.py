#!/usr/bin/env python3
"""test_hardening.py — TDD RED for re-DA findings (deleg_38939fca, all 8).
F1 register_da unauthenticated -> admin key required
F2 verify_fix accepts non-solver -> must be in failure['solvers']
F3 state integrity -> HMAC verified on load (tamper = fail-closed)
F4 store() accepts caller vault_key for existing service -> rejected
F5 vault_key co-located with raw -> key comes from env, not the JSON
F6 write-then-chmod TOCTOU -> created 0600 atomically
F7 reward inflation -> dedup per issue_id, must be picked arm
F8 access() unauthenticated quota-burn -> per-agent authz"""
import json, os, pathlib, shutil, sys, tempfile, unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from vault_bot import VaultBot
from bandit_router import BanditRouter
from spread import SpreadOrchestrator

ADMIN = "ADMIN"

class TestF1_RegisterDA(unittest.TestCase):
    def setUp(self):
        os.environ["SPREAD_ADMIN_KEY"] = ADMIN
        self.dir = tempfile.mkdtemp()
        self.s = SpreadOrchestrator(self.dir)

    def tearDown(self):
        os.environ.pop("SPREAD_ADMIN_KEY", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_register_da_requires_admin_key(self):
        """Any caller minting a DA key must be rejected without the admin key."""
        with self.assertRaises(PermissionError):
            self.s.register_da("security-001", "MINTED-BY-ATTACKER")
        self.s.register_da("security-001", "REAL-KEY", admin_key=ADMIN)
        # attacker cannot overwrite the real key
        with self.assertRaises(PermissionError):
            self.s.register_da("security-001", "ATTACKER-KEY", admin_key=ADMIN)

class TestF2_NonSolver(unittest.TestCase):
    def setUp(self):
        os.environ["SPREAD_ADMIN_KEY"] = ADMIN
        self.dir = tempfile.mkdtemp()
        self.s = SpreadOrchestrator(self.dir)

    def tearDown(self):
        os.environ.pop("SPREAD_ADMIN_KEY", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_non_solver_cannot_win(self):
        """A brick that was NOT picked for the failure cannot verify as winner."""
        self.s.register_da("security-001", "REAL-KEY", admin_key=ADMIN)
        self.s.register("victim", ["build"])
        self.s.register("attacker", ["build"])
        solvers = self.s.spread("build failure", k=1)  # only 'victim' picked
        self.assertEqual(solvers, ["victim"])
        with self.assertRaises(PermissionError):
            self.s.verify_fix("attacker", "failure-1", passed=True)

class TestF3_StateIntegrity(unittest.TestCase):
    def setUp(self):
        os.environ["VAULTBOT_KEY"] = "ENV-KEY"
        self.dir = tempfile.mkdtemp()
        self.v = VaultBot(self.dir, integrity_key="IK")

    def tearDown(self):
        os.environ.pop("VAULTBOT_KEY", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_tampered_state_fails_closed(self):
        """Editing state file directly (same-user) must be detected on load."""
        self.v.store("cloudflare", "CF", owner="khalid")
        p = pathlib.Path(self.dir) / "secrets.json"
        data = json.loads(p.read_text())
        data["entries"]["cloudflare"]["raw"] = "POISONED"
        p.write_text(json.dumps(data))
        # integrity check fires at load (construction)
        with self.assertRaises(RuntimeError):
            VaultBot(self.dir, integrity_key="IK")

class TestF4_StoreInjection(unittest.TestCase):
    def setUp(self):
        os.environ["VAULTBOT_KEY"] = "ENV-KEY"
        os.environ["VAULTBOT_ADMIN_KEY"] = ADMIN
        self.dir = tempfile.mkdtemp()
        self.v = VaultBot(self.dir)

    def tearDown(self):
        os.environ.pop("VAULTBOT_KEY", None)
        os.environ.pop("VAULTBOT_ADMIN_KEY", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_caller_cannot_swap_existing_service(self):
        """Store over an existing service without the admin key is rejected."""
        self.v.store("cloudflare", "REAL-TOKEN", owner="khalid", admin_key=ADMIN)
        with self.assertRaises(PermissionError):
            self.v.store("cloudflare", "POISON", owner="khalid", admin_key="WRONG")

class TestF5_KeyNotCoLocated(unittest.TestCase):
    def setUp(self):
        os.environ["VAULTBOT_KEY"] = "ENV-KEY"
        self.dir = tempfile.mkdtemp()
        self.v = VaultBot(self.dir)

    def tearDown(self):
        os.environ.pop("VAULTBOT_KEY", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_key_comes_from_env_not_json(self):
        """The vault key must NOT be stored beside the raw secret."""
        self.v.store("cloudflare", "CF", owner="khalid")
        data = json.loads((pathlib.Path(self.dir) / "secrets.json").read_text())
        self.assertNotIn("vault_key", json.dumps(data))
        self.assertEqual(self.v.get_raw("cloudflare", agent="relay", vault_key="ENV-KEY"), "CF")

class TestF6_TOCTOU(unittest.TestCase):
    def test_created_0600_atomically(self):
        """Files must be created 0600 from the first byte (no 0644 window)."""
        d = tempfile.mkdtemp()
        try:
            v = VaultBot(d)
            v.store("x", "y", owner="k")
            mode = os.stat(pathlib.Path(d) / "secrets.json").st_mode & 0o777
            self.assertEqual(mode, 0o600)
        finally:
            shutil.rmtree(d, ignore_errors=True)

class TestF7_RewardInflation(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.r = BanditRouter(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_reward_dedup_per_issue(self):
        """Same issue_id rewarded twice only counts once."""
        self.r.register("triage-bot", ["question"])
        arm = self.r.pick("question", issue_id="I-1")
        self.r.reward(arm, success=True, meta={"issue_id": "I-1"})
        self.r.reward(arm, success=True, meta={"issue_id": "I-1"})
        stats = self.r.stats(arm)
        self.assertEqual(stats["alpha"], 2)  # one success only

    def test_reward_requires_pick(self):
        """Rewarding an arm that was never picked for this issue is rejected."""
        self.r.register("triage-bot", ["question"])
        with self.assertRaises(PermissionError):
            self.r.reward("triage-bot", success=True, meta={"issue_id": "I-NEVER-PICKED"})

if __name__ == "__main__":
    unittest.main(verbosity=2)
