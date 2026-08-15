#!/usr/bin/env python3
"""onboard_v2.py — T-024 THE DOOR (round-70 V-14, round-74, khalid's Mishari critique).
"Seconds not steps": machinery server-side, human touches ONE thing — their words.

Flow:
1. human says "I want a brick" (or just talks)
2. bot asks: what do you want to do? (goal-first)
3. bot shows the 16 rules (plain words)
4. human SPEAKS consent in their own words (V-5: never automated)
5. that utterance is recorded (timestamp + Discord ID) = the consent marker
6. manifest signed (issuer key, signing box), allowlist row, brick wakes

Consent = utterance, not click-through. Revocation = one utterance too
(V-14 condition: as easy as consent -> brick powers to read-only).

Consent transcript + plain-words rules receipt join the M-7 evidence package
(V-14 condition 2) — the board audits artifacts, not recollections.
"""
import argparse, base64, json, os, pathlib, re, sys, time, hashlib, hmac

RULES = [
    "Your brick is yours. It works for you, not for us.",
    "Your data stays yours. Nothing leaves your brick unless YOU say so.",
    "Knowledge sharing is OFF by default. Sharing is always a choice.",
    "Your brick has a fixed identity and voice — it behaves as its character.",
    "Your brick earns honestly — bananas come from verified work only.",
    "Verification is external — a non-earner checks before anything mints.",
    "No self-earning. Your brick can't mint its own work.",
    "A death warrant caps every paid run — spend stops at the declared limit.",
    "You can kill your brick anytime. Kill switch: yours.",
    "The ledger is truth. Receipts are append-only.",
    "Consent is per-action, revocable. You can stop anytime.",
    "Your personal lane is never indexed — the fleet brain can't search it.",
    "The rebels can challenge anything — review is open and visible.",
    "Nothing binds until you sign. Your words, your pen, never automated.",
    "Offline capability — your brick works without the fleet where possible.",
    "The mission: every student succeeds. That's why the fleet exists.",
]

GOAL_QUESTIONS = {
    "learn": "What do you want to learn?",
    "earn": "What work do you want to earn bananas with?",
    "build": "What do you want to build?",
    "personal": "What do you want your brick to help you with?",
}

class ConsentTranscript:
    """M-7 evidence: what the person read + what they said, timestamped."""
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry):
        with open(self.path, "a") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
        os.chmod(self.path, 0o600)

def slug(name, discord_id):
    s = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")
    return f"{s}-{discord_id}" if s else f"human-{discord_id}"

def main():
    ap = argparse.ArgumentParser(description="T-024 the door — onboard a human in seconds")
    ap.add_argument("--name", required=True, help="human's name (their words)")
    ap.add_argument("--discord-id", required=True)
    ap.add_argument("--goal", choices=list(GOAL_QUESTIONS), default="personal")
    ap.add_argument("--consent-utterance", required=True,
                    help="THE HUMAN'S OWN WORDS — never generated, never defaulted")
    ap.add_argument("--issuer-key", default=os.environ.get("BAWES_ISSUER_KEY", ""),
                    help="signing box only; NEVER shipped to devices")
    ap.add_argument("--out-dir", default="/srv/bricks/register")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # F4: hostile input refused before anything writes
    if not re.fullmatch(r"[A-Za-z0-9 _.'-]+", args.name):
        return print("REJECTED: name has invalid characters")
    if not args.discord_id.isdigit():
        return print("REJECTED: discord_id must be numeric")
    if not args.consent_utterance.strip():
        return print("REJECTED: consent utterance empty — their words are required")
    # consent is THE HUMAN'S words: at minimum their own name in it (their pen)
    if args.name.lower() not in args.consent_utterance.lower():
        return print("REJECTED: consent utterance must contain the person's own name")

    brick_id = f"{slug(args.name, args.discord_id)}-device-001"
    ts = int(time.time())
    out = pathlib.Path(args.out_dir)
    transcript = ConsentTranscript(out / "consent-transcripts.jsonl")

    manifest = {
        "manifest_version": 1, "brick_id": brick_id,
        "person_id": args.discord_id, "name": args.name,
        "goal": args.goal,
        "consent": {"status": "signed", "signed_by": args.name,
                    "utterance": args.consent_utterance, "ts": ts},
        "privacy": {"knowledge_sharing": "off", "personal_lane": "local-only"},
        "wallet_ref": f"banana-bank/wallet-{brick_id}.jsonl",
        "resource_links": [{"name": "queue", "url": "a2a://bawes/queue"}],
        "ts": ts,
    }

    # consent transcript -> M-7 evidence (what they read + what they said)
    transcript.append({"event": "rules-shown", "brick_id": brick_id,
                       "rules": RULES, "ts": ts})
    transcript.append({"event": "consent-spoken", "brick_id": brick_id,
                       "utterance": args.consent_utterance, "signed_by": args.name,
                       "ts": ts})

    # manifest signed on the SIGNING BOX only (V-5: brick never self-forges)
    if args.issuer_key:
        import subprocess
        kid = "khalid-issuer"
        header = {"alg": "ES256", "kid": kid}
        b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
        payload = b64(json.dumps(header, sort_keys=True).encode()) + "." + \
                  b64(json.dumps(manifest, sort_keys=True).encode())
        sig = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", args.issuer_key],
            input=payload.encode(), capture_output=True).stdout
        manifest["signature"] = b64(sig) + "." + payload
        print(f"SIGNED by {kid} (ES256)")
    else:
        print("WARN: no issuer key — manifest UNSIGNED (signing box only)")

    if not args.dry_run:
        (out / f"manifest-{brick_id}.json").write_text(
            json.dumps(manifest, indent=1, sort_keys=True))
        os.chmod(out / f"manifest-{brick_id}.json", 0o600)
        with open(out / "allowlist.jsonl", "a") as f:
            f.write(json.dumps({"brick_id": brick_id,
                                "discord_id": args.discord_id,
                                "name": args.name, "consent": "signed",
                                "utterance_sha": hashlib.sha256(
                                    args.consent_utterance.encode()).hexdigest()[:16],
                                "ts": ts}, sort_keys=True) + "\n")
        print(f"MANIFEST {brick_id} written (consent=signed, their words)")
        print(f"TRANSCRIPT -> M-7 evidence box (2 entries, 0600)")
    print(f"\nDONE. Brick {brick_id} is awake.")

if __name__ == "__main__":
    main()
