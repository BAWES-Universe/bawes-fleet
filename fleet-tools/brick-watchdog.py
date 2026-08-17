#!/usr/bin/env python3
"""ROUND-146 M2 (extends ROUND-139 F-15): EVERY-brick self-recovery watchdog.

Layers (each catches what the layer below cannot):
1. systemd Restart=always per unit -- process-exit recovery (round-139).
2. Heartbeat ladder per brick: last-ts <60s fresh; >90s stale -> restart the
   writer unit; >300s dead -> FLAG + khalid-notify (coalesced, ONE message
   per incident) -- round-146 abuse/monitoring directive.
3. Port liveness per unit (hung-but-alive catch, round-139).
4. Bad self-change rollback: snapshot -> probe -> revert (unit-file hash
   drift detected -> probe brick -> revert from known-good copy + strike),
   generalized from the round-139 card-6 agi_self_loop pattern via
   brick_guard.py -- now applies to EVERY supervised brick.
5. 3 strikes -> degraded (retrieval-only): watchdog stops restarting that
   brick, marks mode=degraded in state, notifies khalid ONCE. The door
   freshness gate (round-139 card 6c) already refuses serving claims for
   stale bricks, so degraded == honest retrieval-only at every surface.
6. Coverage enforcement: EVERY registered-live brick (registry rows with
   status:live / active:true) must have a supervision record in
   /srv/bricks/control/brick-supervision.json -- mode systemd | cron-loop |
   device. A registered-live brick WITHOUT a record is FLAGGED (never
   unsupervised-and-silent).

Per-brick modes:
- systemd   : unit(s) managed; writer unit restarted on stale heartbeat.
- cron-loop : cron IS the supervision (verify_consumer doctrine); evidence =
              last log write; stale -> FLAG (no restart possible/needed),
              dead -> khalid-notify.
- device    : registered+token, NO local process (rows appear only when the
              device runs its own heartbeat, F-16 self-only doctrine);
              stale -> FLAG, dead -> khalid-notify. NEVER restarts anything
              local (that was the relay-era failure mode).

Config: /srv/bricks/control/brick-supervision.json   (root:root 0644)
State : /srv/bricks/control/brick-supervision-state.json (root:root 0600)
Notify: /srv/bricks/control/khalid-notify.jsonl      (root:root 0600)
Log   : /var/log/brick-watchdog.log
Runs  : root cron every minute (/etc/cron.d/brick-watchdog).
"""
import json, os, subprocess, sys, time, urllib.request, urllib.error

sys.path.insert(0, "/srv/bricks/control")
import brick_guard  # noqa: E402

REGISTRY = os.environ.get("BRICK_REGISTRY", "/srv/bricks/registry/heartbeat-registry.jsonl")
SUPERVISION = os.environ.get("BRICK_SUPERVISION",
                             "/srv/bricks/control/brick-supervision.json")
CONTROL = os.environ.get("BRICK_CONTROL", "/srv/bricks/control")
NOTIFY_LEDGER = os.environ.get("BRICK_NOTIFY_LEDGER",
                               os.path.join(CONTROL, "khalid-notify.jsonl"))
LOG = os.environ.get("BRICK_LOG", "/var/log/brick-watchdog.log")
REGISTER = os.environ.get("BRICK_REGISTER", "/srv/bricks/register/registry.jsonl")

# liveness ladder (card values; per-brick overrides live in supervision.json)
FRESH_S = 60
STALE_S = 90
DEAD_S = 300
NOTIFY_COOLDOWN_S = 21600  # ONE message per incident per brick (6h dedup)
DRY_RUN = os.environ.get("BRICK_NOTIFY_DRYRUN", "0") == "1"  # tests only
KHALID_USER_ID = "189055515819638794"  # khalidalmutawa (door/consent ledger)
DOOR_ENV = "/srv/secrets/door.env"


def log(msg):
    with open(LOG, "a") as f:
        f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))


def load_supervision():
    try:
        with open(SUPERVISION) as f:
            return json.load(f)
    except Exception as e:
        log("ERROR loading %s: %s" % (SUPERVISION, e))
        return {}


def last_ts_per_brick():
    ts = {}
    try:
        with open(REGISTRY) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                ts[r.get("brick_id")] = int(r.get("ts", 0))
    except FileNotFoundError:
        log("ERROR registry missing: %s" % REGISTRY)
    return ts


def registered_live_bricks():
    """registry.jsonl rows with status:live or active:true -> brick_id set."""
    live = set()
    try:
        with open(REGISTER) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("status") == "live" or r.get("active") is True:
                    live.add(r.get("brick_id"))
    except FileNotFoundError:
        pass
    return live


def unit_active(unit):
    r = subprocess.run(["systemctl", "is-active", unit],
                       capture_output=True, text=True)
    return r.stdout.strip() == "active"


def restart(unit, why):
    log("RESTART %s (%s)" % (unit, why))
    subprocess.run(["systemctl", "restart", unit], capture_output=True, text=True)


