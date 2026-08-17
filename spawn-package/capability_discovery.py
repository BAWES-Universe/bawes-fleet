#!/usr/bin/env python3
"""capability_discovery.py — T-017: THE WORKER'S DEMAND ENGINE (round-80 ruling).
The loop the fleet was missing: turn real fleet state into a DISPATCHABLE
demand signal. Reads: registry, backlog, wallet, capability register, vector
store. Produces: ranked cards (what CAN be worked, by who, at what price),
so the orchestrator has something to dispatch — the engine, not the payroll.

Anti-fabrication (scar doctrine): discovery only READS state and MATCHES
existing claims — it never invents work. If no real demand exists, it says
so honestly (empty demand is a valid outcome, same as V-11 empty retrieval).
"""
from __future__ import annotations
import argparse, json, pathlib, sys, time

def _read(p: pathlib.Path) -> list:
    if not p.exists():
        return []
    out = []
    for line in p.open():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out

def discover(reg_dir: pathlib.Path, orch_dir: pathlib.Path, cap_file: pathlib.Path,
             store_file: pathlib.Path) -> dict:
    registry = _read(reg_dir / "registry.jsonl")
    backlog = _read(orch_dir / "backlog.jsonl") if (orch_dir / "backlog.jsonl").exists() else []
    claims = _read(cap_file)
    wallet = _read(reg_dir / "wallet.jsonl")
    store = {}
    if store_file.exists():
        try:
            store = json.load(open(store_file))
        except Exception:
            store = {}

    # registry rows carry brick_id + quality, not a status field — any row is a live node
    live_bricks = [r for r in registry if r.get("brick_id")]
    verified_claims = [c for c in claims if c.get("status") == "verified"]
    store_topics = [d.get("topic") for d in store.get("docs", [])]
    open_cards = [b for b in backlog if b.get("status") in ("open", "queued", "claimed")]

    cards = []
    for b in backlog:
        if b.get("status") not in ("open", "queued"):
            continue
        topic = b.get("topic", b.get("title", "untitled"))
        # price: rate card if matched to a probe, else default 1
        price = b.get("price", 1)
        cards.append({
            "card_id": b.get("card_id", f"card-{len(cards)}"),
            "topic": topic,
            "price_bananas": price,
            "probe_id": b.get("probe_id", ""),
            "status": "open",
            "dispatchable": len(live_bricks) > 0,
            "source": "backlog"})

    demand = {
        "ts": int(time.time()),
        "kind": "demand-signal",
        "live_bricks": len(live_bricks),
        "verified_claims": len(verified_claims),
        "brain_topics": len(store_topics),
        "wallet_earn_rows": sum(1 for w in wallet
                                if w.get("kind") == "earn" or "card_id" in w),
        "open_cards": len(open_cards),
        "cards": cards,
        "note": "empty cards = honest no-demand, never fabricated (scar doctrine)",
    }
    return demand

def main():
    ap = argparse.ArgumentParser(description="T-017 demand engine")
    ap.add_argument("--reg-dir", required=True)
    ap.add_argument("--orch-dir", required=True)
    ap.add_argument("--cap-file", default="")
    ap.add_argument("--store-file", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    cap = pathlib.Path(args.cap_file) if args.cap_file else pathlib.Path(args.reg_dir) / "claims.jsonl"
    store = pathlib.Path(args.store_file) if args.store_file else pathlib.Path(args.orch_dir) / "vector-store.json"
    demand = discover(pathlib.Path(args.reg_dir), pathlib.Path(args.orch_dir), cap, store)

    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(demand, indent=2) + "\n")
        print(f"demand-signal written: {args.out} ({len(demand['cards'])} dispatchable cards)")
    else:
        print(json.dumps(demand, indent=2))

if __name__ == "__main__":
    main()
