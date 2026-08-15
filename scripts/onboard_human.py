#!/usr/bin/env python3
"""onboard_human.py — T-UNIVERSE-022b (Zeus round-66 V-5 APPROVED).
"Give a brick to any human with quick onboarding."
Input:  name + Discord ID (human's own words, or khalid provides)
Output: signed manifest + allowlist row + ONE install command the human runs.
CONSENT HARD RULE (Zeus round-66 V-5): the human's 16-rule sign is NEVER
automated or skipped. This tool prints the install command and the rules;
the brick activates only after the human's real sign. The 30s is machinery,
the person's own pen is their boundary."""
import argparse, base64, hashlib, json, os, pathlib, secrets, sys, time

KEYPAIR = "/root/.hermes/keys/khalid-issuer-private.pem"
MANIFESTS = "/tmp/bawes-fleet/brick-packages"
ALLOWLIST = "/tmp/bawes-fleet/brick-profile/allowlist.jsonl"
INSTALL_REPO = "git@github.com:BAWES-Universe/bawes-fleet.git"

def log(m):
    print(f"[onboard] {m}", flush=True)

def load_key():
    if not os.path.exists(KEYPAIR):
        raise SystemExit(f"no issuer key at {KEYPAIR} — khalid's pen is the boundary")
    from cryptography.hazmat.primitives import serialization
    with open(KEYPAIR, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)

def sign_manifest(manifest, key):
    """JWS ES256 compact — mirrors brick_install.verify_manifest exactly."""
    body = {k: v for k, v in manifest.items() if k != "signature"}
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    payload_b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    hdr_b64 = base64.urlsafe_b64encode(
        json.dumps({"alg": "ES256"}).encode()).rstrip(b"=").decode()
    signing_input = f"{hdr_b64}.{payload_b64}".encode()
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    der = key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    manifest["signature"] = {
        "value": f"{hdr_b64}.{payload_b64}.{sig_b64}",
        "issuer": "khalid", "alg": "ES256", "ts": time.time()}
    return manifest

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="human's name (their own words)")
    ap.add_argument("--discord-id", required=True, help="Discord ID for allowlist")
    ap.add_argument("--person-id", default="", help="optional numeric person id")
    ap.add_argument("--role", default="citizen", choices=["citizen", "student", "staff"])
    ap.add_argument("--allowlist", default=ALLOWLIST)
    ap.add_argument("--out", default=MANIFESTS)
    args = ap.parse_args()

    pid = args.person_id or args.discord_id
    brick_id = f"{args.name.lower().replace(' ', '-')}-device-001"
    slug = f"{args.name.lower().replace(' ', '-')}"

    # 1. identity + manifest (schema mirrors mishari-device-001)
    manifest = {
        "manifest_version": 1,
        "brick_id": brick_id,
        "person_id": str(pid),
        "owner": slug,
        "hardware_owner": slug,
        "kill_switch": slug,
        "identity_card": {"name": f"{args.name}'s Brick", "role": args.role,
                          "voice": "fixed"},
        "skills": [],
        "seeded_knowledge": [],
        "backlog": [],
        "wallet_ref": f"banana-bank/wallet-{brick_id}.jsonl",
        "resource_links": [{"name": "queue",
                            "url": "git@github.com:BAWES-Universe/orbit-browser.git",
                            "branch": "queue", "readonly": True}],
    }
    if os.path.exists(os.path.join(args.out, f"manifest-{brick_id}.json")):
        raise SystemExit(f"brick {brick_id} already exists — collision refused")

    # 2. sign with khalid's key (his pen, the boundary)
    key = load_key()
    manifest = sign_manifest(manifest, key)
    os.makedirs(args.out, exist_ok=True)
    mp = os.path.join(args.out, f"manifest-{brick_id}.json")
    with open(mp, "w") as f:
        json.dump(manifest, f, indent=1)
    os.chmod(mp, 0o600)
    log(f"signed manifest -> {mp}")

    # 3. allowlist row (Discord ID allowlisted for this brick)
    os.makedirs(os.path.dirname(args.allowlist), exist_ok=True)
    row = {"brick_id": brick_id, "discord_id": str(args.discord_id),
           "name": args.name, "ts": time.time(), "consent": "pending-16-rules"}
    with open(args.allowlist, "a") as f:
        f.write(json.dumps(row) + "\n")
    log(f"allowlist -> {args.allowlist}")

    # 4. the ONE install command (human runs it; brick activates AFTER their sign)
    cmd = (f"git clone {INSTALL_REPO} && cd bawes-fleet && "
           f"python3 scripts/brick_install.py --manifest brick-packages/manifest-{brick_id}.json "
           f"--confirm")
    log("=" * 56)
    log(f"BRICK READY: {brick_id}")
    log(f"INSTALL COMMAND (run on YOUR device):")
    log(cmd)
    log("=" * 56)
    log("REMEMBER: read the 16 rules, sign them yourself, THEN run the command.")
    log("Your brick activates only after YOUR real sign. 30s machinery, your pen.")

if __name__ == "__main__":
    main()
