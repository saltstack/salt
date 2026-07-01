"""
Regression tests for packaging scriptlets that decide which user owns the
salt-master state directories on upgrade.

These tests execute the actual scriptlet shell code (from
``pkg/debian/salt-master.preinst`` and the ``%pre master`` block of
``pkg/rpm/salt.spec``) inside a sandbox: the scriptlet operates on a
temporary "root" tree with the system ``chown``, ``ls``, ``id``,
``db_set`` and friends stubbed out. We capture the user the scriptlet
decides on and assert that it honors the ``user:`` directive configured
in ``/etc/salt/master`` / ``/etc/salt/master.d/*.conf``.

Regression for https://github.com/saltstack/salt/issues/68577.
"""

import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
PREINST = REPO_ROOT / "pkg" / "debian" / "salt-master.preinst"
SPEC = REPO_ROOT / "pkg" / "rpm" / "salt.spec"


pytestmark = [
    pytest.mark.skipif(shutil.which("sh") is None, reason="POSIX shell required"),
]


def _extract_deb_upgrade_block(preinst_text):
    """
    Extract the body that runs under the ``upgrade)`` arm of the preinst
    case statement. Drop the debconf-confmodule include (not available in
    a sandbox) and stop before the systemd-helper workaround, which
    writes outside the test sandbox.
    """
    m = re.search(
        r"upgrade\)\s*\n(.*?)\n\s*if \[ ! -f /var/lib/systemd", preinst_text, re.DOTALL
    )
    assert m, "could not locate upgrade arm in preinst"
    body = m.group(1)
    body = re.sub(
        r"^\s*\. /usr/share/debconf/confmodule\s*$", "", body, flags=re.MULTILINE
    )
    return body


def _extract_rpm_pre_master_block(spec_text):
    """
    Extract the shell body of ``%pre master``. The block ends at the
    next ``%pre`` directive (``%pre syndic``).
    """
    m = re.search(r"%pre master\s*\n(.*?)\n%pre syndic", spec_text, re.DOTALL)
    assert m, "could not locate %pre master in spec"
    return m.group(1)


