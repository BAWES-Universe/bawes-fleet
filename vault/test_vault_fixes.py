#!/usr/bin/env python3
"""test_vault_fixes.py — TDD RED for DA BLOCKER fixes (deleg_1139c439 verdict).
B1: get_raw owner check was caller-supplied string (spoofable) — now requires
    a real vault access key (relay-held secret), not a self-declared name.
B2: audit.jsonl / choices.jsonl were world-readable (0644) — now 0600."""
import json, os, pathlib, shutil, sys, tempfile, unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from vault_bot import VaultBot
from bandit_router import BanditRouter

class TestDAFixB1(unittest.TestCase):
    def setUp(self):
        os.environ["VAULTBOT_KEY"] = "ENV-KEY"
        self.dir = tempfile.mkdtemp()
        self.v = VaultBot(self.dir)

    def tearDown(self):
        os.environ.pop("VAULTBOT_KEY", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_raw_read_requires_access_key(self):
        """Spawning with agent='khalid' WITHOUT the key must be rejected."""
        self.v.store("cloudflare", "CF-TOKEN", owner="khalid")
        with self.assertRaises(PermissionError):
            self.v.get_raw("cloudflare", agent="khalid")  # no key provided

    def test_raw_read_with_key_succeeds(self):
        """The relay (holding the vault key) can read raw."""
        self.v.store("cloudflare", "CF-TOKEN", owner="khalid")
        self.assertEqual(
            self.v.get_raw("cloudflare", agent="relay", vault_key="ENV-KEY"), "CF-TOKEN")

    def test_wrong_key_rejected(self):
        self.v.store("cloudflare", "CF-TOKEN", owner="khalid")
        with self.assertRaises(PermissionError):
            self.v.get_raw("cloudflare", agent="relay", vault_key="WRONG")

class TestDAFixB2(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.v = VaultBot(self.dir)
        self.r = BanditRouter(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_audit_file_0600(self):
        self.v.store("x", "y", owner="khalid")
        self.v.access("x", agent="brick", capability="z")
        mode = stat_mode(pathlib.Path(self.dir) / "audit.jsonl")
        self.assertEqual(mode, 0o600)

    def test_choices_file_0600(self):
        self.r.register("b", ["q"])
        self.r.pick("q")
        mode = stat_mode(pathlib.Path(self.dir) / "choices.jsonl")
        self.assertEqual(mode, 0o600)

def stat_mode(p):
    return os.stat(p).st_mode & 0o777

if __name__ == "__main__":
    unittest.main(verbosity=2)
