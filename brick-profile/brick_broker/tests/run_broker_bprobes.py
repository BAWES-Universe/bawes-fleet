#!/usr/bin/env python3
"""CI runner: stage exact Hermes v2026.8.13 + seam, then run BPROBES 15-21.

Used by .github/workflows/ci.yml (job: broker). Stages a full copy of the
pinned Hermes source tree, applies the version-pinned seam installer, then
runs the broker regression suite against the patched stage.

Usage:
    python3 tests/run_broker_bprobes.py --hermes /path/to/v2026.8.13 [--repo /path/to/bawes-fleet]
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hermes", required=True, help="path to exact Hermes v2026.8.13 source tree")
    ap.add_argument("--repo", default=str(pathlib.Path(__file__).resolve().parent.parent))
    args = ap.parse_args()

    hermes = pathlib.Path(args.hermes)
    repo = pathlib.Path(args.repo)
    if not hermes.exists():
        print(f"REJECTED: hermes source not found at {hermes}")
        return 1

    stage = pathlib.Path(tempfile.mkdtemp(prefix="brick-bprobe-ci-"))
    for entry in os.listdir(hermes):
        src = hermes / entry
        if entry in (".git", "__pycache__", "tests"):
            continue
        dst = stage / entry
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    # Apply the version-pinned seam installer to the stage (version stub:
    # the stage is a source tree, not a pip install).
    import importlib.util
    seam_py = repo / "brick-profile" / "hermes-seam" / "install_seam.py"
    spec = importlib.util.spec_from_file_location("install_seam", str(seam_py))
    seam = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seam)
    seam.get_installed_version = lambda: seam.EXPECTED_VERSION
    rc = seam.apply_patch(stage)
    print("seam apply rc:", rc)
    if rc != 0:
        return rc

    env = dict(os.environ, HERMES_SRC=str(stage), REPO=str(repo))
    env["PYTHONPATH"] = str(stage) + ":" + env.get("PYTHONPATH", "")
    probes = repo / "brick-profile" / "brick_broker" / "tests" / "bprobes_15_21.py"
    p = subprocess.run([sys.executable, str(probes)], env=env, capture_output=True, text=True, timeout=300)
    print(p.stdout)
    if p.stderr:
        print("STDERR:", p.stderr[-1500:])
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
