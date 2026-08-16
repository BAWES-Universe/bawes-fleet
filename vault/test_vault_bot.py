#!/usr/bin/env python3
"""test_vault_bot.py — TDD RED for the Vault Bot (consensus @4b1d315 + AGI bandit design).
The vault holds ALL khalid's PATs (Cloudflare, GoDaddy, Vercel, Supabase, GitHub):
- Scoped access: agent calls with a capability, never sees the raw PAT
- Audit log: every access recorded (who, what, when)
- Quota: per-PAT usage caps + anomaly alert flag
- No agent ever reads the raw secret through the API
"""
import json, os, pathlib, shutil, sys, tempfile, unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from vault_bot import VaultBot

class TestVaultBot(unittest.TestCase):
    def setUp(self):
        os.environ["VAULTBOT_KEY"] = "ENV-KEY"
        self.dir = tempfile.mkdtemp()
        self.v = VaultBot(self.dir)

    def tearDown(self):
        os.environ.pop("VAULTBOT_KEY", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_store_secret_scoped(self):
        """Agent stores a PAT under a service; never retrievable raw."""
        self.v.store("cloudflare", "CF-TOKEN-123", owner="khalid")
        self.assertEqual(self.v.has("cloudflare"), True)

    def test_agent_cannot_read_raw(self):
        """The API never returns the raw token to an agent."""
        self.v.store("vercel", "VCTOKEN-abc", owner="khalid")
        with self.assertRaises(PermissionError):
            self.v.get_raw("vercel", agent="brick")

    def test_owner_can_read_raw(self):
        """Only the owner (khalid) with the vault key can retrieve raw tokens."""
        os.environ["VAULTBOT_KEY"] = "ENV-KEY"
        try:
            self.v = VaultBot(self.dir)
            self.v.store("github", "ghp_rawsecret", owner="khalid")
            self.assertEqual(self.v.get_raw("github", agent="khalid", vault_key="ENV-KEY"), "ghp_rawsecret")
        finally:
            os.environ.pop("VAULTBOT_KEY", None)

    def test_audit_log_written(self):
        """Every store and access is audit-logged."""
        self.v.store("supabase", "sb-secret", owner="khalid")
        self.v.access("supabase", agent="agi", capability="read-distilled", vault_key="ENV-KEY")
        rows = self.v.audit()
        self.assertGreaterEqual(len(rows), 2)

    def test_quota_tracking(self):
        """Per-PAT usage counts; quota breach flags an alert."""
        self.v.store("cloudflare", "CF-TOKEN", owner="khalid", quota=2)
        self.v.access("cloudflare", agent="brick", capability="dns", vault_key="ENV-KEY")
        self.v.access("cloudflare", agent="brick", capability="dns", vault_key="ENV-KEY")
        self.v.access("cloudflare", agent="brick", capability="dns", vault_key="ENV-KEY")  # breach
        self.assertEqual(self.v.quota_breached("cloudflare"), True)

    def test_no_raw_in_audit(self):
        """Audit rows never contain the raw secret."""
        self.v.store("cloudflare", "RAW-SECRET-987", owner="khalid")
        self.v.access("cloudflare", agent="brick", capability="dns", vault_key="ENV-KEY")
        for row in self.v.audit():
            self.assertNotIn("RAW-SECRET-987", json.dumps(row))

    def test_unknown_service_fails_closed(self):
        """Unknown service access is denied, not ignored."""
        with self.assertRaises(KeyError):
            self.v.access("nonexistent", agent="brick", capability="x")

if __name__ == "__main__":
    unittest.main(verbosity=2)
