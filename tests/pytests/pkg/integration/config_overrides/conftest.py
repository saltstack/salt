"""
Fixtures for the config-override package tests (issue #69402).

These tests exercise the writable-dir override knobs (SALT_USER,
SALT_GROUP, SALT_HOME, SALT_EXTRAS_DIR) wired into the Linux DEB and
RPM packaging. Each parameterization performs a fresh install with a
specific override mechanism (env vars exported to the package manager,
or a pre-created config file at the DEB or RPM standard location) and
asserts the salt user / home / extras dir landed where requested.

The fixtures here are deliberately function-scoped so each test gets
a clean install/uninstall cycle. They intentionally do *not* depend
on the session-scoped ``install_salt`` fixture from the parent
``tests/pytests/pkg/conftest.py`` — that fixture installs the package
once per session with no overrides, which is the opposite of what we
need.
"""

import logging
import os
import pathlib
import shutil
import subprocess

import pytest
from pytestskipmarkers.utils import platform

from tests.support.pkg import SaltPkgInstall

log = logging.getLogger(__name__)


# Override values used across all override tests. Chosen to be obviously
# non-default so a failure to apply them is loud.
ALT_USER = "alt_salt"
ALT_GROUP = "alt_salt"
ALT_HOME = "/var/lib/alt_salt"
ALT_EXTRAS = "/opt/alt-extras"

# Standard locations of the override config files.
DEB_OVERRIDE_FILE = pathlib.Path("/etc/default/salt-setup")
RPM_OVERRIDE_FILE = pathlib.Path("/etc/sysconfig/salt-minion-setup")

OVERRIDE_CONTENT = (
    f"SALT_USER={ALT_USER}\n"
    f"SALT_GROUP={ALT_GROUP}\n"
    f"SALT_HOME={ALT_HOME}\n"
    f"SALT_EXTRAS_DIR={ALT_EXTRAS}\n"
)


def _cleanup_filesystem_state():
    """
    Best-effort teardown helper. Removes the override config files and
    any alt_salt user/group/home/extras dir that a test may have left
    behind. Idempotent — safe to call even when the test never got far
    enough to create those resources.
    """
    for path in (DEB_OVERRIDE_FILE, RPM_OVERRIDE_FILE):
        if path.exists():
            try:
                path.unlink()
            except OSError as exc:
                log.warning("Could not remove %s: %s", path, exc)
    # Remove user (and its primary group) created by the package install.
    subprocess.run(
        ["userdel", "-f", ALT_USER],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["groupdel", ALT_GROUP],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for target in (ALT_HOME, ALT_EXTRAS):
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)


@pytest.fixture
def cleanup_override_state():
    """
    Wrap a test in a clean-up envelope so neither stale config files nor
    a half-created alt_salt user leak from one parameterized case into
    the next.
    """
    _cleanup_filesystem_state()
    try:
        yield
    finally:
        _cleanup_filesystem_state()


@pytest.fixture
def deb_override_file(cleanup_override_state):
    """
    Pre-create /etc/default/salt-setup with the alt_salt overrides.
    Yields the path so the test can re-read or extend it if needed.
    """
    DEB_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEB_OVERRIDE_FILE.write_text(OVERRIDE_CONTENT, encoding="utf-8")
    yield DEB_OVERRIDE_FILE


@pytest.fixture
def rpm_override_file(cleanup_override_state):
    """
    Pre-create /etc/sysconfig/salt-minion-setup with the alt_salt
    overrides. Yields the path.
    """
    RPM_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    RPM_OVERRIDE_FILE.write_text(OVERRIDE_CONTENT, encoding="utf-8")
    yield RPM_OVERRIDE_FILE


@pytest.fixture
def env_overrides(cleanup_override_state):
    """
    Yield the dict of env vars to pass to the package manager. No
    config file is pre-created — env vars are the only override channel.
    """
    yield {
        "SALT_USER": ALT_USER,
        "SALT_GROUP": ALT_GROUP,
        "SALT_HOME": ALT_HOME,
        "SALT_EXTRAS_DIR": ALT_EXTRAS,
    }


@pytest.fixture
def no_overrides(cleanup_override_state):
    """
    Baseline: no env vars, no config file. The package install must
    fall back to the historical hardcoded defaults (salt:salt user,
    /opt/saltstack/salt home, find-discovered extras dir).
    """
    yield {}


def _install_salt_with(install_env, salt_factories_root_dir, request):
    """
    Spin up a function-scoped SaltPkgInstall, run install() with the
    given env, and yield the installer. Tear down with uninstall().
    Mirrors the parent-conftest install_salt fixture's parameter
    plumbing.
    """
    if platform.is_windows():
        conf_dir = "c:/salt/etc/salt"
    else:
        conf_dir = salt_factories_root_dir / "etc" / "salt"
    with SaltPkgInstall(
        conf_dir=conf_dir,
        pkg_system_service=request.config.getoption("--pkg-system-service"),
        upgrade=False,
        downgrade=False,
        no_uninstall=False,
        no_install=False,
        prev_version=request.config.getoption("prev_version"),
        use_prev_version=request.config.getoption("use_prev_version"),
        install_env=install_env,
    ) as fixture:
        # The context-manager __enter__ ran install() with the chosen
        # env already (because no_install=False and upgrade=False).
        # Force un-install on exit so the next parameterization sees a
        # clean slate.
        fixture.no_uninstall = False
        yield fixture


@pytest.fixture
def install_salt_env(request, salt_factories_root_dir, env_overrides):
    """
    Install fresh with env vars (no override config file).
    """
    yield from _install_salt_with(env_overrides, salt_factories_root_dir, request)


@pytest.fixture
def install_salt_deb_file(request, salt_factories_root_dir, deb_override_file):
    """
    Install fresh with /etc/default/salt-setup pre-created. No env
    vars are exported to the package manager — the file is the sole
    override channel.
    """
    yield from _install_salt_with({}, salt_factories_root_dir, request)


@pytest.fixture
def install_salt_rpm_file(request, salt_factories_root_dir, rpm_override_file):
    """
    Install fresh with /etc/sysconfig/salt-minion-setup pre-created.
    No env vars are exported.
    """
    yield from _install_salt_with({}, salt_factories_root_dir, request)


@pytest.fixture
def install_salt_default(request, salt_factories_root_dir, no_overrides):
    """
    Baseline install with no overrides of any kind. Asserts the
    pre-existing default behavior is preserved.
    """
    yield from _install_salt_with({}, salt_factories_root_dir, request)
