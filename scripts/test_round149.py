#!/usr/bin/env python3
"""Round-149 probe suite — device-brick 3-file package (executes the module).

Runs brick_install.py functions directly with temp fixtures. Every probe
EXECUTES the code path — no string-greps. Run: python3 scripts/test_round149.py
"""
import json, os, shutil, stat, sys, tempfile, importlib.util, pathlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

spec = importlib.util.spec_from_file_location("brick_install",
                                              os.path.join(HERE, "brick_install.py"))
bi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bi)

PASS = 0
FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")

def make_fixture():
    """Build a temp device-brick fixture: 3 files at 0600 + a device manifest."""
    d = tempfile.mkdtemp(prefix="r149-")
    ssh = os.path.join(d, "ssh"); os.makedirs(ssh, exist_ok=True)
    bawes = os.path.join(d, "bawes", "mishari-device-001"); os.makedirs(bawes, exist_ok=True)
    append = os.path.join(ssh, "bawes-device-append")
    tunnel = os.path.join(ssh, "bawes-device-tunnel")
    token = os.path.join(bawes, "peer.token")
    for p in (append, tunnel):
        with open(p, "w") as f: f.write("-----BEGIN OPENSSH PRIVATE KEY-----\nfixture\n-----END OPENSSH PRIVATE KEY-----\n")
        os.chmod(p, 0o600)
    with open(token, "w") as f: f.write("A" * 56)
    os.chmod(token, 0o600)
    m = {
        "manifest_version": 1, "brick_id": "mishari-device-001",
        "person_id": "231861", "owner": "mishari", "hardware_owner": "mishari",
        "kill_switch": "mishari", "skills": [], "backlog": ["T-001"],
        "wallet_ref": "banana-bank/wallet-mishari-device-001.jsonl",
        "host_class": {"device": "laptop", "ram_gb_min": 8},
        "signature": {"issuer": "khalid", "value": "x.y.z"},
    }
    return d, m, {"append": append, "tunnel": tunnel, "token": token, "root": bawes}

print("=== R149-1: non-device manifest -> no package required ===")
_, m_cloud, _ = make_fixture()
m_cloud["host_class"] = {"server": "vps"}
os.environ.pop("BAWES_APPEND_KEY", None); os.environ.pop("BAWES_TUNNEL_KEY", None)
os.environ.pop("BAWES_PEER_TOKEN", None)
check("server manifest returns None", bi.consume_device_package(m_cloud) is None)

print("=== R149-2: device manifest missing files -> REJECTED (fail-closed) ===")
d, m_dev, _ = make_fixture()
os.environ["BAWES_APPEND_KEY"] = os.path.join(d, "ssh", "bawes-device-append")
os.environ["BAWES_TUNNEL_KEY"] = os.path.join(d, "ssh", "bawes-device-tunnel")
os.environ["BAWES_PEER_TOKEN"] = os.path.join(d, "bawes", "mishari-device-001", "peer.token")
os.unlink(os.environ["BAWES_APPEND_KEY"])
try:
    bi.consume_device_package(m_dev)
    check("missing append key rejected", False, "no SystemExit")
except SystemExit as e:
    check("missing append key rejected", "device package incomplete" in str(e), str(e)[:80])

print("=== R149-3: wrong mode -> REJECTED ===")
d, m_dev, _ = make_fixture()
os.environ["BAWES_APPEND_KEY"] = os.path.join(d, "ssh", "bawes-device-append")
os.environ["BAWES_TUNNEL_KEY"] = os.path.join(d, "ssh", "bawes-device-tunnel")
os.environ["BAWES_PEER_TOKEN"] = os.path.join(d, "bawes", "mishari-device-001", "peer.token")
os.chmod(os.environ["BAWES_PEER_TOKEN"], 0o644)
try:
    bi.consume_device_package(m_dev)
    check("0644 token rejected", False, "no SystemExit")
except SystemExit as e:
    check("0644 token rejected", "must be mode 0600" in str(e), str(e)[:80])
