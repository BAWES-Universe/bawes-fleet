#!/usr/bin/env python3
"""End-to-end test of discord_auth.py against a MOCKED Discord backend.

Proves: authorize URL shape (real host/scopes), state CSRF binding,
code->token->identity->session happy path, snowflake-as-string person_id,
users.json upsert role preservation, open-redirect guard.
"""
import json, os, re, sys, tempfile, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ["DISCORD_CLIENT_ID"] = "TEST_CLIENT_ID"
os.environ["DISCORD_CLIENT_SECRET"] = "TEST_SECRET"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discord_auth as da

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))

# ---- mock Discord API -------------------------------------------------------
SNOWFLAKE = "123456789012345678"
class MockDiscord(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):   # token endpoint
        ln = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(ln).decode()
        form = dict(p.split("=", 1) for p in body.split("&"))
        assert form["grant_type"] == "authorization_code" and form["client_id"] == "TEST_CLIENT_ID"
        self._send({"access_token": "MOCK_TOKEN", "token_type": "Bearer", "expires_in": 604800})
    def do_GET(self):    # /users/@me
        assert self.headers.get("Authorization") == "Bearer MOCK_TOKEN"
        self._send({"id": SNOWFLAKE, "username": "khalid_bawes",
                    "global_name": "Khalid", "avatar": "abc123", "discriminator": "0"})

mock_srv = ThreadingHTTPServer(("127.0.0.1", 0), MockDiscord)
threading.Thread(target=mock_srv.serve_forever, daemon=True).start()
mp = mock_srv.server_address[1]
da.DISCORD_TOKEN_URL = f"http://127.0.0.1:{mp}/api/v10/oauth2/token"      # redirect only
da.DISCORD_USERS_ME_URL = f"http://127.0.0.1:{mp}/api/v10/users/@me"      # constants stay real

app = ThreadingHTTPServer(("127.0.0.1", 0), da._DemoHandler)
threading.Thread(target=app.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{app.server_address[1]}"

def get(path, headers=None):
    req = urllib.request.Request(base + path, headers=headers or {})

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None

    try:
        return urllib.request.build_opener(NoRedirect()).open(req)
    except urllib.error.HTTPError as exc:   # 4xx: return as pseudo-response
        return exc

# 1) endpoint hygiene: only real Discord hosts hardcoded in module
src = open(da.__file__).read()
urls = set(re.findall(r'https://[a-z0-9.\-/@]+', src))
allowed = {"https://discord.com/oauth2/authorize",
           "https://discord.com/api/v10/oauth2/token",
           "https://discord.com/api/v10/users/@me",
           "https://cdn.discordapp.com",
           "https://fleet.bawes.net/auth/discord/callback"}
check("no invented endpoints", urls <= allowed, str(urls - allowed))

# 2) /auth/discord -> 302 to real authorize URL w/ identify+guilds+state, sets nonce cookie
r = get("/auth/discord")
loc = r.headers["Location"]; setc = r.headers.get("Set-Cookie", "")
q = dict(p.split("=", 1) for p in loc.split("?", 1)[1].split("&"))
check("authorize 302", r.status == 302)
check("real authorize host", loc.startswith("https://discord.com/oauth2/authorize?"))
check("scope identify+guilds", q.get("scope") == "identify+guilds")
check("response_type=code", q.get("response_type") == "code")
check("redirect_uri matches portal value",
      urllib.parse.unquote(q.get("redirect_uri", "")) == da.redirect_uri())
check("state present", len(q.get("state", "")) > 40)
nonce = setc.split("=", 1)[1].split(";")[0]
check("state nonce bound to HttpOnly cookie", setc.startswith("dbx_oauth_state=") and "HttpOnly" in setc and bool(nonce))

# 3) callback with WRONG state -> honest 400
r = get(f"/auth/discord/callback?code=x&state=forged.{nonce}", {"Cookie": f"dbx_oauth_state={nonce}"})
check("bad state rejected 400", r.status == 400)

# 4) happy path: real state + matching cookie -> token -> identity -> session
r2 = get("/auth/discord")   # fresh state/cookie pair
loc2 = r2.headers["Location"]; st2 = loc2.split("state=", 1)[1]
ck2 = r2.headers.get("Set-Cookie", "").split("=", 1)[1].split(";")[0]
r = get(f"/auth/discord/callback?code=good&state={st2}&next=/dashboard-ish",
        {"Cookie": f"dbx_oauth_state={ck2}"})
sessc = r.headers.get_all("Set-Cookie") or []
sess = [c for c in sessc if c.startswith("dbx_session=")]
check("callback 302 to safe next", r.status == 302 and r.headers["Location"] == "/dashboard-ish")
check("session cookie issued HttpOnly+Lax", bool(sess) and "HttpOnly" in sess[0] and "SameSite=Lax" in sess[0])
tok = sess[0].split("=", 1)[1].split(";")[0]

# 5) session resolves identity, snowflake stays STRING
user = da.get_current_user(f"dbx_session={tok}")
check("session resolves user", user is not None)
check("person_id == snowflake as str", isinstance(user.get("person_id"), str) and user["person_id"] == SNOWFLAKE)
check("identity fields captured", user.get("username") == "khalid_bawes")

# 6) state replay across browsers blocked (no cookie match)
r = get(f"/auth/discord/callback?code=good&state={st2}", {})
check("replay without cookie blocked", r.status == 400)

# 7) expired state rejected
st_exp = da.make_state(now=time.time() - 900)
check("expired state rejected", not da.verify_state(st_exp, json.loads(da._b64u_decode(st_exp.partition('.')[0]))["n"]))

# 8) users.json upsert: creates row keyed by snowflake, preserves role on re-login
tmp = tempfile.mktemp(suffix=".json")
open(tmp, "w").write(json.dumps([{"username": SNOWFLAKE, "role": "admin", "salt": "s", "hash": "h"}]))
da.upsert_discord_user(tmp, {"id": SNOWFLAKE, "username": "khalid_bawes"})
rows = json.load(open(tmp)); row = next(r for r in rows if r["username"] == SNOWFLAKE)
check("upsert preserves existing role", row["role"] == "admin" and row["hash"] == "h")
check("upsert stores profile + last login", row["discord"]["person_id"] == SNOWFLAKE and "last_discord_login" in row)
da.upsert_discord_user(tmp, {"id": "999", "username": "newmember"})
check("upsert appends new member w/ empty hash", any(r["username"] == "999" and r["hash"] == "" for r in json.load(open(tmp))))

# 9) safe_next guard
check("open-redirect guarded", da.safe_next("//evil.com") == "/" and da.safe_next("/approvals") == "/approvals")

print(f"\n{len(PASS)} PASS / {len(FAIL)} FAIL")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL GREEN — flow verified end-to-end against mocked Discord API")
