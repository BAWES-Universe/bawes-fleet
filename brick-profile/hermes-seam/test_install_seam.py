#!/usr/bin/env python3
"""Test install_seam.py lifecycle against a staged copy of the exact 0.20.1 tree.

Covers: apply (preflight+version+SHA+anchors) -> idempotent re-apply with
FULL-STATE verification -> check ACTIVE -> rollback -> check MISSING ->
fail-closed on SHA drift/version/anchor -> PRE-EXISTING plugin dir with
unrelated sentinel survives apply AND rollback -> partial-install repair ->
preflight rejection leaves nothing written.
"""
import importlib.util
import os
import pathlib
import shutil
import sys

# Isolate HERMES_HOME so the installer never touches a real ~/.hermes.
TEST_HOME = pathlib.Path("/tmp/seam-test-home")
if TEST_HOME.exists():
    shutil.rmtree(TEST_HOME)
TEST_HOME.mkdir(parents=True)
os.environ["HERMES_HOME"] = str(TEST_HOME)

sys.path.insert(0, "/tmp/brock-broker/brick-profile/hermes-seam")
import install_seam as seam

STAGE = pathlib.Path(os.environ.get("SEAM_STAGE", "/tmp/seam-test"))
assert STAGE.exists(), "stage copy missing — run via run_seam_test.py"

results = []
def check(name, cond):
    results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

# Stub the installed-version probe (source tree, not a pip install).
seam.get_installed_version = lambda: seam.EXPECTED_VERSION

PLUGIN_DIR = TEST_HOME / "plugins" / "brick_broker"
RUN_PY = STAGE / "gateway" / "run.py"

print("1) --apply on exact copy (fresh: plugin dir created by installer)")
rc = seam.apply_patch(STAGE)
check("apply rc==0", rc == 0)
check("marker present", seam.SEAM_MARKER in RUN_PY.read_text())
check("seam module written", (STAGE / seam.SEAM_MODULE).exists())
check("broker plugin installed", (PLUGIN_DIR / "__init__.py").exists())
check("state file written", (PLUGIN_DIR / seam.STATE_FILE).exists())
check("state says dir_created", seam.plugin_state() is not None and seam.plugin_state().get("dir_created") is True)
check("backup created", len(list(STAGE.rglob("*.bak-seam*"))) >= 1)
check("SET anchor still once (patched once)", RUN_PY.read_text().count("ctx.agent_holder[0] = agent") == 1)
check("_brick_set_agent call present", "_brick_set_agent(agent)" in RUN_PY.read_text())
check("_brick_reset_agent call present", "_brick_reset_agent(_brick_agent_token)" in RUN_PY.read_text())
src = RUN_PY.read_text()
check("set before reset", src.index("_brick_set_agent") < src.index("_brick_reset_agent"))

print("2) idempotent re-apply (full-state verify)")
rc2 = seam.apply_patch(STAGE)
check("re-apply rc==0 (no-op)", rc2 == 0)
check("still exactly one set anchor", RUN_PY.read_text().count("_brick_set_agent(agent)") == 1)

print("3) --check after apply")
s = seam.check_status(STAGE)
check("check reports ACTIVE",
      s["version_ok"] and s["sha_ok"] and s["seam_marker_present"]
      and s["seam_module_installed"] and s["install_complete"])

print("4) --rollback (installer-created dir removed)")
rc3 = seam.rollback(STAGE)
check("rollback rc==0", rc3 == 0)
check("marker removed", seam.SEAM_MARKER not in RUN_PY.read_text())
check("seam module removed", not (STAGE / seam.SEAM_MODULE).exists())
check("broker plugin dir removed (was installer-created)", not PLUGIN_DIR.exists())
check("run.py restored to upstream sha", seam.sha256_of(RUN_PY) == seam.EXPECTED_RUN_SHA256)

print("5) --check after rollback")
s2 = seam.check_status(STAGE)
check("check reports MISSING", not (s2["seam_marker_present"] and s2["seam_module_installed"]))

print("6) fail-closed on SHA drift (modified upstream)")
drift = STAGE / "gateway" / "run.py"
drift.write_text(drift.read_text() + "\n# drift\n")
rc4 = seam.apply_patch(STAGE)
check("drifted apply REJECTED (rc!=0)", rc4 != 0)
check("no marker after rejection", seam.SEAM_MARKER not in drift.read_text())
check("no seam module after rejection", not (STAGE / seam.SEAM_MODULE).exists())
check("no plugin dir after rejection", not PLUGIN_DIR.exists())
drift.write_text(drift.read_text().replace("\n# drift\n", ""))

print("7) fail-closed on version mismatch")
seam.get_installed_version = lambda: "9.9.9"
rc5 = seam.apply_patch(STAGE)
check("wrong-version apply REJECTED", rc5 != 0)
seam.get_installed_version = lambda: seam.EXPECTED_VERSION

print("8) fail-closed on missing anchor")
broken = STAGE / "gateway" / "run.py"
broken.write_text(broken.read_text().replace("ctx.agent_holder[0] = agent", "ctx.agent_holder[0] = agentX"))
rc6 = seam.apply_patch(STAGE)
check("missing-anchor apply REJECTED", rc6 != 0)
check("no seam module after anchor rejection", not (STAGE / seam.SEAM_MODULE).exists())
broken.write_text(broken.read_text().replace("ctx.agent_holder[0] = agentX", "ctx.agent_holder[0] = agent"))

