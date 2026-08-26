# Discord OAuth2 login — wiring into fleet.bawes.net

Files: `discord_auth.py` (the flow, stdlib-only) · `discord-button.html` (login-page block).
person_id = **Discord snowflake, always a string**. Real endpoints only:
`https://discord.com/oauth2/authorize`, `/api/v10/oauth2/token`, `/api/v10/users/@me`.

## 1. One-time setup

- **Discord Developer Portal** → New Application "Brick" → OAuth2 → add redirect
  `https://fleet.bawes.net/auth/discord/callback` → copy Client ID + Client Secret.
- **Secrets on OVH** (token doctrine: never in chat/git): create
  `/srv/build/fleet-dashboard/discord-oauth.env`, mode 0600, owned by the dashboard user:

  ```
  DISCORD_CLIENT_ID=<id>
  DISCORD_CLIENT_SECRET=<secret>
  DISCORD_REDIRECT_URI=https://fleet.bawes.net/auth/discord/callback
  # optional: mirror members into users.json (recommended)
  DISCORD_USERS_FILE=/srv/build/fleet-dashboard/users.json
  ```

  Add `EnvironmentFile=/srv/build/fleet-dashboard/discord-oauth.env` to the
  dashboard's systemd unit (or source it in whatever supervises `dashboard.py`).
  No state secret needed: the module reuses the existing `session.key`.

## 2. Deploy the module

```bash
scp -i /root/.hermes/keys/ovh-vps-deploy discord_auth.py \
    ubuntu@51.75.74.214:/srv/build/fleet-dashboard/
```

## 3. Route registration in dashboard.py (two blocks)

Top of file, next to the other imports:

```python
import discord_auth  # same directory as dashboard.py

# Bridge: after Discord verifies a member, mint the dashboard's NATIVE
# bawes_session cookie. Every existing gated route then works unchanged,
# because verify_session() already trusts signed {u,r,e} payloads.
def _discord_on_login(identity):
    snowflake = str(identity["id"])
    row = {"username": snowflake,
           "role": next((u["role"] for u in load_users()
                         if u.get("username") == snowflake), "member")}
    return [("Set-Cookie", session_cookie_header(row))]
discord_auth.ON_LOGIN = _discord_on_login
```

In `Handler.do_GET`, with the other public early-return routes (before
`_require_session()`), matching the file's existing style:

```python
        if path == "/auth/discord":
            discord_auth.apply(self, discord_auth.oauth_start())
            return

        if path == "/auth/discord/callback":
            discord_auth.apply(self,
                discord_auth.oauth_callback(query, self.headers.get("Cookie", "")))
            return
```

(`query` = everything after `?`; grab it at the top of do_GET:
`path, _, query = self.path.partition("?")`.)

## 4. User lookup on gated routes

Nothing else to change. After login the browser holds `bawes_session`
(signed by the existing `make_session`), so `_require_session()` passes and
`user["username"]` **is the snowflake** — join wallets/registry rows on it:

```python
user, denied = self._require_session()
if denied:
    return
person_id = user["username"]        # e.g. "418016966853967872"
```

Optional standalone mode: skip the ON_LOGIN bridge and call
`discord_auth.get_current_user(self.headers.get("Cookie", ""))` instead — it
reads the module's own `dbx_session` cookie. Use one or the other, not both.

## 5. Login page

Paste `discord-button.html` inside the login form container in
`/srv/build/fleet-dashboard/login.html`, below the password fields. It renders
one gold **Continue with Discord** button (teal hover ring, dark theme) linking
to `/auth/discord`. No JS.

## 6. Ship + verify (receipts, not narration)

```bash
sudo systemctl restart fleet-dashboard   # or Brick's actual unit name
curl -si https://fleet.bawes.net/auth/discord | head -6
# expect: HTTP/2 302 + Location: https://discord.com/oauth2/authorize?client_id=...&scope=identify+guilds&state=...
curl -si https://fleet.bawes.net/auth/discord/callback | head -3   # -> 400 (no state) not 500
```

Then sign in once with a real Discord account and confirm the users.json row
(username = snowflake) + a live gated page rendering.

## Notes / security posture

- State is HMAC-signed + nonce-bound to a short-lived cookie (CSRF-safe,
  single-use, 10-min TTL); sessions are opaque random tokens server-side,
  HttpOnly/SameSite=Lax/Secure cookies; `next` is open-redirect-guarded.
- Snowflakes exceed float64 precision — they are never cast to int anywhere.
- Upserted users.json rows have empty salt/hash → password login can't match
  them; Discord is their only door. Existing roles are preserved on re-login.
- Logout: call `discord_auth.destroy_session(...)` too when clearing
  `bawes_session` (only needed if you use standalone mode).
