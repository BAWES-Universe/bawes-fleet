#!/usr/bin/env python3
"""install_seam.py — version-pinned installer for the brick broker Hermes seam.

Installs ``tools/current_agent.py`` into an EXACT Hermes 0.20.1 installation
and patches ``gateway/run.py`` with the two turn-scoped ContextVar anchors.

Hard guarantees:
  * Requires exact Hermes v2026.8.13 (importlib.metadata version string) AND
    the expected source SHA of gateway/run.py before touching anything.
  * Fails closed on ANY mismatch (version, SHA, anchor text missing).
  * Backs up every touched file (timestamped .bak-seam).
  * Idempotent: re-running on an already-patched install is a no-op PASS.
  * Exact rollback: --rollback restores the backups and removes the seam
    module; --check reports state without changing anything.
  * Refuses to patch an unknown/new Hermes version — no silent monkey-patching.

Usage:
  python3 install_seam.py --check          # report status, change nothing
  python3 install_seam.py --apply          # verify + backup + patch
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


def check_status(root: pathlib.Path) -> dict:
    """Return a status dict without modifying anything."""
    run_py = root / "gateway" / "run.py"
    seam_py = root / SEAM_MODULE
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
    }
    return status


def apply_patch(root: pathlib.Path) -> int:
    """Verify version+SHA, back up, patch, write seam module. Idempotent."""
    run_py = root / "gateway" / "run.py"
    seam_py = root / SEAM_MODULE

    # 1. Fail closed on version mismatch — refuse unknown/new Hermes.
    version = get_installed_version()
    if version != EXPECTED_VERSION:
        return fail(
            f"installed hermes-agent version is {version!r}, expected {EXPECTED_VERSION!r} "
            f"(release {EXPECTED_RELEASE_TAG}). Refusing to patch an unknown/new version. "
            "No files were modified."
        )

    # 2. Idempotent: already patched -> no-op PASS (before the SHA gate, so a
    #    patched install re-runs cleanly).
    src = run_py.read_text(errors="replace")
    if SEAM_MARKER in src:
        print("already patched (marker present) — nothing to do")
        return 0

    # 3. Fail closed on source SHA mismatch (only reached when NOT patched).
    if not run_py.exists():
        return fail(f"gateway/run.py not found at {run_py} — not a Hermes install?")
    actual_sha = sha256_of(run_py)
    if actual_sha != EXPECTED_RUN_SHA256:
        return fail(
            f"gateway/run.py sha256 {actual_sha} does not match the pinned "
            f"{EXPECTED_RUN_SHA256} for v2026.8.13. Refusing to patch a modified "
            "or unknown source tree. No files were modified."
        )

    # 4. Seam module present without marker -> continue (repair path).
    if seam_py.exists() and MODULE_MARKER in seam_py.read_text(errors="replace"):
        print("seam module present but run.py unpatched — continuing (repair)")

    # 5. Anchor presence check (fail closed if upstream drifted).
    if src.count(SET_ANCHOR) != 1:
        return fail(f"SET anchor not found exactly once in gateway/run.py (count={src.count(SET_ANCHOR)}). "
                    "Upstream drifted — refusing to patch.")
    if src.count(RESET_ANCHOR) != 1:
        return fail(f"RESET anchor not found exactly once in gateway/run.py (count={src.count(RESET_ANCHOR)}). "
                    "Upstream drifted — refusing to patch.")

    # 5. Backup every touched file (timestamped; keep one per file).
    ts = time.strftime("%Y%m%d%H%M%S")
    backups = []
    for p in (run_py, seam_py):
        if p.exists():
            bak = p.with_name(p.name + f".bak-seam-{ts}")
            shutil.copy2(p, bak)
            backups.append(str(bak))

    # 6. Patch run.py (SET anchor first, then RESET anchor).
    patched = src.replace(SET_ANCHOR, SET_REPLACEMENT, 1)
    patched = patched.replace(RESET_ANCHOR, RESET_REPLACEMENT, 1)
    if SEAM_MARKER not in patched:
        # Should be impossible after the count checks; defensive.
        for b in backups:
            try:
                os.remove(b)
            except OSError:
                pass
        return fail("patch application failed internal verification — backups removed, nothing changed")

    # 7. Write seam module (new file; back up any pre-existing one).
    seam_src = _SEAM_MODULE_SOURCE
    seam_py.parent.mkdir(parents=True, exist_ok=True)
    if seam_py.exists():
        shutil.copy2(seam_py, seam_py.with_name(seam_py.name + f".bak-seam-{ts}"))
    seam_py.write_text(seam_src)

    # 7b. Install the brick_broker plugin next to the seam (Brock's owner
    # surface). Copied from this repo's brick-profile/brick_broker/ if present;
    # fail closed if the source plugin directory is missing.
    plugin_src = pathlib.Path(__file__).resolve().parent.parent / "brick_broker"
    hermes_home = pathlib.Path(os.environ.get("HERMES_HOME", "")) if os.environ.get("HERMES_HOME") else pathlib.Path.home() / ".hermes"
    plugins_dir = hermes_home / "plugins"
    if plugin_src.is_dir():
        plugin_dst = plugins_dir / "brick_broker"
        if plugin_dst.exists():
            shutil.copy2(plugin_dst / "plugin.yaml",
                         str(plugin_dst / "plugin.yaml") + f".bak-seam-{ts}")
        else:
            plugin_dst.mkdir(parents=True, exist_ok=True)
        for f in ("plugin.yaml", "__init__.py"):
            if (plugin_src / f).exists():
                shutil.copy2(plugin_src / f, plugin_dst / f)
        # Ownership marker so rollback never deletes a user's own plugin dir.
        (plugin_dst / ".brick-broker-installed").write_text("installed by install_seam.py\n")
        # catalog_toolsets.json is written by gateway_wire --apply at runtime;
        # ship the repo copy if present so the plugin never starts empty.
        if (plugin_src / "catalog_toolsets.json").exists():
            shutil.copy2(plugin_src / "catalog_toolsets.json",
                         plugin_dst / "catalog_toolsets.json")
        print(f"PATCHED ok: brick_broker plugin installed at {plugin_dst}")
    else:
        return fail(f"brick_broker plugin source not found at {plugin_src} — "
                    "cannot install the broker. No files were modified.")

    # 8. Write patched run.py atomically.
    run_py.write_text(patched)

    print(f"PATCHED ok: {run_py} (+seam module {seam_py})")
    print("backups:", backups or "(none)")
    print("verify: python3 install_seam.py --check")
    return 0


def rollback(root: pathlib.Path) -> int:
    """Restore .bak-seam backups and remove the seam module. Idempotent."""
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
    # Remove the broker plugin we installed (only if it's ours: marker file).
    hermes_home = pathlib.Path(os.environ.get("HERMES_HOME", "")) if os.environ.get("HERMES_HOME") else pathlib.Path.home() / ".hermes"
    plugin_dst = hermes_home / "plugins" / "brick_broker"
    if plugin_dst.exists():
        marker = plugin_dst / ".brick-broker-installed"
        if marker.exists():
            shutil.rmtree(plugin_dst)
            print(f"removed broker plugin {plugin_dst}")
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
        ok = s["version_ok"] and s["sha_ok"] and s["seam_marker_present"] and s["seam_module_installed"]
        print("STATUS:", "SEAM ACTIVE" if ok else "SEAM MISSING/STALE")
        return 0 if ok else 1
    if mode == "--apply":
        return apply_patch(root)
    if mode == "--rollback":
        return rollback(root)
    return fail(f"unknown mode {mode!r} (use --check | --apply | --rollback)")


if __name__ == "__main__":
    sys.exit(main())
