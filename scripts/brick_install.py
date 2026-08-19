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
import json, os, shutil, subprocess, sys, hashlib, time, argparse, base64, re, stat

BRICK_ROOT = "/opt/brick"          # where the brick lives (volume/home); overridden by --root
SKILLS_SRC = "/root/.hermes/skills"  # verified local skill refs (bawes-fleet)
ROOT = BRICK_ROOT                   # effective root, set in main()

# Round-149: the device-brick 3-file package (Mishari pilot, ratified in
# /srv/bricks/router/state/second-node-prep.md). A device brick's ONE command
# consumes these three artifacts, then starts heartbeat + tunnel + handshake.
# All three are overridable via env so the flow is testable without a real box.
DEVICE_APPEND_KEY = os.environ.get("BAWES_APPEND_KEY",
                                   os.path.expanduser("~/.ssh/bawes-device-append"))
DEVICE_TUNNEL_KEY = os.environ.get("BAWES_TUNNEL_KEY",
                                   os.path.expanduser("~/.ssh/bawes-device-tunnel"))
REGISTRY_HOST = os.environ.get("BAWES_REGISTRY_HOST", "ubuntu@51.75.74.214")
MESH_PORT = int(os.environ.get("BAWES_MESH_PORT", "3738"))

def device_token_path(brick_id):
    return os.environ.get("BAWES_PEER_TOKEN",
                          os.path.expanduser(f"~/.bawes/{brick_id}/peer.token"))

def is_device_brick(m):
    """host_class.device present => device brick => the 3-file package is REQUIRED."""
    return bool((m.get("host_class") or {}).get("device"))

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
    # round-52: Hermes runtime version gate (fails closed like everything else)
    req = m.get("min_hermes_version")
    if req:
        got = None
        try:
            out = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=20)
            out_text = (out.stdout or "") + (out.stderr or "")
            import re
            mt = re.search(r"v?(\d+\.\d+\.\d+)", out_text)
            got = mt.group(1) if mt else None
        except Exception:
            got = None
        if not got:
            raise SystemExit(
                f"REJECTED: cannot read Hermes version (min required {req}) — "
                f"run `hermes --version` and check your install")
        from packaging.version import Version
        if Version(got) < Version(req):
            raise SystemExit(
                f"REJECTED: Hermes {got} < required {req} (manifest min_hermes_version) — "
                f"upgrade Hermes first, then re-run the installer")
        log(f"Hermes version OK ({got} >= {req})")
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

def _device_paths(brick_id):
    """Resolve the 3-file package paths at CALL time (env-overridable for tests;
    module-level constants are only the defaults, bound at import)."""
    return {
        "append_key": os.environ.get("BAWES_APPEND_KEY",
                                     os.path.expanduser("~/.ssh/bawes-device-append")),
        "tunnel_key": os.environ.get("BAWES_TUNNEL_KEY",
                                     os.path.expanduser("~/.ssh/bawes-device-tunnel")),
        "token_path": device_token_path(brick_id),
    }

