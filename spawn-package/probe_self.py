#!/usr/bin/env python3
"""probe_self.py — a brick proves it's healthy before taking real work.
Same known-answer probes as the worker gate (round-33): arithmetic, hash, python.
Exit 0 = verified host. Exit 1 = refuse work.
"""
import argparse, hashlib, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default="probe-001")
    args = ap.parse_args()

    if args.probe == "probe-001":
        ok = (7 * 6 == 42)
    elif args.probe == "probe-002":
        ok = (hashlib.sha256(b"bawes-probe").hexdigest()
              == "7562cc8852fe6a2e4981460fdc284d5fb2b5229270f3c506f673d40481384b25")
    elif args.probe == "probe-003":
        ok = sys.version_info >= (3, 8)
    else:
        print(f"unknown probe {args.probe}")
        return 1

    print(f"probe {args.probe}: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
