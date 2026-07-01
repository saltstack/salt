"""
Regression tests for packaging scriptlets that decide which user owns the
salt-minion state directories on upgrade.

These tests run the actual scriptlet shell code (from
``pkg/debian/salt-minion.preinst`` and ``pkg/rpm/salt.spec``) inside a
sandbox: the scriptlet operates on a temporary "root" tree with the system
``chown``, ``ls``, ``id``, ``db_set``, ``systemctl`` and friends stubbed
out. We capture the user the scriptlet decides on and assert that it
honors the ``user:`` directive configured in ``/etc/salt/minion`` /
``/etc/salt/minion.d/*.conf``.

Regression for https://github.com/saltstack/salt/issues/68793.
"""

import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
PREINST = REPO_ROOT / "pkg" / "debian" / "salt-minion.preinst"
SPEC = REPO_ROOT / "pkg" / "rpm" / "salt.spec"


pytestmark = [
    pytest.mark.skipif(shutil.which("sh") is None, reason="POSIX shell required"),
]


def _extract_deb_upgrade_block(preinst_text):
    """
    Extract the body that runs under the ``upgrade)`` arm of the preinst
    case statement. We chop off the debconf-confmodule include and the
    /opt/saltstack/salt python invocation (neither is available in a
    sandbox) and stop before the systemd-helper workaround, which writes
    outside the test sandbox.
    """
    m = re.search(
        r"upgrade\)\s*\n(.*?)\n\s*if \[ ! -f /var/lib/systemd", preinst_text, re.DOTALL
    )
    assert m, "could not locate upgrade arm in preinst"
    body = m.group(1)
    # Drop the live-environment lines we don't want in the sandbox.
    body = re.sub(
        r"^\s*\. /usr/share/debconf/confmodule\s*$", "", body, flags=re.MULTILINE
    )
    body = re.sub(r"^\s*PY_VER=.*$", "", body, flags=re.MULTILINE)
    return body


def _extract_rpm_pre_minion_block(spec_text):
    """
    Extract the shell body of ``%pre minion``. The block ends at the next
    ``%pre`` directive (``%pre cloud``).
    """
    m = re.search(r"%pre minion\s*\n(.*?)\n%pre cloud", spec_text, re.DOTALL)
    assert m, "could not locate %pre minion in spec"
    return m.group(1)


SANDBOX_PROLOGUE = textwrap.dedent(
    """\
    set -e
    # Redirect filesystem reads inside the scriptlet at the path level.
    # We can't chroot in a unit test, so we replace bare paths with
    # ${SANDBOX}-prefixed ones via sed at extraction time.
    chown() { :; }
    db_set() { :; }
    systemctl() { :; }
    # The id builtin is fine; group lookup returns the configured user
    # name because in the sandbox there's no real group database.
    id() {
        # Emulate `id -gn <user>` by echoing the user (group = user, no
        # passwd entry available in test). Other invocations are ignored.
        if [ "$1" = "-gn" ] && [ -n "$2" ]; then
            echo "$2"
            return 0
        fi
        return 0
    }
    """
)


def _rewrite_paths(body, sandbox):
    """
    Rewrite bare /etc/salt, /run/..., /var/cache/..., /var/log/...,
    /tmp/.salt-minion-upgrade-ownership paths so they live under the
    sandbox tempdir. The scriptlet code intentionally uses absolute
    paths, so the test rewrites them rather than depending on a chroot.
    """
    rules = [
        (r"/etc/salt/minion\.d", f"{sandbox}/etc/salt/minion.d"),
        (r"/etc/salt/minion(?!\.)", f"{sandbox}/etc/salt/minion"),
        (r"/etc/salt/pki/minion", f"{sandbox}/etc/salt/pki/minion"),
        (r"/var/cache/salt/minion", f"{sandbox}/var/cache/salt/minion"),
        (r"/var/log/salt/minion", f"{sandbox}/var/log/salt/minion"),
        (r"/var/run/salt/minion", f"{sandbox}/var/run/salt/minion"),
        (r"/run/salt/minion", f"{sandbox}/run/salt/minion"),
        (r"/run/salt-minion\.pid", f"{sandbox}/run/salt-minion.pid"),
        (
            r"/tmp/\.salt-minion-upgrade-ownership",
            f"{sandbox}/tmp/.salt-minion-upgrade-ownership",
        ),
        (
            r"/etc/sysconfig/salt-minion-setup",
            f"{sandbox}/etc/sysconfig/salt-minion-setup",
        ),
    ]
    for pat, repl in rules:
        body = re.sub(pat, repl, body)
    return body


