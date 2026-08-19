#!/usr/bin/env python3
"""receipt_checker.py — non-LLM choke-point on the member-relay path.

Per DA ruling (khalid-signed 2026-08-19): a 'shipped/installed/done/live' claim
may NOT reach a member or khalid unless it carries a TRIPLE receipt that is
mechanically verifiable — no LLM narration, only grep + ss + exec + parse.

Triple receipt:
  1. commit  — the build commit resolves (git cat-file) in the fleet repo.
  2. port    — the service is actually LISTENING (ss -ltnp), or the installer
               ran on a canary (exit 0 + handshake line in its log).
  3. log     — the pid / .jsonl event / heartbeat row is read back non-empty.
"""
import subprocess, json, os, sys

REPO = "/tmp/bawes-fleet"

def _git_sha_resolves(sha):
    r = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                       cwd=REPO, capture_output=True)
    return r.returncode == 0

def _port_listening(port):
    if not port:
        return False
    r = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True)
    return f":{port}" in r.stdout

def _installer_exercised(cmd, log_path, expect_line):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return False
    if log_path and os.path.exists(log_path):
        data = open(log_path).read()
        return expect_line in data if expect_line else bool(data.strip())
    return True

def _log_readable(log_path):
    return bool(log_path) and os.path.exists(log_path) and os.path.getsize(log_path) > 0

def check_claim(claim):
    """claim: {commit_sha, port, log_path, installer_cmd?, expect_line?, member}
    Returns {allowed: bool, receipts: {commit,port,log}, missing: [..]}."""
    receipts = {}
    # 1. commit
    receipts["commit"] = _git_sha_resolves(claim.get("commit_sha", ""))
    # 2. port/exec
    if claim.get("port"):
        receipts["port"] = _port_listening(claim["port"])
    elif claim.get("installer_cmd"):
        receipts["port"] = _installer_exercised(
            claim["installer_cmd"], claim.get("log_path"), claim.get("expect_line"))
    else:
        receipts["port"] = False
    # 3. log
    receipts["log"] = _log_readable(claim.get("log_path"))
    missing = [k for k, v in receipts.items() if not v]
    return {"allowed": not missing, "receipts": receipts, "missing": missing}

def probe():
    """Deterministic: a fabricated claim (no real commit/port/log) must BLOCK;
    a real commit in the fleet repo must pass the commit receipt."""
    # fabricated claim -> block on all three
    fake = check_claim({"commit_sha": "0000000000000000000000000000000000000000",
                        "port": 18443, "log_path": "/nonexistent/log.jsonl"})
    assert not fake["allowed"] and set(fake["missing"]) == {"commit", "port", "log"}, "fake claim must block"
    # real commit -> commit receipt passes
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    real = check_claim({"commit_sha": head, "port": None, "log_path": None})
    assert real["receipts"]["commit"] is True, "real commit must resolve"
    return "PASS"

if __name__ == "__main__":
    print(probe())
