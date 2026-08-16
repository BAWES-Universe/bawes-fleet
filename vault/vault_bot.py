#!/usr/bin/env python3
"""vault_bot.py — Vault (consensus @4b1d315, AGI guardrails, DA-hardened).
Holds ALL khalid's PATs. Scoped access: agents call with a capability,
never see raw tokens. Owner+key raw reads. Audit every store/access.
Per-PAT quotas with breach alerts. Fail-closed on unknown services.
DA hardening (deleg_38939fca): F3 state HMAC-integrity, F4 store auth,
F5 key from env (never co-located), F6 atomic 0600 creates."""
import hashlib, hmac, json, os, pathlib, time

class VaultBot:
    def __init__(self, base_dir: str, integrity_key: str = ""):
        self.base = pathlib.Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)
        self.secrets_file = self.base / "secrets.json"
        self.audit_file = self.base / "audit.jsonl"
        self.integrity_key = integrity_key or os.environ.get("VAULTBOT_INTEGRITY_KEY", "")
        self.key_from_env = os.environ.get("VAULTBOT_KEY", "")
        self.secrets = self._load()

    def _hmac(self, payload: str) -> str:
        return hmac.new(self.integrity_key.encode(), payload.encode(), hashlib.sha256).hexdigest()

    def _load(self):
        if not self.secrets_file.exists():
            return {}
        raw = self.secrets_file.read_text()
        data = json.loads(raw)
        # F3: integrity check — tampered state fails closed
        if self.integrity_key:
            if data.get("_hmac") != self._hmac(json.dumps(data.get("entries", {}), sort_keys=True)):
                raise RuntimeError("vault state integrity check failed (tampered)")
        return data.get("entries", {})

    def _save(self):
        body = json.dumps(self.secrets, sort_keys=True)
        doc = {"entries": self.secrets}
        if self.integrity_key:
            doc["_hmac"] = self._hmac(body)
        # F6: atomic 0600 create — no 0644 window, no TOCTOU
        fd = os.open(self.secrets_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(doc, indent=2))

    def _audit(self, op, service, agent, capability=""):
        row = {"ts": time.time(), "op": op, "service": service, "agent": agent,
               "capability": capability}
        fd = os.open(self.audit_file, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(json.dumps(row) + "\n")

    def store(self, service: str, raw: str, owner: str, quota: int = 100,
              vault_key: str = "", admin_key: str = ""):
        # F4 (round 3): store-overwrite must FAIL-CLOSED when admin env unset —
        # empty admin_key matching empty env was a fail-open hole.
        expected_admin = os.environ.get("VAULTBOT_ADMIN_KEY", "")
        if service in self.secrets and (not expected_admin or admin_key != expected_admin):
            raise PermissionError("modifying an existing service requires the admin key")
        # F5: the key is NOT stored beside the raw — resolved at read time from env
        self.secrets[service] = {"raw": raw, "owner": owner, "quota": quota,
                                 "used": 0, "breached": False}
        self._save()
        self._audit("store", service, owner)

    def has(self, service: str) -> bool:
        return service in self.secrets

    def get_raw(self, service: str, agent: str, vault_key: str = "") -> str:
        if service not in self.secrets:
            raise KeyError(service)
        entry = self.secrets[service]
        # F5 (round 3): NO constant fallback — if the env key is absent the
        # process is misconfigured and raw reads are DENIED, never degraded.
        if not self.key_from_env or vault_key != self.key_from_env:
            raise PermissionError("raw read requires the vault key (relay only)")
        self._audit("raw_read", service, agent)
        return entry["raw"]

    def access(self, service: str, agent: str, capability: str, vault_key: str = ""):
        # F8 (round 3): access() requires the vault key — no unauthenticated
        # quota-burn or forged breach flags.
        if service not in self.secrets:
            raise KeyError(service)
        if not self.key_from_env or vault_key != self.key_from_env:
            raise PermissionError("access requires the vault key (relay only)")
        entry = self.secrets[service]
        entry["used"] += 1
        if entry["used"] > entry["quota"]:
            entry["breached"] = True
        self._save()
        self._audit("access", service, agent, capability)
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
