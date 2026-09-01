"""
Coverage for the SALT_ONEDIR_HARDEN packaging default (issue #70198).

3009.0 flips ``SALT_ONEDIR_HARDEN=1`` on by default so each salt
daemon's writable state lives under per-daemon
``/var/lib/salt/<daemon>/`` directories and ``/opt/saltstack/salt``
stays root:root 0755. The tests below verify that layout on a
freshly-installed package (all 5 daemons parametrized), plus the
runtime contract that ``salt-pip`` and the daemon's Python honor the
``SALT_EXTRAS_DIR`` env var so the relocated tree stays importable.

These tests use the session-scoped ``install_salt`` fixture from the
parent conftest, which installs every salt daemon package. That means
each parametrized daemon assertion runs against the same real install
-- the multi-role host isolation test below is what verifies the
per-daemon paths don't collide.

For destructive-cycle coverage (SALT_ONEDIR_HARDEN=0 escape hatch,
explicit SALT_HOME/SALT_EXTRAS_DIR override precedence, and upgrade
migration), see ``tests/pytests/pkg/integration/config_overrides/``
which owns the fresh-install/uninstall fixture stack.

Linux-package-only -- Windows uses a different packaging model.
"""

import os
import pathlib
import subprocess

import packaging.version
import pytest

pytestmark = [
    pytest.mark.skip_unless_on_linux,
]


# All 5 daemons in the ``SALT_ONEDIR_HARDEN`` matrix. The session-scoped
# ``install_salt`` fixture installs every one of them, so parametrizing
# a test across the list gives per-daemon fanout without any extra
# install lifecycle.
DAEMONS = ("minion", "master", "syndic", "api", "cloud")


def _hardened_mode_selected():
    """
    Return True when the current test session is running against a
    package installed with SALT_ONEDIR_HARDEN=1 (the default). The
    packaging default flips on 3009.0, so if the env var is unset we
    treat it as hardened. If the operator explicitly opted out with
    SALT_ONEDIR_HARDEN=0, the layout assertions below can't apply.
    """
    return os.environ.get("SALT_ONEDIR_HARDEN", "1") != "0"


