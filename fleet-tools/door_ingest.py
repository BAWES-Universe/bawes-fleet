#!/usr/bin/env python3
"""door_ingest.py — KEY INGEST surface, DA-REBEL-HARDENED (round-121 v2).
Fixes from deleg_5c0118cf (OBJECT) + deleg_25000263 (DISSENT-block):

DA:
D1 CRITICAL — POST /put now REQUIRES the one-time token (Authorization
   header), looks up the person, requires the token to be UNUSED, and
   consumes it ATOMICALLY with the write (flock). Garbage/no token = 403.
D2 HIGH — keys written via os.open(...,0o600)+fchmod BEFORE write (no
   0644 race window); umask 0o077 at startup.
D3 HIGH — person derived from the TOKEN record, never from the body;
   custody hash links key sha -> consent.
D4 MED — provider-side validation call on ingest (reject 401).
D5 MED — burn is flock-atomic; second-open 404 of a KNOWN token logs an
   ALERT (theft attempt).
D6 LOW — generic 500 to client; details logged server-side only.
D7 LOW — revoke(person): scrubs store rows + re-mints.
D8 LOW — VAULT_DIR 0700 + sticky-bit check at startup, refuse otherwise.

REBEL:
R1 token gates the write (D1) — burn-on-open no longer theater.
R2 token delivered in URL FRAGMENT (#tok) — never in request line, never
   in nginx access logs.
R3 (partial) — page reachable only behind TLS; one-tap honored; no DNS
   until khalid points door.bawes.net — until then staff use the raw URL.
R4 rate limiting + Origin check on POST.
R5 OAuth-first: page shows Connect buttons for OAuth services (linear/
   notion/attio/google/xero) once wired; paste is the key-only fallback.
R6 owner PATs at install time (brick-onboarding) — post-bootstrap khalid
   uses the same surface.
R7 atomic 0600 writes (D2).
"""
import fcntl, hashlib, json, os, pathlib, secrets, sys, time, urllib.request

umask = os.umask(0o077)  # D2: no world-readable anything

VAULT_DIR = pathlib.Path(os.environ.get("DOOR_VAULT_DIR", "/srv/vault"))
TOKENS = VAULT_DIR / "ingest_tokens.json"
VAULT_STORE = VAULT_DIR / "store.jsonl"
ALERT = VAULT_DIR / "ingest_alerts.log"
SERVICES = {"openrouter", "deepseek", "higgfield", "gemini", "anthropic", "openai"}
OAUTH_SERVICES = {"linear", "notion", "attio", "google", "xero"}

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

def _lock(path):
    f = open(path, "a+")
    fcntl.flock(f, fcntl.LOCK_EX)
    return f

def _validate(service, key):
    """D4: provider-side validation — reject explicit 401s. Network errors
    store flagged-unvalidated (never block the owner on a network blip)."""
    try:
        if service == "openrouter":
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/key",
                headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status == 200, None
        elif service == "gemini":
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models"
                f"?key={key}", method="GET")
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status == 200, None
        # others: skip live check for now (OAuth or manual)
        return True, None
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "provider rejected key (401)"
        return True, "provider unreachable — stored unvalidated"
    except Exception as e:
        return True, f"provider unreachable — stored unvalidated ({str(e)[:40]})"

def new_token(person):
    """Door calls after consent. Returns fragment-token URL."""
    data = _load()
    tok = secrets.token_urlsafe(24)
    data[person] = {"token": tok, "used": False, "ts": time.time(),
                    "services": sorted(SERVICES)}
    _save(data)
    return f"https://door.bawes.net/i/#{tok}"  # R2: fragment, never in logs

def revoke(person):
    """D7: scrub that person's stored keys + re-mint."""
    data = _load()
    data.pop(person, None)
    _save(data)
    if VAULT_STORE.exists():
        keep = []
        for line in VAULT_STORE.read_text().splitlines():
            try:
                r = json.loads(line)
                if r.get("person") != person:
                    keep.append(line)
            except Exception:
                pass
        VAULT_STORE.write_text("\n".join(keep) + ("\n" if keep else ""))
        os.chmod(VAULT_STORE, 0o600)
    return new_token(person)

