#!/usr/bin/env python3
"""ROUND-146 M2 (generalizes round-139 card 6): brick self-recovery guard.

The round-139 card-6 snapshot->probe->revert pattern lived inside
agi_self_loop.py (compose-world). M2 generalizes it to ANY supervised brick
(systemd unit or cron-loop) so EVERY registered live brick can roll back a
bad self-change and degrade honestly after 3 strikes.

API (importable by any brick loop or the watchdog):
  snapshot_brick(rec, state_dir)  -> dict (unit-file hash, ports up, heartbeat age)
  probe_brick(rec, ts_map, now)   -> (ok: bool, reason: str|None)
  revert_brick(rec, snap)         -> (rc, err)  restore unit file + reload + restart
  register_strike(state, brick_id, reason) -> (strikes, degraded)  # 3 -> degraded
  load_state / save_state

State file: <state_dir>/brick-supervision-state.json (root-owned).
Strike rules (matches smart_evolution_guard doctrine):
  1 strike  = restart happened but the brick still fails the next probe
  3 strikes = degraded: retrieval-only — watchdog stops restarting it,
              flags it, notifies khalid once (round-146 abuse/monitoring).
"""
import hashlib, json, os, subprocess, time

FRESH_S = int(os.environ.get("BRICK_FRESH_S", "60"))
STALE_S = int(os.environ.get("BRICK_STALE_S", "90"))
DEAD_S = int(os.environ.get("BRICK_DEAD_S", "300"))
MAX_STRIKES = 3


def load_state(state_dir):
    p = os.path.join(state_dir, "brick-supervision-state.json")
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {"bricks": {}}


def save_state(state_dir, state):
    p = os.path.join(state_dir, "brick-supervision-state.json")
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)