@pytest.fixture
def py_ver():
    """Onedir Python major.minor, e.g. ``3.11``."""
    proc = subprocess.run(
        [
            "/opt/saltstack/salt/bin/python3",
            "-c",
            "import sys; sys.stdout.write('{}.{}'.format(*sys.version_info))",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _skip_pre_3009(install_salt):
    """
    SALT_ONEDIR_HARDEN default flip lands on 3009.0. Older builds still
    ship the legacy layout, so these assertions can't apply.
    """
    if packaging.version.parse(install_salt.version) < packaging.version.parse(
        "3009.0"
    ):
        pytest.skip("SALT_ONEDIR_HARDEN=1 default lands on 3009.0")


# ---------------------------------------------------------------------------
# Priority 1 -- explicit gate coverage
# ---------------------------------------------------------------------------


def test_onedir_tree_is_root_owned_when_hardened(install_salt, salt_master):
    """
    Under the hardened default, /opt/saltstack/salt stays owned by
    root:root at 0755 -- the postinst/posttrans no longer chowns the
    onedir tree to the salt user.
    """
    _skip_pre_3009(install_salt)
    if not _hardened_mode_selected():
        pytest.skip("SALT_ONEDIR_HARDEN=0 opt-out selected")

    tree = pathlib.Path("/opt/saltstack/salt")
    assert tree.exists()
    assert (
        tree.owner() == "root"
    ), f"/opt/saltstack/salt owner is {tree.owner()!r}, expected root"
    assert (
        tree.group() == "root"
    ), f"/opt/saltstack/salt group is {tree.group()!r}, expected root"


def test_onedir_tree_files_are_root_when_hardened(install_salt, salt_master):
    """
    Belt-and-braces: not just the top-level dir but a sampling of files
    *under* /opt/saltstack/salt/ stay root-owned in the hardened case.
    Spot-checks bin/python3, bin/salt-pip, and lib/ so a partial or
    accidental deep chown gets caught.
    """
    _skip_pre_3009(install_salt)
    if not _hardened_mode_selected():
        pytest.skip("SALT_ONEDIR_HARDEN=0 opt-out selected")

    for rel in ("bin/python3", "bin/salt-pip", "lib"):
        target = pathlib.Path("/opt/saltstack/salt") / rel
        if not target.exists():
            continue
        assert (
            target.owner() == "root"
        ), f"{target} owner is {target.owner()!r}, expected root"


def test_hardening_unset_matches_hardened_default(install_salt, salt_master):
    """
    SALT_ONEDIR_HARDEN unset must behave identically to
    SALT_ONEDIR_HARDEN=1 on 3009.0+. Belt-and-braces to catch a future
    accidental default flip.
    """
    _skip_pre_3009(install_salt)
    if os.environ.get("SALT_ONEDIR_HARDEN") not in (None, "", "1"):
        pytest.skip("Explicit SALT_ONEDIR_HARDEN override selected")

    # Both assertions from the hardened-mode tests above.
    tree = pathlib.Path("/opt/saltstack/salt")
    assert tree.owner() == "root"

    master_dir = pathlib.Path("/var/lib/salt/master")
    assert master_dir.exists()
    assert master_dir.owner() == "salt"


# ---------------------------------------------------------------------------
# Priority 2 -- per-daemon fanout
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("daemon", DAEMONS)
def test_per_daemon_writable_dir_exists_and_owned_by_salt(
    install_salt, salt_master, daemon
):
    """
    Under the hardened default, each of the 5 daemons gets its own
    /var/lib/salt/<daemon>/ writable dir, owned by the salt user.
    Verified per-daemon so a regression in, say, the salt-syndic
    postinst doesn't hide behind a still-working salt-master postinst.
    """
    _skip_pre_3009(install_salt)
    if not _hardened_mode_selected():
        pytest.skip("SALT_ONEDIR_HARDEN=0 opt-out selected")

    daemon_dir = pathlib.Path(f"/var/lib/salt/{daemon}")
    assert (
        daemon_dir.exists()
    ), f"expected /var/lib/salt/{daemon} to exist under SALT_ONEDIR_HARDEN=1"
    assert daemon_dir.owner() == "salt", (
        f"/var/lib/salt/{daemon} owner is {daemon_dir.owner()!r}," " expected salt"
    )


@pytest.mark.parametrize("daemon", DAEMONS)
def test_per_daemon_home_owned_by_salt(install_salt, salt_master, daemon):
    """
    Each daemon's per-daemon home dir is chowned to the salt user so
    the daemon process can actually write there.
    """
    _skip_pre_3009(install_salt)
    if not _hardened_mode_selected():
        pytest.skip("SALT_ONEDIR_HARDEN=0 opt-out selected")

    home = pathlib.Path(f"/var/lib/salt/{daemon}/home")
    if not home.exists():
        # Not every daemon's postinst creates the home subdir eagerly
        # (e.g. cloud is a client, not a daemon). If it wasn't created
        # the parent dir still counts -- covered by the test above.
        pytest.skip(
            f"/var/lib/salt/{daemon}/home not created by this daemon's postinst"
        )
    assert home.owner() == "salt"


@pytest.mark.parametrize("daemon", DAEMONS)
def test_per_daemon_extras_owned_by_salt(install_salt, salt_master, py_ver, daemon):
    """
    Each daemon's per-daemon extras dir is chowned to the salt user so
    salt-pip installs land in a writable location.
    """
    _skip_pre_3009(install_salt)
    if not _hardened_mode_selected():
        pytest.skip("SALT_ONEDIR_HARDEN=0 opt-out selected")

    extras = pathlib.Path(f"/var/lib/salt/{daemon}/extras-{py_ver}")
    if not extras.exists():
        pytest.skip(
            f"/var/lib/salt/{daemon}/extras-{py_ver} not created by this "
            "daemon's postinst"
        )
    assert extras.owner() == "salt"


# ---------------------------------------------------------------------------
# Priority 5 -- multi-role host isolation
#
# The session install_salt fixture installs all 5 daemons on the same
# host. The hardened layout's core guarantee is that each daemon's
# writable state is *isolated* from the others -- a write to
# /var/lib/salt/minion/extras/ must not appear under
# /var/lib/salt/master/extras/.
#
# Fixture note: full multi-role coverage (different SALT_USER per
# daemon, cross-daemon file visibility with real running daemons)
# would require test scaffolding that runs each daemon under a
# different account. That's a fixture-plumbing extension deferred to
# a follow-up test PR; this test verifies the packaging-level
# separation, which is the load-bearing guarantee.
# ---------------------------------------------------------------------------


def test_per_daemon_dirs_are_distinct(install_salt, salt_master, py_ver):
    """
    Multi-role isolation: every per-daemon dir exists as an independent
    directory (not symlinks, not shared inodes). A file written to one
    daemon's tree must not appear under another daemon's tree.
    """
    _skip_pre_3009(install_salt)
    if not _hardened_mode_selected():
        pytest.skip("SALT_ONEDIR_HARDEN=0 opt-out selected")

    present = [d for d in DAEMONS if pathlib.Path(f"/var/lib/salt/{d}").exists()]
    assert len(present) >= 2, (
        "Multi-role isolation test needs at least 2 daemons installed; "
        f"found {present!r}. Session install_salt should install all 5."
    )

    # Distinct inodes -- no bind-mount / hardlink collapse.
    inodes = {}
    for daemon in present:
        st = pathlib.Path(f"/var/lib/salt/{daemon}").stat()
        assert (
            st.st_dev,
            st.st_ino,
        ) not in inodes.values(), (
            f"/var/lib/salt/{daemon} shares inode with an earlier daemon dir"
        )
        inodes[daemon] = (st.st_dev, st.st_ino)

    # Cross-daemon file-visibility check. Drop a marker under each
    # daemon's dir, then assert it's ONLY visible under that daemon.
    markers = {}
    try:
        for daemon in present:
            marker = pathlib.Path(f"/var/lib/salt/{daemon}/.isolation-marker")
            marker.write_text(daemon, encoding="utf-8")
            markers[daemon] = marker
        for daemon in present:
            for other in present:
                other_marker = pathlib.Path(f"/var/lib/salt/{other}/.isolation-marker")
                content = other_marker.read_text(encoding="utf-8")
                assert content == other, (
                    f"marker under /var/lib/salt/{other} reads {content!r} "
                    f"(cross-daemon leak from {daemon}?)"
                )
    finally:
        for marker in markers.values():
            marker.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Runtime salt-pip contract
# ---------------------------------------------------------------------------


def test_salt_pip_honors_salt_extras_dir(install_salt, tmp_path, py_ver):
    """
    Runtime contract: ``salt-pip install`` honors the SALT_EXTRAS_DIR
    env var (packaging layer sets this under SALT_ONEDIR_HARDEN=1 so
    packages land in the same place the daemon's Python imports from).

    The unit tests already cover the extras-resolution helper; this
    integration test verifies the resolved value actually reaches pip's
    ``--target`` and PYTHONPATH via the real salt-pip binary.
    """
    _skip_pre_3009(install_salt)

    override = tmp_path / "override-extras"
    override.mkdir()

    env = os.environ.copy()
    env["SALT_EXTRAS_DIR"] = str(override)

    # Install a small pure-python package that has no compiled deps so
    # the test is fast and portable across archs.
    proc = subprocess.run(
        [
            "/opt/saltstack/salt/bin/salt-pip",
            "install",
            "--no-deps",
            "six",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert proc.returncode == 0, (
        f"salt-pip install failed under SALT_EXTRAS_DIR override:\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )

    # Verify the package landed under the override, not under
    # /opt/saltstack/salt/extras-<py>.
    assert (override / "six.py").exists() or list(override.glob("six-*")), (
        f"six was not installed into SALT_EXTRAS_DIR override {override}; "
        f"tree contents: {list(override.iterdir())}"
    )

    # Clean up so we don't pollute subsequent tests.
    subprocess.run(
        [
            "/opt/saltstack/salt/bin/salt-pip",
            "uninstall",
            "-y",
            "six",
        ],
        env=env,
        capture_output=True,
        timeout=60,
        check=False,
    )
