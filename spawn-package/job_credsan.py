#!/usr/bin/env python3
"""job_credsan.py — REAL JOB: Plugn/Yo3an credential-exposure re-scan (card plgn-credsan-001).
Deterministic output: for each known exposure path, does the PUBLIC repo still expose it?
Read-only GitHub API queries. Output = sorted JSON string -> sha256 = verifiable by non-earner.
"""
import hashlib, json, sys, urllib.request

# exposure paths from the round-12 audit (/tmp/plugn-yo3an-audit.md), public-only.
# Round-88: expanded to the FULL BAWES-Universe org — every repo, high-risk paths.
REPOS = [
    "plugn", "plugn-ionic", "yo3an-yii2", "yo3an-ionic",
    "studenthub", "studenthub-admin", "studenthub-staff", "studenthub-candidate", "studenthub-company",
    "pogi", "pogi-admin", "pogi-jobs", "pogi-employer",
    "tamr", "tamr-admin", "tamr-user", "tamr-staff",
    "whitebook", "whitebook-mobile",
]
TARGETS = [
    ("environments/prod/common/config/main-local.php"),
    ("environments/dev/common/config/main-local.php"),
    (".env"),
    ("config/db.php"),
    ("app/config/params-local.php"),
]
OWNERS = "BAWES-Universe"  # all 19 repos live under this org (round-88 verified)

def check(owner: str, repo: str, path: str) -> dict:
    """Does the path exist in the public default branch? status via API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "bawes-worker", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return {"path": path, "repo": repo, "exposed": r.status == 200, "http": r.status}
    except urllib.error.HTTPError as e:
        return {"path": path, "repo": repo, "exposed": False, "http": e.code}
    except Exception as e:
        return {"path": path, "repo": repo, "exposed": "error", "http": str(e)[:60]}

def run() -> str:
    results = []
    for repo in REPOS:
        for path in TARGETS:
            results.append(check(OWNERS, repo, path))
    out = json.dumps({"job": "plgn-credsan-001", "results": results}, sort_keys=True)
    return out

if __name__ == "__main__":
    out = run()
    print(out)
    print("sha256:", hashlib.sha256(out.encode()).hexdigest(), file=sys.stderr)
