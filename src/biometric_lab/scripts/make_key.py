"""Generate the template-encryption key file (and optionally a session secret).

Usage:
    python -m biometric_lab.scripts.make_key [--out PATH] [--force]
    python -m biometric_lab.scripts.make_key --secret   # print a session secret only

The key file is restricted to the current user (chmod 600 on POSIX; icacls on Windows).
Keep it OUTSIDE the data/ folder. Losing it makes templates unreadable.
"""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path

from biometric_lab.config import get_settings
from biometric_lab.core.security.crypto import generate_key


def _restrict(path: Path) -> None:
    if os.name == "posix":
        os.chmod(path, 0o600)
    else:  # Windows: grant only the current user, remove inheritance
        user = os.environ.get("USERNAME", "")
        try:
            subprocess.run(["icacls", str(path), "/inheritance:r"], check=False, capture_output=True)
            if user:
                subprocess.run(
                    ["icacls", str(path), "/grant:r", f"{user}:F"], check=False, capture_output=True
                )
        except OSError:
            print("warning: could not set ACLs; restrict the key file manually", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the encryption key file.")
    parser.add_argument("--out", default=None, help="key file path (default: from settings)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing key file")
    parser.add_argument("--secret", action="store_true", help="print a session secret and exit")
    args = parser.parse_args(argv)

    if args.secret:
        print(secrets.token_urlsafe(48))
        return 0

    out = Path(args.out) if args.out else get_settings().key_file
    if out.exists() and not args.force:
        print(f"refusing to overwrite existing key file: {out} (use --force)", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(generate_key())
    _restrict(out)
    print(f"wrote key file: {out}")
    print("Keep this file safe and outside version control and backups of data/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