SANDBOX_PROLOGUE = textwrap.dedent(
    """\
    set -e
    # The preinst's top-of-file block (which initializes SALT_USER /
    # SALT_GROUP defaults) is outside the `upgrade)` arm we extract, so
    # mirror its defaults here.
    SALT_USER=salt
    SALT_GROUP=salt
    # Stub out side-effectful commands the scriptlet would call against
    # the live system. We just want to observe which user the scriptlet
    # would have chowned/db_set to.
    chown() { :; }
    db_set() {
        # Emit so the test can capture the value the scriptlet wrote to
        # debconf.
        echo "DB_SET $1=$2"
    }
    systemctl() { :; }
    id() {
        # Emulate `id -gn <user>` by echoing the user (group = user, no
        # passwd entry available in test). Other invocations no-op.
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
    Rewrite bare absolute paths so they live under the sandbox tempdir.
    The scriptlet code intentionally uses absolute paths, so the test
    rewrites them rather than depending on a chroot.
    """
    rules = [
        (r"/etc/salt/master\.d", f"{sandbox}/etc/salt/master.d"),
        (r"/etc/salt/master(?!\.)", f"{sandbox}/etc/salt/master"),
        (r"/etc/salt/pki/master", f"{sandbox}/etc/salt/pki/master"),
        (r"/var/cache/salt/master", f"{sandbox}/var/cache/salt/master"),
        (r"/var/log/salt/master", f"{sandbox}/var/log/salt/master"),
        (r"/var/log/salt/key", f"{sandbox}/var/log/salt/key"),
        (r"/var/run/salt/master", f"{sandbox}/var/run/salt/master"),
        (r"(?<!/var)/run/salt/master", f"{sandbox}/run/salt/master"),
        (r"/run/salt-master\.pid", f"{sandbox}/run/salt-master.pid"),
    ]
    for pat, repl in rules:
        body = re.sub(pat, repl, body)
    return body


def _run_deb_block(body, sandbox, argv1="2"):
    """
    Run the deb scriptlet body in a sandbox and return the completed
    process. The test inspects stdout for ``CUR_USER=...`` and for the
    ``DB_SET salt-master/user=...`` line emitted by the stubbed
    ``db_set``.
    """
    rewritten = _rewrite_paths(body, str(sandbox))
    script = (
        SANDBOX_PROLOGUE
        + f"set -- {argv1}\n"
        + rewritten
        + textwrap.dedent(
            """
        echo "DEB_CUR_USER=${CUR_USER:-}"
        echo "DEB_CUR_GROUP=${CUR_GROUP:-}"
        """
        )
    )
    return subprocess.run(
        ["sh", "-c", script], capture_output=True, text=True, check=False
    )


def _run_rpm_block(body, sandbox, argv1="2"):
    """
    Run the ``%pre master`` shell body. The block opens with
    ``if [ $1 -gt 1 ]`` so ``$1`` must be ``> 1`` to trigger the upgrade
    path. The test inspects the resulting ``CUR_USER`` shell variable.
    """
    rewritten = _rewrite_paths(body, str(sandbox))
    script = (
        SANDBOX_PROLOGUE
        + f"set -- {argv1}\n"
        + rewritten
        + textwrap.dedent(
            """
        echo "RPM_CUR_USER=${_MS_CUR_USER:-${CUR_USER:-}}"
        echo "RPM_CUR_GROUP=${_MS_CUR_GROUP:-${CUR_GROUP:-}}"
        """
        )
    )
    return subprocess.run(
        ["sh", "-c", script], capture_output=True, text=True, check=False
    )


def _make_tree(tmp_path):
    """Build a minimal /etc/salt + /var/... tree under tmp_path."""
    for sub in (
        "etc/salt/master.d",
        "etc/salt/pki/master",
        "var/cache/salt/master",
        "var/log/salt",
        "var/run/salt/master",
        "run/salt/master",
        "run",
    ):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def deb_upgrade_block():
    return _extract_deb_upgrade_block(PREINST.read_text())


@pytest.fixture
def rpm_pre_master_block():
    return _extract_rpm_pre_master_block(SPEC.read_text())


def test_deb_preinst_honors_configured_user_in_master(tmp_path, deb_upgrade_block):
    """
    The Debian preinst must use the ``user:`` directive from
    /etc/salt/master when deciding which user owns the state
    directories on upgrade. Filesystem ownership / the default debconf
    ``salt`` answer must not override an explicit config.
    """
    sandbox = _make_tree(tmp_path)
    (sandbox / "etc/salt/master").write_text("user: bob\n")
    proc = _run_deb_block(deb_upgrade_block, sandbox)
    assert proc.returncode == 0, proc.stderr
    assert "DEB_CUR_USER=bob" in proc.stdout, proc.stdout
    assert "DB_SET salt-master/user=bob" in proc.stdout, proc.stdout


def test_deb_preinst_honors_configured_user_in_master_d_dropin(
    tmp_path, deb_upgrade_block
):
    """
    Same as the previous test, but the ``user:`` directive lives in a
    drop-in under /etc/salt/master.d/ rather than the main config.
    """
    sandbox = _make_tree(tmp_path)
    (sandbox / "etc/salt/master.d/_custom.conf").write_text("user: alice\n")
    proc = _run_deb_block(deb_upgrade_block, sandbox)
    assert proc.returncode == 0, proc.stderr
    assert "DEB_CUR_USER=alice" in proc.stdout, proc.stdout
    assert "DB_SET salt-master/user=alice" in proc.stdout, proc.stdout


def test_deb_preinst_falls_back_to_default_when_no_config(tmp_path, deb_upgrade_block):
    """
    With no ``user:`` configured and no live pid file, the preinst
    should fall back to the default ``salt`` user (the existing
    behavior). This guards against regressing the fresh-install /
    config-less path.
    """
    sandbox = _make_tree(tmp_path)
    # No /etc/salt/master, no pid file.
    proc = _run_deb_block(deb_upgrade_block, sandbox)
    assert proc.returncode == 0, proc.stderr
    assert "DEB_CUR_USER=salt" in proc.stdout, proc.stdout


def test_rpm_pre_master_honors_configured_user_in_master(
    tmp_path, rpm_pre_master_block
):
    """
    The rpm ``%pre master`` scriptlet must read ``user:`` from
    /etc/salt/master when deciding which user owns the master state
    directories on upgrade.
    """
    sandbox = _make_tree(tmp_path)
    (sandbox / "etc/salt/master").write_text("user: bob\n")
    proc = _run_rpm_block(rpm_pre_master_block, sandbox)
    assert proc.returncode == 0, proc.stderr
    assert "RPM_CUR_USER=bob" in proc.stdout, proc.stdout


def test_rpm_pre_master_does_not_emit_global_macros(rpm_pre_master_block):
    """
    The original spec contained ``%global _MS_CUR_USER %{_MS_LCUR_USER}``
    lines inside the shell scriptlet. ``%global`` is an rpm build-time
    macro directive; placing it inside the scriptlet body is dead code,
    and the macro references (``%{_MS_LCUR_USER}``) were never defined
    as rpm macros (they were shell variables) so the directive expanded
    to nothing useful. Guard against the broken pattern reappearing.
    Only inspect non-comment lines so this regression test does not
    trip on commentary explaining the historical breakage.
    """
    for line in rpm_pre_master_block.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        assert "%global _MS_CUR_USER" not in line, line
        assert "%global _MS_CUR_GROUP" not in line, line