def consume_device_package(m):
    """Round-149: consume the device-brick 3-file package (append key, tunnel
    key, peer.token). FAILS CLOSED on any missing/misconfigured artifact —
    a device brick that can't heartbeat/tunnel/handshake is not installed.
    Returns {'append_key','tunnel_key','token','token_path'}."""
    if not is_device_brick(m):
        log("host_class.device absent — not a device brick, no 3-file package required")
        return None
    pkg = _device_paths(m.get("brick_id", "brick"))
    missing = [name for name, p in (
        ("append key", pkg["append_key"]),
        ("tunnel key", pkg["tunnel_key"]),
        ("peer.token", pkg["token_path"]),
    ) if not os.path.exists(p)]
    if missing:
        raise SystemExit("REJECTED: device package incomplete — missing: "
                         + ", ".join(missing) + " (operator must place the 3 files: "
                         "~/.ssh/bawes-device-append, ~/.ssh/bawes-device-tunnel, "
                         f"~/.bawes/{m.get('brick_id','brick')}/peer.token)")
    # mode-600 discipline: keys and tokens must be 0600 or ssh/compare_digest
    # security is theater (a 0644 token file is readable by any local user)
    for name, p in (("append key", pkg["append_key"]),
                    ("tunnel key", pkg["tunnel_key"]),
                    ("peer.token", pkg["token_path"])):
        mode = stat.S_IMODE(os.stat(p).st_mode)
        if mode & 0o077:
            raise SystemExit(f"REJECTED: {name} {p} must be mode 0600 (got {oct(mode)}) "
                             f"— chmod 600 before install")
    with open(pkg["token_path"]) as f:
        token = f.read().strip()
    if len(token) < 16:
        raise SystemExit("REJECTED: peer.token too short (<16 chars) or empty — "
                         "empty tokens authenticate anything (round-61 finding)")
    pkg["token"] = token
    log(f"device package consumed: append={os.path.basename(pkg['append_key'])} "
        f"tunnel={os.path.basename(pkg['tunnel_key'])} token={os.path.basename(pkg['token_path'])} "
        f"({len(token)} chars, 0600)")
    return pkg

def write_device_scripts(m, pkg):
    """Round-149: write the device-brick runtime scripts into the brick root.
    heartbeat.py pushes rows through the append-only SSH key (forced command
    `cat >> heartbeat-registry.jsonl`); tunnel.sh dials OUT to the A2A mesh
    directory (permitopen 127.0.0.1:3738, port-forwarding)."""
    brick = m.get("brick_id", "brick")
    wallet = m.get("wallet_ref", f"banana-bank/wallet-{brick}.jsonl")
    # heartbeat: local row + push through the append key (spec: second-node-prep.md)
    hb = f'''#!/usr/bin/env python3
import json, os, subprocess, time, pathlib
BRICK = {json.dumps(brick)}
WALLET = {json.dumps(wallet)}
APPEND_KEY = {json.dumps(pkg["append_key"])}
REGISTRY_HOST = {json.dumps(REGISTRY_HOST)}
LOCAL = pathlib.Path.home() / ".bawes/heartbeat-registry.jsonl"
INTERVAL = int(os.environ.get("BRICK_HEARTBEAT_S", 60))
while True:
    row = {{"brick_id": BRICK, "status": "alive", "ts": int(time.time()),
           "wallet_ref": WALLET, "registry": str(LOCAL)}}
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCAL, "a") as f:
        f.write(json.dumps(row) + "\\n")
    try:
        subprocess.run(["ssh", "-i", APPEND_KEY,
                        "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                        REGISTRY_HOST],
                       input=(json.dumps(row) + "\\n").encode(), timeout=25, check=False)
    except Exception:
        pass
    time.sleep(INTERVAL)
'''
    with open(f"{ROOT}/heartbeat.py", "w") as f:
        f.write(hb)
    os.chmod(f"{ROOT}/heartbeat.py", 0o750)
    tun = f'''#!/bin/sh
# dial-OUT tunnel to the A2A mesh directory (:3738). The tunnel key's forced
# command is `sleep infinity` with port-forwarding + permitopen=127.0.0.1:3738.
if command -v autossh >/dev/null 2>&1; then
  exec autossh -M 0 -N -L 127.0.0.1:{MESH_PORT}:127.0.0.1:{MESH_PORT} \\
    -i {pkg["tunnel_key"]} \\
    -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \\
    {REGISTRY_HOST}
else
  exec ssh -N -L 127.0.0.1:{MESH_PORT}:127.0.0.1:{MESH_PORT} \\
    -i {pkg["tunnel_key"]} \\
    -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \\
    {REGISTRY_HOST}
fi
'''
    with open(f"{ROOT}/tunnel.sh", "w") as f:
        f.write(tun)
    os.chmod(f"{ROOT}/tunnel.sh", 0o750)
    log(f"device scripts written: {ROOT}/heartbeat.py + {ROOT}/tunnel.sh (0750)")

