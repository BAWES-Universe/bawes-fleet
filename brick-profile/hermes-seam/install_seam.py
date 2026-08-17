#!/usr/bin/env python3
"""install_seam.py — version-pinned installer for the brick broker Hermes seam.

Installs ``tools/current_agent.py`` into an EXACT Hermes 0.20.1 installation
and patches ``gateway/run.py`` with the two turn-scoped ContextVar anchors,
then installs the ``brick_broker`` plugin into ``$HERMES_HOME/plugins/``.

Hard guarantees:
  * Requires exact Hermes v2026.8.13 (importlib.metadata version string) AND
    the expected source SHA of gateway/run.py before touching anything.
  * PREFLIGHT EVERYTHING BEFORE WRITING ANYTHING: version, run.py SHA, both
    patch anchors, broker source files, and writable targets are all checked
    up front. A rejection NEVER leaves a partial install behind and never
    claims "no files modified" after files were written.
  * Fails closed on ANY mismatch (version, SHA, anchor text missing).
  * Backs up every touched file (timestamped .bak-seam).
  * Idempotent: re-running on an already-patched install VERIFIES THE ENTIRE
    INSTALLATION STATE (seam module present/current, broker plugin complete,
    ownership state consistent) and repairs what is missing; only a consistent,
    complete install is a no-op PASS. Inconsistent state fails closed.
  * Ownership-safe plugin rollback: a state file records whether the plugin
    directory was CREATED by this installer. Rollback removes a
    newly-created directory in full, but for a PRE-EXISTING directory it
    restores every overwritten file from backup and removes ONLY the files
    this installer created — unrelated/pre-existing files (e.g. a user's
    sentinel) survive apply AND rollback untouched.
  * Exact rollback: --rollback restores the backups and removes the seam
    module; --check reports state without changing anything.
  * Refuses to patch an unknown/new Hermes version — no silent monkey-patching.

Usage:
  python3 install_seam.py --check          # report status, change nothing
  python3 install_seam.py --apply          # preflight + verify + backup + patch
  python3 install_seam.py --rollback       # restore backups, remove seam

Expected upstream anchors (exact Hermes v2026.8.13, sha 54deb156...):
  SET:   line ~5571:  ``ctx.agent_holder[0] = agent``
  RESET: line ~5944:  ``reset_current_session_key(_approval_session_token)``
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import pathlib
import shutil
import sys
import time

# ---------------------------------------------------------------------------
# Version pins — EXACT Hermes the seam is built against
# ---------------------------------------------------------------------------
EXPECTED_VERSION = "0.20.1"                      # PyPI version string
EXPECTED_RELEASE_TAG = "v2026.8.13"              # release tag for the version
EXPECTED_RUN_SHA256 = "54deb156ec7aa699e5bbd36aee9691d1a1e8cccfbb15266d42a559b39f1db742"
# Expected gateway/run.py sha256 (computed from the pinned source tree).

SEAM_MODULE = "tools/current_agent.py"
SEAM_MARKER = "BRICK BROKER SEAM"               # marker written into run.py
MODULE_MARKER = "# brick broker seam: turn-scoped current-agent ContextVar"

# Broker plugin state/ownership files (inside the installed plugin directory).
STATE_FILE = ".brick-seam-state.json"           # ownership + manifest of writes
LEGACY_MARKER = ".brick-broker-installed"       # pre-state-file ownership marker
PLUGIN_FILES = ("plugin.yaml", "__init__.py", "catalog_toolsets.json")

# The two anchor replacements. Each maps an exact upstream snippet to the
# patched snippet (same upstream text, marker + seam call inserted).
SET_ANCHOR = "        ctx.agent_holder[0] = agent"
SET_REPLACEMENT = (
    "        ctx.agent_holder[0] = agent\n"
    "        # " + SEAM_MARKER + " v1: bind the turn-scoped agent ContextVar\n"
    "        from tools.current_agent import set_current_gateway_agent as _brick_set_agent\n"
    "        _brick_agent_token = _brick_set_agent(agent)"
)

RESET_ANCHOR = "            reset_current_session_key(_approval_session_token)"
RESET_REPLACEMENT = (
    "            reset_current_session_key(_approval_session_token)\n"
    "            # " + SEAM_MARKER + " v1: unbind in finally (success/exception/cancel/failure)\n"
    "            try:\n"
    "                from tools.current_agent import reset_current_gateway_agent as _brick_reset_agent\n"
    "                _brick_reset_agent(_brick_agent_token)\n"
    "            except Exception:\n"
    "                pass"
)


def fail(msg: str) -> int:
    print(f"REJECTED: {msg}")
    return 1


def find_package_root() -> pathlib.Path | None:
    """Locate the installed hermes-agent package root (parent of hermes_cli/)."""
    spec = importlib.util.find_spec("hermes_cli")
    if spec is None or spec.origin is None:
        return None
    return pathlib.Path(spec.origin).resolve().parent.parent


def sha256_of(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_installed_version() -> str | None:
    try:
        return importlib.metadata.version("hermes-agent")
    except importlib.metadata.PackageNotFoundError:
        return None


def hermes_home_dir() -> pathlib.Path:
    if os.environ.get("HERMES_HOME"):
        return pathlib.Path(os.environ["HERMES_HOME"])
    return pathlib.Path.home() / ".hermes"


def plugin_target_dir() -> pathlib.Path:
    return hermes_home_dir() / "plugins" / "brick_broker"


def plugin_source_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent / "brick_broker"


def _is_writable_dir(p: pathlib.Path) -> bool:
    return p.exists() and p.is_dir() and os.access(p, os.W_OK)


# ---------------------------------------------------------------------------
# Preflight — EVERY input checked before ANY write
# ---------------------------------------------------------------------------
def preflight(root: pathlib.Path, require_unpatched_sha: bool = True) -> tuple[bool, str]:
    """Check every input needed for a clean first-time apply.

    Returns (ok, message). On ok=False nothing has been modified.
    """
    run_py = root / "gateway" / "run.py"
    seam_py = root / SEAM_MODULE

    version = get_installed_version()
    if version != EXPECTED_VERSION:
        return False, (
            f"installed hermes-agent version is {version!r}, expected {EXPECTED_VERSION!r} "
            f"(release {EXPECTED_RELEASE_TAG}). Refusing to patch an unknown/new version."
        )
    if not run_py.exists():
        return False, f"gateway/run.py not found at {run_py} — not a Hermes install?"
    if require_unpatched_sha:
        actual_sha = sha256_of(run_py)
        if actual_sha != EXPECTED_RUN_SHA256:
            return False, (
                f"gateway/run.py sha256 {actual_sha} does not match the pinned "
                f"{EXPECTED_RUN_SHA256} for v2026.8.13. Refusing to patch a modified "
                "or unknown source tree."
            )
    src = run_py.read_text(errors="replace")
    if src.count(SET_ANCHOR) != 1:
        return False, f"SET anchor not found exactly once in gateway/run.py (count={src.count(SET_ANCHOR)}). Upstream drifted — refusing to patch."
    if src.count(RESET_ANCHOR) != 1:
        return False, f"RESET anchor not found exactly once in gateway/run.py (count={src.count(RESET_ANCHOR)}). Upstream drifted — refusing to patch."

    # Broker plugin source must be complete BEFORE we write anything.
    psrc = plugin_source_dir()
    missing = [f for f in PLUGIN_FILES if not (psrc / f).exists()]
    if not psrc.is_dir() or missing:
        return False, (
            f"brick_broker plugin source incomplete at {psrc} — missing: {missing or '(dir absent)'}. "
            "Cannot install the broker. No files were modified."
        )

    # Writable target locations.
    if not _is_writable_dir(seam_py.parent):
        return False, f"seam module target dir not writable: {seam_py.parent}"
    plugins_parent = hermes_home_dir() / "plugins"
    if plugins_parent.exists() and not _is_writable_dir(plugins_parent):
        return False, f"plugins dir not writable: {plugins_parent}"
    return True, "preflight ok"


# ---------------------------------------------------------------------------
# Broker plugin install (ownership-tracked)
# ---------------------------------------------------------------------------
def install_plugin(ts: str) -> dict:
    """Install the broker plugin into $HERMES_HOME/plugins/brick_broker.

    Returns the ownership state dict. Behavior:
      * If the plugin directory did NOT exist: created by us, so rollback may
        remove it in full (dir_created=True).
      * If it DID exist: every file we overwrite is backed up first; rollback
        restores the backups and removes only files we created; unrelated
        pre-existing files are never touched.
    """
    psrc = plugin_source_dir()
    pdst = plugin_target_dir()
    dir_created = not pdst.exists()
    if dir_created:
        pdst.mkdir(parents=True, exist_ok=True)

    overwrites = {}   # name -> backup filename (only for pre-existing files)
    created = []      # names of files this installer wrote
    for f in PLUGIN_FILES:
        dst = pdst / f
        if dst.exists():
            bak = dst.with_name(dst.name + f".bak-seam-{ts}")
            shutil.copy2(dst, bak)
            overwrites[f] = bak.name
        shutil.copy2(psrc / f, dst)
        created.append(f)

    state = {
        "installed_by": "install_seam.py",
        "ts": ts,
        "dir_created": dir_created,
        "files_written": created,
        "overwrites": overwrites,
    }
    state_path = pdst / STATE_FILE
    if state_path.exists():
        shutil.copy2(state_path, state_path.with_name(state_path.name + f".bak-seam-{ts}"))
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    # Legacy marker kept for backward compatibility / quick ownership checks.
    (pdst / LEGACY_MARKER).write_text("installed by install_seam.py\n")
    print(
        f"PATCHED ok: brick_broker plugin installed at {pdst} "
        f"({'new dir' if dir_created else 'pre-existing dir, overwrites backed up'})"
    )
    return state


def plugin_state() -> dict | None:
    """Read the ownership state file if present."""
    sp = plugin_target_dir() / STATE_FILE
    if not sp.exists():
        return None
    try:
        return json.loads(sp.read_text())
    except Exception:
        return None


def verify_install(root: pathlib.Path) -> tuple[bool, list[str]]:
    """Verify the ENTIRE installation state. Returns (ok, problems)."""
    problems = []
    run_py = root / "gateway" / "run.py"
    seam_py = root / SEAM_MODULE
    if not run_py.exists() or SEAM_MARKER not in run_py.read_text(errors="replace"):
        problems.append("run.py seam marker missing")
    if not seam_py.exists():
        problems.append("seam module missing")
    elif MODULE_MARKER not in seam_py.read_text(errors="replace"):
        problems.append("seam module stale (marker missing)")
    pdst = plugin_target_dir()
    for f in PLUGIN_FILES:
        if not (pdst / f).exists():
            problems.append(f"broker plugin file missing: {f}")
    state = plugin_state()
    legacy = (pdst / LEGACY_MARKER).exists()
    if state is None and not legacy:
        problems.append("plugin ownership state missing (no state file, no legacy marker)")
    return (len(problems) == 0), problems


def repair_install(root: pathlib.Path) -> tuple[bool, list[str]]:
    """Repair a partial installation (missing/stale seam module or plugin files).

    Returns (ok, report). Only ever rewrites files whose content we own;
    pre-existing user files are backed up before overwrite via install_plugin.
    """
    report = []
    ts = time.strftime("%Y%m%d%H%M%S")
    seam_py = root / SEAM_MODULE
    if not seam_py.exists() or MODULE_MARKER not in seam_py.read_text(errors="replace"):
        if seam_py.exists():
            shutil.copy2(seam_py, seam_py.with_name(seam_py.name + f".bak-seam-{ts}"))
        seam_py.parent.mkdir(parents=True, exist_ok=True)
        seam_py.write_text(_SEAM_MODULE_SOURCE)
        report.append("repaired seam module")
    pdst = plugin_target_dir()
    missing = [f for f in PLUGIN_FILES if not (pdst / f).exists()]
    state = plugin_state()
    if missing or state is None:
        install_plugin(ts)
        report.append("repaired broker plugin")
    return True, report


def check_status(root: pathlib.Path) -> dict:
    """Return a status dict without modifying anything."""
    run_py = root / "gateway" / "run.py"
    seam_py = root / SEAM_MODULE
    ok, problems = verify_install(root)
    status = {
        "package_root": str(root),
        "installed_version": get_installed_version(),
        "run_py_exists": run_py.exists(),
        "run_py_sha256": sha256_of(run_py) if run_py.exists() else None,
        "expected_sha256": EXPECTED_RUN_SHA256,
        "seam_module_installed": seam_py.exists(),
        "seam_marker_present": bool(
            run_py.exists() and SEAM_MARKER in run_py.read_text(errors="replace")
        ),
        "backups": sorted(
            str(p.relative_to(root))
            for p in root.rglob("*.bak-seam*")
        ),
        "version_ok": get_installed_version() == EXPECTED_VERSION,
        "sha_ok": (
            run_py.exists()
            and (
                sha256_of(run_py) == EXPECTED_RUN_SHA256
                or SEAM_MARKER in run_py.read_text(errors="replace")
            )
        ),
        "install_complete": ok,
        "install_problems": problems,
    }
    return status


def apply_patch(root: pathlib.Path) -> int:
    """Preflight, then back up, patch, write seam module + plugin. Idempotent
    with full-state verification."""
    run_py = root / "gateway" / "run.py"
    seam_py = root / SEAM_MODULE

    # 1. Version gate (before anything, including the idempotent branch).
    version = get_installed_version()
    if version != EXPECTED_VERSION:
        return fail(
            f"installed hermes-agent version is {version!r}, expected {EXPECTED_VERSION!r} "
            f"(release {EXPECTED_RELEASE_TAG}). Refusing to patch an unknown/new version. "
            "No files were modified."
        )

    src = run_py.read_text(errors="replace") if run_py.exists() else ""
    if SEAM_MARKER in src:
        # 2a. Idempotent path: marker present -> VERIFY THE WHOLE INSTALL
        #     (not an immediate success). Repair missing/stale parts; fail
        #     closed on anything inconsistent we cannot repair.
        ok, problems = verify_install(root)
        if ok:
            print("already installed and fully consistent — nothing to do")
            return 0
        # Attempt repair of the installer-owned parts (seam module, plugin).
        rep_ok, report = repair_install(root)
        ok2, problems2 = verify_install(root)
        if rep_ok and ok2:
            print("installation was incomplete — repaired: " + "; ".join(report))
            return 0
        return fail(
            "installation state inconsistent and could not be fully repaired. "
            f"Problems: {problems2 or problems}. Run --rollback to restore, or "
            "remove the leftover seam marker manually. No further files modified."
        )

    # 2b. First-time path: PREFLIGHT EVERYTHING before writing anything.
    pf_ok, pf_msg = preflight(root, require_unpatched_sha=True)
    if not pf_ok:
        return fail(pf_msg + " No files were modified.")

    ts = time.strftime("%Y%m%d%H%M%S")
    backups = []
    for p in (run_py, seam_py):
        if p.exists():
            bak = p.with_name(p.name + f".bak-seam-{ts}")
            shutil.copy2(p, bak)
            backups.append(str(bak))

    # Patch run.py (SET anchor first, then RESET anchor).
    patched = src.replace(SET_ANCHOR, SET_REPLACEMENT, 1)
    patched = patched.replace(RESET_ANCHOR, RESET_REPLACEMENT, 1)
    if SEAM_MARKER not in patched:
        for b in backups:
            try:
                os.remove(b)
            except OSError:
                pass
        return fail("patch application failed internal verification — backups removed, nothing changed")

    # Write seam module (new file; back up any pre-existing one).
    seam_src = _SEAM_MODULE_SOURCE
    seam_py.parent.mkdir(parents=True, exist_ok=True)
    if seam_py.exists():
        shutil.copy2(seam_py, seam_py.with_name(seam_py.name + f".bak-seam-{ts}"))
    seam_py.write_text(seam_src)

    # Install broker plugin (ownership-tracked).
    install_plugin(ts)

    # Write patched run.py atomically (LAST — so a failure above leaves the
    # seam module + plugin but an UNPATCHED run.py, which --check flags and a
    # re-apply repairs; never a half-patched run.py claiming success).
    run_py.write_text(patched)

    print(f"PATCHED ok: {run_py} (+seam module {seam_py})")
    print("backups:", backups or "(none)")
    print("verify: python3 install_seam.py --check")
    return 0


def _restore_runtime_from_manifest(hermes_home: pathlib.Path) -> int:
    """Restore config.yaml + .env from the gateway_wire rollback manifest.

    The manifest records the EXACT pre-broker backup identities + pre-shas.
    Restores ONLY those recorded backups (never a globbed older backup).
    Fails closed if:
      * the manifest is unreadable,
      * a recorded backup is missing,
      * a restored file's sha does not match the recorded pre-broker sha,
      * the CURRENT runtime file was modified after wiring (user edits since
        apply) — overwriting would destroy unrelated user changes, so refuse
        and explain instead.
    Returns 0 on success (or nothing-to-restore), nonzero on failure.
    """
    mp = hermes_home / "brick-rollback-state.json"
    if not mp.exists():
        print("no gateway_wire rollback manifest found — runtime config/env "
              "untouched (seam-only rollback)")
        return 0
    try:
        manifest = json.loads(mp.read_text())
    except Exception as e:
        print(f"REJECTED: rollback manifest unreadable ({e}) — cannot prove safe "
              "runtime restoration. Fix or remove the manifest manually, then "
              "re-run --rollback.")
        return 1

    config_backup = manifest.get("config_backup")
    env_backup = manifest.get("env_backup")
    config_pre = manifest.get("config_pre_sha256")
    env_pre = manifest.get("env_pre_sha256")
    config_post = manifest.get("config_post_sha256")
    env_post = manifest.get("env_post_sha256")
    cfg_path = hermes_home / "config.yaml"
    env_path = hermes_home / ".env"

    # Never clobber post-apply user edits: if the current file differs from
    # the state wiring wrote, someone changed it since — refuse and explain.
    if config_post and cfg_path.exists() and sha256_of(cfg_path) != config_post:
        print("REJECTED: config.yaml was modified after gateway_wire --apply "
              "(sha differs from the recorded post-wiring state). Refusing to "
              "overwrite your changes with the pre-broker backup. Back up your "
              "edits or revert them, then re-run --rollback.")
        return 1
    if env_post and env_path.exists() and sha256_of(env_path) != env_post:
        print("REJECTED: .env was modified after gateway_wire --apply. Refusing "
              "to overwrite your changes. Revert or back them up, then re-run "
              "--rollback.")
        return 1

    restored = 0
    # config.yaml: restore the recorded backup; if there was NO pre-broker
    # config (backup None), remove the file wiring created.
    if config_backup and pathlib.Path(config_backup).exists():
        shutil.copy2(config_backup, cfg_path)
        if sha256_of(cfg_path) != config_pre:
            print("REJECTED: restored config.yaml does not match the recorded "
                  "pre-broker sha — aborting runtime restore (config left in "
                  "the restored state; re-run after fixing the manifest).")
            return 1
        restored += 1
        print(f"restored {cfg_path} <- {config_backup}")
    elif config_backup is None:
        if cfg_path.exists():
            cfg_path.unlink()
            print(f"removed {cfg_path} (did not exist before wiring)")
    else:
        print(f"REJECTED: recorded config backup missing: {config_backup}")
        return 1

    if env_backup and pathlib.Path(env_backup).exists():
        shutil.copy2(env_backup, env_path)
        if sha256_of(env_path) != env_pre:
            print("REJECTED: restored .env does not match the recorded pre-broker "
                  "sha — aborting runtime restore.")
            return 1
        restored += 1
        print(f"restored {env_path} <- {env_backup}")
    elif env_backup is None:
        if env_path.exists():
            env_path.unlink()
            print(f"removed {env_path} (did not exist before wiring)")
    else:
        print(f"REJECTED: recorded env backup missing: {env_backup}")
        return 1

    mp.unlink()
    print(f"rollback manifest removed ({restored} runtime files restored)")
    return 0


def rollback(root: pathlib.Path) -> int:
    """Transactional rollback across the FULL Brock latency installation.

    Restores the Hermes runtime layer (config.yaml + .env via the
    gateway_wire rollback manifest) AND the source/plugin layer (seam module,
    patched run.py, broker plugin). Idempotent. Ownership-safe for the plugin.
    """
    # 0. Runtime layer first: if the manifest restore fails, refuse to continue
    #    (a half-rolled-back brick with a brokerized config + no plugin is
    #    worse than a fully-brokerized one).
    rc_runtime = _restore_runtime_from_manifest(hermes_home_dir())
    if rc_runtime != 0:
        print("rollback ABORTED: runtime layer could not be restored safely; "
              "seam/plugin layer NOT touched.")
        return rc_runtime

    backups = sorted(root.rglob("*.bak-seam*"))
    restored = 0
    for bak in backups:
        target = bak.with_name(bak.name.rsplit(".bak-seam-", 1)[0])
        if target.exists():
            target.write_bytes(bak.read_bytes())
            restored += 1
            print(f"restored {target} <- {bak.name}")
        else:
            print(f"target missing (skip): {target}")
    seam_py = root / SEAM_MODULE
    if seam_py.exists() and MODULE_MARKER in seam_py.read_text(errors="replace"):
        seam_py.unlink()
        print(f"removed seam module {seam_py}")

    # Ownership-safe plugin rollback.
    pdst = plugin_target_dir()
    if pdst.exists():
        state = plugin_state()
        if state is not None:
            if state.get("dir_created"):
                # We created the whole directory — safe to remove entirely.
                shutil.rmtree(pdst)
                print(f"removed installer-created broker plugin dir {pdst}")
            else:
                # Pre-existing directory: restore overwritten files, remove
                # only files this installer created; leave everything else.
                for name, bakname in (state.get("overwrites") or {}).items():
                    src = pdst / bakname
                    dst = pdst / name
                    if src.exists():
                        dst.write_bytes(src.read_bytes())
                        restored += 1
                        print(f"restored {pdst / name} <- {bakname}")
                for name in (state.get("files_written") or []):
                    f = pdst / name
                    if f.exists() and name not in (state.get("overwrites") or {}):
                        f.unlink()
                        print(f"removed installer-created file {pdst / name}")
                # Remove state + legacy marker (ours).
                for own in (STATE_FILE, LEGACY_MARKER):
                    f = pdst / own
                    if f.exists():
                        f.unlink()
                print(f"preserved pre-existing files in {pdst}")
        elif (pdst / LEGACY_MARKER).exists():
            # Legacy install (pre-state-file): conservative — remove only the
            # files we know we write, never the whole dir.
            for f in PLUGIN_FILES + (STATE_FILE, LEGACY_MARKER):
                p = pdst / f
                if p.exists():
                    p.unlink()
                    print(f"removed legacy installer file {p}")
            print(f"preserved pre-existing files in {pdst} (legacy, no state file)")
    print(f"rollback complete ({restored} files restored)")
    return 0


# The exact seam module source (kept in-sync with current_agent.py in this dir).
_SEAM_MODULE_SOURCE = '''"""Brick broker seam — turn-scoped current-agent ContextVar.

