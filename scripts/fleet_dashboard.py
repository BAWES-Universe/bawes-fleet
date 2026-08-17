#!/usr/bin/env python3
"""fleet_dashboard.py — T-023 ACHIEVEMENTS FEED + FLEET STATUS (DA'd shape).
READ-ONLY: reads register + ledger + router state + vector store, writes
ONE html file + brick-status.json (round-139 card 8 / F-19).
NO web server, NO public bind — served only under the audited topology
(:3743/:3744/:3999/:3738/:3742) or via approved mechanism. If you found
this listening on :8080, that's the lesson being ignored — kill it.

round-139 card 8 (transparency surface — F-19): the BRICK STATUS member
section + brick-status.json are DERIVED, never hand-written — cost/call +
activity from the router ledger, latency from measurements.jsonl, caps from
token records (tokens-meta.jsonl), receipts from wallet earn rows. Pricing
stays labelled 'provisional, unanchored' until real cost rows carrying
invoice_doc_hash exist (the peg). Absence is shown honestly ("—"/no calls).
"""
import json, pathlib, time

REG = pathlib.Path("/srv/bricks/register")
VS = pathlib.Path("/srv/bricks/orchestrator/vector-store.json")
OUT = pathlib.Path("/srv/bricks/fleet-status.html")
ROUTER_STATE = pathlib.Path("/srv/bricks/router/state")
LEDGER = ROUTER_STATE / "ledger.jsonl"
MEASUREMENTS = REG / "measurements.jsonl"
TOKENS_META = ROUTER_STATE / "tokens-meta.jsonl"
BRICK_STATUS_OUT = pathlib.Path("/srv/bricks/brick-status.json")
PRICING_PEG = "invoice_doc_hash"     # real cost rows carrying this key = anchored
HUMAN_PIDS = {"189055", "231861", "690554066815811625"}

HUMANS = [
    {"id": "189055", "name": "Khalid", "brick": "khalid-device-001"},
    {"id": "231861", "name": "Mishari", "brick": "mishari-device-001"},
    {"id": "690554066815811625", "name": "Chahd", "brick": "chahd-cloud-001"},
]

def rows(p):
    out = []
    if p.exists():
        for line in open(p):
            line = line.strip()
            if line:
                try: out.append(json.loads(line))
                except Exception: pass
    return out

def wallet(pid):
    b = {"earned": 0, "spent": 0, "credit": 0, "seed": 0}
    for r in rows(REG / "wallet.jsonl"):
        if r.get("person_id") != pid: continue
        if r.get("kind") == "earn": b["earned"] += r.get("bananas", 0)
        elif r.get("kind") == "spend": b["spent"] += r.get("bananas", 0)
        elif r.get("kind") == "founder-seed" and r.get("state") == "open":
            b["seed"] += r.get("bananas", 0)
        elif r.get("kind") == "credit" and r.get("state") == "open":
            b["credit"] += r.get("bananas", 0)
    b["available"] = b["earned"] - b["spent"] + b["credit"] + b["seed"]
    return b

def achievements(pid):
    """Achievements = verified outputs + consent + gifts, from the REAL record."""
    out = []
    for r in rows(REG / "consent-transcripts.jsonl"):
        if str(r.get("person_id", "")) == pid or pid in str(r.get("brick_id", "")):
            out.append(f"consent recorded: {r.get('event','?')} (evidence box)")
    for r in rows(REG / "wallet.jsonl"):
        if r.get("person_id") != pid: continue
        if r.get("kind") == "credit" and r.get("state") == "open":
            out.append(f"gift credit: {r.get('bananas')}🍌 ({r.get('purpose','gift')})")
    for r in rows(REG / "ledger-cost-rows.log"):
        if str(r.get("person_id", "")) == pid:
            out.append(f"verified work: {r.get('tasks_verified',0)} tasks, {r.get('writeups',0)} write-ups")
    return out or ["no achievements yet — the door is open"]

def vs_stats():
    if VS.exists():
        return json.load(open(VS)).get("stats", {})
    return {}

def fmt_ts(ts):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts)))
    except Exception:
        return "?"