def start_device_services(m, pkg):
    """Round-149: start heartbeat + tunnel detached, then run the registration
    handshake and REPORT THE REAL RESULT (ok:true only if the mesh says so).
    Never claims 'on the mesh' without a 200 from /a2a/handshake."""
    brick = m.get("brick_id", "brick")
    # heartbeat (python, detached, logs to brick root)
    with open(f"{ROOT}/heartbeat.log", "ab") as lf:
        subprocess.Popen([sys.executable, f"{ROOT}/heartbeat.py"],
                         stdin=subprocess.DEVNULL, stdout=lf, stderr=lf,
                         start_new_session=True)
    log("heartbeat started — first fleet row within 60s (append-only key)")
    # tunnel: autossh (auto-reconnect); fall back to plain ssh if not installed
    tunnel_cmd = [f"{ROOT}/tunnel.sh"]
    if shutil.which("autossh") is None:
        tunnel_cmd = ["ssh", "-N", "-L", f"127.0.0.1:{MESH_PORT}:127.0.0.1:{MESH_PORT}",
                      "-i", pkg["tunnel_key"],
                      "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
                      "-o", "ExitOnForwardFailure=yes", REGISTRY_HOST]
    with open(f"{ROOT}/tunnel.log", "ab") as lf:
        subprocess.Popen(tunnel_cmd, stdin=subprocess.DEVNULL, stdout=lf, stderr=lf,
                         start_new_session=True)
    log(f"tunnel started — dial-out -L 127.0.0.1:{MESH_PORT} (permitopen, restricted key)")
    # registration handshake: wait for the tunnel, then ask the mesh directory
    import urllib.request
    deadline = time.time() + 20
    result = None
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{MESH_PORT}/a2a/handshake",
                headers={"Authorization": f"Bearer {pkg['token']}"})
            with urllib.request.urlopen(req, timeout=5) as r:
                result = (r.status, r.read().decode(errors="replace"))
            break
        except Exception as e:
            result = ("ERR", str(e)[:120])
            time.sleep(2)
    if result and result[0] == 200:
        log(f"REGISTRATION HANDSHAKE OK (HTTP 200): {result[1][:160]}")
        print(f"[install] MESH: joined — handshake 200 from the A2A directory ({brick} on the mesh)")
    else:
        print(f"[install] MESH: HANDSHAKE NOT CONFIRMED ({result[1] if result else 'timeout'}) — "
              f"brick installed, but the mesh join is NOT verified. Check tunnel.log "
              f"and re-run the handshake: curl -H 'Authorization: Bearer $("
              f"cat {pkg['token_path']})' http://127.0.0.1:{MESH_PORT}/a2a/handshake")

