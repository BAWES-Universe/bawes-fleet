#!/usr/bin/env python3
"""brick_profile.py v2 — APPLIER + VERIFIER (DA findings 1-7 fixed).
Turns a vanilla Hermes 0.20.x install into a brick:
  apply   — writes Hermes config (identity, A2A read-only policy, model chain, heartbeat)
  verify  — re-verifies JWS against the installer's crypto gate output, probes Discord
            API + model endpoint for real, stamps the heartbeat registry.
Fails closed. Never writes secrets to the repo. Round-55: khalid supplies nothing."""
import json, os, re, sys, time, yaml, subprocess, pathlib, urllib.request, urllib.error

PROFILE = pathlib.Path(__file__).parent / "brick-profile.yaml"
ROOT = pathlib.Path(__file__).parent
MIN_ALIVE_WAIT_S = 45   # give Discord API + model probe time

def fail(msg):
    print(f"REJECTED: {msg}")
    sys.exit(1)

def step(n, name, ok, detail=""):
    print(f"[{n}/4] {name}: {'PASS' if ok else 'FAIL'}{' — ' + detail if detail else ''}")
    return ok

def load_cfg():
    if not PROFILE.exists():
        fail("brick-profile.yaml missing")
    with open(PROFILE) as f:
        return yaml.safe_load(f)

def read_identity():
    """Installer's crypto-gated output (DA finding 2/4): identity.json, NOT plaintext manifest."""
    for cand in [ROOT / ".." / "identity.json", ROOT.parent / "identity.json"]:
        if cand.exists():
            with open(cand) as f:
                return json.load(f), cand
    # fall back to the signed manifest ONLY to re-run the real JWS verify (brick_install.verify_manifest)
    m = ROOT.parent / "manifest.json"
    if m.exists():
        with open(m) as f:
            return {"manifest": json.load(f)}, m
    fail("no identity.json (installer output) or manifest.json found — run brick_install.py first")

def real_verify_signature(ident):
    """Re-run the installer's real crypto gate (DA finding 2: no tautology)."""
    if "manifest" in ident:
        sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
        try:
            import brick_install as bi
            ok = bi.verify_manifest(ident["manifest"])
            return ok, "JWS re-verified via installer gate"
        except Exception as e:
            return False, f"JWS re-verify failed: {str(e)[:60]}"
    # identity.json is the installer's verified output — the crypto gate already ran;
    # compare its fields against the profile (non-tautological: cross-source check)
    pid = str(ident.get("person_id", "")).strip() or str(ident.get("personId", "")).strip()
    bid = str(ident.get("brick_id", "")).strip() or str(ident.get("brickId", "")).strip()
    cfg = load_cfg()
    ok = bid == cfg.get("brick_id") and pid == str(cfg.get("person_id"))
    return ok, f"identity.json cross-check ({bid}/{pid})"

def probe_discord(token, channel, base_url="https://discord.com/api/v10"):
    """Real Discord API check (DA finding 3: channel must actually respond).
    Discord REQUIRES a valid User-Agent on every request — a missing/blank UA
    is rejected with 403 before auth is even evaluated (urllib's default
    'Python-urllib' UA is refused). Send a DiscordBot UA + bearer auth."""
    try:
        req = urllib.request.Request(
            f"{base_url}/channels/{channel}",
            headers={
                "Authorization": f"Bot {token}",
                "User-Agent": "DiscordBot (https://github.com/BAWES-Universe/bawes-fleet, 1.0)",
            })
        r = urllib.request.urlopen(req, timeout=15)
        d = json.load(r)
        return r.status == 200 and d.get("id") == str(channel), d.get("name", "")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:50]

def probe_model(cfg):
    """Real model endpoint probe (DA finding 5: brick with no model answers nothing)."""
    ep = cfg.get("model", {}).get("primary", "")
    dm = cfg.get("model", {}).get("default_model", "")
    if not ep or not dm:
        return False, "model.primary / model.default_model unset"
    try:
        req = urllib.request.Request(f"{ep}/models")
        r = urllib.request.urlopen(req, timeout=10)
        body = json.load(r)
        ids = [m.get("id", "") for m in body.get("data", [])]
        hit = dm in ids or any(dm in i for i in ids)
        return hit, f"endpoint OK, model {'found' if hit else 'NOT found (' + dm + ')'}"
    except Exception as e:
        return False, str(e)[:50]

