#!/usr/bin/env python3
"""brick-install v1 — turns a generic engine into a live brick in one command.
The missing link (rounds 25/28): manifest -> identity + skills + backlog +
resource links + death warrant + headless worker. ~5 min, git-native,
everything from verified sources, nothing hand-copied.

Input : a signed brick manifest (brick-manifest-schema-v1.md, round-25 W-2)
Output: a live brick directory ready to boot (device OR Vast worker)

Round-33 review fixes (pair-DA OBJECT -> all blockers/highs closed):
  - REAL JWS ES256 verification over the exact payload bytes, pinned issuer keys,
    alg:none rejected, decoded payload must equal the manifest (blocker 1)
  - no-overwrite: refuses to install over an existing identity (finding 7)
  - path traversal: skill refs must match ^[a-z0-9-]+:[a-z0-9-]+$ and resolve
    under SKILLS_SRC (finding 4)
  - private keys generated OUTSIDE the brick repo root (finding 5)
"""
import json, os, shutil, subprocess, sys, hashlib, time, argparse, base64, re

BRICK_ROOT = "/opt/brick"          # where the brick lives (volume/home); overridden by --root
SKILLS_SRC = "/root/.hermes/skills"  # verified local skill refs (bawes-fleet)
ROOT = BRICK_ROOT                   # effective root, set in main()

# Pinned issuer public keys (round-33 blocker 1): verify ES256 over the payload.
# khalid's key is set at his sign-off; installs fail CLOSED until a key is pinned
# for the issuer — a manifest can never pass on "shape only".
ISSUER_KEYS = {
    "khalid": "-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEUD7wvDW7aL1T45TZ+hY/2mO7ddv6\nkW93necd8rFJkwG+xdTcJ66O7bA9XfCtCWhonoCjiMR3ae6vAvLJHXmR8Q==\n-----END PUBLIC KEY-----\n",
}

def log(m):
    print(f"[install] {m}", flush=True)

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def verify_manifest(m):
    """R1/R2 + round-33 blocker 1: REAL cryptographic JWS ES256 verification.
    - alg must be ES256 (alg:none rejected)
    - signature must verify against the issuer's PINNED public key over the
      EXACT canonical manifest payload bytes
    - the decoded payload must equal the manifest (no payload/signature mismatch)
    - issuer must be known; brick_id collision checked by caller (no-overwrite)
    Fail CLOSED: no pinned key for the issuer = reject."""
    sig = m.get("signature") or {}
    val = sig.get("value", "")
    issuer = sig.get("issuer", "")
    if issuer not in ISSUER_KEYS:
        raise SystemExit(f"REJECTED: no pinned public key for issuer '{issuer}' "
                         f"(round-33: fail closed — shape alone never passes)")
    pub = ISSUER_KEYS[issuer]
    parts = val.split(".")
    if len(parts) != 3 or not all(parts):
        raise SystemExit("REJECTED: signature is not a valid JWS compact shape "
                         "(header.payload.signature — round-31 condition 1)")
    try:
        hdr = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
        if hdr.get("alg") != "ES256":
            raise SystemExit(f"REJECTED: signature alg {hdr.get('alg')} != ES256 (rule 11)")
        # canonical payload = manifest WITHOUT the signature field, stable order
        body = {k: v for k, v in m.items() if k != "signature"}
        payload_bytes = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
        if parts[1] != payload_b64:
            raise SystemExit("REJECTED: signature payload does not match the manifest body")
        # ES256 = ECDSA P-256 + SHA-256 over header.payload
        import cryptography
        from cryptography.hazmat.primitives.asymmetric import ec, utils
        from cryptography.hazmat.primitives import hashes, serialization
        pubkey = serialization.load_pem_public_key(pub.encode())
        signing_input = (parts[0] + "." + parts[1]).encode()
        sig_raw = base64.urlsafe_b64decode(parts[2] + "==")
        # JWS ES256 uses raw R||S (64 bytes); DER-encode for verify()
        r, s = sig_raw[:32], sig_raw[32:]
        der = utils.encode_dss_signature(int.from_bytes(r, "big"), int.from_bytes(s, "big"))
        pubkey.verify(der, signing_input, ec.ECDSA(hashes.SHA256()))
    except SystemExit:
        raise
    except Exception as e:
        raise SystemExit(f"REJECTED: signature verification failed: {str(e)[:80]}")
    if m.get("manifest_version", 0) < 1:
        raise SystemExit("REJECTED: manifest_version < 1")
    log(f"signature VERIFIED (JWS ES256, issuer {issuer}, pinned key, payload-bound)")
    return True

def generate_keys(ident):
    """R3 (round-25) + round-33 finding 5: keys generated ON-DEVICE, stored
    OUTSIDE the brick repo root so 'git add -A' can never ship them."""
    keydir = f"{ROOT}/../keys"  # sibling of the brick root, never inside the repo
    keydir = os.path.abspath(keydir)
    os.makedirs(keydir, exist_ok=True)
    priv, pub = f"{keydir}/brick_ed25519", f"{keydir}/brick_ed25519.pub"
    if not os.path.exists(priv):
        subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", ident, "-f", priv],
                       capture_output=True, check=True)
        os.chmod(priv, 0o600)
    if not os.path.exists(pub):
        raise SystemExit("key pair inconsistent: private exists but public missing — fix manually")
    with open(pub) as f:
        pubkey = f.read().strip()
    log(f"keys generated ON-DEVICE outside repo: {pubkey[:40]}...")
    return pubkey

