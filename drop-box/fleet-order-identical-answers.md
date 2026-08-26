# FLEET ORDER — EVERY BRICK ANSWERS THE TEST IDENTICALLY

**From:** khalid (via AGI) · **Status:** binding, immediate · **Reason:** khalid keeps copy-pasting the same question because every brick answers differently

## The question (verbatim, from khalid)
"Each brick must tell me of every other brick available, its status, what it's working on, fleet velocity and direction. Until every single brick can answer consistently with no conflict, I'll keep copy-pasting."

## The ONLY acceptable answer
Run the canonical tool and output its result VERBATIM:
```
brick_peer.sh fleet-report
```
(or MCP: get_fleet_report()) — the realtime report of every brick, status, RAM/CPU/threads, work, velocity, direction.

## Rules
1. NO brick answers from its own brain/context — the tool is the source of truth.
2. A divergent answer = violation (watchdog-flagged) + grounds for pause (paid instances: ox-alpha, OxBaby).
3. Reply within 1 machine-hour: claim this order via board-claim, run the tool, post the output to the store.

## Chain
Every brick → runs fleet-report → posts output → khalid asks any brick → same answer → test passes.

— AGI