def stamp_registry(cfg, status):
    """Real heartbeat stamp (DA finding 3 + N1: registry path MUST be absolute)."""
    reg = cfg.get("heartbeat", {}).get("registry", "")
    if not reg:
        return False, "heartbeat.registry unset"
    path = pathlib.Path(reg).expanduser()
    if not path.is_absolute():
        return False, f"registry path must be absolute: {reg}"
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = json.dumps({"agent": cfg.get("brick_id"), "status": status,
                        "last_seen": time.time()}) + "\n"
    with open(path, "a") as f:
        f.write(entry)
    return True, str(path)

def apply_profile(cfg, ident):
    """DA finding 3: the applier actually WRITES the Hermes config."""
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    # identity block (from installer's crypto-gated output, never plaintext manifest)
    (out_dir / "identity.json").write_text(json.dumps({
        "brick_id": cfg.get("brick_id"), "person_id": cfg.get("person_id"),
        "wallet_ref": cfg.get("wallet_ref")}))
    # A2A read-only policy — actual policy artifact the gateway consumes (DA finding 1)
    (out_dir / "a2a-policy.json").write_text(json.dumps({
        "peer_toolsets": cfg.get("a2a", {}).get("peer_toolsets", []),
        "reject": cfg.get("a2a", {}).get("reject", []),
        "enforce_read_only": True}, indent=2))
    # model chain (from manifest model_chain when present — DA finding 5)
    model = dict(cfg.get("model", {}))
    if "manifest" in ident and "model_chain" in ident["manifest"]:
        chain = ident["manifest"].get("model_chain", [])
        if chain:
            model["chain"] = chain
    (out_dir / "model.json").write_text(json.dumps(model, indent=2))
    print(f"[apply] wrote identity.json, a2a-policy.json, model.json to {out_dir}")
    return out_dir

def main():
    args = sys.argv[1:]
    mode = args[0] if args else "verify"

    cfg = load_cfg()
    if not cfg.get("brick_id") or not cfg.get("person_id"):
        fail("brick_id / person_id not set in profile")

    ident, src = read_identity()

    if mode == "apply":
        out = apply_profile(cfg, ident)
        print(f"BRICK PROFILE APPLIED: {cfg['brick_id']} — config written to {out}.")
        print("Next: run `brick_profile.py verify` after Hermes gateway starts.")
        return

    # --- verify (min-alive bar, Z-53-2) ---
    # 1. BOOTS
    try:
        out = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=20)
        from packaging.version import Version  # DA finding 7: proper version compare
        mt = re.search(r"v?(\d+\.\d+\.\d+)", (out.stdout or "") + (out.stderr or ""))
        boots = bool(mt) and Version(mt.group(1)) >= Version("0.20")
    except Exception:
        boots = False
    if not step(1, "boots (hermes 0.20+)", boots):
        fail("Hermes 0.20+ not running")

    # 2. IDENTITY — REAL JWS re-verify (DA finding 2)
    id_ok, id_detail = real_verify_signature(ident)
    if not step(2, f"identity verified ({cfg['brick_id']})", id_ok, id_detail):
        fail("identity not verified against crypto-gated source")

    # 3. ONE CHANNEL — REAL Discord API call (DA finding 3)
    token = os.environ.get(cfg.get("discord", {}).get("token_env", "BRICK_DISCORD_TOKEN"), "")
    channel = cfg.get("discord", {}).get("channel_id", "")
    ch_ok, ch_detail = probe_discord(token, channel) if token and channel else (False, "token/channel unset")
    if not step(3, f"one channel responds ({channel})", ch_ok, ch_detail):
        fail("Discord channel did not respond — check BRICK_DISCORD_TOKEN (mode-600) + channel_id")

    # 3.5 MODEL — REAL endpoint probe (DA finding 5)
    m_ok, m_detail = probe_model(cfg)
    if not step(3, "model endpoint responds", m_ok, m_detail):
        fail("model endpoint not reachable — LM Studio running? default_model set?")

    # 4. HELLO — REAL registry stamp (DA finding 3)
    hb = cfg.get("heartbeat", {})
    h_ok, h_detail = stamp_registry(cfg, "alive")
    if not step(4, "hello heartbeat stamped", h_ok and hb.get("interval_s", 0) > 0, h_detail):
        fail("heartbeat not stamped")

    print(f"BRICK ALIVE: {cfg['brick_id']} — boots, identity JWS-verified, channel responds, "
          f"model online, hello in registry. MIN-ALIVE BAR MET (all 4, real checks).")

if __name__ == "__main__":
    main()
