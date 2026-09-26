#!/usr/bin/env python3
"""Lock the Secure Boot installer contract to complete, matching MOK pairs."""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "tools" / "sl4a-touch.sh"
src = INSTALLER.read_text(encoding="utf-8")

required = {
    "private-key path": 'MOK_KEY="${SL4A_MOK_KEY:-/var/lib/dkms/mok.key}"',
    "certificate path": 'MOK_CERT="${SL4A_MOK_CERT:-/var/lib/dkms/mok.pub}"',
    "pair validator": "mok_pair_paths_match()",
    "private-key validation": 'openssl pkey -in "$key" -passin pass: -noout',
    "certificate validation": 'openssl x509 -in "$cert" -inform DER -noout',
    "public-key match": "openssl dgst -sha256",
    "rotation flag": "--rotate-mok",
    "backup directory": "/var/lib/dkms/sl4a-mok-backup-",
    "existing pair reuse": "Reusing the existing DKMS signing key pair",
    "alternate pair import": "Use another existing key pair",
    "incomplete material refusal": "MOK material is incomplete/invalid",
    "final pair invariant": "signing identity is not a complete matching key pair after setup",
    "enrollment test": 'mokutil --test-key "$MOK_CERT"',
}

missing = [name for name, needle in required.items() if needle not in src]
if missing:
    raise SystemExit("secure boot installer contract missing: " + ", ".join(missing))

if 'if [ ! -f /var/lib/dkms/mok.pub ]; then' in src:
    raise SystemExit("certificate-only MOK existence check has returned")

if 're-run deliberately with --rotate-mok' not in src:
    raise SystemExit("non-interactive incomplete-key safety contract missing")

if "umask 077" in src:
    raise SystemExit("MOK generation must not change the installer's process-wide umask")

subprocess.run(["bash", "-n", str(INSTALLER)], check=True)
print("secure boot installer source test: PASS")
