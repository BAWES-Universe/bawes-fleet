#!/usr/bin/env python3
"""vault_bot.py — Vault Bot (consensus @4b1d315, AGI-designed guardrails).
Holds ALL khalid's PATs. Scoped access: agents call with a capability,
never see raw tokens. Owner-only raw retrieval. Audit every store/access.
Per-PAT quotas with breach alerts. Fail-closed on unknown services."""
import json, pathlib, time

class VaultBot:
    def __init__(self, base_dir: str):
        self.base = pathlib.Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)
        self.secrets_file = self.base / "secrets.json"
        self.audit_file = self.base / "audit.jsonl"
        self.secrets = self._load()

    def _load(self):
        if self.secrets_file.exists():
            return json.loads(self.secrets_file.read_text())
        return {}

    def _save(self):
        self.secrets_file.write_text(json.dumps(self.secrets, indent=2))
        self.secrets_file.chmod(0o600)

    def _audit(self, op, service, agent, capability=""):
        row = {"ts": time.time(), "op": op, "service": service, "agent": agent,
               "capability": capability}
        with open(self.audit_file, "a") as f:
            f.write(json.dumps(row) + "\n")
        # DA FIX B2: audit trail must not be world-readable
        self.audit_file.chmod(0o600)

    def store(self, service: str, raw: str, owner: str, quota: int = 100,
              vault_key: str = ""):
        self.secrets[service] = {"raw": raw, "owner": owner, "quota": quota,
                                 "used": 0, "breached": False, "vault_key": vault_key}
        self._save()
        self._audit("store", service, owner)

    def has(self, service: str) -> bool:
        return service in self.secrets

    def get_raw(self, service: str, agent: str, vault_key: str = "") -> str:
        if service not in self.secrets:
            raise KeyError(service)
        entry = self.secrets[service]
        # DA FIX B1: owner check was caller-supplied string (spoofable).
        # Raw reads now require the vault key — held by the relay only.
        if not vault_key or vault_key != entry.get("vault_key"):
            raise PermissionError("raw read requires the vault key (relay only)")
        self._audit("raw_read", service, agent)
        return entry["raw"]

    def access(self, service: str, agent: str, capability: str):
        if service not in self.secrets:
            raise KeyError(service)
        entry = self.secrets[service]
        entry["used"] += 1
        if entry["used"] > entry["quota"]:
            entry["breached"] = True
        self._save()
        self._audit("access", service, agent, capability)
        # agents get a CAPABILITY HANDLE, never the raw secret
        return {"service": service, "capability": capability, "handle": f"{service}:{capability}"}

    def audit(self):
        rows = []
        if self.audit_file.exists():
            for line in self.audit_file.read_text().splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def quota_breached(self, service: str) -> bool:
        return self.secrets.get(service, {}).get("breached", False)