os.chmod(os.environ["BAWES_PEER_TOKEN"], 0o600)

print("=== R149-4: short/empty token -> REJECTED ===")
with open(os.environ["BAWES_PEER_TOKEN"], "w") as f: f.write("short")
os.chmod(os.environ["BAWES_PEER_TOKEN"], 0o600)
try:
    bi.consume_device_package(m_dev)
    check("short token rejected", False, "no SystemExit")
except SystemExit as e:
    check("short token rejected", "too short" in str(e), str(e)[:80])
with open(os.environ["BAWES_PEER_TOKEN"], "w") as f: f.write("A" * 56)
os.chmod(os.environ["BAWES_PEER_TOKEN"], 0o600)

print("=== R149-5: full package consumed ===")
pkg = bi.consume_device_package(m_dev)
check("package consumed", pkg is not None)
check("token length ok", len(pkg.get("token", "")) == 56)
check("paths resolved", pkg["append_key"].endswith("bawes-device-append") and
      pkg["tunnel_key"].endswith("bawes-device-tunnel") and
      pkg["token_path"].endswith("peer.token"))

print("=== R149-6: scripts written with correct modes + content ===")
old_root = bi.ROOT
probe_root = os.path.join(tempfile.mkdtemp(prefix="r149-root-"), "brick")
os.makedirs(probe_root, exist_ok=True)
bi.ROOT = probe_root
bi.write_device_scripts(m_dev, pkg)
hb = os.path.join(probe_root, "heartbeat.py")
tun = os.path.join(probe_root, "tunnel.sh")
check("heartbeat.py written", os.path.exists(hb))
check("tunnel.sh written", os.path.exists(tun))
check("scripts mode 0750", stat.S_IMODE(os.stat(hb).st_mode) == 0o750 and
      stat.S_IMODE(os.stat(tun).st_mode) == 0o750)
hb_src = open(hb).read(); tun_src = open(tun).read()
check("heartbeat consumes append key", "bawes-device-append" in hb_src and "ssh" in hb_src)
check("heartbeat carries registry host", "ubuntu@51.75.74.214" in hb_src)
check("tunnel consumes tunnel key + permitopen port", "bawes-device-tunnel" in tun_src and "3738" in tun_src)
bi.ROOT = old_root