def brick_status():
    """round-139 card 8 (F-19): per-brick status DERIVED from the real
    record — ledger (cost/call, activity), measurements (latency), token
    records (caps), wallet (receipts), registry. Nothing hand-written."""
    registry = {r.get("brick_id"): r for r in rows(REG / "registry.jsonl")
                if r.get("brick_id")}

    # ledger: cost/call + activity per consumer
    per = {}
    for r in rows(LEDGER):
        b = r.get("consumer")
        if not b:
            continue
        d = per.setdefault(b, {"calls": 0, "cost_total": 0.0, "lanes": {}, "last_ts": 0})
        d["calls"] += 1
        d["cost_total"] += float(r.get("cost", 0) or 0)
        d["lanes"][r.get("lane", "?")] = d["lanes"].get(r.get("lane", "?"), 0) + 1
        d["last_ts"] = max(d["last_ts"], int(r.get("ts", 0) or 0))

    # measurements: latency per brick
    for r in rows(MEASUREMENTS):
        b = r.get("brick_id")
        if not b:
            continue
        d = per.setdefault(b, {"calls": 0, "cost_total": 0.0, "lanes": {}, "last_ts": 0})
        d.setdefault("lat_ms", []).append(float(r.get("latency_ms", 0) or 0))

    # caps from active token records (tokens-meta.jsonl)
    caps = {}
    for r in rows(TOKENS_META):
        if r.get("brick_id") and r.get("status") == "active":
            caps[r["brick_id"]] = float(r.get("spend_cap_usd", 0) or 0)

    # receipts = wallet EARN rows per brick
    receipts = {}
    for r in rows(REG / "wallet.jsonl"):
        b = r.get("brick_id")
        if not b or r.get("kind") != "earn":
            continue
        d = receipts.setdefault(b, {"earns": 0, "bananas": 0})
        d["earns"] += 1
        d["bananas"] += int(r.get("bananas", 0) or 0)

    # pricing peg: anchored only when REAL cost rows carry invoice_doc_hash
    anchored = 0
    for src in (LEDGER, REG / "ledger-cost-rows.log"):
        for r in rows(src):
            if isinstance(r, dict) and r.get(PRICING_PEG):
                anchored += 1
    pricing = {"status": "anchored" if anchored else "provisional",
               "label": "anchored" if anchored else "provisional, unanchored",
               "peg": PRICING_PEG, "anchored_rows": anchored}

    # member set: registry ∪ ledger consumers ∪ token holders ∪ wallet
    # earners ∪ human-owned bricks (absent data shown honestly)
    brick_ids = set(registry) | set(per) | set(caps) | set(receipts)
    for r in rows(REG / "wallet.jsonl"):
        if r.get("brick_id") and r.get("person_id") in HUMAN_PIDS:
            brick_ids.add(r["brick_id"])

    bricks = {}
    for b in sorted(brick_ids):
        d = per.get(b, {})
        lat = sorted(d.get("lat_ms") or [])
        p95 = lat[int(len(lat) * 0.95)] if lat else None
        used = d.get("cost_total", 0.0)
        cap = caps.get(b)
        reg = registry.get(b) or {}
        bricks[b] = {
            "registry": {"quality": reg.get("quality", "unregistered"),
                         "active": bool(reg.get("active", True))},
            "activity": {"calls": d.get("calls", 0),
                         "last_invoke_ts": d.get("last_ts") or None},
            "cost": {"calls": d.get("calls", 0),
                     "total_usd": round(d.get("cost_total", 0.0), 6),
                     "avg_usd_per_call": (round(d.get("cost_total", 0.0) / d["calls"], 6)
                                          if d.get("calls") else None),
                     "by_lane": d.get("lanes", {})},
            "latency_ms": {"measurements": len(lat),
                           "avg": round(sum(lat) / len(lat), 1) if lat else None,
                           "p95": round(p95, 1) if p95 is not None else None},
            "caps": {"spend_cap_usd": cap,
                     "spend_used_usd": round(used, 6),
                     "remaining_usd": round(cap - used, 6) if cap is not None else None},
            "receipts": receipts.get(b, {"earns": 0, "bananas": 0}),
        }
    return {"generated_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pricing": pricing, "bricks": bricks}

