#!/usr/bin/env python3
"""test_modules_da.py — TDD RED for DA round (deleg_530b2bab, 9 findings).
Runs against a throwaway temp base with a test HMAC key — never touches /srv."""
import json, os, pathlib, shutil, sys, tempfile, unittest

sys.path.insert(0, "/opt/modules")
os.environ["MODULES_HMAC_KEY"] = "TEST-KEY"

import modules

class TestDACritical(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        os.environ["MODULES_BASE"] = self.base
        modules.BASE = pathlib.Path(self.base)
        modules.STATE = modules.BASE / "module_state.json"
        modules.LEDGER = modules.BASE / "wallet.jsonl"

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_f1_ghost_signer_rejected(self):
        modules.complete("b1", 1)
        modules.verify("b1", 1, "ghost-nonearner")
        rows = modules._ledger_rows()
        self.assertFalse(any(r.get("kind") == "module-complete" for r in rows))

    def test_f1_case_insensitive_selfsign_dead(self):
        modules.complete("B1", 1)
        modules.verify("B1", 1, "b1")
        rows = modules._ledger_rows()
        self.assertFalse(any(r.get("kind") == "module-complete" for r in rows))

    def test_f2_mint_not_importable(self):
        with self.assertRaises(AttributeError):
            modules.mint("x", 1, "anyone")

    def test_f3_negative_index_dead(self):
        modules.complete("b1", -1)
        rows = modules._ledger_rows()
        self.assertFalse(any(r.get("kind") == "module-complete" for r in rows))

    def test_f3_zero_wrap_dead(self):
        modules.complete("b1", 0)
        rows = modules._ledger_rows()
        self.assertFalse(any(r.get("kind") == "module-complete" for r in rows))

    def test_f4_tamper_fails_closed(self):
        modules.complete("b1", 1)
        raw = modules.STATE.read_text()
        payload, _ = raw.rsplit("|", 1)
        data = json.loads(payload)
        data["b1"] = {"pending": 5}
        # rewrite with WRONG key -> signature mismatch on load
        modules.STATE.write_text(json.dumps(data) + "|deadbeef")
        with self.assertRaises(RuntimeError):
            modules.load()

    def test_f5_ladder_from_ledger(self):
        # skip modules 1..2 via state forge: ledger has nothing, so verify must fail
        st = modules.load()
        st["b1"] = {"pending": 3}
        modules.save(st)
        modules.verify("b1", 3, "security-001")
        rows = modules._ledger_rows()
        self.assertFalse(any(r.get("kind") == "module-complete" for r in rows))

    def test_f6_no_double_mint(self):
        modules.complete("b1", 1)
        modules.verify("b1", 1, "security-001")
        modules.complete("b1", 1)
        rows = modules._ledger_rows()
        cards = [r["card_id"] for r in rows if r.get("kind") == "module-complete"]
        self.assertEqual(cards.count("module-1"), 1)

    def test_f7_module6_needs_14(self):
        modules.complete("b1", 6)  # can't even queue: ladder empty
        st = modules.load()
        st["b1"] = {"pending": 6}
        modules.save(st)
        modules.verify("b1", 6, "security-001")
        rows = modules._ledger_rows()
        self.assertFalse(any(r.get("kind") == "module-complete" for r in rows))

    def test_f8_ledger_0600(self):
        modules.complete("b1", 1)
        modules.verify("b1", 1, "security-001")
        mode = os.stat(modules.LEDGER).st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_f9_out_of_range(self):
        modules.complete("b1", 7)  # must not crash
        modules.verify("b1", 7, "security-001")

    def test_happy_path_still_works(self):
        modules.complete("b1", 1)
        modules.verify("b1", 1, "security-001")
        rows = modules._ledger_rows()
        self.assertTrue(any(r.get("kind") == "module-complete"
                            and r.get("signer") == "security-001" for r in rows))


if __name__ == "__main__":
    unittest.main()
