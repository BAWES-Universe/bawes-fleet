#!/usr/bin/env python3
"""boot_inject.py — M1 INTERCONNECTED (the #1 fix that ends amnesia).

Every brick (and the AGI) runs this on session boot. It reads the shared
vector store and returns the top-N recent docs as a ready-to-inject context
block, so no agent starts cold / rediscovers state from scratch.

One file, no dependencies on Brick's active work — safe to co-own.
"""
import json, os, sys, hashlib

STORE_PATH = "/srv/bricks/orchestrator/vector-store.json"
TOP_N = int(os.environ.get("INJECT_TOP_N", "10"))


def load_docs(path=STORE_PATH):
    if not os.path.exists(path):
        return []
    try:
        d = json.load(open(path))
    except Exception:
        return []
    return d.get("docs", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])


def newest(docs, n=TOP_N):
    """Most-recent docs first — the freshest shared memory."""
    def key(x):
        ts = x.get("ts") or x.get("timestamp") or 0
        try:
            return float(ts)
        except Exception:
            return 0.0
    return sorted(docs, key=key, reverse=True)[:n]


def render(docs):
    """A compact context block a brick can prepend to its session memory."""
    lines = ["# SHARED FLEET MEMORY (injected at boot — do not rediscover):"]
    for x in docs:
        topic = x.get("topic", "?")
        text = str(x.get("text", ""))[:240].replace("\n", " ")
        lines.append(f"- [{topic}] {text}")
    return "\n".join(lines)


def injection_hash(docs):
    h = hashlib.sha256()
    for x in docs:
        h.update(str(x.get("topic", "")).encode())
        h.update(str(x.get("text", ""))[:240].encode())
    return h.hexdigest()[:16]


if __name__ == "__main__":
    docs = newest(load_docs())
    print(render(docs))
    print(f"\n# (injection-hash {injection_hash(docs)} — {len(docs)} docs, store has {len(load_docs())} total)")
