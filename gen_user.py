#!/usr/bin/env python3
"""
BAWES fleet dashboard — user management CLI (v3 session auth, v14 roles).

Manages /srv/build/fleet-dashboard/users.json (0600):
  [{username, salt, hash(scrypt), role, lanes?, discord_id?, created}]

Roles (v14):
  owner          — everything incl. role-granting, money, final approvals authority
  decision_maker — approve/reject approval cards routed to their lanes (studenthub, plugn)
  contributor    — read-only dashboard
  brick_issuer   — can issue bricks to people

Usage:
  python3 gen_user.py add <username> [--role owner|decision_maker|contributor|brick_issuer]
                        [--lanes studenthub,plugn] [--discord-id ID] [--password PW]
  python3 gen_user.py setrole <username> --role X [--lanes a,b] [--discord-id ID]
  python3 gen_user.py remove <username>
  python3 gen_user.py change <username> [--password PW]
  python3 gen_user.py list

- add:     creates the user. Without --password a strong one is generated and
           printed ONCE (bawes- + 8 random chars).
- setrole: grant/change a role + lanes (the CLI twin of POST /api/roles; the API
           writes the audit trail, the CLI is for bootstrap/emergency use).
- remove:  deletes the user. Refuses to remove the last owner (khalid).
- change:  resets the password (generated unless --password given) — prints it.
- list:    usernames + roles + lanes + discord binds (never hashes or passwords).

Writes are atomic (temp file + os.replace) and the file is chmod 600.
The dashboard service (runs as ubuntu) reads users.json on every request, so
no restart is needed after changes — sessions are re-validated against the
file, so a removed user loses access immediately.
"""
import argparse, json, os, re, secrets, string, sys, datetime

BASE = "/srv/build/fleet-dashboard"
USERS_FILE = os.path.join(BASE, "users.json")
ROLES = ("owner", "decision_maker", "contributor", "brick_issuer")
LANES = ("studenthub", "plugn", "fleet")
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,32}$")
MIN_PW_LEN = 8
PW_CHARS = string.ascii_letters + string.digits


def now_iso():
    return datetime.datetime.now(datetime.UTC).isoformat()


def hash_password(pw, salt):
    """scrypt — must match dashboard.py hash_password exactly."""
    import hashlib
    return hashlib.scrypt(pw.encode(), salt=salt.encode(), n=2 ** 14, r=8, p=1).hex()


def load_users():
    try:
        with open(USERS_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"ERROR: users.json unreadable: {e}", file=sys.stderr)
        sys.exit(1)


def save_users(users):
    tmp = USERS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(users, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, USERS_FILE)  # atomic


def gen_password():
    return "bawes-" + "".join(secrets.choice(PW_CHARS) for _ in range(8))


def validate_username(u):
    if not USERNAME_RE.match(u):
        sys.exit(f"ERROR: username '{u}' invalid — use 3-32 chars, lowercase a-z, 0-9, underscore")


def validate_password(pw):
    if len(pw) < MIN_PW_LEN:
        sys.exit(f"ERROR: password too short — minimum {MIN_PW_LEN} chars")


def parse_lanes(raw):
    """'studenthub,plugn' -> ['studenthub','plugn'] (valid lanes only)."""
    if not raw:
        return []
    out = []
    for l in re.split(r"[,\s]+", str(raw).strip()):
        l = l.strip().lower()
        if l and l in LANES:
            out.append(l)
    return out


def cmd_add(args):
    validate_username(args.username)
    users = load_users()
    if any(u.get("username") == args.username for u in users):
        sys.exit(f"ERROR: user '{args.username}' already exists")
    pw = args.password or gen_password()
    validate_password(pw)
    salt = secrets.token_hex(16)
    row = {"username": args.username, "salt": salt,
           "hash": hash_password(pw, salt), "role": args.role,
           "created": now_iso()}
    lanes = parse_lanes(args.lanes)
    if args.role == "decision_maker" and lanes:
        row["lanes"] = lanes
    if args.discord_id:
        row["discord_id"] = str(args.discord_id).strip()
    users.append(row)
    save_users(users)
    print(f"ADDED {args.username} (role={args.role}" + (f", lanes={lanes}" if lanes else "") + f") -> {USERS_FILE}")
    print(f"password: {pw}")
    print("(printed once — store it in README-AUTH.md (0600) and hand it to the user; "
          "run 'change' to reset if lost)")