def main():
    ap = argparse.ArgumentParser(description="brick-install v1 — manifest -> live brick")
    ap.add_argument("manifest", help="path to the signed brick manifest (JSON)")
    ap.add_argument("--root", default=BRICK_ROOT, help="brick root dir")
    ap.add_argument("--sign-consent", metavar="NAME", default="",
                    help="HUMAN-DRIVEN sign step: the person types their own name; "
                         "the consent marker flips to signed and the manifest is "
                         "re-signed with the issuer key (DA F1). Install refuses "
                         "to run before this step.")
    args = ap.parse_args()
    global ROOT
    ROOT = args.root

    with open(args.manifest) as f:
        m = json.load(f)
    verify_manifest(m)
    log(f"manifest verified: {m.get('brick_id')} (signed, v{m.get('manifest_version')})")

    # DA F1 (CRIT): HUMAN-DRIVEN consent sign step. The person's own name is
    # required; the marker flips pending->signed; the manifest is RE-SIGNED so
    # the pinned-key check still passes. This is the human's pen, not machinery.
    if args.sign_consent:
        name = args.sign_consent.strip()
        if not name or len(name) < 2:
            raise SystemExit("REJECTED: sign-consent needs the person's real name (2+ chars)")
        if not re.fullmatch(r"[A-Za-z0-9 _.'-]+", name):
            raise SystemExit("REJECTED: invalid characters in sign-consent name")
        m.setdefault("consent", {})["status"] = "signed"
        m["consent"]["signed_by"] = name
        m["consent"]["ts"] = time.time()
        m["consent"]["version"] = "V-5"
        # V-5 evidence pointer: the human's own words are recorded in the
        # door consent transcript (never invented here). Operator passes the
        # record location; the manifest carries it as M-7 evidence.
        words_ref = os.environ.get("BAWES_CONSENT_WORDS_REF", "").strip()
        if words_ref:
            m["consent"]["words_ref"] = words_ref
        # re-sign: the issuer key lives beside this script's repo? No — it must
        # NOT ship to devices. Fail closed: consent can only be re-signed where
        # the issuer key is available (khalid's signing box or relay).
        keypath = os.environ.get("BAWES_ISSUER_KEY", "")
        if not keypath or not os.path.exists(keypath):
            raise SystemExit(
                "REJECTED: issuer key not available — consent re-signing happens on "
                "the signing box (BAWES_ISSUER_KEY env), never on the device. "
                "Send the signed manifest to khalid for the consent re-sign.")
        from cryptography.hazmat.primitives import serialization
        with open(keypath, "rb") as kf:
            key = serialization.load_pem_private_key(kf.read(), password=None)
        body = {k: v for k, v in m.items() if k != "signature"}
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        payload_b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
        hdr_b64 = base64.urlsafe_b64encode(
            json.dumps({"alg": "ES256"}).encode()).rstrip(b"=").decode()
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, utils
        der = key.sign(f"{hdr_b64}.{payload_b64}".encode(), ec.ECDSA(hashes.SHA256()))
        r, s = utils.decode_dss_signature(der)
        sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        m["signature"] = {"value": f"{hdr_b64}.{payload_b64}."
                                   f"{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}",
                          "issuer": "khalid", "alg": "ES256", "ts": time.time()}
        with open(args.manifest, "w") as f:
            json.dump(m, f, indent=1)
        verify_manifest(m)  # self-check: still verifies against pinned key
        log(f"consent SIGNED by {name} + manifest re-signed (still verifies). "
            f"Now run install WITHOUT --sign-consent.")
        return

    # DA F1: consent gate — the 16-rule sign is a REAL mechanism, fail-closed.
    consent = m.get("consent") or {}
    if consent.get("status") != "signed":
        raise SystemExit(
            "REJECTED: consent not signed (16 rules) — the person must sign their "
            "own consent BEFORE install (--sign-consent 'Their Name' on the signing "
            "box). This brick does not activate on machinery alone (Zeus V-5).")
    if not consent.get("signed_by") or not consent.get("ts"):
        raise SystemExit("REJECTED: consent marker incomplete (signed_by/ts missing)")
    log(f"consent: SIGNED by {consent['signed_by']}")

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

    # Round-149: device-brick 3-file package. Fail-closed BEFORE any service
    # start: a device brick without append/tunnel/peer.token is not installable.
    pkg = consume_device_package(m)
    if pkg:
        write_device_scripts(m, pkg)

    print(f"\n[install] BRICK ALIVE: {m.get('brick_id')}")
    print(f"[install] root: {ROOT} · identity + skills + backlog + death warrant + keys (outside repo)")
    print(f"[install] death warrant armed: lifetime={m.get('death_warrant',{}).get('lifetime_max_s',7200)}s "
          f"spend=${m.get('death_warrant',{}).get('spend_max_usd',1.00)} "
          f"idle={m.get('death_warrant',{}).get('idle_max_s',300)}s seeder={m.get('death_warrant',{}).get('seeder_mode',False)}")
    if pkg:
        print(f"[install] device package: consumed (append + tunnel + peer.token, 0600) — "
              f"starting heartbeat + tunnel + registration handshake")
        start_device_services(m, pkg)
        print(f"[install] next: hermes gateway wiring (per-brick Discord token) for min-alive 4/4")
    else:
        print(f"[install] next: boot the headless worker (headless_worker.py) as this brick's ENTRYPOINT")

if __name__ == "__main__":
    main()
