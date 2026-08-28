# BAWES Fleet Dashboard — Login & Users (v3, 2026-08-24)

Sign in: http://51.75.74.214:3999/login   (also https://fleet.bawes.net/login)
No more browser basic-auth popup. Sessions last 12h (cookie bawes_session,
HMAC-signed, secret in session.key 0600).

## Users
| username | role        | password (current) |
|----------|-------------|--------------------|
| khalid   | owner       | bawes-5IqLEuzl |
| mishari  | contributor | bawes-j5YSsgWD |

Roles: owner = everything incl. /approvals approve/reject/feedback.
       contributor = read-only dashboard + approvals (actions -> 403).

## Managing users (khalid)
  cd /srv/build/fleet-dashboard
  python3 gen_user.py list                          # who has access
  python3 gen_user.py add <username> --role owner   # or --role contributor
  python3 gen_user.py change <username>             # reset password (prints new one)
  python3 gen_user.py remove <username>             # revoke access immediately
Add --password '...' to set your own instead of a generated one.
No service restart needed — users.json is read on every request.

## Verify from any machine
  curl -i http://51.75.74.214:3999/                       # -> 302 Location: /login
  curl -c /tmp/jar -d 'username=khalid&password=PW' http://51.75.74.214:3999/login   # -> 302 + Set-Cookie
  curl -b /tmp/jar http://51.75.74.214:3999/              # -> 200
  curl -b /tmp/jar http://51.75.74.214:3999/logout        # -> 302, cookie cleared

Do NOT put this file or users.json in git or share passwords in public chats.
