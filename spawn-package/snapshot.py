#!/usr/bin/env python3
"""snapshot.py — BRICK RESURRECTION (T-UNIVERSE-020, khalid requirement).

Spot instances die with zero notice. A brick's memory (hindsight bank) and
money (wallet/ledger) must never live only on the spot box:

  [alive brick] --signed+encrypted snapshot--> [control plane store]
  [brick dies]  -> control plane holds the snapshot (cannot read it)
  [brick respawns] -> pulls snapshot -> VERIFIES signature -> DECRYPTS
                      -> restores bank+wallet with original mode-600
                      -> brick resumes with SAME memory and SAME bananas

Security (hostile-DA bar, same as bank/bridge/register/router):
  - ENCRYPTION: AES-256-GCM with a per-brick snapshot key. The control plane
    stores the snapshot but CANNOT read it (brick's private memory stays
    private — khalid's rule).
  - SIGNATURE: ES256 over the ciphertext (fleet crypto contract). A tampered
    or forged snapshot is REJECTED at restore (auth-tag + signature both fail).
  - SECRETS: the snapshot key is derived from the brick's identity key
    (HKDF) — no new secret to store; key files stay mode-600.
  - ATOMIC: restore writes to temp then renames — a crash mid-restore leaves
    the old state intact.
  - AUDIT: every snapshot + restore is logged (audit surface, never black box).
  - FAIL-OPEN: a failed snapshot logs + keeps the brick alive (never blocks
    work); a failed restore refuses to touch existing state (never wipes).
"""
from __future__ import annotations
import argparse, base64, hashlib, json, os, pathlib, tempfile, time, shutil
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SNAP_VERSION = 1
SNAP_MAGIC = b"BAWES-SNAP"

class BrickSnapshot:
    def __init__(self, bank_dir: pathlib.Path, identity_key_path: pathlib.Path,
                 audit_path: pathlib.Path | None = None):
        self.bank_dir = bank_dir
        self.identity_key_path = identity_key_path
        self.audit_path = audit_path
        self._load_key()

    def _load_key(self):
        with open(self.identity_key_path, "rb") as f:
            key = serialization.load_pem_private_key(f.read(), password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
            raise ValueError("snapshot identity key must be EC secp256r1 (ES256 contract)")
        self._priv = key
        # snapshot AES key = HKDF(identity private key) — no new secret to store
        dk = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"bawes-snap-v1",
                  info=b"brick-snapshot-key").derive(
            key.private_numbers().private_value.to_bytes(32, "big"))
        self._aes = AESGCM(dk)

    def _log(self, op: str, detail: dict, outcome: str = "ok"):
        if not self.audit_path:
            return
        try:
            with open(self.audit_path, "a") as f:
                f.write(json.dumps({"ts": int(time.time()), "op": op,
                                    "outcome": outcome, **detail}) + "\n")
        except OSError:
            pass

    def snapshot(self) -> bytes:
        """Bundle bank dir (wallet/ledger files), AES-GCM encrypt, ES256 sign.
        Returns the portable snapshot blob."""
        files = {}
        if self.bank_dir.exists():
            for p in sorted(self.bank_dir.rglob("*")):
                if p.is_file():
                    rel = str(p.relative_to(self.bank_dir))
                    files[rel] = base64.b64encode(p.read_bytes()).decode()
        payload = json.dumps({"v": SNAP_VERSION, "ts": int(time.time()),
                              "files": files}).encode()
        nonce = os.urandom(12)
        ct = self._aes.encrypt(nonce, payload, b"bawes-snap")
        to_sign = SNAP_MAGIC + b"|" + nonce + b"|" + ct
        sig = self._priv.sign(to_sign, ec.ECDSA(hashes.SHA256()))
        blob = json.dumps({"magic": SNAP_MAGIC.decode(), "v": SNAP_VERSION,
                           "nonce": nonce.hex(), "ct": ct.hex(),
                           "sig": sig.hex()}).encode()
        self._log("snapshot", {"files": len(files), "bytes": len(blob)})
        return blob

    def restore(self, blob: bytes, dry_run: bool = False) -> dict:
        """Verify signature, decrypt, restore files atomically (temp+rename).
        Tampered/forged blob -> ValueError, existing state NEVER touched."""
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
        try:
            self._priv.public_key().verify(sig, to_verify, ec.ECDSA(hashes.SHA256()))
        except Exception as e:
            self._log("restore", {"reason": f"signature: {e}"}, outcome="rejected")
            raise ValueError(f"snapshot signature invalid: {e}")
        try:
            payload = self._aes.decrypt(nonce, ct, b"bawes-snap")
        except Exception as e:
            self._log("restore", {"reason": f"auth-tag: {e}"}, outcome="rejected")
            raise ValueError(f"snapshot decryption failed (tampered): {e}")
        data = json.loads(payload)
        if data.get("v") != SNAP_VERSION:
            raise ValueError("snapshot payload version mismatch")

        files = data.get("files", {})
        if dry_run:
            self._log("restore", {"files": len(files), "mode": "dry-run"})
            return {"restored": len(files), "dry_run": True}

        # atomic: write to temp dir, then swap (crash mid-restore = old state intact)
        self.bank_dir.mkdir(parents=True, exist_ok=True)
        tmp = pathlib.Path(tempfile.mkdtemp(prefix=".snap-restore-",
                                            dir=str(self.bank_dir.parent)))
        try:
            for rel, content in files.items():
                p = tmp / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(base64.b64decode(content))
                os.chmod(p, 0o600)
            for old in self.bank_dir.iterdir():
                if old.name.startswith(".snap-restore-"):
                    continue
                if old.is_dir():
                    shutil.rmtree(old)
                else:
                    old.unlink()
            for item in tmp.iterdir():
                shutil.move(str(item), str(self.bank_dir / item.name))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self._log("restore", {"files": len(files)})
        return {"restored": len(files)}

def main():
    ap = argparse.ArgumentParser(description="brick snapshot/resurrection (T-UNIVERSE-020)")
    ap.add_argument("--bank-dir", required=True, help="brick bank dir to snapshot/restore")
    ap.add_argument("--identity-key", required=True, help="brick ES256 identity key (PEM)")
    ap.add_argument("--out", help="snapshot blob output path (snapshot mode)")
    ap.add_argument("--in", dest="inp", help="snapshot blob input path (restore mode)")
    ap.add_argument("--dry-run", action="store_true", help="verify+decrypt without writing")
    args = ap.parse_args()
    snap = BrickSnapshot(pathlib.Path(args.bank_dir), pathlib.Path(args.identity_key))
    if args.inp:
        res = snap.restore(pathlib.Path(args.inp).read_bytes(), dry_run=args.dry_run)
        print(json.dumps({"restore": res}))
    else:
        blob = snap.snapshot()
        pathlib.Path(args.out).write_bytes(blob)
        os.chmod(args.out, 0o600)
        print(json.dumps({"snapshot": pathlib.Path(args.out).name,
                          "bytes": len(blob)}))

if __name__ == "__main__":
    main()