def _sha256_file(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return None


def unit_active(unit):
    r = subprocess.run(["systemctl", "is-active", unit],
                       capture_output=True, text=True)
    return r.stdout.strip() == "active"


def ports_listening(ports):
    """ports: iterable of ints or numeric strings. Returns (ok, missing)."""
    r = subprocess.run(["ss", "-tln"], capture_output=True, text=True)
    out = r.stdout
    missing = []
    for p in ports:
        p = int(p)
        if (":%d " % p) not in out and (":%d\t" % p) not in out:
            missing.append(p)
    return (len(missing) == 0), missing


def snapshot_brick(rec, state_dir):
    """Capture the supervised state of a brick (hashes + liveness only).
    NOTE: does NOT persist anything — the known-good unit copy is written
    ONLY by persist_good_unit() after a probe passes (see watchdog), so a
    tampered file can never poison the restore source."""
    snap = {"ts": int(time.time())}
    unit = rec.get("unit")
    if unit:
        # systemd unit file bytes (the supervisor contract)
        for cand in ("/etc/systemd/system/%s" % unit,
                     "/etc/systemd/system/%s" % unit.replace(".service", ".service")):
            if os.path.exists(cand):
                with open(cand, "rb") as f:
                    snap["unit_sha256"] = hashlib.sha256(f.read()).hexdigest()
                snap["unit_path"] = cand
                break
        snap["unit_active"] = unit_active(unit)
    ports = rec.get("ports") or []
    if ports:
        ok, missing = ports_listening(ports)
        snap["ports"] = ports
        snap["ports_up"] = ok
        snap["ports_missing"] = missing
    snap["execstart"] = _read_execstart(unit)
    return snap


def persist_good_unit(rec, state_dir):
    """Write the CURRENT unit bytes to <state_dir>/units/<unit> (root-owned
    0600). Call ONLY when the unit is verified healthy — this is the
    tamper-proof restore source (control dir is root:root 0755)."""
    unit = rec.get("unit")
    if not unit:
        return None
    path = None
    for cand in ("/etc/systemd/system/%s" % unit,
                 "/etc/systemd/system/%s" % unit.replace(".service", ".service")):
        if os.path.exists(cand):
            path = cand
            break
    if not path:
        return None
    snap_dir = os.path.join(state_dir, "units")
    os.makedirs(snap_dir, exist_ok=True)
    snap_f = os.path.join(snap_dir, unit)
    with open(path, "rb") as src, open(snap_f, "wb") as dst:
        dst.write(src.read())
    os.chmod(snap_f, 0o600)
    return snap_f


def _read_execstart(unit):
    if not unit:
        return None
    r = subprocess.run(["systemctl", "cat", unit], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith("ExecStart="):
            return line[len("ExecStart="):].strip()
    return None


def probe_brick(rec, ts_map, now):
    """Post-change probe: unit active + ports listening + heartbeat fresh.
    Returns (ok, reason)."""
    unit = rec.get("unit")
    if unit and not unit_active(unit):
        return False, "unit %s not active" % unit
    ports = rec.get("ports") or []
    if ports:
        ok, missing = ports_listening(ports)
        if not ok:
            return False, "ports missing: %s" % missing
    writer = rec.get("writer")
    if writer:
        last = ts_map.get(writer)
        if last is None:
            return False, "heartbeat row for %s missing" % writer
        age = now - last
        stale_s = rec.get("stale_s", STALE_S)
        if age > stale_s:
            return False, "heartbeat stale (%ds)" % age
    return True, None


def revert_brick(rec, snap, good_sha=None):
    """AUTO-REVERT: restore the LAST ACCEPTED GOOD unit file + reload + restart.
    Restore sources, in order: the persisted root-owned copy in
    <state_dir>/units/ (written only on acceptance — never on tamper), then
    .bak-r146-m2 / .bak-r139 backups. The target sha is the recorded GOOD
    hash (snap carries the CURRENT/tampered hash; good_sha is the accepted
    one). Returns (rc, err)."""
    unit = rec.get("unit")
    if not unit or "unit_sha256" not in snap:
        return 1, "no unit snapshot to revert"
    want = good_sha or snap.get("good_unit_sha256")
    path = snap.get("unit_path")
    candidates = []
    if path:
        candidates.append(os.path.join(os.path.dirname(path), unit + ".bak-r146-m2"))
        candidates.append(os.path.join(os.path.dirname(path), unit + ".bak-r139"))
    # the persisted known-good copy (root-owned snapshot) is the primary source
    snap_f = None
    for sd in (os.environ.get("BRICK_CONTROL", "/srv/bricks/control"),
               "/srv/bricks/control"):
        c = os.path.join(sd, "units", unit)
        if os.path.exists(c):
            snap_f = c
            break
    if snap_f:
        candidates.insert(0, snap_f)
    good = None
    for cand in candidates:
        if cand and os.path.exists(cand) and _sha256_file(cand) == want:
            good = cand
            break
    if good is None:
        return 2, "no known-good unit copy (want sha %s)" % (want or "?")
    try:
        if os.path.abspath(good) != os.path.abspath(path):
            subprocess.run(["cp", "-p", good, path], check=True)
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True, text=True)
        r = subprocess.run(["systemctl", "restart", unit], capture_output=True, text=True)
        return r.returncode, r.stderr.strip()[:200]
    except Exception as e:
        return 3, str(e)


def register_strike(state, brick_id, reason):
    """Count a death strike; at MAX_STRIKES mark the brick degraded
    (retrieval-only). Returns (strikes, degraded)."""
    b = state.setdefault("bricks", {}).setdefault(brick_id, {})
    b["strikes"] = b.get("strikes", 0) + 1
    b["last_strike"] = int(time.time())
    b["last_strike_reason"] = reason
    degraded = False
    if b["strikes"] >= MAX_STRIKES:
        b["degraded"] = True
        b["mode"] = "degraded"
        b["degraded_at"] = int(time.time())
        b["degraded_reason"] = reason
        degraded = True
    return b["strikes"], degraded


def clear_strikes(state, brick_id):
    b = state.setdefault("bricks", {}).setdefault(brick_id, {})
    b["strikes"] = 0
    b["mode"] = "full"
    b.pop("degraded", None)


def is_degraded(state, brick_id):
    b = state.get("bricks", {}).get(brick_id, {})
    return bool(b.get("degraded")) or b.get("mode") == "degraded"