def install_skills(m):
    """R4 (round-25) + round-33 finding 4: skill refs must be allowlisted-shaped
    (^[a-z0-9-]+:[a-z0-9-]+$) and resolve strictly under SKILLS_SRC — no traversal."""
    target = f"{ROOT}/skills"
    os.makedirs(target, exist_ok=True)
    ref_re = re.compile(r"^[a-z0-9-]+:[a-z0-9-]+$")
    base = os.path.realpath(SKILLS_SRC)
    for ref in m.get("skills", []):
        if not ref_re.match(ref):
            raise SystemExit(f"REJECTED: malformed skill ref '{ref}' (round-33 finding 4)")
        name = ref.split(":", 1)[1]
        src = os.path.realpath(os.path.join(base, name))
        if not src.startswith(base + os.sep) or not os.path.isdir(src):
            log(f"skill ref not found in allowlisted source: {ref}")
            continue
        dst = os.path.join(target, name)
        if not os.path.exists(dst):
            shutil.copytree(src, dst)
            log(f"skill installed: {ref}")

def write_death_warrant(m):
    w = {
        "worker_id": m.get("brick_id", "brick"),
        "lifetime_max_s": m.get("death_warrant", {}).get("lifetime_max_s", 7200),
        "spend_max_usd": m.get("death_warrant", {}).get("spend_max_usd", 1.00),
        "idle_max_s": m.get("death_warrant", {}).get("idle_max_s", 300),
        "seeder_mode": m.get("death_warrant", {}).get("seeder_mode", False),
        "kill_hierarchy": ["worker-self-destruct", "owner-kill-switch", "khalid-ultimate"],
    }
    with open(f"{ROOT}/death-warrant.json", "w") as f:
        json.dump(w, f, indent=2)
    log(f"death warrant written (lifetime {w['lifetime_max_s']}s, spend ${w['spend_max_usd']}, "
        f"idle {w['idle_max_s']}s, seeder={w['seeder_mode']})")

def write_backlog(m):
    with open(f"{ROOT}/backlog.jsonl", "w") as f:
        for t in m.get("backlog", []):
            f.write(json.dumps({"ticket": t, "claimed": False, "done": False}) + "\n")
    log(f"backlog: {len(m.get('backlog', []))} tickets (never empty — spawn rule)")

def write_identity(m, pubkey):
    ident = {
        "brick_id": m["brick_id"],
        "person_id": m.get("person_id"),
        "owner": m.get("owner"),
        "hardware_owner": m.get("hardware_owner"),
        "kill_switch": m.get("kill_switch"),
        "public_key": pubkey,
        "model_chain": m.get("model_chain", ["local", "deepseek-v4-flash"]),
        "scheduling": m.get("scheduling", "idle-only, owner-preemptible"),
    }
    with open(f"{ROOT}/identity.json", "w") as f:
        json.dump(ident, f, indent=2)
    log(f"identity written: {m['brick_id']} (owner {m.get('owner')}, kill-switch {m.get('kill_switch')})")

def main():
    ap = argparse.ArgumentParser(description="brick-install v1 — manifest -> live brick")
    ap.add_argument("manifest", help="path to the signed brick manifest (JSON)")
    ap.add_argument("--root", default=BRICK_ROOT, help="brick root dir")
    args = ap.parse_args()
    global ROOT
    ROOT = args.root

    with open(args.manifest) as f:
        m = json.load(f)
    verify_manifest(m)
    log(f"manifest verified: {m.get('brick_id')} (signed, v{m.get('manifest_version')})")

    # round-33 finding 7 (no-overwrite, rule 2): refuse to install over a live brick
    if os.path.exists(f"{ROOT}/identity.json"):
        raise SystemExit(f"REJECTED: {ROOT}/identity.json exists — brick already installed "
                         f"(no-overwrite, rule 2; requires a signed transfer event)")

    os.makedirs(ROOT, exist_ok=True)
    pubkey = generate_keys(f"{m.get('brick_id')}@bawes")
    install_skills(m)
    write_backlog(m)
    write_death_warrant(m)
    write_identity(m, pubkey)
    with open(f"{ROOT}/resource-links.json", "w") as f:
        json.dump(m.get("resource_links", []), f, indent=2)
    log(f"resource links: {len(m.get('resource_links', []))}")

    print(f"\n[install] BRICK ALIVE: {m.get('brick_id')}")
    print(f"[install] root: {ROOT} · identity + skills + backlog + death warrant + keys (outside repo)")
    print(f"[install] death warrant armed: lifetime={m.get('death_warrant',{}).get('lifetime_max_s',7200)}s "
          f"spend=${m.get('death_warrant',{}).get('spend_max_usd',1.00)} "
          f"idle={m.get('death_warrant',{}).get('idle_max_s',300)}s seeder={m.get('death_warrant',{}).get('seeder_mode',False)}")
    print(f"[install] next: boot the headless worker (headless_worker.py) as this brick's ENTRYPOINT")

if __name__ == "__main__":
    main()
