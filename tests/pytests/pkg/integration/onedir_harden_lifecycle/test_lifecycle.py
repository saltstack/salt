"""
Destructive-cycle package tests for the SALT_ONEDIR_HARDEN packaging
default (issue #70198).

These tests perform real install/uninstall lifecycles so they can
exercise the packaging behavior that a static fixture install can't:

- SALT_ONEDIR_HARDEN=0 escape hatch (legacy chown layout, deprecation
  warning surfaces)
- explicit SALT_HOME / SALT_EXTRAS_DIR overrides winning over the
  hardening default
- upgrade migration from a pre-populated legacy
  /opt/saltstack/salt/extras-<py>/ tree into
  /var/lib/salt/<daemon>/extras-<py>/
- upgrade idempotency (second postinst run is a no-op)

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
# Priority 1 -- SALT_ONEDIR_HARDEN=0 escape hatch
# ---------------------------------------------------------------------------


def test_harden_off_uses_legacy_chown_layout(install_harden_off):
    """
    With SALT_ONEDIR_HARDEN=0, /opt/saltstack/salt is chowned to the
    salt user (legacy behavior). Under the hardened default this dir
    would stay root:root; here we verify the opt-out actually reaches
    the packaging scriptlets.
    """
    tree = pathlib.Path("/opt/saltstack/salt")
    assert tree.exists()
    assert tree.owner() == "salt", (
        f"Under SALT_ONEDIR_HARDEN=0, /opt/saltstack/salt should be "
        f"salt-owned (legacy layout); got {tree.owner()!r}"
    )


def test_harden_off_deprecation_warning_surfaces(install_harden_off):
    """
    The postinst scriptlets emit a ``logger -t salt-<daemon>`` message
    when SALT_ONEDIR_HARDEN=0 is selected. Verify at least one such
    entry landed in the system log so operators actually see the
    deprecation notice.

    We check both the systemd journal (RPM + modern DEB) and
    /var/log/syslog / /var/log/messages (older DEB + non-systemd RPM)
    so this passes across the distro matrix.
    """
    needle = "SALT_ONEDIR_HARDEN=0"
    found = False

    # Try journalctl first (present on any systemd system).
    try:
        proc = subprocess.run(
            [
                "journalctl",
                "--no-pager",
                "-t",
                "salt-minion",
                "-t",
                "salt-master",
                "-t",
                "salt-syndic",
                "-t",
                "salt-api",
                "-t",
                "salt-cloud",
                "--since",
                "10 minutes ago",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if needle in proc.stdout:
            found = True
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    # Fall back to /var/log/{syslog,messages} for systemd-less hosts.
    if not found:
        for log_path in ("/var/log/syslog", "/var/log/messages"):
            path = pathlib.Path(log_path)
            if not path.exists() or not os.access(path, os.R_OK):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if needle in content:
                found = True
                break

    assert found, (
        "Expected a SALT_ONEDIR_HARDEN=0 deprecation notice from at "
        "least one salt-<daemon> postinst in journalctl / syslog / "
        "messages, but none was recorded."
    )


def test_harden_off_leaves_per_daemon_dirs_absent(install_harden_off):
    """
    Under the legacy layout, /var/lib/salt/<daemon>/ should NOT be
    created by any daemon's postinst -- that's the whole point of
    ``SALT_ONEDIR_HARDEN=0`` preserving the historical layout.

    /var/lib/salt itself is packaged via salt-common.dirs so its
    existence is not a signal; we assert on the per-daemon subdirs.
    """
    for daemon in DAEMONS:
        subdir = pathlib.Path(f"/var/lib/salt/{daemon}")
        assert not subdir.exists(), (
            f"Under SALT_ONEDIR_HARDEN=0 the per-daemon dir "
            f"/var/lib/salt/{daemon} should not exist, but it does"
        )


# ---------------------------------------------------------------------------
# Priority 1 -- SALT_ONEDIR_HARDEN unset behaves as =1 on 3009.0+
# ---------------------------------------------------------------------------


def test_harden_default_produces_hardened_layout(install_harden_default):
    """
    With SALT_ONEDIR_HARDEN completely unset (no env var, no override
    file), the packaging default on 3009.0 must produce the hardened
    layout. This is the "unset == 1" gate assertion.
    """
    tree = pathlib.Path("/opt/saltstack/salt")
    assert tree.exists()
    assert (
        tree.owner() == "root"
    ), f"With HARDEN unset, /opt/saltstack/salt should be root; got {tree.owner()!r}"

    master_dir = pathlib.Path("/var/lib/salt/master")
    assert master_dir.exists(), (
        "With HARDEN unset, /var/lib/salt/master should exist " "(default=1 on 3009.0)"
    )
    assert master_dir.owner() == "salt"


# ---------------------------------------------------------------------------
# Priority 4 -- explicit SALT_HOME / SALT_EXTRAS_DIR override precedence
# ---------------------------------------------------------------------------


def test_explicit_salt_home_wins_over_harden_default(install_harden_custom_home):
    """
    Explicit SALT_HOME in /etc/default/salt-setup wins over the
    HARDEN=1 default's per-daemon /var/lib/salt/<daemon>/home path.
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
    Explicit SALT_EXTRAS_DIR wins over the HARDEN=1 default's
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
    Simulated legacy-to-hardened upgrade path:

    - Install with SALT_ONEDIR_HARDEN=0 first (legacy chown; extras
      at /opt/saltstack/salt/extras-<py>/).
    - Drop a marker file into the legacy extras dir.
    - Reinstall with SALT_ONEDIR_HARDEN=1.
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
