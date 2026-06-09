"""
Package-level integration tests for the salt user / home / extras-dir
override knobs added in issue #69402.

These tests install a freshly built Salt package against a real DEB or
RPM system and verify that the four override channels each route the
configuration through to the installed system:

1. ``/etc/default/salt-setup`` — DEB-conventional override file.
2. ``/etc/sysconfig/salt-minion-setup`` — RPM-conventional override
   file (also honored on DEB for cross-distro parity).
3. ``SALT_USER`` / ``SALT_GROUP`` / ``SALT_HOME`` / ``SALT_EXTRAS_DIR``
   exported in the environment of the package manager invocation.
4. None of the above — baseline. Confirms the historical defaults
   (``salt:salt`` user, ``/opt/saltstack/salt`` home, find-discovered
   extras dir) still work when nobody overrides anything.

Each parameterization performs a fresh ``apt install`` / ``yum install``
cycle and asserts the resulting passwd / group / filesystem state
matches the override that was supplied. The cleanup envelope
(``cleanup_override_state``) removes any override file, the alt_salt
user, and ``/var/lib/alt_salt`` / ``/opt/alt-extras`` between tests.
"""

import grp
import logging
import os
import pathlib
import pwd

import pytest

from tests.pytests.pkg.integration.config_overrides.conftest import (
    ALT_EXTRAS,
    ALT_GROUP,
    ALT_HOME,
    ALT_USER,
)

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_unless_on_linux(reason="Linux DEB/RPM packaging only"),
]


def _getent_passwd(user):
    """
    Return the passwd entry tuple for ``user``, or ``None`` if missing.
    """
    try:
        return pwd.getpwnam(user)
    except KeyError:
        return None


def _resolved_extras_dir(install_salt):
    """
    Resolve the version-suffixed extras dir under ``ALT_EXTRAS`` if the
    package install honored the relocation override. The installer may
    create the parent ``ALT_EXTRAS`` itself and drop the ``extras-X.Y``
    layout underneath, or chown the parent and let the existing
    ``/opt/saltstack/salt/extras-X.Y`` keep its old location while the
    parent is owned by alt_salt. Both shapes are acceptable; the
    contract is "the directory the override pointed at is owned by the
    override user."
    """
    py_ver = install_salt.package_python_version()
    candidates = [
        pathlib.Path(ALT_EXTRAS),
        pathlib.Path(ALT_EXTRAS) / f"extras-{py_ver}",
        pathlib.Path("/opt/saltstack/salt") / f"extras-{py_ver}",
    ]
    return [p for p in candidates if p.exists()]


def _assert_alt_salt_passwd(home_should_be):
    """
    Common assertion block for every override case. Confirms the
    alt_salt user landed in /etc/passwd with the right home dir and
    is a member of the alt_salt group.
    """
    entry = _getent_passwd(ALT_USER)
    assert (
        entry is not None
    ), f"Expected user {ALT_USER!r} to be created by the package install"
    assert entry.pw_dir == home_should_be, (
        f"Expected {ALT_USER}'s home to be {home_should_be!r}, " f"got {entry.pw_dir!r}"
    )
    # Group membership: gid resolves to a group whose name is ALT_GROUP.
    primary = grp.getgrgid(entry.pw_gid)
    assert primary.gr_name == ALT_GROUP, (
        f"Expected primary group of {ALT_USER} to be {ALT_GROUP!r}, "
        f"got {primary.gr_name!r}"
    )


def _assert_extras_dir_owned_by_alt_salt(install_salt):
    """
    Confirm SALT_EXTRAS_DIR was honored: the relocated extras tree
    exists and at least one node in it is owned by alt_salt.
    """
    found = _resolved_extras_dir(install_salt)
    assert any(
        p.exists() for p in found
    ), f"None of the expected extras-dir paths exist: {found!r}"
    for path in found:
        if str(path).startswith(ALT_EXTRAS):
            # The relocated path; ownership must match the override.
            assert path.owner() == ALT_USER, (
                f"Expected {path} to be owned by {ALT_USER}, " f"got {path.owner()}"
            )
            return
    pytest.fail(
        f"No path under {ALT_EXTRAS} was found; the SALT_EXTRAS_DIR "
        f"override was not honored. Candidates: {found!r}"
    )


def _is_deb(install_salt):
    return install_salt.distro_id in ("ubuntu", "debian")


def test_env_var_overrides(install_salt_env):
    """
    Export SALT_USER / SALT_GROUP / SALT_HOME / SALT_EXTRAS_DIR in the
    package-manager invocation environment (no config file). The
    package's preinst must consume them and create the alt_salt user
    with the alt home and chown the alt extras dir accordingly.
    """
    _assert_alt_salt_passwd(home_should_be=ALT_HOME)
    _assert_extras_dir_owned_by_alt_salt(install_salt_env)


def test_deb_default_file_override(install_salt_deb_file):
    """
    Pre-create /etc/default/salt-setup with the alt_salt overrides.
    The DEB preinst must source the file before applying its SALT_*
    defaults, producing the same alt_salt result as the env-var path.

    Skipped on RPM systems — /etc/default/ is not the RPM convention.
    On RPM, the equivalent test_rpm_sysconfig_file_override case
    covers the parallel mechanism.
    """
    if not _is_deb(install_salt_deb_file):
        pytest.skip("/etc/default/salt-setup is the DEB-side override convention")
    _assert_alt_salt_passwd(home_should_be=ALT_HOME)
    _assert_extras_dir_owned_by_alt_salt(install_salt_deb_file)


def test_rpm_sysconfig_file_override(install_salt_rpm_file):
    """
    Pre-create /etc/sysconfig/salt-minion-setup with the alt_salt
    overrides. RPM's %pre and %post minion scriptlets source this file
    natively; the DEB preinst scripts source it too (for cross-distro
    parity, since this PR), so the same test exercises both stacks.
    """
    _assert_alt_salt_passwd(home_should_be=ALT_HOME)
    _assert_extras_dir_owned_by_alt_salt(install_salt_rpm_file)


def test_default_no_overrides(install_salt_default):
    """
    Baseline: with no env vars and no override file, the package
    install must fall back to the long-standing defaults — ``salt``
    user, ``/opt/saltstack/salt`` (or whatever the spec/preinst sets
    SALT_HOME to by default), and the find-discovered extras dir.
    The alt_salt user must NOT exist.
    """
    assert (
        _getent_passwd(ALT_USER) is None
    ), f"Baseline install must not create the override user {ALT_USER}"
    # The default salt user must still exist.
    default = _getent_passwd("salt")
    assert (
        default is not None
    ), "Baseline install must still create the default 'salt' user"
    # And the relocated extras dir must NOT exist — that's an
    # override-only artifact.
    assert not os.path.isdir(
        ALT_EXTRAS
    ), f"Baseline install must not create the override extras dir {ALT_EXTRAS}"
    # The historical extras-X.Y under /opt/saltstack/salt must still be
    # present (when an extras dir exists at all).
    py_ver = install_salt_default.package_python_version()
    default_extras = pathlib.Path(f"/opt/saltstack/salt/extras-{py_ver}")
    if default_extras.exists():
        # When the default extras dir exists it must be owned by the
        # default salt user (not alt_salt, which isn't even created).
        assert default_extras.owner() == "salt", (
            f"Default extras dir {default_extras} owned by "
            f"{default_extras.owner()}, expected salt"
        )
