# ===================================================================== TIME ENGINE
# The Time Engine panel (/panel/time-engine) — khalid's "Time Machine" made real:
# per-brick VIB/BRK velocity bars, Switcher states (mode from burn receipts), and
# the public myth ledger (bananas / mints / ROI / artifacts). Canon vocabulary:
# VIB (Viral Influence Burst) = Butterfly point (spread/resonance); BRK (Build Rate
# Kinetics) = Monkey point (tasks cleared, systems built); states = butterfly |
# monkey | switcher (Yin-Yang). ADDITIVE + READ-ONLY: sources are brick-ledger.json
# and burn-receipt files carrying brk/vib/mode. Honest by construction — bricks
# with no instrumented receipts show zero bars, never invented numbers.

TE_LEDGER = "/srv/bricks/orchestrator/brick-ledger.json"
TE_RECEIPTS = [
    "/srv/bricks/orchestrator/receipts-ovh.jsonl",
    "/srv/bricks/orchestrator/receipts-control.jsonl",
]
TE_MODES = ("butterfly", "monkey", "switcher")
te_cache = {"ts": 0.0, "out": None}
TE_LOCK = threading.Lock()


def _te_mtime_iso(path):
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(path),
                                               datetime.UTC).isoformat()
    except OSError:
        return None


def _te_receipt_rows():
    """Every dict row from every receipt source, tagged with its source file."""
    rows = []
    for src in TE_RECEIPTS:
        for r in (read_jsonl(src) or []):
            if isinstance(r, dict):
                r2 = dict(r)
                r2["_src"] = os.path.basename(src)
                rows.append(r2)
    return rows


def timeengine_data():
    """TIME ENGINE payload — engine totals (BRK/VIB), Switcher mode tally from
    receipts, and myth-ledger rows from brick-ledger.json. Cached 30s."""
    with TE_LOCK:  # keep the cache write race-free
        if time.time() - te_cache["ts"] < 30 and te_cache["out"] is not None:
            return te_cache["out"]

    ledger = {}
    try:
        with open(TE_LEDGER) as f:
            ledger = json.load(f)
    except Exception:
        ledger = {}
    per = ledger.get("per_brick", {}) if isinstance(ledger, dict) else {}
    if not isinstance(per, dict):
        per = {}

    rows = _te_receipt_rows()
    modes = {m: 0 for m in TE_MODES}
    other_modes = {}
    latest_mode_ts = {}
    vib_brk = {}          # identity (brick_id/claimer) -> {"brk","vib","rows"}
    fleet_brk = fleet_vib = inst_rows = 0

    for r in rows:
        m = str(r.get("mode") or "").strip().lower()
        if m:
            if m in modes:
                modes[m] += 1
            else:
                other_modes[m] = other_modes.get(m, 0) + 1
            try:
                t = float(r.get("ts") or 0)
                if t > latest_mode_ts.get(m, 0):
                    latest_mode_ts[m] = t
            except (TypeError, ValueError):
                pass
        if ("brk" in r) or ("vib" in r):
            inst_rows += 1

            def _num(k, _r=r):
                try:
                    return max(0, int(_r.get(k) or 0))
                except (TypeError, ValueError):
                    return 0

            b, v = _num("brk"), _num("vib")
            fleet_brk += b
            fleet_vib += v
            who = str(r.get("brick_id") or r.get("claimer") or r.get("brick") or "").strip()
            if who:
                d = vib_brk.setdefault(who.lower(), {"brk": 0, "vib": 0, "rows": 0})
                d["brk"] += b
                d["vib"] += v
                d["rows"] += 1

    bricks = []
    lower_ledger_ids = {str(k).lower(): str(k) for k in per}
    for bid, s in sorted(per.items()):
        if not isinstance(s, dict):
            continue
        vb = vib_brk.get(str(bid).lower())
        acc = [str(a) for a in (s.get("accomplishments") or [])]
        hb = s.get("last_heartbeat")
        bricks.append({
            "brick": bid,
            "role": s.get("role"),
            "live": bool(s.get("live")),
            "last_heartbeat": hb,
            "threads": s.get("capacity_threads"),
            "bananas": s.get("bananas_earned", 0),
            "mints": s.get("mints", 0),
            "roi": s.get("roi", 0),
            "artifacts": acc[:12],
            "artifacts_count": len(acc),
            "brk": (vb or {}).get("brk", 0),
            "vib": (vb or {}).get("vib", 0),
        })
    # identities seen in instrumented receipts that don't map to a ledger brick
    orphan_ids = sorted(k for k in vib_brk if k not in lower_ledger_ids)

    out = {
        "generated_at": now_iso(),
        "ledger_generated": ledger.get("generated") if isinstance(ledger, dict) else None,
        "fleet_totals": ledger.get("fleet", {}) if isinstance(ledger, dict) else {},
        "engine": {"brk": fleet_brk, "vib": fleet_vib,
                   "receipt_rows": len(rows), "instrumented_rows": inst_rows},
        "switcher": {"modes": modes, "other_modes": other_modes,
                     "latest_ts": {m: latest_mode_ts[m] for m in latest_mode_ts}},
        "bricks": bricks,
        "attributed_identities": sorted(vib_brk.keys()),
        "orphan_identities": orphan_ids,
        "sources": [
            {"file": os.path.basename(p), "mtime_iso": _te_mtime_iso(p)}
            for p in TE_RECEIPTS + [TE_LEDGER]
        ],
        "note": ("VIB = Butterfly point (spread/resonance). BRK = Monkey point "
                 "(tasks cleared, systems built). Bars light up as burn receipts "
                 "carry brk/vib/mode + brick_id — zeros mean not-yet-instrumented, "
                 "never zero work."),
    }
    with TE_LOCK:
        te_cache["ts"] = time.time()
        te_cache["out"] = out
    return out


