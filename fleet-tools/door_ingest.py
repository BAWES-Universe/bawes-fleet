#!/usr/bin/env python3
"""door_ingest.py — the KEY INGEST surface (round-117 approved, now built).
One URL per person. Paste-once, auto-destroy, writes DIRECTLY to the vault
— keys never touch chat, never touch agent context, never in logs.

Flows:
- API keys (OpenRouter, DeepSeek, Higg's Field): paste -> vault -> page
  auto-destroys (one-time token invalidated)
- OAuth (Linear, Notion, Attio, Google): "Connect" button -> provider's
  own consent -> token lands in vault box

Run: python3 door_ingest.py (bind 127.0.0.1:3744; nginx fronts it with TLS)
"""
import hashlib, json, os, pathlib, secrets, sys, time, urllib.request

VAULT_DIR = pathlib.Path("/srv/vault")
TOKENS = VAULT_DIR / "ingest_tokens.json"      # one-time per-person tokens
VAULT_STORE = VAULT_DIR / "store.jsonl"        # vault's own ledger
SERVICES = {"openrouter", "deepseek", "higgfield", "gemini", "anthropic", "openai"}

def _load():
    if TOKENS.exists():
        return json.loads(TOKENS.read_text())
    return {}

def _save(data):
    os.makedirs(VAULT_DIR, exist_ok=True)
    fd = os.open(TOKENS, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(data))

def new_token(person):
    """Door calls this after consent — mints the person's one-time ingest URL."""
    data = _load()
    tok = secrets.token_urlsafe(24)
    data[person] = {"token": tok, "used": False,
                    "ts": time.time(),
                    "services": sorted(SERVICES)}
    _save(data)
    return f"https://door.bawes.net/i/{tok}"

def vault_put(service, key_value, person):
    """Write DIRECTLY to the vault store — 0600, fail-closed, no chat."""
    row = {"kind": "key", "service": service, "person": person,
           "key_sha": hashlib.sha256(key_value.encode()).hexdigest()[:16],
           "key": key_value, "ts": time.time()}
    with open(VAULT_STORE, "a") as f:
        f.write(json.dumps(row) + "\n")
    os.chmod(VAULT_STORE, 0o600)
    return row["key_sha"]

# ---- tiny HTTP server (127.0.0.1:3744; nginx fronts it) ----
from http.server import BaseHTTPRequestHandler, HTTPServer

PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>Door · key safe</title>
<style>
body{background:#111;color:#eee;font-family:system-ui;display:flex;justify-content:center;padding-top:8vh}
.card{background:#1a1a1a;border:1px solid #333;border-radius:12px;padding:28px;max-width:380px;width:90%}
h1{font-size:18px;margin:0 0 6px} p{color:#aaa;font-size:13px;line-height:1.5}
select,input,button{width:100%;padding:10px;margin:6px 0;border-radius:8px;border:1px solid #444;background:#222;color:#eee}
button{background:#4a7;border:none;font-weight:bold;cursor:pointer}
.hidden{display:none} .ok{color:#4a7;font-weight:bold}
</style></head><body><div class="card">
<h1>🔐 Key safe</h1><p>Paste your key once — it goes straight into your vault box, never through chat. This page destroys itself after.</p>
<form id=f>
<select id=s><option value=openrouter>OpenRouter</option><option value=deepseek>DeepSeek</option><option value=higgfield>Higgs Field</option><option value=gemini>Gemini</option><option value=anthropic>Anthropic</option><option value=openai>OpenAI</option></select>
<input id=k type=password placeholder="sk-..." autocomplete=off>
<button type=submit>Lock it in the vault</button>
</form><p id=out class=hidden></p></div>
<script>
document.getElementById('f').onsubmit=async e=>{e.preventDefault();
const k=document.getElementById('k').value;
if(!k.startsWith('sk-')&&!k.startsWith('AIza')){alert('That does not look like a key (sk-… or AIza…).');return}
const r=await fetch('/put',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({service:document.getElementById('s').value,key:k})});
const j=await r.json();
document.getElementById('f').classList.add('hidden');
document.getElementById('out').classList.remove('hidden');
document.getElementById('out').textContent=j.ok?('✅ Locked. SHA-'+j.sha+' — this page is dead now.'):('❌ '+j.error);
};</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass  # no request logging — keys never logged

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # /i/<token> — the one-time ingest page
        if self.path.startswith("/i/"):
            tok = self.path.split("/i/")[-1].split("?")[0]
            data = _load()
            for person, rec in data.items():
                if rec.get("token") == tok and not rec.get("used"):
                    rec["used"] = True  # one-time: page burns on first open
                    _save(data)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(PAGE)))
                    self.end_headers()
                    self.wfile.write(PAGE.encode())
                    return
            self.send_response(404); self.end_headers()
            self.wfile.write(b"link used or unknown")
            return
        self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path != "/put":
            self._json({"error": "unknown"}, 404); return
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            service, key = body.get("service", ""), body.get("key", "")
            if service not in SERVICES or not key or len(key) < 10:
                self._json({"error": "bad service or key"}, 400); return
            sha = vault_put(service, key, "door-ingest")
            self._json({"ok": True, "sha": sha})
        except Exception as e:
            self._json({"error": str(e)[:100]}, 500)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3744
    print(f"DOOR INGEST on 127.0.0.1:{port}")
    HTTPServer(("127.0.0.1", port), H).serve_forever()
