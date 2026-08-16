#!/usr/bin/env python3
"""Test install_seam.py lifecycle against a staged copy of the exact 0.20.1 tree.

Covers: apply (version+SHA+anchors) -> idempotent re-apply -> check ACTIVE ->
rollback -> check MISSING -> fail-closed on SHA drift.
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

print("1) --apply on exact copy")
rc = seam.apply_patch(STAGE)
check("apply rc==0", rc == 0)
run_py = STAGE / "gateway" / "run.py"
check("marker present", seam.SEAM_MARKER in run_py.read_text())
check("seam module written", (STAGE / seam.SEAM_MODULE).exists())
check("broker plugin installed", (TEST_HOME / "plugins" / "brick_broker" / "__init__.py").exists())
check("plugin ownership marker", (TEST_HOME / "plugins" / "brick_broker" / ".brick-broker-installed").exists())
check("backup created", len(list(STAGE.rglob("*.bak-seam*"))) >= 1)
check("SET anchor still once (patched once)", run_py.read_text().count("ctx.agent_holder[0] = agent") == 1)
check("_brick_set_agent call present", "_brick_set_agent(agent)" in run_py.read_text())
check("_brick_reset_agent call present", "_brick_reset_agent(_brick_agent_token)" in run_py.read_text())
# order: set must appear before reset
src = run_py.read_text()
check("set before reset", src.index("_brick_set_agent") < src.index("_brick_reset_agent"))

print("2) idempotent re-apply")
rc2 = seam.apply_patch(STAGE)
check("re-apply rc==0 (no-op)", rc2 == 0)
check("still exactly one set anchor", run_py.read_text().count("_brick_set_agent(agent)") == 1)

print("3) --check after apply")
s = seam.check_status(STAGE)
check("check reports ACTIVE", s["version_ok"] and s["sha_ok"] and s["seam_marker_present"] and s["seam_module_installed"])

print("4) --rollback")
rc3 = seam.rollback(STAGE)
check("rollback rc==0", rc3 == 0)
check("marker removed", seam.SEAM_MARKER not in run_py.read_text())
check("seam module removed", not (STAGE / seam.SEAM_MODULE).exists())
check("broker plugin removed", not (TEST_HOME / "plugins" / "brick_broker").exists())
check("run.py restored to upstream sha", seam.sha256_of(run_py) == seam.EXPECTED_RUN_SHA256)

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
# restore
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
broken.write_text(broken.read_text().replace("ctx.agent_holder[0] = agentX", "ctx.agent_holder[0] = agent"))

fails = [n for n, ok in results if not ok]
print(f"\n== RESULT: {len(results)-len(fails)}/{len(results)} PASS", "ALL PASS" if not fails else f"FAILED: {fails}")
sys.exit(1 if fails else 0)
