#!/usr/bin/env python3
"""test_onboarding_e2e.py — AGI lane: acceptance probes for the consent->wake->chat path.

Defines "done" for the one missing link (member DMs door -> consents -> brick wakes
-> member chats with it) AND the "beats current live product" bar (current = parked
brick + canned 'I don't have memory of that' fallback).

Non-LLM, deterministic. Each probe checks an OBSERVABLE outcome (registry row,
process/heartbeat, reply text), not Brick's internal code — so it stays valid as the
implementation changes. Brick builds the path; these probes are the gate.
"""
import json, os, re, subprocess, sys

CANNED = [
    "I don't have memory of that",
    "only answer from verified fleet knowledge",
    "route this to the fleet queue",
    "HONEST_FALLBACK",
    "got ahead of myself",
    "where were we",
]

# --- helpers (read live fleet state) ---
def _registry_rows():
    p = "/srv/bricks/register/registry.jsonl"
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p) if l.strip()]

def _consent_rows():
    p = "/srv/bricks/register/consent-transcripts.jsonl"
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p) if l.strip()]

def _canned_hits(text):
    return [c for c in CANNED if c.lower() in text.lower()]

# --- probes ---
def probe_door_greeting(greeting: str):
    """A member's first DM must get a natural, non-canned greeting."""
    assert greeting and greeting.strip(), "empty greeting"
    assert not _canned_hits(greeting), f"canned greeting: {_canned_hits(greeting)}"
    return "PASS"

def probe_consent_recorded(uid: str):
    """After the member says yes, a consent row must exist for their uid."""
    rows = _consent_rows()
    hit = [r for r in rows if str(r.get("user_id", r.get("uid", ""))) == str(uid)
           and str(r.get("status", r.get("consent", ""))).lower() in ("yes", "confirmed", "signed", "true")]
    assert hit, f"no consent row for {uid}"
    return "PASS"

def probe_brick_wakes(brick_id: str):
    """The brick's registry row must flip from parked to a live status."""
    rows = [r for r in _registry_rows() if r.get("brick_id") == brick_id]
    assert rows, f"no registry row for {brick_id}"
    live = [r for r in rows if r.get("status") not in ("parked", "stopped", "tombstoned")]
    assert live, f"brick {brick_id} never woke (all parked)"
    return "PASS"

def probe_real_reply(reply: str):
    """The member's next DM must get a real answer, not a canned fallback."""
    assert reply and reply.strip(), "empty reply"
    assert not _canned_hits(reply), f"canned reply: {_canned_hits(reply)}"
    return "PASS"

def probe_no_fallback(log_paths=("/tmp/door-fallback.jsonl", "/tmp/r149-fallback.jsonl")):
    """Zero fallback rows may fire during the whole journey."""
    for p in log_paths:
        if os.path.exists(p):
            assert os.path.getsize(p) == 0, f"fallback fired: {p}"
    return "PASS"

if __name__ == "__main__":
    print("probes loaded:", [n for n in dir() if n.startswith("probe_")])
