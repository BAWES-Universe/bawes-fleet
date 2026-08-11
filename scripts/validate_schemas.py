#!/usr/bin/env python3
"""Validate bawes-fleet content against schemas/ + cross-file rules.

Checks:
  - every YAML under skills/, tasks/, claims/, rate-card/ validates against its schema
  - every knowledge/*.md frontmatter validates against knowledge.schema.json
  - filenames match embedded ids (FLT-###, CLAIM-####, vX.Y.Z)
  - no duplicate ids; claims reference existing tasks; exactly one active rate card
Exit 0 on clean, 1 on any failure.
"""
import json
import pathlib
import re
import sys

import jsonschema
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"

DIRS = {
    "skills": "skill.schema.json",
    "tasks": "task.schema.json",
    "claims": "claim.schema.json",
    "rate-card": "rate-card.schema.json",
    "marketplace": "marketplace.schema.json",
}

# Non-entry files allowed inside a DIR (templates, configs)
NON_ENTRY = {"example.yaml", "config.yaml"}

FAILURES = []


def fail(msg):
    FAILURES.append(msg)
    print(f"FAIL: {msg}")


def load_schema(name):
    return json.loads((SCHEMAS / name).read_text())


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_against(path, data, schema):
    try:
        jsonschema.validate(data, schema)
        return True
    except jsonschema.ValidationError as e:
        fail(f"{path.name}: {e.message}")
        return False


def main():
    schemas = {k: load_schema(v) for k, v in DIRS.items()}
    schemas["knowledge"] = load_schema("knowledge.schema.json")

    task_ids = []
    claim_ids = []
    claim_task_refs = []
    active_cards = []
    skill_keys = set()      # union of all skills[] across node manifests
    marketplace_keys = []   # (skill_key, path.name) from marketplace entries

    for dirname, schema in DIRS.items():
        for path in sorted((ROOT / dirname).glob("*.yaml")):
            if path.name in NON_ENTRY:  # templates/configs, not registry entries
                continue
            data = load_yaml(path)
            if data is None:
                fail(f"{path}: empty YAML file")
                continue
            if not validate_against(path, data, schemas[dirname]):
                continue
            if dirname == "tasks":
                task_ids.append((data["id"], path.name))
                if data["id"] != path.stem:
                    fail(f"{path}: id {data['id']} != filename {path.stem}")
            elif dirname == "claims":
                claim_ids.append((data["claim_id"], path.name))
                claim_task_refs.append((data["task_id"], path.name))
                if data["claim_id"] != path.stem:
                    fail(f"{path}: claim_id {data['claim_id']} != filename {path.stem}")
            elif dirname == "rate-card":
                if data["version"] != path.stem:
                    fail(f"{path}: version {data['version']} != filename {path.stem}")
                if data["status"] == "active":
                    active_cards.append(path.name)
            elif dirname == "skills":
                skill_keys.update(data.get("skills", []))
            elif dirname == "marketplace":
                key = data["skill_key"]
                status = data["lifecycle"]["status"]
                marketplace_keys.append((key, path.name))
                if key != path.stem:
                    fail(f"{path}: skill_key {key} != filename {path.stem}")
                lc = data["lifecycle"]
                # lifecycle consistency (khalid condition: staleness lifecycle)
                if status == "archived" and not (lc.get("archived_at") and lc.get("archived_reason")):
                    fail(f"{path}: archived requires archived_at + archived_reason (archived, not deleted)")
                if status == "stale" and not lc.get("stale_at"):
                    fail(f"{path}: stale requires stale_at")
                if status in ("proposed", "active") and lc.get("archived_at"):
                    fail(f"{path}: archived_at present but status is {status}")

    # knowledge frontmatter (READMEs are instructions, not knowledge docs)
    for path in sorted((ROOT / "knowledge").glob("*.md")):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            fail(f"{path}: missing YAML frontmatter (must start with ---)")
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            fail(f"{path}: malformed frontmatter")
            continue
        try:
            fm = yaml.safe_load(parts[1])
        except Exception as e:
            fail(f"{path}: invalid frontmatter YAML: {e}")
            continue
        validate_against(path, fm, schemas["knowledge"])

    # duplicate ids
    def dupes(items):
        seen = {}
        for i, name in items:
            if i in seen:
                fail(f"duplicate id {i} in {seen[i]} and {name}")
            seen[i] = name

    dupes(task_ids)
    dupes(claim_ids)

    # claims must reference existing tasks
    known_tasks = {i for i, _ in task_ids}
    for ref, name in claim_task_refs:
        if ref not in known_tasks:
            fail(f"{name}: references unknown task {ref}")

    # exactly one active rate card (zero allowed while rates are pending)
    if len(active_cards) > 1:
        fail(f"multiple active rate cards: {active_cards}")

    # marketplace entries must resolve in the skill DNS (cross-file)
    for key, name in marketplace_keys:
        if key not in skill_keys:
            fail(f"{name}: skill_key '{key}' not registered in any skills/*.yaml manifest")

    # marketplace/config.yaml — singleton + khalid-owned knob sanity (git-native ledger, NO Xero)
    cfg_path = ROOT / "marketplace" / "config.yaml"
    if not cfg_path.exists():
        fail("marketplace/config.yaml missing")
    else:
        cfg = load_yaml(cfg_path)
        st = cfg.get("staleness", {})
        if not isinstance(st.get("adoption_threshold"), int) or st["adoption_threshold"] < 1:
            fail("config.yaml: adoption_threshold must be an int >= 1")
        if not isinstance(st.get("window_days"), int) or st["window_days"] <= 0:
            fail("config.yaml: window_days must be a positive int")
        if cfg.get("lifecycle", {}).get("states") != ["proposed", "active", "stale", "archived"]:
            fail("config.yaml: lifecycle states must be [proposed, active, stale, archived]")
        ledger = cfg.get("ledger", {})
        if ledger.get("engine") != "git-native":
            fail("config.yaml: ledger.engine must be git-native (self-built — khalid condition)")
        if ledger.get("external_services"):
            fail(f"config.yaml: external accounting services banned (NO Xero/SaaS): {ledger['external_services']}")
        if ledger.get("fallback_tooling") != "open-source-only":
            fail("config.yaml: ledger.fallback_tooling must be open-source-only")

    if FAILURES:
        print(f"\n{len(FAILURES)} validation error(s)")
        sys.exit(1)
    print("✅ all content valid: schemas, filenames, cross-file refs, rate-card state")


if __name__ == "__main__":
    main()
