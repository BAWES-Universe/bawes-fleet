# Schemas

JSON Schemas (draft 2020-12) that lock the fleet repo's file formats. CI validates every PR against these (`scripts/validate_schemas.py`).

| Schema | Validates | File convention |
|---|---|---|
| `task.schema.json` | `tasks/*.yaml` | `FLT-###.yaml` |
| `claim.schema.json` | `claims/*.yaml` | `CLAIM-####.yaml` |
| `rate-card.schema.json` | `rate-card/*.yaml` | `vX.Y.Z.yaml` |
| `skill.schema.json` | `skills/*.yaml` | `<node-name>.yaml` |
| `knowledge.schema.json` | frontmatter of `knowledge/*.md` | `<slug>.md` with YAML frontmatter |

## Rules

- **Schemas are versioned like the rate card.** A breaking schema change bumps the schema version and updates this table + the validator in the same PR. One change at a time.
- **Backward compatible**: new optional fields only — old files keep validating.
- IDs are checked cross-file: task ids referenced by claims must exist; no duplicate ids; filenames must match the id in the file.
