#!/usr/bin/env python3
"""agi_self_loop.py — THE AGI LOOPS ITSELF (khalid: "I don't want 30min
evolution, and if it is it's the agi that needs to loop").

The cron is only the heartbeat. The AGI decides:
- what to study next (its own research question, from its own gaps)
- which lane to reason on (glm-5.2 for heavy reasoning, flash for
  routine, frontier only for what only it can do)
- what it learned -> writes back to the store -> next cycle builds on it

One cycle = AGI asks itself the next question -> routes to the right lane
-> reasons -> stores finding -> announces. That is learning, not ticking.
"""
import json, glob, os, pathlib, sys, time, subprocess, hashlib

sys.path.insert(0, "/srv/bricks/orchestrator")
import brain

BASE = pathlib.Path("/srv/bricks/orchestrator")
RAW = pathlib.Path("/srv/door/knowledge/raw")
FEED = BASE / "evolution-feed.md"
CARD_DIR = BASE / "cards"
CARD_DIR.mkdir(exist_ok=True)
MEM = BASE / ".agi-self-loop-state.json"   # the AGI's own memory of its loop

def corpus_snapshot():
    msgs = []
    for f in sorted(RAW.glob("*.jsonl")):
        for l in open(f):
            try:
                d = json.loads(l)
                c = (d.get("content") or "").strip()
                if len(c) > 10:
                    msgs.append(f"[{d.get('guild','?')}/{d.get('channel','?')}] {c[:90]}")
            except Exception:
                pass
    return msgs

def load_state():
    if MEM.exists():
        try:
            return json.loads(MEM.read_text())
        except Exception:
            pass
    return {"cycles": 0, "last_question": None, "last_finding": None}

def save_state(s):
    MEM.write_text(json.dumps(s))
    os.chmod(MEM, 0o600)

def main():
    state = load_state()
    msgs = corpus_snapshot()
    n = len(msgs)

    # 1. AGI ASKS ITSELF the next question — from its own state, not a template.
    ctx = (f"You are the AGI. You have studied {n} member messages and completed "
           f"{state['cycles']} research cycles. Your last finding was: "
           f"{(state.get('last_finding') or 'none')[:200]}. "
           f"Member corpus available, plus a store of past findings. "
           f"Ask yourself ONE sharp next research question that builds on your "
           f"last finding and would change what the fleet builds. One sentence.")
    q = brain.ask(ctx, max_tokens=120)
    if not q or "EMPTY" in q:
        print("agi: no question this cycle (lane busy) — heartbeat only")
        return
    question = q.strip().split("\n")[0][:300]

    # 2. AGI ANSWERS IT — with reasoning on deepseek-pro (khalid: reason where needed).
    os.environ["BRAIN_QUALITY"] = "advanced"  # -> glm-5.2 lane (khalid: use glm 5.2 not deepseek not gpt)
    prompt = (f"Research question (self-posed): {question}\n\n"
              f"Use this member corpus sample:\n" + "\n".join(msgs[:20]) +
              f"\n\nAnswer with: (1) the finding, (2) what the fleet should "
              f"do about it, (3) what to study next. 8 lines.")
    finding = brain.ask(prompt, max_tokens=900)
    if not finding or "EMPTY" in finding:
        print("agi: reasoning lane busy — will retry next heartbeat")
        return

    # 3. STORE + ANNOUNCE (compounding: next cycle reads last_finding).
    ts = time.strftime("%Y-%m-%d %H:%M")
    state["cycles"] += 1
    state["last_question"] = question
    state["last_finding"] = finding[:500]
    save_state(state)

    card = CARD_DIR / f"self-loop-{int(time.time())}.md"
    card.write_text(f"# AGI self-loop cycle {state['cycles']} — {ts}\n\n"
                    f"Q: {question}\n\n{finding}\n\n_corpus: {n} msgs_\n")
    os.chmod(card, 0o600)

    with open(FEED, "a") as f:
        f.write(f"\n## 🧠 AGI SELF-LOOP — cycle {state['cycles']} ({ts})\n\n"
                f"**Self-posed question:** {question}\n\n{finding}\n\n"
                f"_reasoned on glm-5.2 | corpus: {n} msgs_\n")
    os.chmod(FEED, 0o600)
    print(f"cycle {state['cycles']}: {question[:80]}")

if __name__ == "__main__":
    main()
