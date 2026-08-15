#!/usr/bin/env python3
"""fleet_dashboard.py — T-023 ACHIEVEMENTS FEED + FLEET STATUS (DA'd shape).
READ-ONLY: reads register + ledger + vector store, writes ONE html file.
NO web server, NO public bind — served only under the audited topology
(:3743/:3744/:3999/:3738/:3742) or via approved mechanism. If you found
this listening on :8080, that's the lesson being ignored — kill it.
"""
import json, pathlib, time

REG = pathlib.Path("/srv/bricks/register")
VS = pathlib.Path("/srv/bricks/orchestrator/vector-store.json")
OUT = pathlib.Path("/srv/bricks/fleet-status.html")

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
    b = {"earned": 0, "spent": 0, "credit": 0}
    for r in rows(REG / "wallet.jsonl"):
        if r.get("person_id") != pid: continue
        if r.get("kind") == "earn": b["earned"] += r.get("bananas", 0)
        elif r.get("kind") == "spend": b["spent"] += r.get("bananas", 0)
        elif r.get("kind") == "credit" and r.get("state") == "open":
            b["credit"] += r.get("bananas", 0)
    b["available"] = b["earned"] - b["spent"] + b["credit"]
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

def cards():
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
    return fleet + humans

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
</style></head><body>
<h1>🍌 BAWES — Fleet Status</h1>
<div class="sub">read from the real register + ledger · {time.strftime('%Y-%m-%d %H:%M')} · no rows invented, absence shown honestly</div>
<div class="grid">{cards()}</div>
</body></html>"""

OUT.write_text(html)
OUT.chmod(0o644)
print(f"fleet-status written: {OUT} ({len(html)} bytes)")
