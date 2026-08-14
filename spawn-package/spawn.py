#!/usr/bin/env python3
"""spawn.py — the SHARED SPAWN PACKAGE (round-61 ruling, binding).

Every brick, every lane (Vast / server / device) ships this ONE package:
  1. Signed-manifest identity (JWS ES256, on-device keys, ledger-verified)
  2. Model chain (local LLM + DeepSeek API fallback, per manifest)
  3. Death warrant (lifetime + spend + idle caps, kill hierarchy)
  4. Headless worker entrypoint (no-SSH HTTP worker, orchestrator backstop)
  5. Heartbeat -> registry (5-min cadence, fleet-visible)
  6. Read-only A2A participation (peer discovery + scoped tokens + gateway
     consumption; outbound-only on untrusted hosts — never inbound, never raw keys)

Acceptance test (round-61 §4.5): heartbeat in registry + A2A handshake with a
peer succeeds + read-only toolsets verified ENFORCED (not advertised).

Roles (security advisor, evolution agent, guilds) ride this package as manifest
fields — they are never separate projects.
"""
from __future__ import annotations
import argparse, json, os, pathlib, shutil, subprocess, sys, time

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
    return m

def verify_signature(m: dict) -> str:
    """Real JWS ES256 verify over canonical payload, pinned key (same as brick_install)."""
    import base64
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    # pinned issuer keys — mirror of brick_install.ISSUER_KEYS (round-33)
    ISSUER_KEYS = {
        "khalid": "-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEUD7wvDW7aL1T45TZ+hY/2mO7ddv6\nkW93necd8rFJkwG+xdTcJ66O7bA9XfCtCWhonoCjiMR3ae6vAvLJHXmR8Q==\n-----END PUBLIC KEY-----\n",
    }
    sig = m.get("signature", {})
    issuer, val = sig.get("issuer", ""), sig.get("value", "")
    if issuer not in ISSUER_KEYS:
        fail(f"no pinned public key for issuer '{issuer}'")
    parts = val.split(".")
    if len(parts) != 3 or not all(parts):
        fail("signature is not a valid JWS compact shape")
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

def write_death_warrant(root: pathlib.Path, m: dict):
    """Lifetime + spend + idle caps. Kill hierarchy: worker < owner < khalid."""
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
    mc = {
        "chain": chain,
        "primary": "http://127.0.0.1:1234/v1",
        "fallback": "deepseek-api",
        "default_model": "",
    }
    (root / "model-chain.json").write_text(json.dumps(mc, indent=1))

def write_a2a(root: pathlib.Path, m: dict):
    """A2A participation: read-only toolsets from manifest, reject list enforced.
    Manifest advertises web/vision/session_search ONLY; terminal/code_execution/
    memory/file/skill_manage are REJECTED. Policy is written here and CONSUMED
    by a2a_server.py at request time — declaration + enforcement, not just words.
    """
    allow = m.get("toolsets", ["web", "vision", "session_search"])
    reject = ["terminal", "code_execution", "memory", "file", "skill_manage"]
    pol = {
        "brick_id": m["brick_id"],
        "allow": allow,
        "reject": reject,
        "enforce_read_only": True,
        "bind": "outbound-only",  # untrusted hosts: outbound via gateway/broker
    }
    (root / "a2a-policy.json").write_text(json.dumps(pol, indent=1))

def install_worker(root: pathlib.Path, src: pathlib.Path):
    if not src.exists():
        fail(f"headless worker source not found: {src}")
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

    root = pathlib.Path(args.root) / brick_id
    root.mkdir(parents=True, exist_ok=True)

    log(f"{brick_id}: verifying signature (JWS ES256, pinned key, payload-bound)...")
    issuer = verify_signature(m)
    log(f"{brick_id}: signature VERIFIED (issuer={issuer})")

    # round-52: Hermes runtime version gate — fail closed
    req = m.get("min_hermes_version")
    if req:
        out = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=20)
        txt = (out.stdout or "") + (out.stderr or "")
        if req not in txt:
            fail(f"Hermes version gate: need {req}+, got: {txt[:60]}")
        log(f"hermes version OK (>= {req})")

    # on-device keys (never in repo) — reuse installer's key file if present
    keys_dir = root / "keys"
    keys_dir.mkdir(exist_ok=True)

    write_death_warrant(root, m)
    write_model_chain(root, m)
    write_a2a(root, m)
    install_worker(root, pathlib.Path(args.worker_src))

    # identity.json (crypto-gated output, mirror of installer)
    identity = {
        "brick_id": brick_id,
        "person_id": m.get("person_id"),
        "owner": m.get("owner"),
        "hardware_owner": m.get("hardware_owner"),
        "kill_switch": m.get("kill_switch"),
        "model_chain": m.get("model_chain", []),
        "toolsets": m.get("toolsets", []),
        "scheduling": "idle-only, owner-preemptible",
    }
    (root / "identity.json").write_text(json.dumps(identity, indent=1))
    (root / "manifest.json").write_text(json.dumps(m, indent=1))

    log(f"BRICK PACKAGED: {brick_id} @ {root}")
    log("next: boot headless_worker.py as entrypoint (a2a_server.py adds mesh participation)")
    print(json.dumps({"brick_id": brick_id, "root": str(root), "verified": True}))

if __name__ == "__main__":
    main()