print("9) PRE-EXISTING plugin dir: unrelated sentinel survives apply + rollback")
PRE_EXISTING = PLUGIN_DIR
PRE_EXISTING.mkdir(parents=True, exist_ok=True)
sentinel = PRE_EXISTING / "unrelated-sentinel.txt"
sentinel.write_text("user data — must survive\n")
original_plugin_yaml = PRE_EXISTING / "plugin.yaml"
original_plugin_yaml.write_text("name: user-plugin-original\n")   # user's own version
rc7 = seam.apply_patch(STAGE)
check("apply rc==0 with pre-existing dir", rc7 == 0)
check("sentinel survives apply", sentinel.exists() and "must survive" in sentinel.read_text())
check("state says dir NOT created", seam.plugin_state() is not None and seam.plugin_state().get("dir_created") is False)
check("overwrites recorded", bool(seam.plugin_state().get("overwrites")))
check("plugin.yaml overwritten (with backup)", "name: brick_broker" in (PRE_EXISTING / "plugin.yaml").read_text() or "name:" in (PRE_EXISTING / "plugin.yaml").read_text())
rc8 = seam.rollback(STAGE)
check("rollback rc==0 with pre-existing dir", rc8 == 0)
check("sentinel SURVIVES rollback", sentinel.exists() and "must survive" in sentinel.read_text())
check("pre-existing plugin.yaml restored to ORIGINAL", "user-plugin-original" in (PRE_EXISTING / "plugin.yaml").read_text())
check("installer-created __init__.py removed", not (PRE_EXISTING / "__init__.py").exists())
check("state file removed", not (PRE_EXISTING / seam.STATE_FILE).exists())
check("legacy marker removed", not (PRE_EXISTING / seam.LEGACY_MARKER).exists())
check("run.py still rolled back clean", seam.SEAM_MARKER not in RUN_PY.read_text())
# clean up the pre-existing fixture for subsequent tests
shutil.rmtree(PRE_EXISTING)

print("10) partial-install repair: missing seam module / missing plugin file")
rc9 = seam.apply_patch(STAGE)
check("fresh apply rc==0", rc9 == 0)
# (a) delete the seam module -> re-apply must repair it
(STAGE / seam.SEAM_MODULE).unlink()
rc10 = seam.apply_patch(STAGE)
check("re-apply repairs missing seam module (rc==0)", rc10 == 0)
check("seam module restored", (STAGE / seam.SEAM_MODULE).exists())
# (b) delete a plugin file -> re-apply must repair it
(PLUGIN_DIR / "__init__.py").unlink()
rc11 = seam.apply_patch(STAGE)
check("re-apply repairs missing plugin file (rc==0)", rc11 == 0)
check("plugin __init__.py restored", (PLUGIN_DIR / "__init__.py").exists())
check("state still consistent", seam.plugin_state() is not None)
# (c) delete state + legacy marker -> verify fails, re-apply repairs
(PLUGIN_DIR / seam.STATE_FILE).unlink()
(PLUGIN_DIR / seam.LEGACY_MARKER).unlink()
ok, problems = seam.verify_install(STAGE)
check("verify flags missing ownership state", not ok and any("ownership" in p for p in problems))
rc12 = seam.apply_patch(STAGE)
check("re-apply repairs missing state (rc==0)", rc12 == 0)
check("state regenerated", seam.plugin_state() is not None)
seam.rollback(STAGE)
# Clean up fixture: rollback correctly PRESERVED the (now pre-existing) plugin
# dir with its restored files — remove it so test 11 starts from a clean slate.
if PLUGIN_DIR.exists():
    shutil.rmtree(PLUGIN_DIR)

print("11) preflight rejection writes NOTHING (plugin source missing)")
_orig_src = seam.plugin_source_dir
seam.plugin_source_dir = lambda: STAGE / "no-such-plugin-source"
rc13 = seam.apply_patch(STAGE)
check("missing plugin source REJECTED (rc!=0)", rc13 != 0)
check("no marker written", seam.SEAM_MARKER not in RUN_PY.read_text())
check("no seam module written", not (STAGE / seam.SEAM_MODULE).exists())
check("no plugin dir written", not PLUGIN_DIR.exists())
seam.plugin_source_dir = _orig_src

print("12) preflight rejection writes NOTHING (writable-target fail)")
# Point HERMES_HOME at a path whose plugins dir is a FILE (cannot mkdir under it)
seam.hermes_home_dir = lambda: TEST_HOME / "blocked-home"
_blocked = TEST_HOME / "blocked-home"
_blocked.mkdir(exist_ok=True)
(_blocked / "plugins").write_text("file, not dir\n")   # plugins as a FILE
rc14 = seam.apply_patch(STAGE)
check("unwritable plugins target REJECTED (rc!=0)", rc14 != 0)
check("no marker written (target fail)", seam.SEAM_MARKER not in RUN_PY.read_text())
check("no seam module written (target fail)", not (STAGE / seam.SEAM_MODULE).exists())
seam.hermes_home_dir = lambda: TEST_HOME

fails = [n for n, ok in results if not ok]
print(f"\n== RESULT: {len(results)-len(fails)}/{len(results)} PASS", "ALL PASS" if not fails else f"FAILED: {fails}")
sys.exit(1 if fails else 0)
