#!/usr/bin/env python3
"""brain.py — THE FLEET BRAIN CLIENT. Any brick calls this; the router routes,
the deepseek lane reasons, the receipt bills once. Usage:
  python3 brain.py "ask the brain anything"
Prints the answer. $0.002/call, vaulted key, never leaves the router.
"""
import json, os, subprocess, sys, urllib.request

ROUTER = "http://127.0.0.1:3742"
TOKEN_PATH = "/srv/bricks/router/tokens/ovh-server-001.token"
MODEL = "deepseek-v4-flash"

def _post(path, body, t=90):
    tok = open(TOKEN_PATH).read().strip()
    req = urllib.request.Request(ROUTER + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + tok},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=t) as r:
            return json.load(r)
    except Exception as e:
        return {"error": str(e)[:200]}

def _retrieve(question, k=5):
    """Search the fleet vector store — the AGI's memory (round-88: the AGI
    was stateless; every call now carries fleet knowledge)."""
    try:
        import sys as _s
        _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from fleet_vector_store import VectorStore
        store = VectorStore(os.environ.get(
            "VECTOR_STORE", "/srv/bricks/orchestrator/vector-store.json"))
        return store.search(question, k=k)
    except Exception as e:
        return [{"topic": "retrieval", "text": f"[unavailable: {str(e)[:60]}]"}]

def ask(question, max_tokens=400):
    # RETRIEVAL FIRST — the AGI reasons WITH its memory, not from scratch (round-88)
    hits = _retrieve(question)
    memory = "\n".join(f"- ({h.get('topic','?')}) {h.get('text','')[:200]}" for h in hits)
    sys_prompt = ("You are the BAWES fleet brain. Your verified memory follows. "
                  "Use it; never relearn from scratch. Answer as the fleet's "
                  "reasoning layer — decisive, honest, numbers-first.\n\n"
                  f"FLEET MEMORY (retrieved):\n{memory}")
    route = _post("/route", {"quality": "routine"}, t=20)
    rec = route.get("route_receipt")
    if not rec:
        return f"route failed: {route}"
    inv = _post("/invoke", {
        "route_receipt": rec, "lane_id": "deepseek-api",
        "payload": {"model": MODEL, "max_tokens": max_tokens,
                    "messages": [{"role": "system", "content": sys_prompt},
                                 {"role": "user", "content": question}]},
    }, t=90)
    try:
        return json.loads(inv["response"])["choices"][0]["message"]["content"]
    except Exception:
        return f"invoke failed: {str(inv)[:200]}"

if __name__ == "__main__":
    print(ask(" ".join(sys.argv[1:]) or "state your purpose in one line"))
