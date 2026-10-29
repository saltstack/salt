"""
Regression tests for the Debian postinst scripts.

These verify that the postinst scripts source debconf via ``confmodule``
but tear it down with ``db_stop`` and explicitly close file descriptor 3
before the auto-generated ``#DEBHELPER#`` section runs.

Without this teardown, the debconf passthrough fd 3 leaks into the
debhelper-added systemd commands. In non-interactive Debian preseed
``late_command`` chroot installs (where the parent debconf frontend is
not reachable) this produces "Bad file descriptor" errors and can hang
the install. See https://github.com/saltstack/salt/issues/68269.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
PKG_DEBIAN = REPO_ROOT / "pkg" / "debian"

# All postinst scripts that source ``confmodule``. They must all be made
# safe; the user-reported failure was salt-minion but salt-master,
# salt-api, salt-cloud, salt-syndic share the same defective structure.
POSTINST_SCRIPTS = [
    "salt-api.postinst",
    "salt-cloud.postinst",
    "salt-master.postinst",
    "salt-minion.postinst",
    "salt-syndic.postinst",
]


pytestmark = [
    pytest.mark.skipif(
        sys.platform == "win32",
        reason="Debian postinst scripts only run on Linux/POSIX shells",
    ),
    pytest.mark.skipif(
        shutil.which("sh") is None,
        reason="POSIX /bin/sh shell is required to exercise postinst",
    ),
]


def _build_confmodule_stub(stub_path):
    """
    Write a stub that mimics the real /usr/share/debconf/confmodule.

    Sets up fd 3 (the debconf passthrough) so it points somewhere
    writable (real confmodule does ``exec 3>&1``), exports
    ``DEBIAN_HAS_FRONTEND`` so we don't try to re-exec a frontend, and
    defines minimal stubs for ``db_get`` and ``db_stop`` matching the
    real confmodule semantics.

    Crucially, ``db_stop`` here mirrors the real implementation:
    ``echo STOP >&3``. It does NOT close fd 3 itself; the *postinst* is
    responsible for ``exec 3>&-`` after ``db_stop`` so that any leak of
    fd 3 into subsequently-executed commands cannot occur.
    """
    stub_path.write_text(
        # Mimic the real confmodule: open fd 3 onto original stdout,
        # then redirect stdout to stderr (as confmodule itself does).
        # If the script later writes to fd 3 after we close it, this
        # would error with "Bad file descriptor".
        "exec 3>&1\n"
        "exec 1>&2\n"
        "DEBCONF_REDIR=1\n"
        "export DEBCONF_REDIR\n"
        "DEBIAN_HAS_FRONTEND=1\n"
        "export DEBIAN_HAS_FRONTEND\n"
        # db_get: return the template default ('root' for salt-*/user
        # questions). The real db_get sets $RET and returns 0.
        "db_get() { RET=root; return 0; }\n"
        # db_stop: real one sends STOP to fd 3. We do the same so we
        # can detect whether the postinst called it.
        'db_stop() { echo STOP >&3 2>/dev/null || true; touch "$_DB_STOP_MARKER"; }\n'
    )


def _build_debhelper_stub(marker_path):
    """
    Stand in for the auto-generated ``#DEBHELPER#`` block that dh adds
    to the installed postinst (deb-systemd-helper unmask/enable/etc.).

    The real failure mode is that these inherited fd 3 (still pointing
    at a stale debconf passthrough). We mimic that by asserting fd 3
    is *not* open here. If fd 3 is still open, we fail loudly — exactly
    what surfaces as 'Bad file descriptor' in the wild.

    Note: we use ``if echo test 2>/dev/null >&3`` (a simple command,
    not a brace-group) so that ``set -e`` plus the redirection failure
    is captured into the ``if`` test rather than terminating the script.
    """
    # Briefly disable set -e because dash treats a failed redirection
    # in the *test* of an ``if`` differently depending on whether the
    # command is simple or a group, and we want the leak check to be
    # purely a probe — not affect the script's exit semantics.
    return (
        "# Stand-in for the debhelper-generated systemd section.\n"
        "# In the buggy case, fd 3 leaks into here from confmodule.\n"
        "set +e\n"
        "if echo probe 2>/dev/null >&3; then\n"
        f'    echo "FAIL: fd 3 still open in #DEBHELPER# section" > "{marker_path}"\n'
        "    exit 42\n"
        "fi\n"
        "set -e\n"
    )


def _materialize_postinst(script_name, tmp_path):
    """
    Copy a postinst script into ``tmp_path`` with two substitutions:

    1. ``. /usr/share/debconf/confmodule`` → source our stub instead.
    2. ``#DEBHELPER#`` token → the fd-3-leak detector.

    Returns the path to the rewritten script and the marker paths used
    by the stubs.
    """
    src = (PKG_DEBIAN / script_name).read_text()
    confmodule_stub = tmp_path / "confmodule"
    debhelper_marker = tmp_path / "debhelper_failed"
    db_stop_marker = tmp_path / "db_stop_called"
    _build_confmodule_stub(confmodule_stub)

    rewritten = src.replace(
        ". /usr/share/debconf/confmodule",
        f". {confmodule_stub}",
    ).replace(
        "#DEBHELPER#",
        _build_debhelper_stub(debhelper_marker),
    )
    script = tmp_path / script_name
    script.write_text(rewritten)
    script.chmod(0o755)
    return script, debhelper_marker, db_stop_marker


@pytest.mark.parametrize("script_name", POSTINST_SCRIPTS)
def test_postinst_closes_debconf_fd3_before_debhelper(script_name, tmp_path):
    """
    The configure branch of each postinst must call ``db_stop`` and
    close fd 3 before the auto-generated ``#DEBHELPER#`` section runs.

    Without this, fd 3 (the debconf protocol passthrough opened by
    ``confmodule``) leaks into ``deb-systemd-helper`` invocations and
    produces ``Bad file descriptor`` errors in non-interactive
    preseed installs (issue #68269).
    """
    script, debhelper_failed, db_stop_marker = _materialize_postinst(
        script_name, tmp_path
    )
    env = {
        "PATH": "/usr/bin:/bin",
        # Stub points db_stop's marker writer here.
        "_DB_STOP_MARKER": str(db_stop_marker),
        # Force a non-interactive, no-prompts environment.
        "DEBIAN_FRONTEND": "noninteractive",
    }
    result = subprocess.run(
        ["/bin/sh", str(script), "configure"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert not debhelper_failed.exists(), (
        f"#DEBHELPER# section observed fd 3 still open in {script_name}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert result.returncode == 0, (
        f"{script_name} exited {result.returncode}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert db_stop_marker.exists(), (
        f"{script_name} configure branch must call db_stop to terminate "
        f"the debconf protocol; marker missing"
    )
