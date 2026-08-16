import json, os, pathlib, shutil, tempfile, time, unittest, sys
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

class TestDoorV41Fixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ["BRICK_DISCORD_TOKEN"] = "x"
        os.environ["DOOR_VAULT_DIR"] = cls.tmp
        import importlib.util
        spec = importlib.util.spec_from_file_location("door_v4", str(HERE / "door_v4.py"))
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)
        cls.m.STATE_DIR = pathlib.Path(cls.tmp)
        cls.m.FLOW = cls.m.STATE_DIR / "flow.jsonl"
        cls.m.PROFILES = cls.m.STATE_DIR / "profiles.json"
        cls.m.TRANSCRIPT = cls.m.STATE_DIR / "consent-transcripts.jsonl"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_da3_rejoin_no_corruption(self):
        m = self.m
        uid = "friend-001"
        r1 = m.handle_dm(uid, "hoostralie", "__JOIN__", time.time())
        self.assertIsNotNone(r1, "first join must trigger welcome")
        m.handle_dm(uid, "hoostralie", "I make music and want help promoting it", time.time())
        goal = m.load_profiles()[uid].get("goal")
        self.assertNotIn("__JOIN__", goal, "goal must be the real answer")
        # second join event (rejoin/cross-guild) must NOT overwrite
        r2 = m.handle_dm(uid, "hoostralie", "__JOIN__", time.time())
        self.assertIsNone(r2, "rejoin must send NO DM (dedup)")
        self.assertEqual(m.load_profiles()[uid].get("goal"), goal,
                         "rejoin must not clobber the goal")

    def test_da5_transcript_0600(self):
        m = self.m
        uid = "pii-001"
        m.handle_dm(uid, "p", "__JOIN__", time.time())
        m.handle_dm(uid, "p", "goal is x", time.time())   # -> building
        m.handle_dm(uid, "p", "skills a, b", time.time()) # -> confirming
        m.handle_dm(uid, "p", "yes", time.time())         # -> consented + spawn
        mode = os.stat(m.TRANSCRIPT).st_mode & 0o777
        self.assertEqual(mode, 0o600, "consent transcript must be 0600")
        sp = m.STATE_DIR / "brick-spawns.jsonl"
        if sp.exists():
            self.assertEqual(os.stat(sp).st_mode & 0o777, 0o600,
                             "spawn log must be 0600")

    def test_rebel_consent_before_pitch_stage(self):
        # the 'new' prompt must ask consent, not promise earnings
        import re
        src = open(HERE / "door_v4.py").read()
        self.assertNotIn("works for you and earns with you", src,
                         "earning promise must be gone")
        self.assertIn("ask consent, plainly", src,
                      "first contact must ask consent")

    def test_dedup_second_join_silent(self):
        m = self.m
        uid = "dup-001"
        r1 = m.handle_dm(uid, "d", "__JOIN__", time.time())
        self.assertIsNotNone(r1)
        r2 = m.handle_dm(uid, "d", "__JOIN__", time.time())
        self.assertIsNone(r2, "dedup: 1 join -> 1 DM")

if __name__ == "__main__":
    unittest.main()
