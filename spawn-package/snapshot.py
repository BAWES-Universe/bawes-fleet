#!/usr/bin/env python3
"""snapshot.py — BRICK RESURRECTION (T-UNIVERSE-020, khalid requirement).

Spot instances die with zero notice. A brick's memory (hindsight bank) and
money (wallet/ledger) must never live only on the spot box:

  [alive brick] --signed+encrypted snapshot--> [control plane store]
  [brick dies]  -> control plane holds the snapshot (cannot read it)
  [brick respawns] -> pulls snapshot -> VERIFIES signature -> DECRYPTS
                      -> restores bank+wallet with original mode-600
                      -> brick resumes with SAME memory and SAME bananas

Hostile-DA hardened (all 8 findings closed):
  F1 path traversal: rel validated — absolute or ".." components rejected,
     resolved path must stay inside the bank.
  F2 key support: ed25519 (fleet spawn/install standard) AND secp256r1 (ES256
     contract) both accepted; HKDF derivation uses the private scalar.
  F3 empty-wipe: 0-file snapshot refused (degraded); 0-file restore onto a
     non-empty bank refused without --force.
  F4 atomic swap: bank -> bank.old, tmp -> bank, rmtree bank.old (crash-safe).
  F5 CLI audit: --audit arg wired; audit file mode-600.
  F6 crash paths: payload parse + wipe loop wrapped -> clean ValueError + row.
  F7 symlinks: file symlinks skipped at snapshot (no arbitrary local content
     bundled); dir symlinks never followed by rglob.
  F8 modes: audit 600, restored bank dir 700.
"""
from __future__ import annotations
import argparse, base64, json, os, pathlib, shutil, tempfile, time
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SNAP_VERSION = 1
SNAP_MAGIC = b"BAWES-SNAP"
ALGO_ED25519 = "ed25519"
ALGO_SECP256R1 = "secp256r1"

def _safe_rel(rel: str) -> str:
    """F1: reject absolute paths and '..' traversal components."""
    if not rel or rel.startswith(("/", "\\")) or "\\" in rel:
        raise ValueError(f"unsafe snapshot path: {rel!r}")
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise ValueError(f"unsafe snapshot path: {rel!r}")
    return rel