def send_khalid_dm(text):
    """DA-ruled channel (round-144 R3): door bot DM to khalid, coalesced.
    Door bot token: /srv/secrets/door.env (0600). User-Agent mandatory."""
    if DRY_RUN:
        log("NOTIFY(dry-run) -> khalid DM: %s" % text[:160])
        return "dry-run"
    try:
        with open(DOOR_ENV) as f:
            tok = f.read().strip()
        if not tok:
            return "no-token"
        hdr = {"Authorization": "Bot " + tok,
               "Content-Type": "application/json",
               "User-Agent": "BAWES fleet watchdog (round-146 M2)"}
        req = urllib.request.Request(
            "https://discord.com/api/v10/users/@me/channels",
            data=json.dumps({"recipient_id": KHALID_USER_ID}).encode(),
            headers=hdr, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            ch = json.loads(r.read())
        req2 = urllib.request.Request(
            "https://discord.com/api/v10/channels/%s/messages" % ch["id"],
            data=json.dumps({"content": text}).encode(),
            headers=hdr, method="POST")
        with urllib.request.urlopen(req2, timeout=15) as r2:
            return "sent"
    except urllib.error.HTTPError as e:
        return "http-%s" % e.code
    except Exception as e:
        return "err:%s" % type(e).__name__


def notify_khalid(state, brick_id, kind, text):
    """Coalesced: ONE durable row + one DM per (brick, kind) per cooldown."""
    b = state.setdefault("bricks", {}).setdefault(brick_id, {})
    last = b.get("last_notify_%s" % kind, 0)
    now = int(time.time())
    if now - last < NOTIFY_COOLDOWN_S:
        return False  # already notified this incident
    row = {"kind": kind, "brick_id": brick_id, "ts": now, "text": text,
           "channel": "khalid-dm", "delivered": None}
    with open(NOTIFY_LEDGER, "a") as f:
        f.write(json.dumps(row) + "\n")
    res = send_khalid_dm(text)
    row["delivered"] = res
    with open(NOTIFY_LEDGER, "a") as f:
        f.write(json.dumps({"kind": kind, "brick_id": brick_id, "ts": now,
                            "delivery_result": res}) + "\n")
    b["last_notify_%s" % kind] = now
    log("NOTIFY %s %s (delivery=%s)" % (kind, brick_id, res))
    return True


def check_cron_brick(brick_id, rec, state, now):
    """cron-loop bricks: evidence = last log write. Cron is their restart."""
    ev = rec.get("evidence")
    stale_s = rec.get("stale_s", 2 * rec.get("interval_s", 1800))
    dead_s = rec.get("dead_s", 4 * rec.get("interval_s", 1800))
    if not ev or not os.path.exists(ev):
        log("FLAG %s: cron evidence missing (%s)" % (brick_id, ev))
        notify_khalid(state, brick_id, "dead",
                      "🍌 BAWES: %s has NO cron evidence (%s) — check the loop." % (brick_id, ev))
        return
    age = now - os.path.getmtime(ev)
    if age > dead_s:
        log("FLAG %s: cron-loop DEAD (no evidence %ds)" % (brick_id, age))
        notify_khalid(state, brick_id, "dead",
                      "🍌 BAWES: %s cron-loop is DEAD — no run for %ds. "
                      "Last evidence %s." % (brick_id, age, ev))
    elif age > stale_s:
        log("FLAG %s: cron-loop stale (no evidence %ds)" % (brick_id, age))


def check_device_brick(brick_id, rec, ts_map, state, now):
    """device bricks: own heartbeat only (F-16). Flag/notify, never restart."""
    writer = rec.get("writer", brick_id)
    last = ts_map.get(writer)
    stale_s = rec.get("stale_s", STALE_S)
    dead_s = rec.get("dead_s", DEAD_S)
    if last is None:
        log("FLAG %s: device brick registered but NEVER heartbeated (no local "
            "process — install pending?)" % brick_id)
        return
    age = now - last
    if age > dead_s:
        log("FLAG %s: device brick DEAD (heartbeat %ds old)" % (brick_id, age))
        notify_khalid(state, brick_id, "dead",
                      "🍌 BAWES: %s device brick is DEAD — no heartbeat for %ds."
                      % (brick_id, age))
    elif age > stale_s:
        log("FLAG %s: device brick stale (heartbeat %ds old)" % (brick_id, age))


def check_systemd_brick(brick_id, rec, ts_map, state, now):
    """systemd bricks: heartbeat ladder on the writer + port liveness +
    snapshot->probe->revert on unit drift + strikes -> degraded."""
    unit = rec.get("unit")
    writer = rec.get("writer")
    ports = rec.get("ports") or []
    stale_s = rec.get("stale_s", STALE_S)
    dead_s = rec.get("dead_s", DEAD_S)
    b = state.setdefault("bricks", {}).setdefault(brick_id, {})

    if brick_guard.is_degraded(state, brick_id):
        # degraded: retrieval-only. No auto-restart churn; keep flagging.
        log("DEGRADED %s: watchdog passive (retrieval-only, no restarts)" % brick_id)
        return

    # --- bad self-change rollback: unit-file drift -> APPLY -> probe -> revert ---
    # (generalized round-139 card 6: snapshot before, apply, probe after,
    #  auto-revert on fail — the drift IS the apply signal)
    if unit:
        snap = brick_guard.snapshot_brick(rec, CONTROL)
        good = b.get("good_unit_sha256")
        cur = snap.get("unit_sha256")
        if cur and good and cur != good:
            log("SELFCHANGE %s: unit file hash drift (good=%s cur=%s) — applying "
                "then probing" % (brick_id, good[:12], cur[:12]))
            # apply the change (make it live), then probe — a change that only
            # looks fine while the old process still runs is NOT accepted
            subprocess.run(["systemctl", "restart", unit], capture_output=True, text=True)
            time.sleep(3)
            ok, reason = brick_guard.probe_brick(rec, ts_map, now)
            if not ok:
                rc, err = brick_guard.revert_brick(rec, snap, good_sha=good)
                strikes, degraded = brick_guard.register_strike(state, brick_id,
                                                                "unit drift probe fail: %s" % reason)
                log("REVERT %s (rc=%s err=%s) strike=%d degraded=%s"
                    % (brick_id, rc, err, strikes, degraded))
                if degraded:
                    notify_khalid(state, brick_id, "degraded",
                                  "🍌 BAWES: %s DEGRADED (3 strikes — retrieval-only). "
                                  "Auto-restarts stopped; door reports waking-not-serving. "
                                  "Fleet queue ticket opened." % brick_id)
                return
            # probe passed -> the self-change survived a restart; accept
            log("SELFCHANGE %s: probe OK after restart — accepting new unit state" % brick_id)
            brick_guard.clear_strikes(state, brick_id)
            brick_guard.persist_good_unit(rec, CONTROL)
            b["good_unit_sha256"] = cur
        elif cur and good is None:
            # first sighting: persist this as the known-good baseline
            brick_guard.persist_good_unit(rec, CONTROL)
            b["good_unit_sha256"] = cur

    # --- heartbeat ladder (writer row freshness) ---
    if writer:
        last = ts_map.get(writer)
        if last is None or (now - last) > dead_s:
            age = "missing" if last is None else "%ds" % (now - last)
            log("FLAG %s: brick DEAD (heartbeat %s)" % (brick_id, age))
            notify_khalid(state, brick_id, "dead",
                          "🍌 BAWES: %s is DEAD — heartbeat %s. Watchdog can't "
                          "revive; check the unit." % (brick_id, age))
            return
        if (now - last) > stale_s:
            # restart the writer; if a restart happened very recently and the
            # row is STILL stale, the restart did not fix it -> strike.
            last_restart = b.get("last_restart_ts", 0)
            if now - last_restart < 120:
                strikes, degraded = brick_guard.register_strike(
                    state, brick_id,
                    "restart did not revive heartbeat (%ds stale)" % (now - last))
                log("STRIKE %s (strikes=%d degraded=%s)" % (brick_id, strikes, degraded))
                if degraded:
                    notify_khalid(state, brick_id, "degraded",
                                  "🍌 BAWES: %s DEGRADED (3 strikes — retrieval-only). "
                                  "Auto-restarts stopped; door reports waking-not-serving. "
                                  "Fleet queue ticket opened." % brick_id)
                return
            log("STALE %s: heartbeat %ds old -> restart writer %s"
                % (brick_id, now - last, unit))
            restart(unit, "registry row %s stale (%ds)" % (brick_id, now - last))
            b["last_restart_ts"] = now
            return

    # --- port liveness per unit (hung-but-alive catch) ---
    for port, punit in ports.items():
        if not unit_active(punit):
            restart(punit, "unit not active (port %s)" % port)
            return
        r = subprocess.run(["ss", "-tln"], capture_output=True, text=True)
        needle = ":%s " % port
        if needle not in r.stdout and (":%s\t" % port) not in r.stdout:
            restart(punit, "port %s not listening while unit active" % port)
            return
    # healthy tick: clear strikes so a single blip is not fatal
    brick_guard.clear_strikes(state, brick_id)


def main():
    now = int(time.time())
    cfg = load_supervision()
    ts_map = last_ts_per_brick()
    state = brick_guard.load_state(CONTROL)
    state.setdefault("bricks", {})

    # coverage enforcement: every registered-live brick must be supervised
    live = registered_live_bricks()
    for bid in sorted(live):
        if bid not in cfg:
            log("COVERAGE-GAP: registered-live brick %s has NO supervision "
                "record (add to %s)" % (bid, SUPERVISION))

    for brick_id, rec in cfg.items():
        mode = rec.get("mode", "systemd")
        if mode == "cron-loop":
            check_cron_brick(brick_id, rec, state, now)
        elif mode == "device":
            check_device_brick(brick_id, rec, ts_map, state, now)
        else:
            check_systemd_brick(brick_id, rec, ts_map, state, now)

    brick_guard.save_state(CONTROL, state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
