"""
Check that each platform's lint requirements lock file can actually be
installed alongside that platform's own CI requirements lock file.

The "Lint" CI job only ever runs on Linux, so nothing in CI exercises
``nox -e lint-salt``/``lint-tests`` on Darwin, FreeBSD or Windows. Those
platforms' lint lock files are only ever installed when a developer runs
the ``lint-salt``/``lint-tests`` pre-commit hooks locally, which means a
version conflict between, say, ``darwin.lock`` and ``darwin-lint.lock``
would otherwise go unnoticed until someone hit it by hand. This check
mirrors what nox actually does (install both lock files together) without
needing a real macOS/FreeBSD/Windows runner.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from ptscripts import Context, command_group

import tools.utils

cgroup = command_group(
    name="lint-locks",
    help="Lint Requirements Lock Consistency Checks",
    parent="pre-commit",
)

CI_REQUIREMENTS_DIR = tools.utils.REPO_ROOT / "requirements" / "static" / "ci"

# platform key -> uv --python-platform value, or None to use --universal
# (uv has no "freebsd" platform tag, so those locks are resolved universally)
PLATFORMS: dict[str, str | None] = {
    "linux": "linux",
    "darwin": "macos",
    "freebsd": None,
    "windows": "windows",
}


@cgroup.command(
    name="check",
)
def check(ctx: Context) -> None:
    """
    Ensure every platform's CI lock and lint lock resolve together.
    """
    uv = shutil.which("uv")
    if not uv:
        ctx.error("Could not find the 'uv' binary")
        ctx.exit(1)

    errors = 0
    with tempfile.TemporaryDirectory(prefix="lint-locks-check-") as tempdir:
        output_file = Path(tempdir) / "combined.lock"
        for pydir in sorted(CI_REQUIREMENTS_DIR.glob("py3.*")):
            if not pydir.is_dir():
                continue
            python_version = pydir.name[len("py") :]
            for platform, python_platform in PLATFORMS.items():
                base_lock = pydir / f"{platform}.lock"
                lint_lock = pydir / f"{platform}-lint.lock"
                if not base_lock.exists() or not lint_lock.exists():
                    continue
                cmdline = [
                    uv,
                    "pip",
                    "compile",
                    str(base_lock.relative_to(tools.utils.REPO_ROOT)),
                    str(lint_lock.relative_to(tools.utils.REPO_ROOT)),
                    "--python-version",
                    python_version,
                    "--no-emit-index-url",
                    "-o",
                    str(output_file),
                ]
                if python_platform is None:
                    cmdline.append("--universal")
                else:
                    cmdline.extend(["--python-platform", python_platform])
                ret = ctx.run(*cmdline, check=False, capture=True)
                if ret.returncode != 0:
                    errors += 1
                    ctx.error(
                        f"Cannot resolve '{base_lock.relative_to(tools.utils.REPO_ROOT)}' "
                        f"together with '{lint_lock.relative_to(tools.utils.REPO_ROOT)}':"
                    )
                    ctx.error(ret.stderr.decode(errors="replace").strip())

    if errors:
        ctx.error(f"Found {errors} lint lock consistency errors")
    ctx.exit(errors)