Hermes 0.20.1 compatibility seam (installed by brick-profile/hermes-seam/
install_seam.py): exposes the active gateway AIAgent to broker invocation.
"""
# brick broker seam: turn-scoped current-agent ContextVar
from __future__ import annotations

import contextvars

_current_agent: contextvars.ContextVar = contextvars.ContextVar(
    "brick_current_gateway_agent", default=None
)


def set_current_gateway_agent(agent) -> contextvars.Token:
    """Bind the current gateway agent for this turn. Returns a reset token."""
    return _current_agent.set(agent)


def reset_current_gateway_agent(token: contextvars.Token) -> None:
    """Unbind the turn-scoped agent binding (call in finally)."""
    _current_agent.reset(token)


def get_current_gateway_agent():
    """Return the agent bound for the current turn, or None (fail closed)."""
    return _current_agent.get()
'''


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    root = find_package_root()
    if root is None:
        return fail("could not locate installed hermes-agent package (hermes_cli not importable)")
    print(f"hermes package root: {root}")

    if mode == "--check":
        s = check_status(root)
        print(json.dumps(s, indent=2, default=str))
        ok = s["version_ok"] and s["sha_ok"] and s["seam_marker_present"] and s["seam_module_installed"] and s["install_complete"]
        print("STATUS:", "SEAM ACTIVE" if ok else "SEAM MISSING/STALE")
        return 0 if ok else 1
    if mode == "--apply":
        return apply_patch(root)
    if mode == "--rollback":
        return rollback(root)
    return fail(f"unknown mode {mode!r} (use --check | --apply | --rollback)")


if __name__ == "__main__":
    sys.exit(main())
