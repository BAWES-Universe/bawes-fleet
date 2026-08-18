#!/usr/bin/env python3
"""evolution_engine.py — self-orchestrating evolution loop (AGI lane: the machine).

For each hole in the manifest: ask the model to write the patch → apply → run the
non-LLM probe → retry failures with error feedback → log verified fixes to
evolution-rounds.jsonl. No human in the loop.

Usage: python3 evolution_engine.py [--model-url http://127.0.0.1:8000/v1] [--max-attempts 3]
"""
import json, sys, os, re, subprocess, urllib.request, time, datetime, argparse

REGISTRY = "/srv/bricks/orchestrator/evolution-rounds.jsonl"

def call_model(url, prompt, max_tokens=1500):
    req = json.dumps({"messages": [{"role": "user", "content": prompt}],
                      "stream": False, "max_tokens": max_tokens, "temperature": 0.2}).encode()
    r = urllib.request.urlopen(urllib.request.Request(
        url, data=req, headers={"Content-Type": "application/json"}), timeout=300)
    return json.loads(r.read())["choices"][0]["message"]["content"]

def extract_code(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    return (m.group(1) if m else text).strip()

def run_probe(probe_file, probe_fn, workdir):
    code = f"import sys; sys.path.insert(0, '{workdir}')\nimport importlib\n"
    code += f"m = importlib.import_module('{probe_file}')\n"
    code += f"r = m.{probe_fn}()\nprint('GREEN:', r)\n"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=workdir, timeout=60)
    return r.returncode == 0, (r.stdout + r.stderr).strip()

def log_round(hole_id, patch, probe, result, author):
    row = {"round": f"R-{int(time.time())}", "type": "evolution", "hole": hole_id,
           "patch": patch, "probe": probe, "result": result, "author": author,
           "verified_by": "non-earner AGI", "ts": datetime.datetime.utcnow().isoformat() + "Z"}
    with open(REGISTRY, "a") as f:
        f.write(json.dumps(row) + "\n")
    return row

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-url", default="http://127.0.0.1:8000/v1/chat/completions")
    ap.add_argument("--manifest", default="/srv/bricks/orchestrator/holes.json")
    ap.add_argument("--workdir", default="/srv/sprint")
    ap.add_argument("--max-attempts", type=int, default=3)
    a = ap.parse_args()

    holes = json.load(open(a.manifest))
    os.makedirs(a.workdir, exist_ok=True)
    results = {}
    for hole in holes:
        hid = hole["id"]; fname = hole["file"]; probe = hole["probe"]; fn = hole["probe_fn"]
        prompt = hole["prompt"]
        for attempt in range(1, a.max_attempts + 1):
            code = extract_code(call_model(a.model_url, prompt))
            open(os.path.join(a.workdir, fname), "w").write(code)
            ok, out = run_probe(probe, fn, a.workdir)
            if ok:
                row = log_round(hid, fname, f"{probe}.{fn}", "GREEN", "qwen3.8-27b")
                results[hid] = "GREEN"
                print(f"[GREEN] {hid} (attempt {attempt})", flush=True)
                break
            else:
                print(f"[RED] {hid} attempt {attempt}: {out[-200:]}", flush=True)
                prompt += f"\nYour previous patch FAILED the probe with: {out[-300:]}. Fix it."
        else:
            results[hid] = "RED"
    green = sum(1 for v in results.values() if v == "GREEN")
    print(f"\n=== {green}/{len(holes)} GREEN ===")
    sys.exit(0 if green == len(holes) else 1)

if __name__ == "__main__":
    main()
