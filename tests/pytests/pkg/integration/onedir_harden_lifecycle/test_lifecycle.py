"""
Destructive-cycle package tests for the SALT_ONEDIR_HARDEN packaging
opt-in on 3006.x (issue #70198).

On 3006.x the default is UNSET (legacy chown layout preserved).
Operators opt in explicitly via ``SALT_ONEDIR_HARDEN=1`` to get the
hardened per-daemon layout early on LTS. The default flips to hardened
on 3009.0.

These tests perform real install/uninstall lifecycles so they can
exercise the packaging behavior that a static fixture install can't:

- SALT_ONEDIR_HARDEN unset = legacy chown layout (3006.x default)
- SALT_ONEDIR_HARDEN=1 = hardened per-daemon layout
- explicit SALT_HOME / SALT_EXTRAS_DIR overrides winning over the
  hardened opt-in
- upgrade migration from a pre-populated legacy
  /opt/saltstack/salt/extras-<py>/ tree into
  /var/lib/salt/<daemon>/extras-<py>/ when operator opts in to
  hardening
- upgrade idempotency (second postinst run with HARDEN=1 is a no-op)

The fixtures live in ``conftest.py`` and mirror the destructive-cycle
pattern established by ``tests/pytests/pkg/integration/config_overrides/``.

Linux-package-only.
"""

import logging
import os
import pathlib
import subprocess

import pytest

from tests.pytests.pkg.integration.onedir_harden_lifecycle.conftest import (
    CUSTOM_EXTRAS,
    CUSTOM_HOME,
    LEGACY_EXTRAS_MARKER_CONTENT,
    LEGACY_EXTRAS_MARKER_NAME,
)

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_unless_on_linux(reason="Linux DEB/RPM packaging only"),
    pytest.mark.destructive_test,
]


DAEMONS = ("minion", "master", "syndic", "api", "cloud")


# ---------------------------------------------------------------------------
# Priority 1 -- SALT_ONEDIR_HARDEN unset (3006.x default) = legacy layout
# ---------------------------------------------------------------------------


def test_harden_default_uses_legacy_chown_layout(install_harden_default):
    """
    With SALT_ONEDIR_HARDEN completely unset (no env var, no override
    file), the packaging default on 3006.x is the legacy layout:
    /opt/saltstack/salt is chowned to the salt user.

    On 3009.0 this default flips to hardened; this test pins the LTS
    default so an accidental default flip on 3006.x fails CI loud.
    """
    tree = pathlib.Path("/opt/saltstack/salt")
    assert tree.exists()
    assert tree.owner() == "salt", (
        f"With SALT_ONEDIR_HARDEN unset on 3006.x, /opt/saltstack/salt "
        f"should be salt-owned (legacy layout); got {tree.owner()!r}"
    )


def test_harden_default_leaves_per_daemon_dirs_absent(install_harden_default):
    """
    Under the 3006.x legacy default, /var/lib/salt/<daemon>/ should
    NOT be created by any daemon's postinst -- that's what the hardened
    opt-in enables.

    /var/lib/salt itself is packaged via salt-common.dirs so its
    existence is not a signal; we assert on the per-daemon subdirs.
    """
    for daemon in DAEMONS:
        subdir = pathlib.Path(f"/var/lib/salt/{daemon}")
        assert not subdir.exists(), (
            f"With SALT_ONEDIR_HARDEN unset on 3006.x the per-daemon "
            f"dir /var/lib/salt/{daemon} should not exist, but it does"
        )


# ---------------------------------------------------------------------------
# Priority 1 -- SALT_ONEDIR_HARDEN=1 opt-in = hardened layout
# ---------------------------------------------------------------------------


def test_harden_on_produces_hardened_layout(install_harden_on):
    """
    With SALT_ONEDIR_HARDEN=1 selected via the override file + env,
    the packaging must produce the hardened layout on 3006.x:
    /opt/saltstack/salt stays root:root and per-daemon dirs exist
    under /var/lib/salt/.
    """
    tree = pathlib.Path("/opt/saltstack/salt")
    assert tree.exists()
    assert tree.owner() == "root", (
        f"With HARDEN=1 opt-in, /opt/saltstack/salt should be root; "
        f"got {tree.owner()!r}"
    )

    master_dir = pathlib.Path("/var/lib/salt/master")
    assert (
        master_dir.exists()
    ), "With HARDEN=1 opt-in, /var/lib/salt/master should exist"
    assert master_dir.owner() == "salt"


# ---------------------------------------------------------------------------
# Priority 4 -- explicit SALT_HOME / SALT_EXTRAS_DIR override precedence
# ---------------------------------------------------------------------------


def test_explicit_salt_home_wins_over_harden_default(install_harden_custom_home):
    """
    Explicit SALT_HOME in /etc/default/salt-setup wins over the
    HARDEN=1 opt-in's per-daemon /var/lib/salt/<daemon>/home path.
    The custom SALT_HOME must exist and be owned by the salt user;
    /opt/saltstack/salt must still be root:root (hardening still on).
    """
    custom = pathlib.Path(CUSTOM_HOME)
    assert custom.exists(), (
        f"Explicit SALT_HOME={CUSTOM_HOME} should have been created "
        "by salt-common preinst"
    )
    assert custom.owner() == "salt"

    # /opt/saltstack/salt still root-owned because HARDEN=1 still
    # in effect (explicit SALT_HOME doesn't turn off hardening).
    tree = pathlib.Path("/opt/saltstack/salt")
    assert tree.owner() == "root"