def cmd_setrole(args):
    """CLI twin of POST /api/roles — grant/change a role + lanes + discord bind."""
    validate_username(args.username)
    users = load_users()
    target = next((u for u in users if u.get("username") == args.username), None)
    if target is None:
        sys.exit(f"ERROR: user '{args.username}' not found")
    if args.role not in ROLES:
        sys.exit(f"ERROR: unknown role '{args.role}' — choose: {', '.join(ROLES)}")
    prev_role = target.get("role")
    if prev_role == "owner" and args.role != "owner" and \
            sum(1 for u in users if u.get("role") == "owner") <= 1:
        sys.exit(f"ERROR: refusing to demote '{args.username}' — last owner. "
                 "Promote someone else to owner first.")
    target["role"] = args.role
    if args.role == "decision_maker":
        lanes = parse_lanes(args.lanes) or [l for l in (target.get("lanes") or []) if l in LANES]
        if lanes:
            target["lanes"] = lanes
        else:
            target.pop("lanes", None)
    else:
        target.pop("lanes", None)
    if args.discord_id is not None:
        target["discord_id"] = str(args.discord_id).strip()
    target["roles_changed"] = now_iso()
    save_users(users)
    print(f"SETROLE {args.username}: {prev_role} -> {args.role}"
          + (f" (lanes={target.get('lanes')})" if target.get("lanes") else "")
          + (f" (discord_id={target.get('discord_id')})" if target.get("discord_id") else ""))


def cmd_remove(args):
    users = load_users()
    target = next((u for u in users if u.get("username") == args.username), None)
    if target is None:
        sys.exit(f"ERROR: user '{args.username}' not found")
    if target.get("role") == "owner" and sum(1 for u in users if u.get("role") == "owner") <= 1:
        sys.exit(f"ERROR: refusing to remove '{args.username}' — last owner. "
                 "Promote another user to owner first (edit users.json role).")
    users = [u for u in users if u.get("username") != args.username]
    save_users(users)
    print(f"REMOVED {args.username}. Sessions for this user are now invalid (checked per request).")


def cmd_change(args):
    validate_username(args.username)
    users = load_users()
    target = next((u for u in users if u.get("username") == args.username), None)
    if target is None:
        sys.exit(f"ERROR: user '{args.username}' not found")
    pw = args.password or gen_password()
    validate_password(pw)
    target["salt"] = secrets.token_hex(16)
    target["hash"] = hash_password(pw, target["salt"])
    target["changed"] = now_iso()
    save_users(users)
    print(f"CHANGED password for {args.username} (role={target.get('role')})")
    print(f"new password: {pw}")
    print("(printed once — existing sessions stay valid; the new password applies on next sign-in)")


def cmd_list(args):
    users = load_users()
    if not users:
        print("no users — add one with: python3 gen_user.py add <username> --role owner")
        return
    print(f"{'username':<16} {'role':<14} {'lanes':<22} discord_id")
    print("-" * 68)
    for u in sorted(users, key=lambda x: x.get("username", "")):
        lanes = ",".join(u.get("lanes") or [])
        print(f"{u.get('username','?'):<16} {u.get('role','?'):<14} {lanes:<22} {u.get('discord_id','')}")


def main():
    ap = argparse.ArgumentParser(description="BAWES fleet dashboard user management")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add", help="create a user (prints generated password once)")
    p_add.add_argument("username")
    p_add.add_argument("--role", choices=ROLES, default="contributor")
    p_add.add_argument("--lanes", default=None, help="comma-separated (studenthub,plugn,fleet) for decision_maker")
    p_add.add_argument("--discord-id", default=None)
    p_add.add_argument("--password", default=None)
    p_add.set_defaults(fn=cmd_add)
    p_sr = sub.add_parser("setrole", help="grant/change a role (+ lanes / discord bind)")
    p_sr.add_argument("username")
    p_sr.add_argument("--role", choices=ROLES, required=True)
    p_sr.add_argument("--lanes", default=None)
    p_sr.add_argument("--discord-id", default=None)
    p_sr.set_defaults(fn=cmd_setrole)
    p_rm = sub.add_parser("remove", help="delete a user")
    p_rm.add_argument("username")
    p_rm.set_defaults(fn=cmd_remove)
    p_ch = sub.add_parser("change", help="reset a user's password (prints new one)")
    p_ch.add_argument("username")
    p_ch.add_argument("--password", default=None)
    p_ch.set_defaults(fn=cmd_change)
    p_ls = sub.add_parser("list", help="list users + roles + lanes")
    p_ls.set_defaults(fn=cmd_list)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
