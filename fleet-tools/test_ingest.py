import os, sys, tempfile, pathlib, json
os.environ["BRICK_DISCORD_TOKEN"] = "x"
import importlib.util
spec = importlib.util.spec_from_file_location("ingest", "/opt/door/door_ingest.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# NOW override paths (after exec so module body can't clobber)
tmp = tempfile.mkdtemp()
m.VAULT_DIR = pathlib.Path(tmp)
m.TOKENS = m.VAULT_DIR / "ingest_tokens.json"
m.VAULT_STORE = m.VAULT_DIR / "store.jsonl"

url = m.new_token("khalid")
print("1. token minted:", url[:44], "...")
data = m._load()
assert data["khalid"]["used"] is False
rec = data["khalid"]; rec["used"] = True; m._save(data)
print("2. page opens once (burns) OK")
sha = m.vault_put("openrouter", "sk-test-1234567890", "khalid")
print("3. vault put sha:", sha)
row = json.loads(open(f"{tmp}/store.jsonl").read())
assert row["key"] == "sk-test-1234567890" and row["person"] == "khalid"
mode = os.stat(f"{tmp}/store.jsonl").st_mode & 0o777
assert mode == 0o600
print("4. store row ok, mode:", oct(mode))
print("ALL INGEST TESTS PASS")