class BrickSnapshot:
    def __init__(self, bank_dir: pathlib.Path, identity_key_path: pathlib.Path,
                 audit_path: pathlib.Path | None = None):
        self.bank_dir = bank_dir
        self.identity_key_path = identity_key_path
        self.audit_path = audit_path
        self._load_key()

    def _load_key(self):
        raw = open(self.identity_key_path, "rb").read()
        key = None
        # F2-R: real fleet keys are ssh-keygen OpenSSH format — try that FIRST
        try:
            key = serialization.load_ssh_private_key(raw, password=None)
        except (ValueError, TypeError):
            key = serialization.load_pem_private_key(raw, password=None)
        if isinstance(key, ed25519.Ed25519PrivateKey):
            self._algo = ALGO_ED25519
            self._priv = key
            scalar = key.private_bytes(
                serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                serialization.NoEncryption())
        elif isinstance(key, ec.EllipticCurvePrivateKey) and key.curve.name == "secp256r1":
            self._algo = ALGO_SECP256R1
            self._priv = key
            scalar = key.private_numbers().private_value.to_bytes(32, "big")
        else:
            raise ValueError("identity key must be ed25519 or secp256r1")
        dk = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"bawes-snap-v1",
                  info=b"brick-snapshot-key").derive(scalar)
        self._aes = AESGCM(dk)

    def _sign(self, data: bytes) -> bytes:
        if self._algo == ALGO_ED25519:
            return self._priv.sign(data)
        return self._priv.sign(data, ec.ECDSA(hashes.SHA256()))

    def _verify(self, sig: bytes, data: bytes) -> bool:
        try:
            if self._algo == ALGO_ED25519:
                self._priv.public_key().verify(sig, data)
            else:
                self._priv.public_key().verify(sig, data, ec.ECDSA(hashes.SHA256()))
            return True
        except Exception:
            return False

    def _log(self, op: str, detail: dict, outcome: str = "ok"):
        if not self.audit_path:
            return
        try:
            with open(self.audit_path, "a") as f:
                f.write(json.dumps({"ts": int(time.time()), "op": op,
                                    "outcome": outcome, **detail}) + "\n")
            os.chmod(self.audit_path, 0o600)   # F8
        except OSError:
            pass

    def snapshot(self) -> bytes:
        """Bundle bank dir files (symlinks SKIPPED, F7), AES-GCM encrypt, sign.
        Refuses 0-file snapshots (F3) — an empty bank is a degraded state."""
        files = {}
        if self.bank_dir.exists():
            for p in sorted(self.bank_dir.rglob("*")):
                if p.is_file() and not p.is_symlink():   # F7
                    rel = _safe_rel(str(p.relative_to(self.bank_dir)))
                    files[rel] = base64.b64encode(p.read_bytes()).decode()
        if not files:
            self._log("snapshot", {"files": 0, "reason": "empty bank"}, outcome="degraded")
            raise ValueError("refusing empty-bank snapshot (degraded state — nothing to preserve)")
        payload = json.dumps({"v": SNAP_VERSION, "ts": int(time.time()),
                              "algo": self._algo, "files": files}).encode()
        nonce = os.urandom(12)
        ct = self._aes.encrypt(nonce, payload, b"bawes-snap")
        to_sign = SNAP_MAGIC + b"|" + nonce + b"|" + ct
        sig = self._sign(to_sign)
        blob = json.dumps({"magic": SNAP_MAGIC.decode(), "v": SNAP_VERSION,
                           "nonce": nonce.hex(), "ct": ct.hex(),
                           "sig": sig.hex()}).encode()
        self._log("snapshot", {"files": len(files), "bytes": len(blob)})
        return blob

    def restore(self, blob: bytes, dry_run: bool = False, force: bool = False) -> dict:
        """Verify, decrypt, restore atomically. F1 traversal rejected, F3
        empty-restore guard, F4 atomic swap, F6 clean errors."""
        try:
            obj = json.loads(blob)
            if obj.get("magic") != SNAP_MAGIC.decode() or obj.get("v") != SNAP_VERSION:
                raise ValueError("bad snapshot magic/version")
            nonce = bytes.fromhex(obj["nonce"]); ct = bytes.fromhex(obj["ct"])
            sig = bytes.fromhex(obj["sig"])
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self._log("restore", {"reason": f"malformed: {e}"}, outcome="rejected")
            raise ValueError(f"snapshot malformed: {e}")
        to_verify = SNAP_MAGIC + b"|" + nonce + b"|" + ct
        if not self._verify(sig, to_verify):
            self._log("restore", {"reason": "signature invalid"}, outcome="rejected")
            raise ValueError("snapshot signature invalid")
        try:
            payload = self._aes.decrypt(nonce, ct, b"bawes-snap")
        except Exception as e:
            self._log("restore", {"reason": f"auth-tag: {e}"}, outcome="rejected")
            raise ValueError(f"snapshot decryption failed (tampered): {e}")
        try:
            data = json.loads(payload)
            if not isinstance(data, dict) or data.get("v") != SNAP_VERSION:
                raise ValueError("bad payload")
            files = data.get("files", {})
            if not isinstance(files, dict):
                raise ValueError("bad files map")
        except Exception as e:
            self._log("restore", {"reason": f"payload: {e}"}, outcome="rejected")
            raise ValueError(f"snapshot payload invalid: {e}")

        # F1: validate EVERY path before touching disk
        try:
            safe = {_safe_rel(rel): content for rel, content in files.items()}
        except ValueError as e:
            self._log("restore", {"reason": str(e)}, outcome="rejected")
            raise
        # F3: 0-file restore onto a NON-EMPTY bank = amnesia wipe — refuse.
        # F4-R: also count bank.old (a crash at rename-2 preserves the original
        # there — the guard must not let an empty restore destroy it).
        def _file_count(p):
            return len([x for x in (p.rglob("*") if p.exists() else []) if x.is_file()])
        if not safe:
            existing = _file_count(self.bank_dir) + _file_count(
                self.bank_dir.with_name(self.bank_dir.name + ".old"))
            if existing and not force:
                self._log("restore", {"reason": "empty snapshot onto non-empty bank"},
                          outcome="rejected")
                raise ValueError("refusing empty-snapshot restore onto non-empty bank (use --force)")
        if dry_run:
            self._log("restore", {"files": len(safe), "mode": "dry-run"})
            return {"restored": len(safe), "dry_run": True}

        self.bank_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.bank_dir, 0o700)   # F8
        tmp = pathlib.Path(tempfile.mkdtemp(prefix=".snap-restore-",
                                            dir=str(self.bank_dir.parent)))
        try:
            for rel, content in safe.items():
                p = tmp / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(base64.b64decode(content))
                os.chmod(p, 0o600)
            # F4: atomic swap — old state intact until the rename lands
            old = self.bank_dir.with_name(self.bank_dir.name + ".old")
            if self.bank_dir.exists():
                if old.exists():
                    shutil.rmtree(old, ignore_errors=True)
                os.rename(str(self.bank_dir), str(old))
            try:
                os.rename(str(tmp), str(self.bank_dir))
            except Exception:
                # F4-R: rename-2 failed — roll the ORIGINAL back, never leave
                # the bank missing or the original stranded
                if old.exists() and not self.bank_dir.exists():
                    os.rename(str(old), str(self.bank_dir))
                shutil.rmtree(tmp, ignore_errors=True)
                raise
            shutil.rmtree(old, ignore_errors=True)
        except Exception as e:
            try:
                shutil.rmtree(tmp, ignore_errors=True)   # F4-R2: never leak decrypted residue
            except Exception:
                pass
            self._log("restore", {"reason": f"wipe: {e}"}, outcome="error")
            raise ValueError(f"restore failed (original data preserved): {e}")
        self._log("restore", {"files": len(safe)})
        return {"restored": len(safe)}

def main():
    ap = argparse.ArgumentParser(description="brick snapshot/resurrection (T-UNIVERSE-020)")
    ap.add_argument("--bank-dir", required=True)
    ap.add_argument("--identity-key", required=True)
    ap.add_argument("--out", help="snapshot blob output path")
    ap.add_argument("--in", dest="inp", help="snapshot blob input path")
    ap.add_argument("--audit", help="audit log path (default: <bank-dir>/snapshot-audit.jsonl)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="allow empty restore onto non-empty bank")
    args = ap.parse_args()
    audit = pathlib.Path(args.audit) if args.audit else \
        pathlib.Path(args.bank_dir) / "snapshot-audit.jsonl"   # F5: audit wired
    snap = BrickSnapshot(pathlib.Path(args.bank_dir),
                         pathlib.Path(args.identity_key), audit)
    if args.inp:
        res = snap.restore(pathlib.Path(args.inp).read_bytes(),
                           dry_run=args.dry_run, force=args.force)
        print(json.dumps({"restore": res}))
    else:
        blob = snap.snapshot()
        pathlib.Path(args.out).write_bytes(blob)
        os.chmod(args.out, 0o600)
        print(json.dumps({"snapshot": pathlib.Path(args.out).name,
                          "bytes": len(blob)}))

if __name__ == "__main__":
    main()
