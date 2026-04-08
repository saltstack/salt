"""
Helpers for test-suite ``sshd`` instances.

Minimal container images (e.g. Ubuntu CI) often ship OpenSSH without creating the
runtime directory used for privilege separation (commonly ``/run/sshd``). If that
directory is missing, ``sshd`` exits immediately with:

    Missing privilege separation directory: /run/sshd

which surfaces as :class:`~pytestshellutils.exceptions.FactoryNotStarted` in tests.
"""

from __future__ import annotations

import logging
import os
import pathlib
import shutil
import subprocess
import sys

log = logging.getLogger(__name__)


def ensure_sshd_privilege_separation_directories(
    sshd_config_file: str | os.PathLike[str] | None = None,
) -> None:
    """
    Ensure privilege-separation (and similar) directories exist before starting ``sshd``.

    * Prefer directories reported by ``sshd -T`` for the test config (portable across
      distros / OpenSSH builds).
    * If none are found, on Linux only, create ``/run/sshd`` — the usual expectation
      on Debian/Ubuntu-family images when ``/run`` is tmpfs and the package postinst
      did not run (typical in CI containers).

    Creating an unused empty directory is harmless; skipping non-Linux fallbacks
    avoids touching paths that do not apply to macOS or Windows SSH test runs.
    """
    if os.name == "nt":
        return

    sshd = shutil.which("sshd")
    if not sshd:
        log.debug("sshd not in PATH; skipping privilege-separation directory setup")
        return

    config_path: pathlib.Path | None = None
    if sshd_config_file is not None:
        p = pathlib.Path(sshd_config_file)
        if p.is_file():
            config_path = p.resolve()

    cmd = [sshd, "-T"]
    if config_path is not None:
        cmd.extend(["-f", str(config_path)])

    dirs: list[str] = []
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(None, 1)
                if len(parts) != 2:
                    continue
                key, val = parts[0].lower(), parts[1].strip()
                if "privsep" not in key:
                    continue
                if val in ("none", "yes", "no", "sandbox"):
                    continue
                if val.startswith("/"):
                    dirs.append(val)
        else:
            log.debug(
                "sshd -T failed (rc=%s): %s",
                proc.returncode,
                (proc.stderr or proc.stdout or "").strip()[:500],
            )
    except OSError as exc:
        log.debug("Could not query sshd -T: %s", exc)

    if not dirs and sys.platform.startswith("linux") and os.path.isdir("/run"):
        dirs.append("/run/sshd")

    for d in dirs:
        try:
            os.makedirs(d, mode=0o755, exist_ok=True)
            log.debug("Ensured sshd runtime directory exists: %s", d)
        except OSError as exc:
            log.debug("Could not create %s: %s", d, exc)
