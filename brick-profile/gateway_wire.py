#!/usr/bin/env python3
"""gateway_wire.py — T-UNIVERSE-022 THE CONSUMER (khalid: "the product's face").
The missing wiring: reads brick-profile/out/*.json (identity.json,
a2a-policy.json, model.json — written by brick_profile.py apply) and writes
the REAL Hermes gateway config so a brick profile becomes a LIVE brick:
  - ~/.hermes/config.yaml  (identity, A2A read-only policy, model chain)
  - ~/.hermes/.env         (DISCORD_BOT_TOKEN, DISCORD_ALLOWED_USERS)
Fails closed. Never writes secrets to the repo. Dry-run default.
Round-64/Zeus: consumer ships within the week; receipts within days of sign.
"""
import json, os, re, sys, pathlib, shutil, subprocess, datetime

OUT = pathlib.Path(__file__).parent / "out"
HERMES_DIR = pathlib.Path.home() / ".hermes"
CONFIG = HERMES_DIR / "config.yaml"
ENV = HERMES_DIR / ".env"
BACKUP_SUFFIX = ".bak-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")

def fail(msg):
    print(f"REJECTED: {msg}")
    sys.exit(1)

def load_out(name):
    p = OUT / name
    if not p.exists():
        fail(f"{name} missing — run brick_profile.py apply first")
    with open(p) as f:
        return json.load(f)

def write_env(env_path, pairs):
    """Append/update KEY=VALUE lines in an env file, preserving everything else."""
    lines = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()
    keys = set(pairs)
    kept = [l for l in lines if l.strip() and not l.split("=", 1)[0].strip() in keys]
    kept += [f"{k}={v}" for k, v in pairs.items()]
    env_path.write_text("\n".join(kept) + "\n")
    os.chmod(env_path, 0o600)

def patch_yaml_block(path, marker, block):
    """Insert/replace a YAML block delimited by # BEGIN/END <marker> markers."""
    text = path.read_text() if path.exists() else ""
    begin = f"# BEGIN {marker}"
    end = f"# END {marker}"
    new_block = f"{begin}\n{block}\n{end}"
    if begin in text:
        text = re.sub(rf"{begin}.*?{end}", new_block, text, flags=re.S)
    else:
        text = text.rstrip() + "\n" + new_block + "\n"
    path.write_text(text)

def wire(dry_run=True, force=False):
    ident = load_out("identity.json")
    a2a = load_out("a2a-policy.json")
    model = load_out("model.json")

    brick_id = ident.get("brick_id")
    person_id = ident.get("person_id")
    discord_user_id = ident.get("discord_user_id")
    if not brick_id or not person_id:
        fail("identity.json missing brick_id/person_id")
    if not discord_user_id:
        fail("identity.json missing discord_user_id — Discord identity is explicit, "
             "never inferred from person_id")

    # ---- 1. .env: Discord token + allowed users (A2A enforcement target) ----
    token = os.environ.get("BRICK_DISCORD_TOKEN", "")
    if not token and not force:
        fail("BRICK_DISCORD_TOKEN not set (and no --force) — brick can't speak")
    users = [discord_user_id]
    pairs = {"BRICK_ID": brick_id, "PERSON_ID": person_id, "DISCORD_USER_ID": discord_user_id}
    if token:
        pairs["DISCORD_BOT_TOKEN"] = token
    pairs["DISCORD_ALLOWED_USERS"] = ",".join(str(u) for u in users)

    # ---- 2. config.yaml: A2A read-only policy block ----
    reject = a2a.get("reject") or ["terminal", "code_execution", "memory", "file", "skill_manage"]
    a2a_block = (
        "a2a_policy:\n"
        f"  brick_id: {brick_id}\n"
        f"  enforce_read_only: {str(a2a.get('enforce_read_only', True)).lower()}\n"
        "  reject:\n" + "".join(f"    - {t}\n" for t in reject)
    )

    # ---- 3. config.yaml: model chain (local → fleet router) ----
    chain = model.get("chain") or []
    m_block = (
        "brick_model:\n"
        f"  primary: {model.get('primary', '')}\n"
        f"  default_model: {model.get('default_model', '')}\n"
        "  chain:\n" + "".join(f"    - {c}\n" for c in chain)
    )

    if dry_run:
        print(f"[dry] would wire brick '{brick_id}' (person {person_id})")
        print(f"[dry]   .env: DISCORD_BOT_TOKEN={'<set>' if token else '<MISSING>'} "
              f"DISCORD_ALLOWED_USERS={users}")
        print(f"[dry]   config.yaml: a2a_policy + brick_model blocks")
        print("[dry] nothing written")
        return 0

    # backup originals, then write
    if CONFIG.exists():
        shutil.copy2(CONFIG, str(CONFIG) + BACKUP_SUFFIX)
    if ENV.exists():
        shutil.copy2(ENV, str(ENV) + BACKUP_SUFFIX)
    write_env(ENV, pairs)
    patch_yaml_block(CONFIG, "BRICK-A2A", a2a_block)
    patch_yaml_block(CONFIG, "BRICK-MODEL", m_block)
    os.chmod(CONFIG, 0o600)
    print(f"wired brick '{brick_id}' -> {HERMES_DIR} (backups: {BACKUP_SUFFIX})")
    print("receipt:", {"brick_id": brick_id, "person_id": person_id,
                       "a2a_reject": reject, "chain": chain,
                       "ts": datetime.datetime.utcnow().isoformat() + "Z"})
    return 0

if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    force = "--force" in sys.argv
    sys.exit(wire(dry_run=dry, force=force))