def test_explicit_salt_extras_dir_wins_over_harden_default(
    install_harden_custom_extras,
):
    """
    Explicit SALT_EXTRAS_DIR wins over the HARDEN=1 opt-in's
    per-daemon /var/lib/salt/<daemon>/extras-<py> path. The custom
    dir must exist and be owned by the salt user.
    """
    custom = pathlib.Path(CUSTOM_EXTRAS)
    assert custom.exists(), (
        f"Explicit SALT_EXTRAS_DIR={CUSTOM_EXTRAS} should have been "
        "created by a daemon postinst"
    )
    assert custom.owner() == "salt"

    # /opt/saltstack/salt still root-owned.
    tree = pathlib.Path("/opt/saltstack/salt")
    assert tree.owner() == "root"


# ---------------------------------------------------------------------------
# Priority 3 -- upgrade migration + idempotency
# ---------------------------------------------------------------------------


def test_upgrade_migration_moves_legacy_extras(install_harden_upgrade_migration):
    """
    Simulated legacy-to-hardened upgrade path on 3006.x:

    - Install with SALT_ONEDIR_HARDEN unset first (legacy chown; extras
      at /opt/saltstack/salt/extras-<py>/, the 3006.x default).
    - Drop a marker file into the legacy extras dir.
    - Reinstall with SALT_ONEDIR_HARDEN=1 opt-in.
    - Assert the marker migrated into
      /var/lib/salt/<daemon>/extras-<py>/, the legacy dir was
      removed, and the new per-daemon extras dir is salt-owned.

    The migration is per-daemon; any single daemon's postinst that
    finds populated legacy extras AND an empty per-daemon extras will
    do the move. At least one daemon-side move must have happened for
    this test to pass.
    """
    installer, py_ver = install_harden_upgrade_migration

    # Marker should NOT be at the legacy location any more.
    legacy_marker = pathlib.Path(
        f"/opt/saltstack/salt/extras-{py_ver}/{LEGACY_EXTRAS_MARKER_NAME}"
    )
    assert not legacy_marker.exists(), (
        f"Legacy marker at {legacy_marker} should have been migrated "
        "away by the hardened postinst"
    )

    # It should be at one of the per-daemon extras dirs.
    per_daemon_locations = [
        pathlib.Path(f"/var/lib/salt/{d}/extras-{py_ver}/{LEGACY_EXTRAS_MARKER_NAME}")
        for d in DAEMONS
    ]
    migrated = [p for p in per_daemon_locations if p.exists()]
    assert migrated, (
        f"Expected {LEGACY_EXTRAS_MARKER_NAME} to be migrated into at "
        f"least one /var/lib/salt/<daemon>/extras-{py_ver}/ location; "
        f"none found. Checked: {[str(p) for p in per_daemon_locations]}"
    )

    # Marker content preserved verbatim.
    for marker_path in migrated:
        assert (
            marker_path.read_text(encoding="utf-8") == LEGACY_EXTRAS_MARKER_CONTENT
        ), f"Migrated marker at {marker_path} has wrong content"
        # And owned by the salt user, not root.
        assert marker_path.parent.owner() == "salt", (
            f"Migrated extras dir {marker_path.parent} should be "
            f"salt-owned; got {marker_path.parent.owner()!r}"
        )


def test_upgrade_migration_is_idempotent(install_harden_upgrade_migration):
    """
    Re-running the migration path is a no-op: the second time through,
    the legacy extras dir is either gone or empty, so nothing moves
    and nothing errors. We invoke the postinst-equivalent behavior by
    calling ``dpkg-reconfigure`` / ``rpm -q --scripts`` re-run and
    verifying idempotency at the filesystem level.

    Simpler and more robust approach: assert that after the first
    migration (which the fixture already performed), the per-daemon
    location still contains the marker AND the legacy dir does not
    contain a stale copy. If the migration ran twice we'd see the
    marker in the legacy dir get re-created + re-moved with mv
    complaining about existing dest.
    """
    installer, py_ver = install_harden_upgrade_migration

    # First migration ran in the fixture. Now simulate a second
    # postinst pass by triggering apt reinstall / yum reinstall on
    # the daemon whose extras dir received the marker.
    per_daemon_locations = [
        pathlib.Path(f"/var/lib/salt/{d}/extras-{py_ver}/{LEGACY_EXTRAS_MARKER_NAME}")
        for d in DAEMONS
    ]
    original_migrated = [p for p in per_daemon_locations if p.exists()]
    assert original_migrated, (
        "Migration fixture didn't produce a migrated marker; the "
        "upstream test_upgrade_migration_moves_legacy_extras case "
        "should fail first."
    )

    # Force a re-run of the postinst equivalent by reconfiguring or
    # reinstalling salt-common.
    if pathlib.Path("/usr/bin/apt-get").exists():
        env = os.environ.copy()
        env["DEBIAN_FRONTEND"] = "noninteractive"
        subprocess.run(
            ["dpkg-reconfigure", "salt-common", "salt-master"],
            check=False,
            env=env,
            capture_output=True,
            timeout=180,
        )
    elif pathlib.Path("/usr/bin/dnf").exists():
        subprocess.run(
            ["dnf", "reinstall", "-y", "salt-master"],
            check=False,
            capture_output=True,
            timeout=180,
        )

    # Marker still at migrated location.
    still_migrated = [p for p in per_daemon_locations if p.exists()]
    assert still_migrated == original_migrated, (
        f"Idempotency broken: marker set changed from "
        f"{[str(p) for p in original_migrated]} to "
        f"{[str(p) for p in still_migrated]} after re-run"
    )

    # And the legacy dir did not get resurrected with a stale marker.
    legacy_marker = pathlib.Path(
        f"/opt/saltstack/salt/extras-{py_ver}/{LEGACY_EXTRAS_MARKER_NAME}"
    )
    assert not legacy_marker.exists(), (
        f"Legacy marker at {legacy_marker} reappeared after " "idempotent re-run"
    )