def _run_block(body, sandbox, argv1="2"):
    """
    Run the scriptlet body in a sandbox and return the value of CUR_USER
    (deb) or the contents of the upgrade-ownership marker file (rpm).
    The marker is the contract used to communicate the chosen user to
    %post minion in the rpm spec.
    """
    rewritten = _rewrite_paths(body, str(sandbox))
    script = (
        SANDBOX_PROLOGUE
        + f"set -- {argv1}\n"
        + rewritten
        + textwrap.dedent(
            f"""
        # Emit the chosen user so the test can inspect it. CUR_USER is
        # the variable set in the deb preinst; for the rpm we read the
        # marker file the scriptlet wrote.
        echo "DEB_CUR_USER=${{CUR_USER:-}}"
        if [ -f {sandbox}/tmp/.salt-minion-upgrade-ownership ]; then
            echo "RPM_MARKER=$(cat {sandbox}/tmp/.salt-minion-upgrade-ownership)"
        fi
        """
        )
    )
    proc = subprocess.run(
        ["sh", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc


def _make_tree(tmp_path):
    """Build a minimal /etc/salt + /var/... tree under tmp_path."""
    for sub in (
        "etc/salt/minion.d",
        "etc/salt/pki/minion",
        "var/cache/salt/minion",
        "var/log/salt",
        "var/run/salt/minion",
        "run/salt/minion",
        "tmp",
        "etc/sysconfig",
    ):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def deb_upgrade_block():
    return _extract_deb_upgrade_block(PREINST.read_text())


@pytest.fixture
def rpm_pre_minion_block():
    return _extract_rpm_pre_minion_block(SPEC.read_text())


def test_deb_preinst_honors_configured_user_in_minion(tmp_path, deb_upgrade_block):
    """
    The Debian preinst must use the ``user:`` directive from
    /etc/salt/minion when deciding which user owns the state
    directories on upgrade. Filesystem ownership (which under systemd is
    often root for cache/pki on first upgrade) must not override an
    explicit config.
    """
    sandbox = _make_tree(tmp_path)
    (sandbox / "etc/salt/minion").write_text("user: bob\n")
    proc = _run_block(deb_upgrade_block, sandbox)
    assert proc.returncode == 0, proc.stderr
    assert "DEB_CUR_USER=bob" in proc.stdout, proc.stdout


def test_deb_preinst_honors_configured_user_in_minion_d_dropin(
    tmp_path, deb_upgrade_block
):
    """
    Same as the previous test, but the ``user:`` directive lives in a
    drop-in under /etc/salt/minion.d/ rather than the main config.
    """
    sandbox = _make_tree(tmp_path)
    (sandbox / "etc/salt/minion.d/_custom.conf").write_text("user: alice\n")
    proc = _run_block(deb_upgrade_block, sandbox)
    assert proc.returncode == 0, proc.stderr
    assert "DEB_CUR_USER=alice" in proc.stdout, proc.stdout


def test_rpm_pre_minion_honors_configured_user_in_minion(
    tmp_path, rpm_pre_minion_block
):
    """
    The rpm %pre minion scriptlet must write the configured user (not
    just whatever filesystem ownership it sees) into the
    /tmp/.salt-minion-upgrade-ownership marker file. %post minion reads
    that marker and chowns based on it.
    """
    sandbox = _make_tree(tmp_path)
    (sandbox / "etc/salt/minion").write_text("user: bob\n")
    proc = _run_block(rpm_pre_minion_block, sandbox)
    assert proc.returncode == 0, proc.stderr
    assert "RPM_MARKER=bob:bob" in proc.stdout, proc.stdout


def test_rpm_pre_minion_does_not_emit_global_macros(rpm_pre_minion_block):
    """
    The original spec contained ``%global _MN_CUR_USER %{MINION_USER}``
    style lines inside the shell scriptlet. ``%global`` is an rpm
    build-time macro directive; placing it inside the scriptlet body is
    dead code, and the macro references ``%{MINION_USER}`` /
    ``%{_MN_LCUR_USER}`` were never defined as rpm macros (they were
    shell variables) so the directive expanded to nothing useful. Guard
    against the broken pattern reappearing. Only inspect non-comment
    lines so this regression test does not trip on commentary that
    explains the historical breakage.
    """
    for line in rpm_pre_minion_block.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        assert "%global _MN_CUR_USER" not in line, line
        assert "%global _MN_CUR_GROUP" not in line, line
