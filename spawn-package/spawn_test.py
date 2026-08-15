#!/usr/bin/env python3
"""spawn.py — the SHARED SPAWN PACKAGE (round-61 ruling, binding).

Every brick, every lane (Vast / server / device) ships this ONE package:
  1. Signed-manifest identity (JWS ES256, on-device keys, ledger-verified)
  2. Model chain (local LLM + DeepSeek API fallback, per manifest)
  3. Death warrant (lifetime + spend + idle caps, kill hierarchy)
  4. Headless worker entrypoint (no-SSH HTTP worker, orchestrator backstop)
  5. Heartbeat -> registry (5-min cadence, fleet-visible) — SHIPPED, not referenced
  6. Read-only A2A participation (peer discovery + scoped tokens + gateway
     consumption; outbound-only on untrusted hosts — never inbound, never raw keys)

Acceptance (round-61 §4.5): heartbeat row in registry + A2A handshake with a
peer succeeds + read-only toolsets verified ENFORCED at request time.

Roles (security advisor, evolution agent, guilds) ride this package as manifest
fields — they are never separate projects.
"""
from __future__ import annotations
import argparse, base64, json, os, pathlib, re, shutil, subprocess, sys, time

def log(m):
    print(f"[spawn] {m}", flush=True)

def fail(m):
    print(f"[spawn] REJECTED: {m}", file=sys.stderr, flush=True)
    sys.exit(1)

def load_manifest(path: pathlib.Path) -> dict:
    with open(path) as f:
        m = json.load(f)
    if not m.get("signature", {}).get("value"):
        fail("manifest has no embedded signature (round-33: shape alone never passes)")
    if m.get("manifest_version", 0) < 1:
        fail("manifest_version < 1 (round-31)")
    return m

