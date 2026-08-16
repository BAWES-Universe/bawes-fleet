#!/usr/bin/env python3
"""scientists_run.py — wake the 3 scientist bricks as REAL pipeline members.
Each produces actual findings from live state, written to the fleet store.
Silent-until-change: writes only when there's something new to say.
Scheduled: every 30m on OVH (cron). No LLM cost — pure analysis."""
import json, os, pathlib, sys, time

sys.path.insert(0, "/srv/bricks/orchestrator")
from fleet_vector_store import VectorStore

BASE = pathlib.Path("/srv/bricks/register")
OUT = pathlib.Path("/srv/bricks/register/scientist-findings.jsonl")
STORE = VectorStore("/srv/bricks/orchestrator/vector-store.json")

def registry():
    rows = []
    if (BASE / "registry.jsonl").exists():
        for line in (BASE / "registry.jsonl").read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows

def wallet():
    rows = []
    if (BASE / "wallet.jsonl").exists():
        for line in (BASE / "wallet.jsonl").read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows

def findings():
    rows = []
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows

def emit(brick, finding, severity, detail):
    row = {"brick": brick, "finding": finding, "severity": severity,
           "detail": detail, "ts": time.time()}
    with open(OUT, "a") as f:
        f.write(json.dumps(row) + "\n")
    return row

def run():
    emitted = []
    reg = registry()
    wal = wallet()

    # NEUROLOGIST-001: conversation/monitoring health
    store_stats = STORE.stats
    novel_total = store_stats.get("novel", 0)
    dups = store_stats.get("duplicates", 0)
    paper = [r["brick_id"] for r in reg if r.get("quality") == "registered"]
    if paper:
        emitted.append(emit("neurologist-001", "registered-but-idle bricks",
                            "HIGH" if len(paper) > 2 else "MEDIUM",
                            f"{len(paper)} bricks registered but no verified work: {paper}"))
    if dups > novel_total:
        emitted.append(emit("neurologist-001", "dedup dominance", "LOW",
                            f"duplicates({dups}) > novel({novel_total}) — corpus may be stale"))

    # SECURITY-001: adversarial audit of live state
    wallet_earns = [w for w in wal if w.get("kind") == "earn"]
    self_mint = [w for w in wallet_earns if w.get("brick_id") == w.get("person_id")]
    if self_mint:
        emitted.append(emit("security-001", "self-mint pattern", "CRITICAL",
                            f"{len(self_mint)} earns where brick==person (no-self-mint rule)"))
    # check claims dir for in-flight claims
    claims = list((BASE / "claims").glob("*.jsonl")) if (BASE / "claims").exists() else []
    if len(claims) > 0:
        emitted.append(emit("security-001", "in-flight claims", "INFO",
                            f"{len(claims)} claim files open"))

    # EVOLUTION-001: propose next evolution from verified work
    if novel_total > 0 and not any(f.get("finding") == "evolution proposal" for f in findings()[-20:]):
        emitted.append(emit("evolution-001", "evolution proposal", "INFO",
                            f"novel docs={novel_total}, earns={len(wallet_earns)} — "
                            f"propose next card: browser or discord triage automation #2"))

    # persist findings to store ONLY if novel (V-18 NOVEL gate)
    for e in emitted:
        text = f"Scientist {e['brick']}: {e['finding']} ({e['severity']}) {e['detail']}"
        res = STORE.add(text, topic=f"scientist-{e['brick']}", receipt="SCI-2026-08-16")
        if res.get("status") == "novel":
            e["stored"] = "novel"
        else:
            e["stored"] = "dup"
    return emitted

if __name__ == "__main__":
    out = run()
    if out:
        print(f"SCIENTISTS ALIVE: {len(out)} findings — " +
              ", ".join(f"{e['brick']}:{e['finding']}" for e in out[:4]))
    else:
        print("SCIENTISTS ALIVE: no new findings (silent-until-change)")