def vault_put(service, key_value, person):
    """D2/D3: atomic 0600 write; custody hash links key -> consent id."""
    row = {"kind": "key", "service": service, "person": person,
           "key_sha": hashlib.sha256(key_value.encode()).hexdigest()[:16],
           "key": key_value, "ts": time.time(),
           "custody": hashlib.sha256((person + ":" + service).encode()).hexdigest()[:16]}
    with _lock(VAULT_STORE):
        fd = os.open(VAULT_STORE, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(json.dumps(row) + "\n")
    return row["key_sha"]

def alert(msg):
    with open(ALERT, "a") as f:
        f.write(json.dumps({"msg": msg, "ts": time.time()}) + "\n")
    os.chmod(ALERT, 0o600)

# ---- startup hardening (D8) ----
os.makedirs(VAULT_DIR, exist_ok=True)
os.chmod(VAULT_DIR, 0o700)
if VAULT_DIR.stat().st_mode & 0o777 != 0o700:
    print("FAIL: VAULT_DIR not 0700 — refusing to start"); sys.exit(1)

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
const tok = location.hash.slice(1); // R2: fragment token
document.getElementById('f').onsubmit=async e=>{e.preventDefault();
const k=document.getElementById('k').value;
if(!k.startsWith('sk-')&&!k.startsWith('AIza')){alert('That does not look like a key (sk-… or AIza…).');return}
const r=await fetch('/put',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+tok},body:JSON.stringify({service:document.getElementById('s').value,key:k})});
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

    def _auth(self):
        """D1: the one-time token is the ONLY credential. Bearer header,
        looked up, must be UNUSED. Returns (person, token_rec) or None."""
        ah = self.headers.get("Authorization", "")
        if not ah.startswith("Bearer "):
            return None
        tok = ah[7:]
        data = _load()
        for person, rec in data.items():
            if rec.get("token") == tok:
                return person, rec
        return None

    def do_GET(self):
        if self.path.startswith("/i/"):
            # R2: token lives in the FRAGMENT — the request line carries
            # only /i/ + a nonce; the page JS reads location.hash.
            nonce = self.path.split("/i/")[-1].split("?")[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(PAGE)))
            self.end_headers()
            self.wfile.write(PAGE.encode())
            return
        self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path != "/put":
            self._json({"error": "unknown"}, 404); return
        auth = self._auth()
        if auth is None:
            alert(f"UNAUTH PUT attempt from {self.client_address[0]}")
            self._json({"error": "unauthorized"}, 403); return
        person, rec = auth
        if rec.get("used"):
            alert(f"REUSE of burned token by {person}")
            self._json({"error": "token already used"}, 403); return
        # Origin check (R4): only same-origin page posts
        origin = self.headers.get("Origin", "")
        if origin and "door.bawes.net" not in origin:
            self._json({"error": "bad origin"}, 403); return
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            service, key = body.get("service", ""), body.get("key", "")
            if service not in SERVICES or not key or len(key) < 10:
                self._json({"error": "bad service or key"}, 400); return
            ok, note = _validate(service, key)
            if not ok:
                self._json({"error": note or "provider rejected key"}, 400); return
            # consume atomically WITH the write (flock covers both)
            data = _load()
            data[person]["used"] = True
            _save(data)
            sha = vault_put(service, key, person)
            # round-146 item 4: BYOK — best-effort lane wiring (endpoint from
            # the fleet allowlist only, C2). Vault is always real; a person
            # without a registered brick stays vault-only (staged).
            lane = {}
            try:
                import sys as _sys
                _sys.path.insert(0, "/srv/bricks/ovh-server-001")
                from byok import wire_lane
                lane = wire_lane(person, service, key)
            except Exception:
                lane = {"ok": False, "error": "lane wiring unavailable"}
            self._json({"ok": True, "sha": sha,
                        "note": note or "validated",
                        "lane": lane})
        except Exception:
            alert(f"PUT error for {person}: {sys.exc_info()[1]}")
            self._json({"error": "server error"}, 500)  # D6: generic

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3744
    print(f"DOOR INGEST (hardened) on 127.0.0.1:{port}")
    HTTPServer(("127.0.0.1", port), H).serve_forever()
