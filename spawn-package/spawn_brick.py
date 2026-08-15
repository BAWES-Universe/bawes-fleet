#!/usr/bin/env python3
"""spawn_brick.py — THE MOTHER BRICK: gives away verified instances of itself.
Round-85. A verified mother brick clones itself into children:
  child identity (lineage: parent_brick_id) + own wallet namespace + own
  registry row + own model-chain. Children inherit the mother's package,
  NOT her credentials or person_id. Unverified mothers cannot spawn.
"""
import hashlib, json, pathlib, time


def can_spawn(mother: dict):
    """A mother must be VERIFIED to spawn (round-63 owner-gate: unverified
    nodes never carry real work, and spawning IS real work)."""
    if not mother.get("verified"):
        return False, "mother not verified — pass probe first"
    return True, "ok"


def derive_child_identity(mother: dict, child_id: str, skills: list) -> dict:
    """Child identity: own brick_id, own person_id (never the mother's),
    lineage chained via parent_brick_id, inherited owner/kill_switch."""
    # child person_id = hash of (parent + child) — unique, non-transferable
    seed = f"{mother['brick_id']}:{child_id}:{mother['person_id']}".encode()
    child_person = hashlib.sha256(seed).hexdigest()[:12]
    return {
        "brick_id": child_id,
        "person_id": child_person,
        "parent_brick_id": mother["brick_id"],
        "owner": mother.get("owner", "bawes"),
        "kill_switch": mother.get("kill_switch", mother.get("owner", "bawes")),
        "skills": list(skills),
        "lineage": [mother["brick_id"]] + list(mother.get("lineage", [])),
        "public_key": mother.get("public_key", ""),
        "verified": False,  # child must prove itself before real work
    }


def wallet_namespace(child_id: str) -> str:
    """Wallet namespace = the child's OWN brick_id. Never shared with mother."""
    return child_id


def registry_row(mother: dict, child_id: str, skills: list) -> dict:
    """Registry row with lineage — the fleet can trace who spawned whom."""
    return {
        "brick_id": child_id,
        "parent_brick_id": mother["brick_id"],
        "skills": list(skills),
        "quality": "registered",
        "ts": int(time.time()),
    }


def spawn(mother: dict, child_id: str, skills: list, base_dir: pathlib.Path):
    """Full spawn: identity + registry + wallet namespace + model chain.
    Returns the child's package path. Raises if mother unverified."""
    ok, reason = can_spawn(mother)
    if not ok:
        raise ValueError(reason)
    d = base_dir / child_id
    d.mkdir(parents=True, exist_ok=True)
    ident = derive_child_identity(mother, child_id, skills)
    (d / "identity.json").write_text(json.dumps(ident, indent=2) + "\n")
    (d / "model-chain.json").write_text(json.dumps({
        "brick": child_id,
        "brain": "router://127.0.0.1:3742/lane/deepseek-api",
        "model": "deepseek-v4-flash",
        "routing": "router-001",
        "credential_policy": "vaulted — key never leaves router",
        "status": "REGISTERED",
    }, indent=2) + "\n")
    # wallet namespace file (child's own)
    (d / "wallet.jsonl").write_text(json.dumps({
        "kind": "wallet-open", "brick_id": child_id, "bananas": 0, "ts": time.time(),
    }) + "\n")
    return d
