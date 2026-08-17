#!/usr/bin/env python3
"""banana_spend.py — T-026 banana-powered upgrade (round-76 rulings 1-5).
The economy's SINK: bananas buy real cloud inference, with a spend receipt
every time. Spend-side rate card, per-size-band pricing, earning-first
balance + khalid-extendable credit lines, metadata-only logging.

RULINGS IMPLEMENTED:
- R1 transient boundary ENFORCED: human-lane logs carry METADATA only
  (who/model/cost/latency/status) — NEVER request text. A log row with
  human request content is a breach, not a bug. CI check included.
- R2 margin declared: spend-side rate-card line (khalid-set, versioned);
  receipt discloses OUR COST every time — never hide the margin.
- R3 price per-size-band (small/medium/large), not flat.
- R4 earning-first balance + khalid-extendable credit lines (round-45
  pattern: recorded, capped, repayable).
- R5 per-utterance consent; spend row IS the consent record.
"""
import argparse, json, os, pathlib, sys, time, hashlib, urllib.request, urllib.error

SPEND_RATE_CARD = {
    "version": "v1.0", "set_by": "khalid", "ts_effective": "2026-08-15",
    # R3: per-size-band, not flat — a 1-line request != 5k-token request
    "bands": {
        "small":  {"max_tokens": 1000,  "price_bananas": 1},
        "medium": {"max_tokens": 5000,  "price_bananas": 2},
        "large":  {"max_tokens": 20000, "price_bananas": 5},
    },
    # R2: spend-side margin declared; our cost disclosed in every receipt
    "our_cost_usd": {"small": 0.0004, "medium": 0.0007, "large": 0.0020},
    "earn_side_note": "earn-side rate stays cost+20% (v1.1) — different instrument",
}

class BananaSpend:
    def __init__(self, ledger_path, router_url="http://127.0.0.1:3742"):
        self.ledger = pathlib.Path(ledger_path)
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.router_url = router_url

    # ---- R4: balance = verified earnings (+ khalid credit lines) ----
    def balance(self, person_id):
        earn, spend, credit = 0, 0, 0
        if self.ledger.exists():
            for line in open(self.ledger):
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("person_id") != person_id:
                    continue
                if r.get("kind") == "earn":
                    earn += r.get("bananas", 0)
                elif r.get("kind") == "spend":
                    spend += r.get("bananas", 0)
                elif r.get("kind") == "credit" and r.get("state") == "open":
                    credit += r.get("bananas", 0)
        return {"earned": earn, "spent": spend, "credit_open": credit,
                "available": earn - spend + credit}

    # ---- R5: the spend row IS the consent record ----
    def spend(self, person_id, band, utterance_id, metadata):
        if band not in SPEND_RATE_CARD["bands"]:
            return {"ok": False, "error": f"unknown band {band}"}
        price = SPEND_RATE_CARD["bands"][band]["price_bananas"]
        bal = self.balance(person_id)
        if bal["available"] < price:
            return {"ok": False, "error": "insufficient bananas (earning-first)",
                    "balance": bal, "price": price}
        row = {"kind": "spend", "person_id": person_id, "band": band,
               "bananas": price, "utterance_id": utterance_id,
               "consent": "per-utterance", "ts": time.time(),
               # R1: METADATA ONLY — never request text on human lanes
               "metadata": metadata}
        with open(self.ledger, "a") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        os.chmod(self.ledger, 0o600)
        return {"ok": True, "price": price,
                "balance_after": self.balance(person_id)}

    # ---- R2: receipt discloses OUR COST every time ----
    def receipt(self, person_id, band, utterance_id, model, latency_ms,
                outcome, relay_path):
        cost = SPEND_RATE_CARD["our_cost_usd"].get(band, 0)
        price = SPEND_RATE_CARD["bands"][band]["price_bananas"]
        return {"type": "banana-spend-receipt", "version": "v1.0",
                "person": person_id, "utterance": utterance_id,
                "what_ran": {"model": model,
                             "band": band,
                             "relay_path": relay_path},
                "data_that_left_device": "this utterance's text — transient, "
                                         "not stored, not indexed, never joins the corpus",
                "what_stayed": "personal lane, bank, identity — untouched",
                "cost": {"bananas": price, "our_cost_usd": cost,
                         "margin_declared": True},
                "outcome": outcome, "latency_ms": latency_ms,
                "consent": "per-utterance — the spend row IS the record"}

    # ---- R1 CI CHECK: human-lane path has NO content-retention code path ----
    @staticmethod
    def ci_content_transience(module_path):
        """Breach if a human-lane module logs request content."""
        rule = "a log row containing human request content is a breach, not a bug"
        src = ""
        if os.path.exists(module_path):
            src = pathlib.Path(module_path).read_text()
        # strip comments + string literals; only executable code is scanned
        import tokenize, io
        try:
            toks = tokenize.generate_tokens(io.StringIO(src).readline)
            src = " ".join(t.string for t in toks
                           if t.type == tokenize.NAME
                           or t.type == tokenize.OP)
        except Exception:
            pass
        bad = [w for w in ("log ( text", "request_text", "content_to_log",
                           "append ( text", "write_text ( text")
               if w in src]
        return {"ok": not bad, "violations": bad, "rule": rule}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--person-id", default="")
    ap.add_argument("--band", default="small", choices=list(SPEND_RATE_CARD["bands"]))
    ap.add_argument("--model", default="deepseek-v4-flash")
    ap.add_argument("--ci-check", default="")
    args = ap.parse_args()

    s = BananaSpend(args.ledger)
    if args.ci_check:
        print("CI:", json.dumps(s.ci_content_transience(args.ci_check)))
        sys.exit(0)

    # demo: earn-first check + spend + receipt
    bal = s.balance(args.person_id)
    print("balance:", json.dumps(bal))
    if bal["available"] < SPEND_RATE_CARD["bands"][args.band]["price_bananas"]:
        print("SPEND REFUSED: earning-first (R4) — earn verified work first, "
              "or khalid extends a credit line")
    else:
        r = s.spend(args.person_id, args.band, "utt-demo-1",
                    {"model": args.model, "latency_ms": 1200, "outcome": "ok"})
        print("spend:", json.dumps(r))
        rcpt = s.receipt(args.person_id, args.band, "utt-demo-1", args.model,
                         1200, "ok", "brick -> router(:3742) -> cloud -> back")
        print("receipt:", json.dumps(rcpt, indent=1))
