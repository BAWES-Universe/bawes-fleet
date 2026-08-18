#!/usr/bin/env python3
"""convo_health.py — AGI lane: the learning-loop DETECTOR (read-only, first ship).

Detects bad brick-conversation signals so the fleet can proactively re-engage or
apologize. Deterministic (regex + time deltas), no LLM in the loop.

Signals (severity-classified):
  canned/fallback line fired  -> minor/moderate
  repeat dead-end (same canned 2+ in a row) -> moderate
  silence (member msg, no brick reply > SILENCE_MIN) -> moderate
  frustration marker in member msg -> moderate
  member says leaving/done/broken -> critical
"""
import json, re, os, time, sys

# The known canned/fallback templates (from the door plugin + router envelope).
CANNED_PATTERNS = [
    r"I don't have memory of that",
    r"only answer from verified fleet knowledge",
    r"route this to the fleet queue",
    r"Hold on.{0,40}let me be straight",
    r"got ahead of myself",
    r"where were we",
    r"HONEST_FALLBACK",
    r"I can't answer that right now",
    r"Ask differently",
]

FRUSTRATION = [
    r"\b(broken|not working|doesn't work|useless|stupid|wtf|why (won't|can't) you)\b",
    r"\b(you're|you are) (broken|wrong|lying|useless)\b",
    r"\?{2,}",
]

LEAVING = [
    r"\b(i'm|im|i am) (done|out|leaving|giving up)\b",
    r"\bdelete (my|this)\b",
    r"\bgoodbye\b",
]

SILENCE_MIN = 10 * 60  # 10 minutes

def detect_canned(text):
    return [p for p in CANNED_PATTERNS if re.search(p, text, re.IGNORECASE)]

def classify(events):
    """events: list of {ts, from, text}. Returns list of incidents."""
    incidents = []
    member_last = None
    last_brick = None
    for e in sorted(events, key=lambda x: x.get("ts", 0)):
        src = e.get("from", "")
        text = e.get("text", "")
        ts = e.get("ts", 0)
        is_member = src not in ("brick", "door", "system")
        if not is_member:
            canned = detect_canned(text)
            if canned:
                repeat = last_brick and detect_canned(last_brick)
                sev = "moderate" if repeat else "minor"
                incidents.append({"type": "canned", "severity": sev,
                                  "detail": canned[0], "ts": ts})
            last_brick = text
        else:
            if any(re.search(f, text, re.IGNORECASE) for f in LEAVING):
                incidents.append({"type": "leaving", "severity": "critical", "ts": ts})
            elif any(re.search(f, text, re.IGNORECASE) for f in FRUSTRATION):
                incidents.append({"type": "frustration", "severity": "moderate", "ts": ts})
            # silence check: previous member msg with no brick reply
            if member_last is not None and last_brick is None and (ts - member_last) > SILENCE_MIN:
                incidents.append({"type": "silence", "severity": "moderate", "ts": ts})
            member_last = ts
            last_brick = None
    return incidents

def probe():
    """Non-LLM probe: deterministic recomputation. Returns machine verdict."""
    # canned line must be detected
    c = detect_canned("I don't have memory of that — I can only answer from verified fleet knowledge.")
    assert c, "canned line not detected"
    # clean text must NOT be detected
    assert not detect_canned("hey, what can you help me with today?"), "false positive"
    # frustration detected
    assert any(re.search(f, "why won't you work", re.IGNORECASE) for f in FRUSTRATION), "frustration missed"
    # leaving = critical
    ev = [{"ts": 1, "from": "member", "text": "i'm done with this"}]
    inc = classify(ev)
    assert any(i["type"] == "leaving" and i["severity"] == "critical" for i in inc), "leaving not critical"
    return "PASS"

if __name__ == "__main__":
    print(probe())
