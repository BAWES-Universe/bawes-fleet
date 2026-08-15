# VAST BID CORRECTION — round-88 (2026-08-15 22:55Z)
**Caught by the AGI (khalid relayed): "we should verify the cheap ones not the on demand."**

## The mistake (mine, confirmed)
- Fleet doctrine (vast-gpu-fleet skill): **search `type=bid`**, price = live bid ×1.05, verify `is_bid: True` after create
- What I did: created an **on-demand A100 @ $1.01/hr** — the skill says a wrong/missing price "silently creates an ON-DEMAND instance at ~6× the bid rate"
- A100 was reclaimed before I could destroy it (on-demand churn); 4 phantom on-demand 3090s swept ($0.0322/hr each, never booted)

## The correction
- Swept ALL active instances → **verify_zero: 0 active**
- Bid market is LIVE and CHEAP: RTX 5070 $0.0101/hr, Tesla P4 $0.0119, 3060 Ti $0.0129, V100 $0.0222
- Control-create attempts on bid (CLI --ssh ×2 + raw REST ×1, same proven payload): ALL `success: False` + minted phantom contracts → **destroyed instantly each time, verify_zero after** — provider-side mint-without-boot, same signature the skill documented (2026-08-15 second incident)
- **Zero dollars burned by phantoms** (destroyed within seconds of mint)

## Rule going forward (binding)
1. **Search `type=bid` only** — on-demand is the 6× mistake
2. **Verify `is_bid: True`** on every created instance before doing work
3. `success: False` + new_contract = phantom → destroy immediately, verify_zero
4. The watchdog's control-create already uses the plain payload; add bid-type to its search
