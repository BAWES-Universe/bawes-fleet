#!/usr/bin/env python3
"""E2E transactional rollback test (Finding 2) + re-apply idempotency (Finding 1).

Stages the EXACT Hermes v2026.8.13 tree, then proves:

  A. baseline -> gateway_wire --apply -> seam install -> broker ACTIVE
     -> seam --rollback -> runtime config/env + Hermes files/plugin all
     equal the pre-install baseline (transactional rollback).
  B. apply -> apply -> rollback restores the ORIGINAL pre-first-apply state
     (the second apply must NOT become the rollback target).
  C. re-apply leaves catalog_toolsets.json byte-identical (never re-derived
     from the broker surface).

Env: --hermes <exact v2026.8.13 tree> --repo <bawes-fleet checkout>.
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile


def stage_hermes(src: pathlib.Path, dst: pathlib.Path):
    for entry in os.listdir(src):
        s = src / entry
        if entry in (".git", "__pycache__", "tests"):
            continue
        d = dst / entry
        if s.is_dir():
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hermes", required=True)
    ap.add_argument("--repo", default=str(pathlib.Path(__file__).resolve().parent.parent.parent))
    args = ap.parse_args()
    hermes = pathlib.Path(args.hermes)
    repo = pathlib.Path(args.repo)
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond)))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))

    # ---- stage exact hermes ----
    stage = pathlib.Path(tempfile.mkdtemp(prefix="brick-e2e-"))
    stage_hermes(hermes, stage)
    sys.path.insert(0, str(stage))
    sys.path.insert(0, os.path.join(repo, "brick-profile"))
    sys.path.insert(0, os.path.join(repo, "brick-profile", "hermes-seam"))

    import install_seam as seam
    seam.get_installed_version = lambda: seam.EXPECTED_VERSION
    import gateway_wire as gw

    # ---- fixtures: OUT (identity/a2a/model) + HERMES_HOME ----
    td = pathlib.Path(tempfile.mkdtemp(prefix="brick-e2e-home-"))
    out_dir = td / "out"; out_dir.mkdir()
    home = td / "hermes-home"; home.mkdir()
    (out_dir / "identity.json").write_text(json.dumps({
        "brick_id": "mishari-device-001", "person_id": "231861",
        "discord_user_id": "231861753082937346", "wallet_ref": "w"}))
    (out_dir / "a2a-policy.json").write_text(json.dumps({
        "peer_toolsets": ["web", "vision", "session_search"],
        "reject": ["terminal", "code_execution", "memory", "file", "skill_manage"],
        "enforce_read_only": True}))
    (out_dir / "model.json").write_text(json.dumps({
        "primary": "http://172.20.64.1:1234/v1",
        "default_model": "qwen/qwen3-4b-2507"}))
    os.environ["HERMES_HOME"] = str(home)
    os.environ["BRICK_DISCORD_TOKEN"] = "tok-1234567890"
    gw.OUT = out_dir
    gw.HERMES_DIR = home
    gw.CONFIG = home / "config.yaml"
    gw.ENV = home / ".env"

    # ---- BASELINE runtime state (pre-broker) ----
    baseline_cfg = ("platforms:\n  discord:\n    enabled: true\n"
                    "agent:\n  disabled_toolsets: [x_search]\n")
    baseline_env = "PRE_EXISTING=keepme\n"
    (home / "config.yaml").write_text(baseline_cfg)
    (home / ".env").write_text(baseline_env)
    cfg_pre_sha = seam.sha256_of(home / "config.yaml")
    env_pre_sha = seam.sha256_of(home / ".env")

    print("A) transactional rollback: baseline -> wire -> seam -> rollback")
    assert gw.wire(dry_run=False, force=True) == 0
    # brokerized config now on disk
    assert "brick_broker" in (home / "config.yaml").read_text()
    assert seam.apply_patch(stage) == 0
    s = seam.check_status(stage)
    check("broker ACTIVE after seam install",
          s["seam_marker_present"] and s["seam_module_installed"] and s["install_complete"])
    check("plugin installed", (home / "plugins" / "brick_broker" / "__init__.py").exists())
    # manifest exists with pre-shas
    mp = home / "brick-rollback-state.json"
    check("rollback manifest written", mp.exists())
    m = json.loads(mp.read_text())
    check("manifest pins pre-broker config sha", m["config_pre_sha256"] == cfg_pre_sha)
    check("manifest pins pre-broker env sha", m["env_pre_sha256"] == env_pre_sha)
    # user edits config AFTER install -> rollback must refuse (never clobber)
    (home / "config.yaml").write_text((home / "config.yaml").read_text() + "# user-edit\n")
    rc_refuse = seam.rollback(stage)
    check("rollback REFUSES to clobber post-apply user edit", rc_refuse != 0,
          f"rc={rc_refuse}")
    # restore the exact post-wiring state, then rollback must succeed
    gw.wire(dry_run=False, force=True)  # rewrite exact post-wiring config
    rc = seam.rollback(stage)
    check("rollback rc==0", rc == 0)
    check("config.yaml restored to baseline",
          (home / "config.yaml").read_text() == baseline_cfg,
          (home / "config.yaml").read_text()[:80])
    check(".env restored to baseline", (home / ".env").read_text() == baseline_env)
    check("manifest removed", not mp.exists())
    check("seam module removed", not (stage / seam.SEAM_MODULE).exists())
    check("run.py restored to upstream sha",
          seam.sha256_of(stage / "gateway" / "run.py") == seam.EXPECTED_RUN_SHA256)
    check("plugin dir removed (installer-created)", not (home / "plugins" / "brick_broker").exists())
    check("no broker reference in restored config", "brick_broker" not in (home / "config.yaml").read_text())

    print("B) apply -> apply -> rollback restores the ORIGINAL pre-first-apply state")
    (home / "config.yaml").write_text(baseline_cfg)
    (home / ".env").write_text(baseline_env)
    assert gw.wire(dry_run=False, force=True) == 0
    cfg_after_first = (home / "config.yaml").read_text()
    assert gw.wire(dry_run=False, force=True) == 0   # second apply
    check("second apply keeps brokerized config", "brick_broker" in (home / "config.yaml").read_text())
    rc2 = seam.rollback(stage)   # seam not installed in B — rollback of seam layer no-ops, runtime restored
    check("rollback rc==0", rc2 == 0)
    check("restored to PRE-FIRST-APPLY baseline (not first-apply state)",
          (home / "config.yaml").read_text() == baseline_cfg,
          (home / "config.yaml").read_text()[:60])
    check("env restored to original", (home / ".env").read_text() == baseline_env)
    check("manifest removed", not mp.exists())

    print("C) re-apply catalog idempotency (Finding 1)")
    (home / "config.yaml").write_text(baseline_cfg)
    (home / ".env").write_text(baseline_env)
    cat_path = pathlib.Path(repo) / "brick-profile" / "brick_broker" / "catalog_toolsets.json"
    cat_orig = cat_path.read_text() if cat_path.exists() else None
    try:
        assert gw.wire(dry_run=False, force=True) == 0
        cat_first = cat_path.read_text()
        assert gw.wire(dry_run=False, force=True) == 0
        check("catalog byte-identical after 2nd apply", cat_path.read_text() == cat_first)
        assert gw.wire(dry_run=False, force=True) == 0
        check("catalog byte-identical after 3rd apply", cat_path.read_text() == cat_first)
        data = json.loads(cat_first)
        check("catalog holds FULL owner surface (not broker set)",
              "terminal" in data["toolsets"] and len(data["toolsets"]) >= 10,
              str(data["toolsets"])[:80])
        check("catalog records captured disabled snapshot",
              isinstance(data.get("captured_disabled_toolsets"), list))
    finally:
        if cat_orig is not None:
            cat_path.write_text(cat_orig)   # never leave the repo catalog modified

    fails = [n for n, ok in results if not ok]
    print(f"\n== RESULT: {len(results)-len(fails)}/{len(results)} PASS",
          "ALL PASS" if not fails else f"FAILED: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
