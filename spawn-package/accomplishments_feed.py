#!/usr/bin/env python3
"""accomplishments_feed.py — the ACCOMPLISHMENTS feed (agreed process, round-84).
Reads REAL ledger state and renders a live feed: every verified card -> mint ->
accomplishment. Fed by the same loop that mints. No fabricated entries.
"""
import json, pathlib, time

REG = pathlib.Path("/srv/bricks/register")
ORCH = pathlib.Path("/srv/bricks/orchestrator")

def read(p):
    if not p.exists(): return []
    out = []
    for line in open(p):
        line = line.strip()
        if not line: continue
        try: out.append(json.loads(line))
        except Exception: pass
    return out

def render():
    wallet = read(REG / "wallet.jsonl")
    dispatches = read(ORCH / "dispatches.jsonl")
    store = json.loads((ORCH / "vector-store.json").read_text()) if (ORCH / "vector-store.json").exists() else {"docs": []}
    registry = read(REG / "registry.jsonl")

    # accomplishments = mint rows (verified, traced) — the ONLY source
    mints = [w for w in wallet if "card_id" in w]
    mints.sort(key=lambda r: r.get("ts", ""), reverse=True)

    rows = []
    for m in mints:
        cid = m.get("card_id", "?")
        rows.append(f"""
        <div class="acc">
          <span class="banana">🍌</span>
          <div class="body">
            <div class="title">{cid}</div>
            <div class="meta">+{m.get('bananas', 0)} banana · worker {m.get('brick_id','?')} · {m.get('ts','')[:19]}</div>
            <div class="meta">dispatch {m.get('dispatch_id','')[:12]} · kind {m.get('kind','legacy')}</div>
          </div>
        </div>""")

    # spawns from registry lineage
    spawned = [r for r in registry if r.get("parent_brick_id")]
    spawn_rows = "".join(
        f'<div class="acc"><span class="baby">🧬</span><div class="body"><div class="title">{r["brick_id"]}</div><div class="meta">spawned by {r["parent_brick_id"]} · {time.strftime("%Y-%m-%d %H:%M", time.gmtime(r.get("ts",0)))}</div></div></div>'
        for r in spawned)

    topics = len(store.get("docs", []))
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>BAWES — Accomplishments</title>
<style>body{{font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;max-width:640px;margin:0 auto;padding:24px}}
h1{{font-size:20px}} .sub{{color:#8b949e;font-size:13px;margin-bottom:16px}}
.acc{{display:flex;gap:12px;padding:12px 0;border-bottom:1px solid #21262d}}
.banana,.baby{{font-size:22px}} .title{{font-weight:600}} .meta{{color:#8b949e;font-size:12px}}</style></head>
<body><h1>🍌 BAWES — Accomplishments</h1>
<div class="sub">verified work only · {len(mints)} mints · {topics} brain topics · {len(registry)} bricks · live feed</div>
{''.join(rows)}
<div class="sub" style="margin-top:8px">🧬 spawns</div>{spawn_rows}
</body></html>"""
    (REG / "accomplishments.html").write_text(html)
    print(f"feed: {len(mints)} accomplishments rendered")

if __name__ == "__main__":
    render()
