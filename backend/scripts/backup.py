#!/usr/bin/python3
"""Run as postgres; custom-format backup, atomic publication and 14-file retention."""
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import subprocess


def main():
    directory = Path("/var/backups/bashgroup")
    with (directory / ".backup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        final = directory / f"bashgroup-{stamp}.dump"
        temporary = final.with_suffix(".incomplete")
        os.umask(0o077)
        try:
            subprocess.run(["pg_dump", "--format=custom", "--no-password", "--file", str(temporary), "bashgroup"], check=True)
            subprocess.run(["pg_restore", "--list", str(temporary)], check=True, stdout=subprocess.DEVNULL)
            if temporary.stat().st_size == 0:
                raise RuntimeError("Empty database backup")
            os.replace(temporary, final)
            for old in sorted(directory.glob("bashgroup-*.dump"), reverse=True)[14:]:
                old.unlink()
            print(f"Backup ready: {final.name} ({final.stat().st_size} bytes); retention: 14 files")
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
