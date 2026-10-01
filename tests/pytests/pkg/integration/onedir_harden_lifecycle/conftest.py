"""
Destructive-cycle fixtures for the SALT_ONEDIR_HARDEN packaging opt-in
tests (issue #70198).

On 3006.x the default is UNSET (legacy layout). These tests need a
fresh install/uninstall cycle per case so they can exercise:

- SALT_ONEDIR_HARDEN unset (default on 3006.x) = legacy chown layout
- SALT_ONEDIR_HARDEN=1 opt-in = hardened per-daemon layout
- explicit SALT_HOME / SALT_EXTRAS_DIR overrides winning over the
  hardened opt-in's per-daemon defaults
- upgrade migration from a pre-populated legacy /opt/saltstack/salt/
  extras-<py>/ tree into per-daemon /var/lib/salt/<daemon>/extras-<py>/
  when the operator opts in to hardening
- upgrade idempotency (re-running postinst with HARDEN=1 is a no-op)

The fixture stack mirrors ``tests/pytests/pkg/integration/config_overrides/``
which pioneered the pattern: skip the whole subtree during
--upgrade/--downgrade/--no-install passes (we manage our own install
lifecycle), spin up a function-scoped SaltPkgInstall, force-purge on
failure so a bad postinst doesn't cascade into the session-scoped
install_salt fixture.

Linux-package-only.
"""

import contextlib
import logging
import os
import pathlib
import shutil
import subprocess

import pytest
from pytestskipmarkers.utils import platform

from tests.support.pkg import SaltPkgInstall

log = logging.getLogger(__name__)


# Standard override-file locations. Same as the config_overrides suite.
DEB_OVERRIDE_FILE = pathlib.Path("/etc/default/salt-setup")
RPM_OVERRIDE_FILE = pathlib.Path("/etc/sysconfig/salt-minion-setup")

# Custom SALT_HOME / SALT_EXTRAS_DIR paths used to prove explicit
# overrides win over the SALT_ONEDIR_HARDEN=1 opt-in's per-daemon
# /var/lib/salt/<daemon>/{home,extras-<py>} paths.
CUSTOM_HOME = "/opt/custom-salt-home"
CUSTOM_EXTRAS = "/opt/custom-salt-extras"

# Marker written into /opt/saltstack/salt/extras-<py>/ before an
# upgrade so the migration test can verify contents moved.
LEGACY_EXTRAS_MARKER_NAME = ".onedir-harden-migration-marker"
LEGACY_EXTRAS_MARKER_CONTENT = "pre-upgrade payload"


SALT_PACKAGES = [
    "salt-api",
    "salt-cloud",
    "salt-common",
    "salt-dbg",
    "salt-debuginfo",
    "salt-master",
    "salt-minion",
    "salt-ssh",
    "salt-syndic",
    "salt",
]


def pytest_collection_modifyitems(config, items):
    """
    Skip destructive-cycle tests during pkg sessions that expect the
    session-scoped install_salt fixture to stay stable. Same rationale
    as config_overrides/conftest.py.
    """
    if not (
        config.getoption("--upgrade")
        or config.getoption("--downgrade")
        or config.getoption("--no-install")
    ):
        return
    conftest_dir = pathlib.Path(__file__).resolve().parent
    skip_marker = pytest.mark.skip(
        reason=(
            "onedir-harden lifecycle tests perform destructive install "
            "cycles; they only run during fresh-install passes."
        )
    )
    for item in items:
        try:
            item_path = pathlib.Path(str(item.fspath)).resolve()
        except (OSError, ValueError):
            continue
        if conftest_dir in item_path.parents:
            item.add_marker(skip_marker)