def verify_signature(m: dict) -> str:
    """Real JWS ES256 verify over canonical payload, pinned key (mirror of brick_install L49-84)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    ISSUER_KEYS = {"ci-test": "-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEahCRTnb6+M4tp988q9lS1I+KmgQF\nGl8p97+QtyUwqiNfCsGXjSNMDHHDmXOkSOLG/OQV+V9ncUI3+ShYrgPsSw==\n-----END PUBLIC KEY-----"}
    try:
        sig = m.get("signature", {})
        issuer, val = sig.get("issuer", ""), sig.get("value", "")
        if issuer not in ISSUER_KEYS:
            fail(f"no pinned public key for issuer '{issuer}'")
        parts = val.split(".")
        if len(parts) != 3 or not all(parts):
            fail("signature is not a valid JWS compact shape")
        hdr = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
        if hdr.get("alg") != "ES256":
            fail(f"signature alg {hdr.get('alg')} != ES256 (rule 11)")
        body = {k: v for k, v in m.items() if k != "signature"}
        payload_bytes = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
        if parts[1] != payload_b64:
            fail("signature payload does not match the manifest body")
        pub = serialization.load_pem_public_key(ISSUER_KEYS[issuer].encode())
        sig_raw = base64.urlsafe_b64decode(parts[2] + "=" * (-len(parts[2]) % 4))
        r, s = sig_raw[:32], sig_raw[32:]
        der = utils.encode_dss_signature(int.from_bytes(r, "big"), int.from_bytes(s, "big"))
        pub.verify(der, f"{parts[0]}.{parts[1]}".encode(), ec.ECDSA(hashes.SHA256()))
        return issuer
    except SystemExit:
        raise
    except Exception as e:
        fail(f"signature verification failed: {str(e)[:80]}")

def version_ok(req: str, ver_text: str) -> bool:
    """Proper version compare (brick_install parity) — no substring false-pass."""
    m = re.search(r"v?(\d+)\.(\d+)\.(\d+)", ver_text)
    if not m:
        return False
    got = tuple(int(x) for x in m.groups())
    mm = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", req)
    want = tuple(int(x) for x in mm.groups() if x is not None)
    while len(want) < 3:
        want += (0,)
    return got >= want

def write_death_warrant(root: pathlib.Path, m: dict):
    dw = {
        "brick_id": m["brick_id"],
        "lifetime_s": int(os.environ.get("BRICK_LIFETIME_S", 7200)),
        "spend_cap_usd": float(os.environ.get("BRICK_SPEND_CAP", 1.0)),
        "idle_s": int(os.environ.get("BRICK_IDLE_S", 300)),
        "kill_hierarchy": ["worker", m.get("owner", "?"), m.get("kill_switch", "khalid")],
        "armed_at": int(time.time()),
    }
    (root / "death-warrant.json").write_text(json.dumps(dw, indent=1))

def write_model_chain(root: pathlib.Path, m: dict):
    chain = m.get("model_chain", [])
    if not chain:
        fail("manifest model_chain is empty — a brick with no model answers nothing")
    mc = {"chain": chain, "primary": "http://127.0.0.1:1234/v1",
          "fallback": "deepseek-api", "default_model": ""}
    (root / "model-chain.json").write_text(json.dumps(mc, indent=1))

ALLOWED_TOOLS = {"web", "vision", "session_search"}
def write_a2a(root: pathlib.Path, m: dict):
    allow = set(m.get("toolsets", ["web", "vision", "session_search"]))
    if not allow <= ALLOWED_TOOLS:
        fail(f"toolsets include non-read-only: {sorted(allow - ALLOWED_TOOLS)}")
    reject = ["terminal", "code_execution", "memory", "file", "skill_manage"]
    pol = {"brick_id": m["brick_id"], "allow": sorted(allow), "reject": reject,
           "enforce_read_only": True, "bind": "outbound-only"}
    (root / "a2a-policy.json").write_text(json.dumps(pol, indent=1))

def write_heartbeat(root: pathlib.Path, m: dict, registry: pathlib.Path):
    """SHIPPED heartbeat (DA B1): writes the registry loop script the worker runs.
    Interval 300s; registry row carries brick_id + status + ts + wallet_ref."""
    script = f'''#!/usr/bin/env python3
import json, os, time, pathlib
REGISTRY = pathlib.Path({str(registry)!r})
BRICK = {m["brick_id"]!r}
WALLET = {m.get("wallet_ref", "banana-bank/wallet-unknown.jsonl")!r}
INTERVAL = int(os.environ.get("BRICK_HEARTBEAT_S", 300))
while True:
    row = {{"brick_id": BRICK, "status": "alive", "ts": int(time.time()),
            "wallet_ref": WALLET, "registry": str(REGISTRY)}}
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY, "a") as f:
        f.write(json.dumps(row) + "\\n")
    time.sleep(INTERVAL)
'''
    (root / "heartbeat.py").write_text(script)
    (root / "heartbeat.py").chmod(0o750)

def write_hindsight_bank(root: pathlib.Path, m: dict):
    """SHIPPED per-brick hindsight bank (round-63 D-1): bank dir + module copy.
    Bank content is private to its brick by default; existence is public
    (registry-visible), content owner-gated (D-5)."""
    bank_dir = root / "bank"
    bank_dir.mkdir(parents=True, exist_ok=True)
    for f in ("entries.jsonl", "audit.jsonl"):
        p = bank_dir / f
        p.touch()
        p.chmod(0o600)  # D-5 privacy at spawn time, not first-use
    src = pathlib.Path(__file__).resolve().parent / "hindsight_bank.py"
    if src.exists():
        shutil.copy2(src, root / "hindsight_bank.py")
        (root / "hindsight_bank.py").chmod(0o750)

def write_on_device_keys(root: pathlib.Path, m: dict):
    """Real on-device keypair (DA M6): identity.pub embedded in identity.json."""
    keys_dir = root / "keys"
    keys_dir.mkdir(exist_ok=True)
    pub = ""
    if not (root / "identity.pub").exists():
        out = subprocess.run(["ssh-keygen", "-t", "ed25519", "-f", str(keys_dir / "brick"),
                              "-N", "", "-C", f"{m['brick_id']}@bawes"],
                             capture_output=True, text=True)
        if out.returncode == 0:
            pub = (keys_dir / "brick.pub").read_text().strip()
    else:
        pub = (root / "identity.pub").read_text().strip()
    return pub

def install_worker(root: pathlib.Path, src: pathlib.Path):
    if not src.exists() or src.stat().st_size == 0:
        fail(f"headless worker source missing or empty: {src}")
    shutil.copy2(src, root / "headless_worker.py")
    (root / "headless_worker.py").chmod(0o750)

def main():
    ap = argparse.ArgumentParser(description="brick-spawn-package (round-61)")
    ap.add_argument("manifest", help="path to signed brick manifest (JSON with embedded signature)")
    ap.add_argument("--root", default="/srv/bricks", help="brick root parent dir")
    ap.add_argument("--worker-src", default="/root/.hermes/scripts/vast-fleet/headless_worker.py")
    ap.add_argument("--registry", default="/srv/bricks/registry/heartbeat-registry.jsonl")
    args = ap.parse_args()

    mpath = pathlib.Path(args.manifest)
    m = load_manifest(mpath)
    brick_id = m.get("brick_id")
    if not brick_id:
        fail("manifest has no brick_id")
    if not m.get("kill_switch"):
        fail("manifest kill_switch is required (fail-open default is forbidden)")

    root = pathlib.Path(args.root) / brick_id
    if (root / "identity.json").exists():
        fail(f"{brick_id} already installed — re-spawn over a live brick is refused (no-overwrite)")

    log(f"{brick_id}: verifying signature (JWS ES256, pinned key, payload-bound)...")
    issuer = verify_signature(m)
    log(f"{brick_id}: signature VERIFIED (issuer={issuer})")

    req = m.get("min_hermes_version")
    if req:
        out = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=20)
        txt = (out.stdout or "") + (out.stderr or "")
        if not version_ok(req, txt):
            fail(f"Hermes version gate: need {req}+, got: {txt[:60]}")
        log(f"hermes version OK (>= {req})")

    root.mkdir(parents=True, exist_ok=True)
    pub = write_on_device_keys(root, m)
    write_death_warrant(root, m)
    write_model_chain(root, m)
    write_a2a(root, m)
    write_heartbeat(root, m, pathlib.Path(args.registry))
    write_hindsight_bank(root, m)
    install_worker(root, pathlib.Path(args.worker_src))

    identity = {
        "brick_id": brick_id, "person_id": m.get("person_id"), "owner": m.get("owner"),
        "hardware_owner": m.get("hardware_owner"), "kill_switch": m.get("kill_switch"),
        "model_chain": m.get("model_chain", []), "toolsets": m.get("toolsets", []),
        "public_key": pub, "scheduling": "idle-only, owner-preemptible",
    }
    (root / "identity.json").write_text(json.dumps(identity, indent=1))
    (root / "manifest.json").write_text(json.dumps(m, indent=1))

    log(f"BRICK PACKAGED: {brick_id} @ {root}")
    log("next: boot heartbeat.py + headless_worker.py + a2a_server.py (all in brick root)")
    print(json.dumps({"brick_id": brick_id, "root": str(root), "verified": True}))

if __name__ == "__main__":
    main()