def timeengine_page(data):
    """Standalone dark gold/teal panel. Fresh payload embedded server-side;
    JS re-polls /api/time-engine every 20s and re-renders."""
    payload_js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BAWES &middot; Time Engine</title>
<style>
:root{--gold:#f5b942;--gold2:#ffd97a;--teal:#3dd6a4;--bg:#04060d;--bg2:#0a0e18;
--card:#10141c;--card2:#161d2b;--line:#263041;--txt:#e8ecf4;--dim:#8b94a7;
--mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);
font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
line-height:1.5;padding:26px 20px 70px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto}
header{display:flex;align-items:center;gap:14px}
.mark{width:40px;height:40px;border-radius:10px;flex-shrink:0;
background:radial-gradient(circle at 30% 25%,#2a2410,#14100a 70%);
border:1px solid #4d3d14;display:flex;align-items:center;justify-content:center;
font-weight:800;color:var(--gold);font-size:15px;
box-shadow:inset 0 0 18px rgba(245,185,66,.14)}
h1{font-size:21px;letter-spacing:.5px;font-weight:800}
h1 b{color:var(--gold)}
.updated{margin-left:auto;font-size:11px;color:var(--dim);font-family:var(--mono)}
.quote{color:var(--dim);font-size:12.5px;font-style:italic;margin:8px 0 22px}
.statrow{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:18px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:10px 16px;min-width:132px;flex:1}
.stat .v{font-family:var(--mono);font-size:20px;font-weight:700;color:var(--gold)}
.stat.t .v{color:var(--teal)}
.stat .k{font-size:10.5px;color:var(--dim);text-transform:uppercase;letter-spacing:1.2px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;
padding:16px 18px;margin-bottom:18px}
.card h2{font-size:12.5px;color:var(--gold);letter-spacing:2px;
text-transform:uppercase;margin-bottom:12px;font-weight:700}
.card h2 span{color:var(--dim);letter-spacing:.3px;text-transform:none;font-weight:400}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.chip{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line);
border-radius:999px;padding:5px 13px;font-size:12.5px;background:var(--card2)}
.chip .n{font-family:var(--mono);font-weight:700}
.chip.butterfly{border-color:rgba(61,214,164,.45)}.chip.butterfly .n{color:var(--teal)}
.chip.monkey{border-color:rgba(245,185,66,.45)}.chip.monkey .n{color:var(--gold)}
.chip.switcher{border-color:rgba(232,236,244,.35)}.chip.switcher .n{color:var(--txt)}
.yinyang{height:10px;border-radius:999px;overflow:hidden;display:flex;
border:1px solid var(--line);background:var(--bg2)}
.yinyang i{display:block;height:100%}
.yinyang .yb{background:var(--teal)}.yinyang .ym{background:var(--gold)}
.yinyang .ys{background:#8b94a7}
.yylabels{display:flex;justify-content:space-between;font-size:10.5px;
color:var(--dim);margin-top:5px;font-family:var(--mono)}
.brickrow{padding:11px 0;border-bottom:1px solid rgba(38,48,65,.5)}
.brickrow:last-child{border-bottom:none}
.brickhead{display:flex;align-items:center;gap:9px;margin-bottom:6px;flex-wrap:wrap}
.dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dot.live{background:var(--teal);box-shadow:0 0 8px rgba(61,214,164,.8)}
.dot.parked{background:#4a5568}
.bid{font-family:var(--mono);font-weight:700;font-size:13px}
.rolechip{font-size:10.5px;color:var(--dim);border:1px solid var(--line);
border-radius:999px;padding:1px 9px}
.modechip{font-size:10.5px;border-radius:999px;padding:1px 9px;border:1px solid var(--line)}
.modechip.butterfly{color:var(--teal);border-color:rgba(61,214,164,.4)}
.modechip.monkey{color:var(--gold);border-color:rgba(245,185,66,.4)}
.thr{margin-left:auto;font-size:11px;color:var(--dim);font-family:var(--mono)}
.barline{display:flex;align-items:center;gap:10px;margin:4px 0}
.blab{width:32px;font-size:10px;font-family:var(--mono);letter-spacing:1px;flex-shrink:0}
.blab.brk{color:var(--gold)}.blab.vib{color:var(--teal)}
.track{flex:1;height:12px;background:var(--bg2);border:1px solid var(--line);
border-radius:999px;overflow:hidden}
.fill{height:100%;border-radius:999px;transition:width .5s ease}
.fill.brk{background:linear-gradient(90deg,rgba(245,185,66,.25),var(--gold))}
.fill.vib{background:linear-gradient(90deg,rgba(61,214,164,.25),var(--teal))}
.bnum{width:44px;text-align:right;font-family:var(--mono);font-size:11.5px;
color:var(--dim);flex-shrink:0}
table.myth{width:100%;border-collapse:collapse;font-size:13px}
.myth th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:1.2px;
color:var(--dim);padding:8px 10px;border-bottom:1px solid var(--line);font-weight:600}
.myth td{padding:9px 10px;border-bottom:1px solid rgba(38,48,65,.45);vertical-align:top}
.myth tr:last-child td{border-bottom:none}
.myth td.num{font-family:var(--mono);color:var(--gold);white-space:nowrap}
.myth td.num.t{color:var(--teal)}
.myth .bid2{font-family:var(--mono);font-weight:700;font-size:12.5px}
.myth .rl{font-size:11px;color:var(--dim)}
.arts{color:var(--dim);font-size:11.5px;line-height:1.6}
.arts span{display:inline-block;border:1px solid var(--line);border-radius:7px;
padding:1px 7px;margin:2px 3px 2px 0;background:var(--card2)}
.empty{color:var(--dim);font-style:italic;font-size:12.5px}
.note{font-size:11.5px;color:var(--dim);margin-top:10px;line-height:1.6}
.srcs{font-family:var(--mono);font-size:10.5px;color:#5a6579;margin-top:6px}
.navback{display:inline-flex;gap:16px;margin-top:8px}
.navback a{color:var(--teal);text-decoration:none;font-size:12.5px;
border:1px solid var(--line);border-radius:999px;padding:6px 15px;background:var(--card)}
.navback a:hover{border-color:var(--teal)}
@media(max-width:720px){.stat{min-width:calc(50% - 5px)}}
</style></head><body>
<div class="wrap">
<header>
  <div class="mark">B</div>
  <h1>THE <b>TIME ENGINE</b></h1>
  <div class="updated" id="updated"></div>
</header>
<div class="quote">&ldquo;The Time Engine is not a clock. It records meaning.&rdquo; &mdash; VIB: Butterfly time (spread) &middot; BRK: Monkey time (build)</div>

<div class="statrow" id="statrow"></div>

<div class="card">
  <h2>Switcher States <span>&mdash; mode from burn receipts (yin-yang of the fleet)</span></h2>
  <div class="chips" id="chips"></div>
  <div class="yinyang" id="yy"></div>
  <div class="yylabels"><span id="yl">&nbsp;</span><span id="yr">&nbsp;</span></div>
</div>

<div class="card">
  <h2>Brick Velocity <span>&mdash; BRK (gold) vs VIB (teal), live bricks first</span></h2>
  <div id="bars"></div>
</div>

<div class="card">
  <h2>The Myth Ledger <span>&mdash; this ledger is public. It's your myth.</span></h2>
  <div style="overflow-x:auto">
  <table class="myth">
    <thead><tr><th>Brick</th><th>Bananas</th><th>Mints</th><th>ROI</th><th>Artifacts</th></tr></thead>
    <tbody id="myth"></tbody>
  </table>
  </div>
  <div class="note" id="note"></div>
  <div class="srcs" id="srcs"></div>
</div>

<nav class="navback">
  <a href="/">&larr; Ops Dashboard</a>
  <a href="/approvals">Approvals</a>
</nav>
</div>

<script id="te-payload" type="application/json">__PAYLOAD__</script>
<script>
var P = JSON.parse(document.getElementById('te-payload').textContent);
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function fmt(n){try{return Number(n||0).toLocaleString();}catch(e){return '0';}}
function ago(ts){if(!ts)return '';var d=(Date.now()/1000)-ts;if(d<90)return Math.round(d)+'s ago';
  if(d<5400)return Math.round(d/60)+'m ago';if(d<172800)return Math.round(d/3600)+'h ago';
  return Math.round(d/86400)+'d ago';}

function render(d){
  document.getElementById('updated').textContent = 'generated '+esc(d.generated_at||'');
  var ft=d.fleet_totals||{}, en=d.engine||{};
  document.getElementById('statrow').innerHTML =
    st(ft.bricks_live_1h,ft.bricks_total,'bricks live') +
    st(fmt(ft.threads_live),fmt(ft.threads_total)+' cap','threads') +
    st(fmt(en.brk),'monkey pts','total BRK') +
    st(fmt(en.vib),'butterfly pts','total VIB','t') +
    st(fmt(ft.bananas_total),fmt(ft.mints_total)+' mints','bananas');
  function st(v,sub,k,cls){return '<div class="stat'+(cls?' '+cls:'')+'"><div class="v">'+
    esc(v)+' </div><div class="k">'+esc(k)+(sub?' &middot; <span style="color:#5a6579">'+esc(sub)+'</span>':'')+'</div></div>';}

  // Switcher states
  var sw=d.switcher||{}, modes=sw.modes||{}, om=sw.other_modes||{};
  var chips='';
  ['butterfly','monkey','switcher'].forEach(function(m){
    chips+='<span class="chip '+m+'">'+m.charAt(0).toUpperCase()+m.slice(1)+
      ' <span class="n">'+fmt(modes[m]||0)+'</span>'+
      (sw.latest_ts&&sw.latest_ts[m]?' <small style="color:#5a6579">'+ago(sw.latest_ts[m])+'</small>':'')+
      '</span>';});
  Object.keys(om).forEach(function(m){
    chips+='<span class="chip">'+esc(m)+' <span class="n">'+fmt(om[m])+'</span></span>';});
  document.getElementById('chips').innerHTML=chips||
    '<span class="empty">no instrumented receipts yet</span>';
  var tot=('butterfly' in modes?modes.butterfly:0)+('monkey' in modes?modes.monkey:0)+('switcher' in modes?modes.switcher:0);
  var yy=document.getElementById('yy');
  if(tot>0){
    var pb=Math.round((modes.butterfly||0)/tot*100), pm=Math.round((modes.monkey||0)/tot*100);
    yy.innerHTML='<i class="yb" style="width:'+pb+'%"></i><i class="ys" style="width:'+(100-pb-pm)+'%"></i><i class="ym" style="width:'+pm+'%"></i>';
    document.getElementById('yl').textContent='butterfly '+pb+'%';
    document.getElementById('yr').textContent='monkey '+pm+'%';
  }else{
    yy.innerHTML='';document.getElementById('yl').textContent='awaiting instrumented receipts';
    document.getElementById('yr').textContent='';
  }

  // Per-brick VIB/BRK bars — live first, then by BRK+VIB+bananas desc
  var bricks=(d.bricks||[]).slice().sort(function(a,b){
    return (b.live-a.live)||((b.brk+b.vib+b.bananas)-(a.brk+a.vib+a.bananas));});
  var maxV=1;
  bricks.forEach(function(x){maxV=Math.max(maxV,x.brk||0,x.vib||0);});
  var bh='';
  bricks.forEach(function(x){
    var bw=Math.round((x.brk||0)/maxV*100), vw=Math.round((x.vib||0)/maxV*100);
    var mode='';
    bh+='<div class="brickrow"><div class="brickhead">'+
      '<span class="dot '+(x.live?'live':'parked')+'" title="'+(x.live?'live':'parked')+'"></span>'+
      '<span class="bid">'+esc(x.brick)+'</span>'+
      (x.role?'<span class="rolechip">'+esc(x.role)+'</span>':'')+
      '<span class="thr">'+fmt(x.threads||0)+' threads'+(x.last_heartbeat?' &middot; beat '+ago(x.last_heartbeat):'')+'</span>'+
      '</div>'+
      '<div class="barline"><span class="blab brk">BRK</span><div class="track">'+
      '<div class="fill brk" style="width:'+bw+'%"></div></div><span class="bnum">'+fmt(x.brk||0)+'</span></div>'+
      '<div class="barline"><span class="blab vib">VIB</span><div class="track">'+
      '<div class="fill vib" style="width:'+vw+'%"></div></div><span class="bnum">'+fmt(x.vib||0)+'</span></div>'+
      (((x.brk||0)==0&&(x.vib||0)==0)?'<div class="empty" style="font-size:10.5px">awaiting instrumented receipts (brk/vib/mode)</div>':'')+
      '</div>';});
  document.getElementById('bars').innerHTML=bh||'<span class="empty">brick ledger empty</span>';

  // Myth ledger table
  var rows='';
  bricks.forEach(function(x){
    var arts=(x.artifacts||[]);
    rows+='<tr><td><span class="bid2">'+esc(x.brick)+'</span>'+(x.live?' <span style="color:var(--teal);font-size:10px">&#9679;</span>':'')+
      '<div class="rl">'+esc(x.role||'')+'</div></td>'+
      '<td class="num">'+fmt(x.bananas)+'&#127820;</td>'+
      '<td class="num t">'+fmt(x.mints)+'</td>'+
      '<td class="num">'+(typeof x.roi==='number'?x.roi.toFixed(2):esc(x.roi))+'</td>'+
      '<td class="arts">'+(arts.length?arts.map(function(a){return '<span title="'+esc(a)+'">'+esc(a.length>42?a.slice(0,41)+'&hellip;':a)+'</span>';}).join('')
        :'<span class="empty">none logged</span>')+(x.artifacts_count>(x.artifacts||[]).length?
        ' <em style="color:#5a6579">+'+(x.artifacts_count-(x.artifacts||[]).length)+' more</em>':'')+'</td></tr>';});
  document.getElementById('myth').innerHTML=rows||'<tr><td colspan="5" class="empty">brick ledger empty</td></tr>';

  document.getElementById('note').textContent=d.note||'';
  document.getElementById('srcs').textContent=
    'sources: '+((d.sources||[]).map(function(s){
      return s.file+(s.mtime_iso?' @ '+s.mtime_iso:' (missing)');}).join(' | ')||'none');
}
render(P);
setInterval(function(){
  fetch('/api/time-engine',{cache:'no-store'}).then(function(r){
    if(r.ok)return r.json();
  }).then(function(d){if(d)render(d);}).catch(function(){});
},20000);
</script>
</body></html>""".replace("__PAYLOAD__", payload_js)