def _purge_salt_packages():
    """Force-purge every salt package. Idempotent.

    On RPM-based systems we ALSO invoke ``rpm -e --nodeps --allmatches``
    for any packages that survive the pkg-manager remove. This is
    load-bearing on Photon's ``tdnf`` shim: ``tdnf remove`` sometimes
    leaves rpmdb metadata behind for packages it just removed. On the
    next install, RPM then reports ``$1 > 1`` in scriptlets because it
    thinks the package is being upgraded, not freshly installed. That
    silently skips every ``if [ $1 -gt 1 ]; then :; else ... ; fi``
    fresh-install branch in ``%posttrans master/syndic/api/cloud``,
    which is where the legacy chown of ``/opt/saltstack/salt`` and the
    hardened ``install -d`` of ``/var/lib/salt/<daemon>/`` live.
    Symptom: ``test_hardening_unset_matches_legacy_default`` sees
    ``/opt/saltstack/salt`` still root-owned after a fresh HARDEN-unset
    install; ``test_upgrade_migration_moves_legacy_extras`` finds the
    hardened per-daemon dirs never got the migrated marker.
    """
    if shutil.which("apt-get") is not None:
        subprocess.run(
            ["dpkg", "--purge", "--force-all", *SALT_PACKAGES],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        env = os.environ.copy()
        env["DEBIAN_FRONTEND"] = "noninteractive"
        subprocess.run(
            ["apt-get", "purge", "-y", *SALT_PACKAGES],
            check=False,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["apt-get", "autoremove", "-y"],
            check=False,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    if shutil.which("dnf") is not None:
        subprocess.run(
            ["dnf", "remove", "-y", *SALT_PACKAGES],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    elif shutil.which("yum") is not None:
        subprocess.run(
            ["yum", "remove", "-y", *SALT_PACKAGES],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    # Belt-and-braces: force-drop any lingering rpmdb entries. tdnf on
    # Photon can leave the rpmdb saying $1 > 1 on the next install.
    if shutil.which("rpm") is not None:
        subprocess.run(
            [
                "rpm",
                "-e",
                "--nodeps",
                "--allmatches",
                "--noscripts",
                *SALT_PACKAGES,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _cleanup_filesystem_state():
    """Wipe override files, custom paths, and per-daemon dirs."""
    for path in (DEB_OVERRIDE_FILE, RPM_OVERRIDE_FILE):
        if path.exists():
            with contextlib.suppress(OSError):
                path.unlink()
    _purge_salt_packages()
    subprocess.run(
        ["userdel", "-f", "salt"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["groupdel", "salt"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Tear down every per-daemon dir + custom override targets so the
    # next case starts clean.
    for target in (
        CUSTOM_HOME,
        CUSTOM_EXTRAS,
        "/var/lib/salt",
    ):
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
    # Wipe debconf db so a fresh install re-prompts.
    if shutil.which("debconf-communicate") is not None:
        for key in (
            "salt-master/user",
            "salt-minion/user",
            "salt-api/user",
            "salt-syndic/user",
        ):
            try:
                subprocess.run(
                    ["debconf-communicate"],
                    input=f"PURGE {key}\n",
                    text=True,
                    check=False,
                    timeout=5,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except (subprocess.SubprocessError, OSError):
                pass


@pytest.fixture
def cleanup_harden_state():
    """Clean-up envelope around a destructive install cycle."""
    _cleanup_filesystem_state()
    try:
        yield
    finally:
        _cleanup_filesystem_state()


def _install_with(env, request, salt_factories_root_dir):
    """
    Shared helper: perform a fresh install with the given install_env,
    force-purging on any preinst/postinst failure so subsequent tests
    inherit a clean dpkg/rpm state.
    """
    if platform.is_windows():
        conf_dir = "c:/salt/etc/salt"
    else:
        conf_dir = salt_factories_root_dir / "etc" / "salt"
    installer = SaltPkgInstall(
        conf_dir=conf_dir,
        pkg_system_service=request.config.getoption("--pkg-system-service"),
        upgrade=False,
        downgrade=False,
        no_uninstall=False,
        no_install=False,
        prev_version=request.config.getoption("prev_version"),
        use_prev_version=request.config.getoption("use_prev_version"),
        install_env=env,
    )
    try:
        with contextlib.ExitStack() as stack:
            try:
                stack.enter_context(installer)
            except BaseException:
                _purge_salt_packages()
                raise
            installer.no_uninstall = False
            yield installer
    finally:
        _purge_salt_packages()


@pytest.fixture
def install_harden_default(cleanup_harden_state, request, salt_factories_root_dir):
    """
    Fresh install with SALT_ONEDIR_HARDEN completely unset. Verifies
    the built-in default on 3006.x (legacy chown layout preserved). No
    override file is created and no env var is exported.
    """
    yield from _install_with({}, request, salt_factories_root_dir)


@pytest.fixture
def install_harden_on(cleanup_harden_state, request, salt_factories_root_dir):
    """
    Fresh install with SALT_ONEDIR_HARDEN=1 in the DEB override file
    and exported to the RPM package-manager env (RPM scriptlets don't
    inherit env from yum, so the file channel is what actually reaches
    the RPM %pre / %posttrans). Verifies the hardened per-daemon
    layout opt-in on 3006.x.
    """
    DEB_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEB_OVERRIDE_FILE.write_text("SALT_ONEDIR_HARDEN=1\n", encoding="utf-8")
    RPM_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    RPM_OVERRIDE_FILE.write_text("SALT_ONEDIR_HARDEN=1\n", encoding="utf-8")
    yield from _install_with(
        {"SALT_ONEDIR_HARDEN": "1"}, request, salt_factories_root_dir
    )


@pytest.fixture
def install_harden_custom_home(cleanup_harden_state, request, salt_factories_root_dir):
    """
    Fresh install with SALT_ONEDIR_HARDEN=1 (opt-in) AND an explicit
    SALT_HOME override. Proves the explicit override wins over the
    hardened opt-in's per-daemon /var/lib/salt/<daemon>/home path.
    """
    DEB_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEB_OVERRIDE_FILE.write_text(
        f"SALT_ONEDIR_HARDEN=1\nSALT_HOME={CUSTOM_HOME}\n", encoding="utf-8"
    )
    RPM_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    RPM_OVERRIDE_FILE.write_text(
        f"SALT_ONEDIR_HARDEN=1\nSALT_HOME={CUSTOM_HOME}\n", encoding="utf-8"
    )
    yield from _install_with(
        {"SALT_ONEDIR_HARDEN": "1", "SALT_HOME": CUSTOM_HOME},
        request,
        salt_factories_root_dir,
    )


@pytest.fixture
def install_harden_custom_extras(
    cleanup_harden_state, request, salt_factories_root_dir
):
    """
    Fresh install with SALT_ONEDIR_HARDEN=1 (opt-in) AND an explicit
    SALT_EXTRAS_DIR override. Proves the explicit override wins over
    the hardened opt-in's per-daemon
    /var/lib/salt/<daemon>/extras-<py> path.
    """
    DEB_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEB_OVERRIDE_FILE.write_text(
        f"SALT_ONEDIR_HARDEN=1\nSALT_EXTRAS_DIR={CUSTOM_EXTRAS}\n", encoding="utf-8"
    )
    RPM_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    RPM_OVERRIDE_FILE.write_text(
        f"SALT_ONEDIR_HARDEN=1\nSALT_EXTRAS_DIR={CUSTOM_EXTRAS}\n", encoding="utf-8"
    )
    yield from _install_with(
        {"SALT_ONEDIR_HARDEN": "1", "SALT_EXTRAS_DIR": CUSTOM_EXTRAS},
        request,
        salt_factories_root_dir,
    )


def _populate_legacy_extras(py_ver, marker_content=LEGACY_EXTRAS_MARKER_CONTENT):
    """
    Pre-populate /opt/saltstack/salt/extras-<py>/ with a marker file so
    the upgrade-migration test can verify contents moved into the
    per-daemon location. Called after the first (legacy) install and
    before the SALT_ONEDIR_HARDEN=1 postinst re-run.

    The extras-<py> directory has to be world-writable-then-chowned
    before the marker is written because /opt/saltstack/salt is
    root-owned in hardened installs. We're operating between installs
    so we own the whole tree.
    """
    extras_dir = pathlib.Path(f"/opt/saltstack/salt/extras-{py_ver}")
    extras_dir.mkdir(parents=True, exist_ok=True)
    marker = extras_dir / LEGACY_EXTRAS_MARKER_NAME
    marker.write_text(marker_content, encoding="utf-8")
    return marker


def _reinstall_salt_packages(pkg_paths, install_env):
    """
    In-place reinstall of the salt packages, keeping the on-disk
    /opt/saltstack/salt/ tree intact between transactions so an
    untracked marker file placed under /opt/saltstack/salt/extras-<py>/
    survives to the second %posttrans run. This is the reliable way to
    exercise the legacy-to-hardened %posttrans migration path on
    Photon's tdnf, where a full purge + fresh install would let tdnf
    remove /opt/saltstack/salt/ between the two installs and take the
    marker with it.

    Uses ``rpm --reinstall <pkg-paths>`` on RPM distros and
    ``apt-get install --reinstall`` on DEB. Env vars are passed via
    both process env AND the sysconfig/setup file (RPM scriptlets
    don't inherit env from yum/dnf/tdnf; DEB scripts do).
    """
    env = os.environ.copy()
    env.update(install_env)
    if shutil.which("apt-get") is not None:
        env["DEBIAN_FRONTEND"] = "noninteractive"
        subprocess.run(
            [
                "apt-get",
                "install",
                "--reinstall",
                "-y",
                "-o",
                "DPkg::Options::=--force-confdef",
                "-o",
                "DPkg::Options::=--force-confold",
                *pkg_paths,
            ],
            check=True,
            env=env,
        )
        return
    # RPM: ``rpm --reinstall`` re-runs %pre/%post/%posttrans for each
    # package while leaving untracked files under packaged directories
    # in place -- exactly the state we need to exercise the migration
    # block. ``--nodigest --nosignature`` mirrors the ``--nogpgcheck``
    # tdnf install flag used by SaltPkgInstall on Photon for the
    # unsigned nightly ``3006.27+NNN.gSHA`` artifacts.
    subprocess.run(
        [
            "rpm",
            "--reinstall",
            "--nodigest",
            "--nosignature",
            *pkg_paths,
        ],
        check=True,
        env=env,
    )


@pytest.fixture
def install_harden_upgrade_migration(
    cleanup_harden_state, request, salt_factories_root_dir
):
    """
    Simulate the legacy-to-hardened upgrade path on 3006.x:

    1. Install with SALT_ONEDIR_HARDEN unset (legacy layout, 3006.x
       default).
    2. Drop a marker file into /opt/saltstack/salt/extras-<py>/.
    3. Write SALT_ONEDIR_HARDEN=1 into the sysconfig/default setup
       file so the next %posttrans / postinst picks up the opt-in.
    4. Reinstall in place -- reruns %posttrans without wiping
       /opt/saltstack/salt/, so the untracked marker file survives to
       the migration block. This is the failure mode on Photon 4/5
       when the previous fixture design (purge + fresh install) let
       tdnf clean the marker between installs.
    5. Yield the installer so the test can assert the marker moved to
       /var/lib/salt/<daemon>/extras-<py>/ and the legacy dir was
       cleaned up.
    """
    if platform.is_windows():
        conf_dir = "c:/salt/etc/salt"
    else:
        conf_dir = salt_factories_root_dir / "etc" / "salt"

    # Step 1: legacy install (HARDEN unset on 3006.x = legacy default).
    legacy_installer = SaltPkgInstall(
        conf_dir=conf_dir,
        pkg_system_service=request.config.getoption("--pkg-system-service"),
        upgrade=False,
        downgrade=False,
        no_uninstall=False,
        no_install=False,
        prev_version=request.config.getoption("prev_version"),
        use_prev_version=request.config.getoption("use_prev_version"),
        install_env={},
    )
    try:
        with contextlib.ExitStack() as stack:
            try:
                stack.enter_context(legacy_installer)
            except BaseException:
                _purge_salt_packages()
                raise
            py_ver = legacy_installer.package_python_version()

            # Step 2: populate the legacy extras dir with a marker.
            marker = _populate_legacy_extras(py_ver)
            assert marker.exists()

            # Step 3: write HARDEN=1 to the override file so the
            # scriptlets pick it up (RPM scriptlets don't inherit env
            # from yum/dnf/tdnf; the file channel is what actually
            # reaches %pre / %posttrans).
            DEB_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
            DEB_OVERRIDE_FILE.write_text("SALT_ONEDIR_HARDEN=1\n", encoding="utf-8")
            RPM_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
            RPM_OVERRIDE_FILE.write_text("SALT_ONEDIR_HARDEN=1\n", encoding="utf-8")

            # Step 4: in-place reinstall keeps /opt/saltstack/salt/
            # intact between transactions so the untracked marker file
            # survives to the migration block's ls -A check.
            _reinstall_salt_packages(
                legacy_installer.pkgs,
                {"SALT_ONEDIR_HARDEN": "1"},
            )

            yield legacy_installer, py_ver
    finally:
        _purge_salt_packages()