def member_section(bs):
    """round-139 card 8: per-brick status card — derived, never hand-written."""
    p = bs["pricing"]
    badge = ("<span class='prov'>PROVISIONAL, UNANCHORED</span>" if p["status"] == "provisional"
             else "<span class='anch'>ANCHORED</span>")
    trs = ""
    for b, st in bs["bricks"].items():
        c, l, a, cap, rc = st["cost"], st["latency_ms"], st["activity"], st["caps"], st["receipts"]
        cost = f"${c['avg_usd_per_call']:.4f}" if c["avg_usd_per_call"] is not None else "—"
        lat = f"{l['avg']:.0f} ms" if l["avg"] is not None else "—"
        act = fmt_ts(a["last_invoke_ts"]) if a["last_invoke_ts"] else "no calls yet"
        capv = (f"${cap['spend_used_usd']:.4f} / ${cap['spend_cap_usd']:.2f}"
                if cap["spend_cap_usd"] is not None else "no token")
        rec = f"{rc['bananas']}🍌 · {rc['earns']} earns" if rc["earns"] else "—"
        trs += (f"<tr><td><b>{b}</b></td>"
                f"<td>{cost}<br><span class='m'>{c['calls']} calls · ${c['total_usd']:.4f} total</span></td>"
                f"<td>{lat}<br><span class='m'>{l['measurements']} meas</span></td>"
                f"<td>{act}</td><td>{capv}</td><td>{rec}</td></tr>")
    return f"""
    <div class="card member">
      <h2>🧱 BRICK STATUS — derived (F-19)</h2>
      <div class="price">pricing: {badge} — real cost rows with <code>{p['peg']}</code> are the peg ({p['anchored_rows']} anchored rows)</div>
      <table class="member">
        <tr><th>Brick</th><th>Cost / call</th><th>Latency</th><th>Last activity</th><th>Cap (used / limit)</th><th>Receipts</th></tr>
        {trs}
      </table>
    </div>"""

def allowance_card():
    """round-146 item 3: OPEN ALLOWANCE ALERTS + per-person bucket — DERIVED
    read-only from allowances.jsonl (the escalation surface, R3.4/R6)."""
    try:
        import sys as _sys
        _sys.path.insert(0, "/srv/bricks/ovh-server-001")
        import allowance_meter as m
        rows = m.read()
    except Exception as e:
        return (f"<div class='card'><h2>🍌 ALLOWANCE ALERTS</h2>"
                f"<p class='m'>meter unavailable: {str(e)[:80]}</p></div>")
    mth = m.month()
    alerts = [r for r in rows if r.get("kind") == "alert"
              and r.get("month") == mth]
    open_alerts = []
    for r in alerts:
        st = m.alert_status(r.get("alert_id"))
        if st.get("state") != "closed":
            open_alerts.append((r, st))
    rows_html = ""
    if open_alerts:
        for r, st in open_alerts:
            name = r.get("name") or m.person_name(r.get("person_id", ""))
            rows_html += (f"<tr><td>{name} ({r.get('brick_id','?')})</td>"
                          f"<td>{r.get('usage')}/{r.get('allowance')}</td>"
                          f"<td>${float(r.get('cost_usd') or 0):.4f}</td>"
                          f"<td>{st.get('state')}</td></tr>")
    else:
        rows_html = ("<tr><td colspan='4' class='m'>no open alerts — "
                     "nobody is blocked</td></tr>")
    # per-person bucket lines
    people = sorted({r.get("person_id") for r in rows
                     if r.get("kind") == "usage_debit" and r.get("month") == mth})
    bucket_lines = ""
    for p in people:
        b = m.bucket(p, mth)
        bucket_lines += (f"<tr><td>{m.person_name(p)}</td>"
                         f"<td>{b['usage']}/{b['allowance']} free"
                         f"{' · ' + str(b['paid']) + ' paid' if b['paid'] else ''}</td>"
                         f"<td>{'⛔ at cap — retrieval-only' if b['exhausted'] else 'ok'}</td></tr>")
    return f"""
    <div class="card member">
      <h2>🍌 ALLOWANCE ALERTS (round-146) — derived, read-only</h2>
      <table class="member">
        <tr><th>Person (brick)</th><th>Usage</th><th>Cost so far</th><th>Alert state</th></tr>
        {rows_html}
      </table>
      <div class="price">Buckets this month: {len(people)} metered person(s)</div>
      <table class="member">
        <tr><th>Person</th><th>Free usage / allowance</th><th>State</th></tr>
        {bucket_lines}
      </table>
    </div>"""

