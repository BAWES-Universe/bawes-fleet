#!/usr/bin/env python3
"""
discord_auth.py — Discord OAuth2 login for fleet.bawes.net (BAWES fleet).

Drop-in module for the stdlib-http.server dashboard (`dashboard.py` on OVH).
Implements the complete OAuth2 Authorization Code flow with real Discord
endpoints ONLY:

    authorize : https://discord.com/oauth2/authorize
    token     : https://discord.com/api/v10/oauth2/token
    identity  : https://discord.com/api/v10/users/@me

Flow
----
  1. GET /auth/discord
       -> builds an HMAC-signed `state` (CSRF), stores its nonce in a
          short-lived cookie, 302s the browser to Discord's authorize URL
          with scopes `identify guilds`.
  2. GET /auth/discord/callback?code=...&state=...
       -> verifies state (signature + expiry + cookie match),
       -> exchanges `code` for a bearer token (POST form-encoded),
       -> fetches the user identity from /users/@me,
       -> person_id = Discord snowflake (kept as a STRING — snowflakes
          overflow float64/JS numbers; never cast to int),
       -> creates a session, sets the session cookie, redirects to `/`.

Integration contract (works with dashboard.py v5 unchanged)
-----------------------------------------------------------
Route handlers here return plain triples `(status, headers, body_bytes)`
where `headers` is a LIST of (name, value) pairs (multiple Set-Cookie are
allowed). Call `discord_auth.apply(handler, triple)` inside do_GET — it
speaks raw BaseHTTPRequestHandler, so no changes to `_send` are needed.
See README.md for the exact 8-line wiring.

Configuration (env vars)
------------------------
  DISCORD_CLIENT_ID        application id from the Discord Developer Portal
  DISCORD_CLIENT_SECRET    application oauth2 secret (treat like a vault item)
  DISCORD_REDIRECT_URI     default: https://fleet.bawes.net/auth/discord/callback
  DISCORD_OAUTH_SECRET     HMAC secret for state signing; falls back to the
                           dashboard's session.key file, else a sibling
                           oauth_state.key is auto-created (mode 0600)
  DISCORD_SESSION_TTL      seconds; default 43200 (12h, matches dashboard)
  DISCORD_USERS_FILE       optional users.json to upsert members into

Dependencies: Python 3.9+ stdlib only (urllib, hmac, http.server). No pip.

Self-test/demo: `python3 discord_auth.py --demo` serves a mini login page on
127.0.0.1:8789 with the three routes wired end-to-end.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Real Discord endpoints (do not invent others)
# ---------------------------------------------------------------------------
DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/v10/oauth2/token"
DISCORD_USERS_ME_URL = "https://discord.com/api/v10/users/@me"

# Documented CDN origin for avatar hashes returned by /users/@me.
DISCORD_CDN = "https://cdn.discordapp.com"

SCOPES = ["identify", "guilds"]          # Growth spec: identify + guilds
STATE_TTL = 600                          # state lives 10 minutes, one use
STATE_COOKIE = "dbx_oauth_state"         # short-lived CSRF nonce cookie
SESSION_COOKIE = "dbx_session"           # issued on successful login

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def client_id() -> str:
    return _env("DISCORD_CLIENT_ID")


def client_secret() -> str:
    return _env("DISCORD_CLIENT_SECRET")


def redirect_uri() -> str:
    """Where Discord sends the browser back. Must match the Developer Portal
    OAuth2 redirect list exactly (scheme+host+path)."""
    return _env("DISCORD_REDIRECT_URI",
                "https://fleet.bawes.net/auth/discord/callback")


def session_ttl() -> int:
    try:
        return int(_env("DISCORD_SESSION_TTL", "43200"))
    except ValueError:
        return 43200


def users_file() -> str:
    """Optional users.json to upsert authenticated Discord users into."""
    return _env("DISCORD_USERS_FILE")


_OAUTH_SECRET_CACHE: str | None = None


def oauth_secret() -> str:
    """HMAC secret used to sign OAuth `state` tokens.

    Order: DISCORD_OAUTH_SECRET env -> dashboard's session.key (same trust
    domain) -> auto-create oauth_state.key next to this module (0600),
    mirroring how dashboard.py bootstraps session.key."""
    global _OAUTH_SECRET_CACHE
    if _OAUTH_SECRET_CACHE:
        return _OAUTH_SECRET_CACHE
    env = _env("DISCORD_OAUTH_SECRET")
    if env:
        _OAUTH_SECRET_CACHE = env
        return env
    # Reuse the dashboard key if it exists (same-box deployment default).
    for candidate in (
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "session.key"),
        "/srv/build/fleet-dashboard/session.key",
    ):
        try:
            with open(candidate, "r", encoding="utf-8") as fh:
                secret = fh.read().strip()
            if secret:
                _OAUTH_SECRET_CACHE = secret
                return secret
        except OSError:
            continue
    # Last resort: create our own 0600 key beside this module.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "oauth_state.key")
    secret = ""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            secret = fh.read().strip()
    except OSError:
        pass
    if not secret:
        secret = secrets.token_urlsafe(48)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(secret)
    _OAUTH_SECRET_CACHE = secret
    return secret


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DiscordAuthError(Exception):
    """Any failure inside the OAuth flow (bad state, Discord 4xx/5xx, ...)."""


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib urllib only)
# ---------------------------------------------------------------------------


def _http_json(url: str, *, method: str = "GET", data=None,
               headers: dict | None = None, timeout: int = 10) -> dict:
    """Minimal JSON-over-HTTP with hard timeout. Raises DiscordAuthError on
    transport errors or non-2xx so callers can render honest error pages."""
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # Discord answers errors as JSON
        try:
            detail = exc.read().decode("utf-8")[:500]
        except Exception:
            detail = ""
        raise DiscordAuthError(
            f"Discord API {exc.code} on {url}: {detail}") from exc
    except Exception as exc:
        raise DiscordAuthError(f"Discord API unreachable ({url}): {exc}") from exc


# ---------------------------------------------------------------------------
# OAuth state — HMAC-signed {nonce, exp}, double-checked against a cookie
# ---------------------------------------------------------------------------


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64u_decode(txt: str) -> bytes:
    pad = "=" * (-len(txt) % 4)
    return base64.urlsafe_b64decode(txt + pad)


def make_state(now: float | None = None) -> str:
    """Signed state: base64url(json{nonce,exp}).hmac_sha256_hex."""
    payload = _b64u(json.dumps({
        "n": secrets.token_urlsafe(16),
        "e": int((now or time.time()) + STATE_TTL),
    }, separators=(",", ":")).encode())
    sig = hmac.new(oauth_secret().encode(), payload.encode(),
                   hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_state(state: str, cookie_nonce: str) -> bool:
    """State is valid only if: signature ok, not expired, AND its nonce equals
    the one stored in the browser's STATE_COOKIE (binds state to THIS browser,
    classic CSRF double-submit)."""
    if not state or "." not in state or not cookie_nonce:
        return False
    payload, _, sig = state.partition(".")
    expect = hmac.new(oauth_secret().encode(), payload.encode(),
                      hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expect):
        return False
    try:
        data = json.loads(_b64u_decode(payload))
    except Exception:
        return False
    if int(data.get("e", 0)) < time.time():
        return False
    return hmac.compare_digest(str(data.get("n", "")), str(cookie_nonce))


# ---------------------------------------------------------------------------
# Sessions — server-side store, opaque random cookie token
# ---------------------------------------------------------------------------

_SESSIONS: dict[str, dict] = {}
_LOCK = threading.Lock()


def create_session(identity: dict) -> str:
    """Store the authenticated identity, return the opaque cookie token.
    person_id is ALWAYS the snowflake string."""
    token = secrets.token_urlsafe(32)
    with _LOCK:
        # opportunistic GC of expired sessions
        cut = time.time()
        for k in [k for k, s in _SESSIONS.items() if s["expires"] < cut]:
            _SESSIONS.pop(k, None)
        _SESSIONS[token] = {
            "person_id": str(identity["id"]),          # snowflake as STRING
            "username": identity.get("username", ""),
            "global_name": identity.get("global_name") or "",
            "avatar": identity.get("avatar") or "",
            "created": time.time(),
            "expires": time.time() + session_ttl(),
        }
    return token


def get_cookie_value(cookie_header: str, name: str) -> str:
    """Pull one cookie out of a raw `Cookie:` header (same parsing rules as
    dashboard.py's _cookie_value)."""
    for part in (cookie_header or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == name:
            return v
    return ""


def get_current_user(cookie_header: str) -> dict | None:
    """Resolve the signed-in user from a raw Cookie header, or None.
    This is what protected routes call (see README 'user lookup')."""
    token = get_cookie_value(cookie_header, SESSION_COOKIE)
    if not token:
        return None
    with _LOCK:
        sess = _SESSIONS.get(token)
        if not sess or sess["expires"] < time.time():
            _SESSIONS.pop(token, None)
            return None
        return dict(sess)


def destroy_session(cookie_header: str) -> None:
    token = get_cookie_value(cookie_header, SESSION_COOKIE)
    if token:
        with _LOCK:
            _SESSIONS.pop(token, None)


# ---------------------------------------------------------------------------
# Optional users.json upsert — gives existing routes a stable lookup key
# ---------------------------------------------------------------------------


def upsert_discord_user(path: str, identity: dict, role: str = "member") -> dict:
    """Insert/update a users.json row keyed by username == snowflake.

    Row shape matches the dashboard's [{username, salt, hash, role, created}]
    convention; salt/hash stay empty => password login disabled for this row
    (POST /login will simply not match it — auth happens here only). Existing
    roles are preserved so admins promoted manually keep their role."""
    snowflake = str(identity["id"])
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            rows = json.load(fh)
        if not isinstance(rows, list):
            rows = []
    except OSError:
        rows = []
    profile = discord_profile(identity)
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for row in rows:
        if isinstance(row, dict) and row.get("username") == snowflake:
            row.setdefault("salt", "")
            row.setdefault("hash", "")
            row["discord"] = profile
            row["last_discord_login"] = now_iso
            break
    else:
        rows.append({
            "username": snowflake,          # person_id = Discord snowflake
            "salt": "",
            "hash": "",
            "role": role,
            "created": now_iso,
            "auth": "discord",
            "discord": profile,
            "last_discord_login": now_iso,
        })
    tmp = f"{path}.tmp.{os.getpid()}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    os.replace(tmp, path)                    # atomic swap
    return rows[-1] if rows else {}


def discord_profile(identity: dict) -> dict:
    """Compact identity record stored alongside the user row / session."""
    out = {
        "person_id": str(identity.get("id", "")),   # snowflake STRING
        "username": identity.get("username", ""),
        "global_name": identity.get("global_name") or "",
    }
    if identity.get("avatar"):
        out["avatar_url"] = (
            f"{DISCORD_CDN}/avatars/{identity['id']}/{identity['avatar']}.png")
    return out


# ---------------------------------------------------------------------------
# Flow step 1 — /auth/discord : redirect to Discord's authorize URL
# ---------------------------------------------------------------------------


def build_authorize_url(state: str, redirect_uri_: str | None = None) -> str:
    qs = urllib.parse.urlencode({
        "client_id": client_id(),
        "redirect_uri": redirect_uri_ or redirect_uri(),
        "response_type": "code",
        "scope": " ".join(SCOPES),               # identify + guilds
        "state": state,
    })
    return f"{DISCORD_AUTHORIZE_URL}?{qs}"


def secure_cookies() -> bool:
    """Set `Secure` on cookies when the public URL is https (it is)."""
    return redirect_uri().startswith("https://")


def oauth_start() -> tuple[int, list[tuple[str, str]], bytes]:
    """Handle GET /auth/discord. Returns a 302 triple to Discord."""
    if not client_id() or not client_secret():
        return _html(500,
            "Discord login is not configured: set DISCORD_CLIENT_ID and "
            "DISCORD_CLIENT_SECRET (see README.md).")
    state = make_state()
    nonce = json.loads(_b64u_decode(state.partition(".")[0]))["n"]
    cookie = (f"{STATE_COOKIE}={nonce}; Path=/; HttpOnly; SameSite=Lax; "
              f"Max-Age={STATE_TTL}"
              + ("; Secure" if secure_cookies() else ""))
    headers = [
        ("Location", build_authorize_url(state)),
        ("Set-Cookie", cookie),
        ("Cache-Control", "no-store"),
    ]
    return 302, headers, b""


# ---------------------------------------------------------------------------
# Flow step 2 — /auth/discord/callback : code -> token -> identity -> session
# ---------------------------------------------------------------------------


def exchange_code(code: str) -> dict:
    """Exchange the authorization code for an access token (form-encoded POST,
    per Discord docs). Returns {access_token, token_type, expires_in, ...}."""
    form = urllib.parse.urlencode({
        "client_id": client_id(),
        "client_secret": client_secret(),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),          # MUST equal step-1 value
    }).encode()
    tok = _http_json(DISCORD_TOKEN_URL, method="POST", data=form,
                     headers={"Content-Type":
                              "application/x-www-form-urlencoded"})
    if not tok.get("access_token"):
        raise DiscordAuthError("token exchange returned no access_token")
    return tok


def fetch_identity(access_token: str) -> dict:
    """GET /users/@me with the bearer token -> Discord user object.
    `id` is the snowflake (string)."""
    me = _http_json(DISCORD_USERS_ME_URL,
                    headers={"Authorization": f"Bearer {access_token}"})
    if not me.get("id"):
        raise DiscordAuthError("/users/@me returned no id")
    return me


def oauth_callback(query: str, cookie_header: str) -> tuple[int, list[tuple[str, str]], bytes]:
    """Handle GET /auth/discord/callback?code=..&state=..

    Success -> 302 to `next_path` (or /) with the session cookie set.
    Failure -> honest 400/502 page, never a fake session."""
    params = dict(urllib.parse.parse_qsl(query))

    # Discord reports user-denied / other failures as error params.
    if params.get("error"):
        reason = params.get("error_description") or params["error"]
        return _html(400, f"Discord sign-in was cancelled or failed: {reason}")

    # CSRF: state must be signed, fresh, and match this browser's cookie.
    if not verify_state(params.get("state", ""),
                        get_cookie_value(cookie_header, STATE_COOKIE)):
        return _html(400,
            "Sign-in link expired or state mismatch. Go back and try again.")

    code = params.get("code", "")
    if not code:
        return _html(400, "Missing ?code from Discord.")

    try:
        token = exchange_code(code)
        identity = fetch_identity(token["access_token"])
    except DiscordAuthError as exc:
        return _html(502, f"Discord OAuth failed: {exc}")

    # person_id = snowflake; optionally mirror into users.json for lookups.
    uf = users_file()
    if uf:
        try:
            upsert_discord_user(uf, identity)
        except OSError as exc:
            print(f"[discord_auth] users.json upsert failed: {exc}", flush=True)

    # Hook for hosts that mint their OWN session cookie (e.g. the dashboard's
    # native bawes_session). Whatever Set-Cookie header it returns is appended;
    # if unset, this module issues its own dbx_session cookie.
    extra_headers: list[tuple[str, str]] = []
    if ON_LOGIN is not None:
        try:
            result = ON_LOGIN(identity)
            if isinstance(result, list):
                extra_headers.extend(result)
        except Exception as exc:  # host bug must not hang the login page
            print(f"[discord_auth] on_login hook failed: {exc}", flush=True)
    if not extra_headers:
        token_id = create_session(identity)
        cookie = (f"{SESSION_COOKIE}={token_id}; Path=/; HttpOnly; "
                  f"SameSite=Lax; Max-Age={session_ttl()}"
                  + ("; Secure" if secure_cookies() else ""))
        extra_headers.append(("Set-Cookie", cookie))

    # Clear the one-time state cookie, land on the destination page.
    next_path = safe_next(params.get("next", "/"))
    extra_headers.append((
        "Set-Cookie",
        f"{STATE_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"))
    extra_headers.append(("Cache-Control", "no-store"))
    return 302, [("Location", next_path)] + extra_headers, b""


def safe_next(nxt: str) -> str:
    """Open-redirect guard: only same-site absolute paths."""
    return nxt if nxt.startswith("/") and not nxt.startswith("//") else "/"


#: Optional host hook: ON_LOGIN(identity) -> list[("Set-Cookie", "...")]
ON_LOGIN = None


# ---------------------------------------------------------------------------
# Response plumbing — speaks raw BaseHTTPRequestHandler
# ---------------------------------------------------------------------------


def _html(status: int, message: str) -> tuple[int, list[tuple[str, str]], bytes]:
    body = (f"<!doctype html><meta charset='utf-8'><title>BAWES</title>"
            f"<body style='background:#0B0E14;color:#E7ECF3;"
            f"font-family:system-ui;display:grid;place-items:center;height:100vh'>"
            f"<div style='max-width:34rem;text-align:center'>"
            f"<p style='color:#F0B429;font-weight:700'>{status}</p>"
            f"<p>{message}</p>"
            f"<p><a href='/login' style='color:#2DD4BF'>&larr; back to login</a></p>"
            f"</div></body>").encode()
    ctype = "text/html; charset=utf-8"
    return status, [("Content-Type", ctype)], body


def apply(handler: BaseHTTPRequestHandler, triple) -> None:
    """Write a `(status, [(name, value)...], body_bytes)` triple onto any
    BaseHTTPRequestHandler. Used inside do_GET:

        if path == "/auth/discord":
            discord_auth.apply(self, discord_auth.oauth_start()); return
    """
    status, headers, body = triple
    handler.send_response(status)
    seen_ct = False
    for name, value in headers:
        if name.lower() == "content-type":
            seen_ct = True
        handler.send_header(name, value)
    if body and not seen_ct:
        handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    if body:
        handler.wfile.write(body)


# ---------------------------------------------------------------------------
# Demo / self-test: `python3 discord_auth.py --demo`
# Serves a mini BAWES-branded login page + the two OAuth routes on :8789.
# With dummy credentials the first hop still proves itself: you get a real
# 302 to discord.com with correct scope/state, and the state/cookie binding.
# ---------------------------------------------------------------------------


class _DemoHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _cookies(self):
        return self.headers.get("Cookie", "")

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/auth/discord":
            apply(self, oauth_start())
        elif path == "/auth/discord/callback":
            apply(self, oauth_callback(query, self._cookies()))
        elif path == "/whoami":
            user = get_current_user(self._cookies())
            body = json.dumps(user or {"signed_in": False}, indent=1).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path in ("/", "/login"):
            body = DEMO_PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()


DEMO_PAGE = """<!doctype html><html><head><meta charset='utf-8'>
<title>Brick — sign in</title></head>
<body style='background:#0B0E14;color:#E7ECF3;font-family:system-ui;
display:grid;place-items:center;height:100vh;margin:0'>
<div style='text-align:center'>
<h1 style='font-weight:800'>Sign in to <span style='color:#F0B429'>Brick</span></h1>
<p><a href='/auth/discord' style='display:inline-block;background:#F0B429;color:#0B0E14;
font-weight:700;padding:.9rem 1.6rem;border-radius:12px;text-decoration:none'>
Continue with Discord</a></p>
<p style='color:#5B667A'><a href='/whoami' style='color:#2DD4BF'>/whoami</a> ·
<a href='/auth/discord/callback?denied=1' style='color:#2DD4BF'>simulate callback</a></p>
</div></body></html>"""


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        port = 8789
        print(f"[discord_auth] demo on http://127.0.0.1:{port} "
              f"(set DISCORD_CLIENT_ID/SECRET for the real hop)", flush=True)
        ThreadingHTTPServer(("127.0.0.1", port), _DemoHandler).serve_forever()
    else:
        print(__doc__)
