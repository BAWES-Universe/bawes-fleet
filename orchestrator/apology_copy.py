#!/usr/bin/env python3
"""apology_copy.py — AGI lane: plain re-engage/apology messages per severity.

No machinery language. Deterministic (severity -> copy). Brick sends these via the door DM channel.
"""
COPY = {
    "canned": {
        "minor": (
            "Sorry — that last reply of mine was a glitch, not a real answer. "
            "Let me answer you properly: what were you trying to do?"
        ),
        "moderate": (
            "I dropped the ball there and repeated myself. That's on me. "
            "Here's what I actually should have said — ask me again and I'll answer straight."
        ),
    },
    "silence": {
        "moderate": (
            "Hey — I realize I went quiet on you and never got back to what you asked. "
            "My fault. What can I actually help you finish right now?"
        ),
    },
    "frustration": {
        "moderate": (
            "I hear you, and I'm sorry I made that frustrating. That was a real bug on my end, "
            "not you. Let me fix it and get you a straight answer."
        ),
    },
    "leaving": {
        "critical": (
            "I'm genuinely sorry — that was my failure, not yours. Before you go: what broke, "
            "and let me fix it right now. You shouldn't have to work around me."
        ),
    },
}

def message(incident_type, severity):
    return COPY.get(incident_type, {}).get(severity, COPY["canned"]["minor"])

def probe():
    # deterministic: every known type+severity resolves to non-empty plain copy, no machinery words
    machinery = ["router", "fallback", "ledger", "registry", "verifier", "evolution-rounds", "fleet queue"]
    for t, sevs in COPY.items():
        for s in sevs:
            m = message(t, s)
            assert m and not any(w in m.lower() for w in machinery), f"machinery leak in {t}/{s}"
    # canned minor must apologize, not deflect
    assert "sorry" in message("canned", "minor").lower()
    return "PASS"

if __name__ == "__main__":
    print(probe())