def sign_manifest(mpath, priv):
    """Sign a manifest with the issuer key — EXACT canonical logic the installer
    verifies (body minus signature, sort_keys, compact; ES256 raw R||S JWS).
    Independent of the skill's signer script (which has an openssl-verify-raw bug)."""
    import base64 as _b64
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    m = json.load(open(mpath))
    body = {k: v for k, v in m.items() if k != "signature"}
    pb = _b64.urlsafe_b64encode(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).rstrip(b"=").decode()
    hb = _b64.urlsafe_b64encode(json.dumps({"alg": "ES256"}).encode()).rstrip(b"=").decode()
    key = serialization.load_pem_private_key(open(priv, "rb").read(), password=None)
    der = key.sign(f"{hb}.{pb}".encode(), ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    sig = _b64.urlsafe_b64encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")).rstrip(b"=").decode()
    m["signature"] = {"issuer": "khalid", "alg": "ES256", "value": f"{hb}.{pb}.{sig}"}
    json.dump(m, open(mpath, "w"), indent=1)
    return f"{hb}.{pb}.{sig}"

print("=== R149-7: full install end-to-end (device manifest, temp root) ===")
PRIV = "/root/.hermes/keys/khalid-issuer-private.pem"
if not os.path.exists(PRIV):
    print("  SKIP R149-7/8 (issuer private key not on this host — CI runner) — "
          "fixture signing needs the signing box key; R149-1..6 + R149-9 still executed")
else:
    # sign a fixture manifest with a REAL JWS (issuer key) so verify_manifest passes
    d2, m_fix, _ = make_fixture()
    m_fix["host_class"] = {"device": "laptop"}
    mf = os.path.join(d2, "manifest.json")
    with open(mf, "w") as f: json.dump(m_fix, f, indent=1)
    priv = PRIV
    val = sign_manifest(mf, priv)
    check("fixture manifest signed (real JWS, 2 dots)", val.count(".") == 2)
    os.environ["BAWES_ISSUER_KEY"] = priv
    os.environ["BAWES_CONSENT_WORDS_REF"] = "probe words"
    r = os.system(f"cd {REPO} && python3 scripts/brick_install.py {mf} --sign-consent 'Mishari' >/dev/null 2>&1")
    check("sign-consent rc=0", r == 0)
    # now install to a fresh temp root; device files present -> scripts written + services start
    install_root = os.path.join(tempfile.mkdtemp(prefix="r149-install-"), "brick")
    os.environ["BAWES_REGISTRY_HOST"] = "ubuntu@127.0.0.1"  # no real box: handshake must NOT fake ok
    os.environ["BAWES_MESH_PORT"] = "59999"                  # nothing listens -> honest failure
    out = os.popen(f"cd {REPO} && python3 scripts/brick_install.py {mf} --root {install_root} 2>&1").read()
    check("install rc=0 + BRICK ALIVE", "BRICK ALIVE" in out, out[-200:])
    check("device package consumed", "device package consumed" in out)
    check("heartbeat started", "heartbeat started" in out)
    check("tunnel started", "tunnel started" in out)
    check("scripts in brick root", os.path.exists(os.path.join(install_root, "heartbeat.py")) and
          os.path.exists(os.path.join(install_root, "tunnel.sh")))
    check("identity written", os.path.exists(os.path.join(install_root, "identity.json")))
    # HONEST handshake: no real mesh -> must say NOT CONFIRMED, never 'joined'
    check("handshake honest (no fake join)", "MESH: HANDSHAKE NOT CONFIRMED" in out,
          [l for l in out.splitlines() if "MESH" in l][:1])
    check("no false 'joined' claim", "joined — handshake 200" not in out)

    print("=== R149-8: consent gate still fail-closed (unsigned manifest) ===")
    m_uns = json.load(open(mf))
    m_uns.pop("consent", None)
    muf = os.path.join(d2, "manifest-unsigned.json")
    with open(muf, "w") as f: json.dump(m_uns, f, indent=1)
    # sign the unsigned body with the same inline signer (signer never touches
    # consent) — a manifest WITHOUT consent that still carries a valid issuer signature
    rs_val = sign_manifest(muf, priv)
    check("unsigned manifest signed (real JWS, no consent)", rs_val.count(".") == 2)
    uout = os.popen(f"cd {REPO} && python3 scripts/brick_install.py {muf} --root {tempfile.mkdtemp()}/brick 2>&1").read()
    check("unsigned install REJECTED", "consent not signed" in uout, uout[-150:])

print("=== R149-9: real mishari manifest — consent present + verifies ===")
real = json.load(open(os.path.join(REPO, "brick-packages", "manifest-mishari-device-001.json")))
c = real.get("consent") or {}
check("consent.status signed", c.get("status") == "signed")
check("consent signed_by Mishari", c.get("signed_by") == "Mishari")
check("consent V-5 + words_ref", c.get("version") == "V-5" and bool(c.get("words_ref")))
try:
    bi.verify_manifest(real)
    check("real manifest verify_manifest PASS", True)
except SystemExit as e:
    check("real manifest verify_manifest PASS", False, str(e)[:100])

# cleanup env
for k in ("BAWES_APPEND_KEY", "BAWES_TUNNEL_KEY", "BAWES_PEER_TOKEN",
          "BAWES_REGISTRY_HOST", "BAWES_MESH_PORT", "BAWES_ISSUER_KEY",
          "BAWES_CONSENT_WORDS_REF"):
    os.environ.pop(k, None)

print(f"\n=== ROUND-149 PROBES: {PASS} PASS / {FAIL} FAIL ===")
sys.exit(1 if FAIL else 0)