def cards(bs):
    st = vs_stats()
    fleet = f"""
    <div class="card fleet">
      <h2>🏗️ FLEET</h2>
      <table>
        <tr><td>Knowledge store</td><td>{st.get('raw_in',0)} write-ups · {st.get('novel',0)} novel · {st.get('duplicates',0)} dup caught</td></tr>
        <tr><td>Evolution standard</td><td>V-18: NOVEL rate is the number</td></tr>
        <tr><td>Last measurement</td><td>V-20b: NOVEL 1.00 on 12 real tasks, $0</td></tr>
        <tr><td>Economy</td><td>earn = verified work · spend = T-026 upgrade, receipted</td></tr>
      </table>
    </div>"""
    humans = ""
    for h in HUMANS:
        w = wallet(h["id"])
        ach = "".join(f"<li>{a}</li>" for a in achievements(h["id"]))
        humans += f"""
    <div class="card">
      <h2>{h['name']}</h2>
      <table>
        <tr><td>Brick</td><td><b>{h['brick']}</b></td></tr>
        <tr><td>Available</td><td><b>🍌 {w['available']}</b> (earned {w['earned']} · spent {w['spent']} · credit {w['credit']})</td></tr>
      </table>
      <div class="ach"><b>Achievements</b><ul>{ach}</ul></div>
    </div>"""
    return fleet + humans + allowance_card() + member_section(bs)

bs = brick_status()
BRICK_STATUS_OUT.write_text(json.dumps(bs, indent=2) + "\n")
BRICK_STATUS_OUT.chmod(0o644)
print(f"brick-status written: {BRICK_STATUS_OUT} "
      f"(pricing={bs['pricing']['label']}, anchored_rows={bs['pricing']['anchored_rows']}, "
      f"{len(bs['bricks'])} bricks)")

html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>BAWES — Fleet Status</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body {{ font-family: -apple-system, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; padding: 20px; }}
 h1 {{ font-size: 22px; margin: 0 0 4px; }} .sub {{ color: #8b949e; font-size: 13px; margin-bottom: 20px; }}
 .grid {{ display: flex; flex-wrap: wrap; gap: 16px; }}
 .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 16px; min-width: 270px; max-width: 420px; }}
 .card h2 {{ margin: 0 0 10px; font-size: 17px; }}
 table {{ border-collapse: collapse; width: 100%; }}
 td {{ padding: 4px 6px; font-size: 14px; border-bottom: 1px solid #21262d; vertical-align: top; }}
 td:first-child {{ color: #8b949e; }}
 .ach {{ margin-top: 12px; font-size: 13px; color: #8b949e; }} .ach ul {{ margin: 6px 0 0; padding-left: 18px; }}
 .ach li {{ margin: 3px 0; color: #e6edf3; }}
 .fleet {{ background: #101623; }}
 .card.member {{ min-width: 620px; max-width: 940px; }}
 .member th {{ color: #8b949e; font-size: 12px; text-align: left; padding: 4px 6px; border-bottom: 1px solid #21262d; }}
 .member td {{ font-size: 13px; }}
 .m {{ color: #8b949e; font-size: 11px; }}
 .price {{ margin: 6px 0 10px; font-size: 13px; background: #1c2128; border: 1px solid #30363d; border-radius: 6px; padding: 6px 8px; }}
 .prov {{ color: #f0b429; font-weight: 600; }}
 .anch {{ color: #3fb950; font-weight: 600; }}
 code {{ color: #79c0ff; }}
</style></head><body>
<h1>🍌 BAWES — Fleet Status</h1>
<div class="sub">read from the real register + ledger · {time.strftime('%Y-%m-%d %H:%M')} · no rows invented, absence shown honestly</div>
<div class="grid">{cards(bs)}</div>
</body></html>"""

OUT.write_text(html)
OUT.chmod(0o644)
print(f"fleet-status written: {OUT} ({len(html)} bytes)")
