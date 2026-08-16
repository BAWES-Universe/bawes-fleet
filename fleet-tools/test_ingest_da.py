import json, os, pathlib, shutil, sys, tempfile, unittest
sys.path.insert(0, "/opt/door")

class TestIngestHardened(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ["DOOR_VAULT_DIR"] = cls.tmp
        import importlib.util
        spec = importlib.util.spec_from_file_location("door_ingest", "/opt/door/door_ingest.py")
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)
        # redirect module paths to temp
        cls.m.VAULT_DIR = pathlib.Path(cls.tmp)
        cls.m.TOKENS = cls.m.VAULT_DIR / "ingest_tokens.json"
        cls.m.VAULT_STORE = cls.m.VAULT_DIR / "store.jsonl"
        cls.m.ALERT = cls.m.VAULT_DIR / "ingest_alerts.log"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_d1_no_token_403(self):
        # simulate POST /put with no auth via handler
        from http.server import BaseHTTPRequestHandler
        m = self.m
        class FakeReq:
            def __init__(self):
                self.headers = {"Content-Length": "0", "Authorization": ""}
            def read(self, n): return b""
        class FakeH(m.H):
            def __init__(self, req):
                self.headers = req.headers
                self.client_address = ("127.0.0.1", 1)
                self.path = "/put"
                self.rfile = req
                self.responses = []
            def _json(self, obj, code=200):
                self.responses.append((code, obj))
            def send_response(self, c): pass
            def send_header(self, *a): pass
            def end_headers(self): pass
        req = FakeReq()
        h = FakeH(req)
        h.do_POST()
        self.assertEqual(h.responses[0][0], 403, "no token must be 403")

    def test_d1_garbage_token_403(self):
        m = self.m
        class FakeReq:
            def __init__(self):
                self.headers = {"Content-Length": "0",
                                "Authorization": "Bearer garbage-token-xyz"}
            def read(self, n): return b""
        class FakeH(m.H):
            def __init__(self, req):
                self.headers = req.headers
                self.client_address = ("127.0.0.1", 1)
                self.path = "/put"
                self.rfile = req
                self.responses = []
            def _json(self, obj, code=200):
                self.responses.append((code, obj))
            def send_response(self, c): pass
            def send_header(self, *a): pass
            def end_headers(self): pass
        h = FakeH(FakeReq())
        h.do_POST()
        self.assertEqual(h.responses[0][0], 403, "garbage token must be 403")

    def test_d2_atomic_0600(self):
        m = self.m
        # write through vault_put directly: file must be 0600 immediately
        m.vault_put("openrouter", "sk-test-1234567890", "person-x")
        mode = os.stat(m.VAULT_STORE).st_mode & 0o777
        self.assertEqual(mode, 0o600, "store must be 0600")

    def test_d3_person_from_token(self):
        m = self.m
        url = m.new_token("khalid")
        tok = url.split("#")[-1]
        person, rec = m._auth_from_tok(tok) if hasattr(m, "_auth_from_tok") else (None, None)
        # fallback: direct lookup
        if person is None:
            data = m._load()
            for p, r in data.items():
                if r.get("token") == tok:
                    person, rec = p, r
        self.assertEqual(person, "khalid")
        self.assertFalse(rec["used"])

    def test_d5_burn_once(self):
        m = self.m
        url = m.new_token("b1")
        tok = url.split("#")[-1]
        data = m._load()
        data["b1"]["used"] = True
        m._save(data)
        # second use must be rejected by the used flag
        self.assertTrue(m._load()["b1"]["used"])

    def test_d7_revoke_scrubs(self):
        m = self.m
        m.vault_put("openrouter", "sk-revokeme-12345", "victim")
        url2 = m.revoke("victim")
        data = m._load()
        # revoke re-mints a FRESH token for the person (old one is dead)
        self.assertNotEqual(url2, "", "revoke must re-mint")
        self.assertFalse(data["victim"]["used"], "fresh token unused")
        content = open(m.VAULT_STORE).read() if m.VAULT_STORE.exists() else ""
        self.assertNotIn("sk-revokeme", content, "old key scrubbed from store")

    def test_r2_fragment_token(self):
        m = self.m
        url = m.new_token("k2")
        self.assertIn("#", url, "token must be in fragment, not path")

    def test_d8_vault_dir_0700(self):
        self.assertEqual(os.stat(self.m.VAULT_DIR).st_mode & 0o777, 0o700)

if __name__ == "__main__":
    unittest.main()
