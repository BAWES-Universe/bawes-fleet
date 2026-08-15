"""tests_spawn_brick.py — TDD for the mother-brick cloner (round-85).
Contracts: a verified mother brick can spawn children; each child gets its own
identity (lineage: parent_brick_id), registry row, wallet namespace, model-chain;
unverified mothers CANNOT spawn.
"""
import json, os, pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.path.insert(0, os.path.join(str(pathlib.Path(__file__).parent.parent), "spawn-package"))

from spawn_brick import (
    derive_child_identity, registry_row, wallet_namespace, can_spawn,
)

MOTHER = {
    "brick_id": "mother-001",
    "person_id": "000001",
    "owner": "bawes",
    "public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIE/9huaR7ughFdGRAPW5GMNv3VTaBo9Q11HBco1VsF18 mother@bawes",
    "skills": ["probe", "spawn", "tune"],
    "verified": True,
}

def test_child_identity_carries_lineage():
    child = derive_child_identity(MOTHER, "child-001", ["probe"])
    assert child["brick_id"] == "child-001"
    assert child["parent_brick_id"] == "mother-001"
    assert child["person_id"] != MOTHER["person_id"], "child must NOT inherit the mother's person_id"
    assert "skills" in child and "probe" in child["skills"]

def test_child_gets_own_wallet_namespace():
    ns = wallet_namespace("child-001")
    assert ns == "child-001", "wallet namespace = child's own brick_id, never shared"

def test_unverified_mother_cannot_spawn():
    unverified = dict(MOTHER, verified=False)
    ok, reason = can_spawn(unverified)
    assert ok is False, "unverified mother must not spawn"
    assert "verified" in reason.lower()

def test_registry_row_has_lineage():
    row = registry_row(MOTHER, "child-001", ["probe"])
    assert row["brick_id"] == "child-001"
    assert row["parent_brick_id"] == "mother-001"
    assert row["quality"] == "registered"
    assert row["ts"] > 0

if __name__ == "__main__":
    import traceback
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{4 - failures}/4 passed")
    sys.exit(1 if failures else 0)
