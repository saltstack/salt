# -*- coding: utf-8 -*-
'''
tests for pkg state
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import glob
import time
from collections import namedtuple

# Import Salt libs
import salt.utils.path
import salt.utils.pkg.rpm

# Import 3rd-party libs
import pytest
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

log = logging.getLogger(__name__)

Package = namedtuple('Package', ['name', 'version'])
PackageCap = namedtuple('PackageCap', ['cap', 'realpkg'])


@pytest.fixture(scope='module', autouse=True)
def pkgmgr_avail(sminion):
    '''
    Skip tests if the package manager is not available for use
    '''
    def proc_fd_lsof(path):
        '''
        Return True if any entry in /proc/locks points to path.  Example data:

        .. code-block:: bash

            # cat /proc/locks
            1: FLOCK  ADVISORY  WRITE 596 00:0f:10703 0 EOF
            2: FLOCK  ADVISORY  WRITE 14590 00:0f:11282 0 EOF
            3: POSIX  ADVISORY  WRITE 653 00:0f:11422 0 EOF
        '''
        # https://www.centos.org/docs/5/html/5.2/Deployment_Guide/s2-proc-locks.html
        locks = sminion.functions.cmd.run(['cat', '/proc/locks']).splitlines()
        for line in locks:
            fields = line.split()
            try:
                _, _, inode = fields[5].split(':')
                inode = int(inode)
            except (IndexError, ValueError):
                pytest.skip('Failed to parse inode info from fields: {}'.format(fields))

            for fd in glob.glob('/proc/*/fd'):
                fd_path = os.path.realpath(fd)
                # If the paths match and the inode is locked
                if fd_path == path and os.stat(fd_path).st_ino == inode:
                    return True

    def get_lock(path):
        '''
        Return True if any locks are found for path
        '''
        # Try lsof if it's available
        lock = False
        if salt.utils.path.which('lsof'):
            lock = sminion.functions.cmd.run(['lsof', path])
        elif sminion.opts['grains'] == 'Arch':
            lock = os.path.isfile(path)
        elif sminion.opts['grains'].get('kernel') == 'Linux':
            # Try to find any locks on path from /proc/locks
            lock = proc_fd_lsof(path)
        return True if lock else False

    locks = []
    os_family = sminion.opts['grains'].get('os_family', '')
    if 'Debian' in os_family:
        locks.append('/var/lib/apt/lists/lock')
    elif os_family == 'Arch':
        locks.append('/var/lib/pacman/db.lck')
    if locks:
        for path in locks:
            for idx in range(13):
                if idx == 12:
                    pytest.skip('Package database locked after 60 seconds, bailing out')
                if get_lock(path):
                    time.sleep(5)
                    continue
                else:
                    break

    # Last but not least, make sure the package index is up to date
    sminion.functions.pkg.refresh_db()


@pytest.fixture(scope='module')
def _pkg_targets(sminion):
    _pkg_targets_mapping = {
        'Arch': ['sl', 'libpng'],
        'Debian': ['python-plist', 'apg'],
        'RedHat': ['units', 'zsh-html'],
        'FreeBSD': ['aalib', 'pth'],
        'Suse': ['aalib', 'htop'],
        'MacOS': ['libpng', 'jpeg'],
        'Windows': ['putty', '7zip'],
    }
    os_family = sminion.opts['grains'].get('os_family', '')
    _pkg_targets = _pkg_targets_mapping.get(os_family, [])

    # Make sure that we have targets that match the os_family. If this
    # fails then the _PKG_TARGETS dict above needs to have an entry added,
    # with two packages that are not installed before these tests are run
    if not _pkg_targets:
        pytest.fail('Could not find pkg_targets for os_family=\'{}\''.format(os_family))
    return _pkg_targets


@pytest.fixture(scope='module')
def pkg_targets(sminion, _pkg_targets):
    _targets = []
    for target in _pkg_targets:
        log.warning('Processing target %r', target)
        version = sminion.functions.pkg.latest_version(target)
        if not version:
            # The package might be installed
            version = sminion.functions.pkg.version(target)
            if version:
                # Be sure to uninstall it
                sminion.functions.pkg.remove(name=target)
        log.warning('Processing target %r. Version: %s', target, version)
        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to not be installed before we run the states below
        assert version
        _targets.append(Package(name=target, version=version))
    yield _targets
    # Always uninstall packages
    sminion.functions.pkg.remove(pkgs=[target.name for target in _targets])


@pytest.fixture(scope='module')
def pkg_target_1(sminion, _pkg_targets):
    target = _pkg_targets[0]
    version = sminion.functions.pkg.latest_version(target)
    if not version:
        # The package might be installed
        version = sminion.functions.pkg.version(target)
        if version:
            # Be sure to uninstall it
            sminion.functions.pkg.remove(name=target)
    log.warning('Processing target %r. Version: %s', target, version)
    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so this package
    # needs to not be installed before we run the states below
    assert version
    yield Package(name=target, version=version)
    # Always uninstall packages
    sminion.functions.pkg.remove(name=target)


@pytest.mark.destructive_test
def test_pkg_001_installed(states, pkg_target_1):
    '''
    This is a destructive test as it installs and then removes a package
    '''
    ret = states.pkg.installed(name=pkg_target_1.name, refresh=False)
    assert ret.result is True


@pytest.mark.skipif('grains["os_family"] == "FreeBSD"',
                    reason='Version specification not supported on FreeBSD')
@pytest.mark.destructive_test
def test_pkg_002_installed_with_version(states, pkg_target_1):
    '''
    This is a destructive test as it installs and then removes a package
    '''
    ret = states.pkg.installed(name=pkg_target_1.name,
                               version=pkg_target_1.version,
                               refresh=False)
    assert ret.result is True


@pytest.mark.destructive_test
def test_pkg_003_installed_multipkg(states, pkg_targets):
    '''
    This is a destructive test as it installs and then removes two packages
    '''
    ret = states.pkg.installed(name=None,
                               pkgs=[target.name for target in pkg_targets],
                               refresh=False)
    assert ret.result is True


@pytest.mark.skipif('grains["os_family"] == "FreeBSD"',
                    reason='Version specification not supported on FreeBSD')
@pytest.mark.skipif('grains["os_family"] == "Suse"',
                    reason='Don\'t run on Suse')
@pytest.mark.destructive_test
def test_pkg_004_installed_multipkg_with_version(states, pkg_targets):
    '''
    This is a destructive test as it installs and then removes two packages
    '''
    pkgs = [{pkg_targets[0].name: pkg_targets[0].version}, pkg_targets[1].name]

    ret = states.pkg.installed(name=None, pkgs=pkgs, refresh=False)
    assert ret.result is True


@pytest.fixture(scope='module')
def pkg_32_target(sminion):
    _pkg_targets_mapping = {
        'CentOS': 'xz-devel.i686'
    }
    os_name = sminion.opts['grains'].get('os', '')
    target = _pkg_targets_mapping.get(os_name, '')
    if not target:
        pytest.skip('Test not applicable for OS {osfinger}'.format(**sminion.opts['grains']))

    log.warning('Processing target %r', target)
    version = sminion.functions.pkg.latest_version(target)
    if not version:
        # The package might be installed
        version = sminion.functions.pkg.version(target)
        if version:
            # Be sure to uninstall it
            sminion.functions.pkg.remove(name=target)
    log.warning('Processing target %r. Version: %s', target, version)
    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so this package
    # needs to not be installed before we run the states below
    assert version
    yield Package(name=target, version=version)
    # Always uninstall packages
    sminion.functions.pkg.remove(name=target)


@pytest.mark.destructive_test
def test_pkg_005_installed_32bit(states, pkg_32_target):
    '''
    This is a destructive test as it installs and then removes a package
    '''
    ret = states.pkg.installed(name=pkg_32_target.name, refresh=False)
    assert ret.result is True


@pytest.mark.destructive_test
def test_pkg_006_installed_32bit_with_version(states, pkg_32_target):
    '''
    This is a destructive test as it installs and then removes a package
    '''
    ret = states.pkg.installed(name=pkg_32_target.name, version=pkg_32_target.version, refresh=False)
    assert ret.result is True


@pytest.fixture(scope='module')
def pkg_dot_target(sminion):
    # Test packages with dot in pkg name
    # (https://github.com/saltstack/salt/issues/8614)
    _pkg_targets_mapping = {
        'RedHat': {'5': 'python-migrate0.5',
                   '6': 'tomcat6-el-2.1-api',
                   '7': 'tomcat-el-2.2-api'}
    }
    os_family = sminion.opts['grains'].get('os_family', '')
    if not os_family:
        pytest.skip('Test not applicable for OS {osfinger}'.format(**sminion.opts['grains']))
    os_versions = _pkg_targets_mapping.get(os_family, {})
    osmajorrelease = sminion.opts['grains']['osmajorrelease']
    target = os_versions.get(osmajorrelease)
    if not target:
        pytest.skip('Test not applicable for OS {osfinger}'.format(**sminion.opts['grains']))

    log.warning('Processing target %r', target)
    version = sminion.functions.pkg.latest_version(target)
    if not version:
        # The package might be installed
        version = sminion.functions.pkg.version(target)
        if version:
            # Be sure to uninstall it
            sminion.functions.pkg.remove(name=target)
    log.warning('Processing target %r. Version: %s', target, version)
    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so this package
    # needs to not be installed before we run the states below
    assert version
    yield Package(name=target, version=version)
    # Always uninstall packages
    sminion.functions.pkg.remove(name=target)


@pytest.mark.destructive_test
def test_pkg_007_with_dot_in_pkgname(states, pkg_dot_target):
    '''
    This tests for the regression found in the following issue:
    https://github.com/saltstack/salt/issues/8614

    This is a destructive test as it installs a package
    '''
    ret = states.pkg.installed(name=pkg_dot_target.name, refresh=False)
    assert ret.result is True


@pytest.fixture(scope='module')
def pkg_epoch_target(sminion):
    # Test packages with dot in pkg name
    # (https://github.com/saltstack/salt/issues/8614)
    _pkg_targets_mapping = {
        'RedHat': {'7': 'comps-extras'},
    }
    os_family = sminion.opts['grains'].get('os_family', '')
    if not os_family:
        pytest.skip('Test not applicable for OS {osfinger}'.format(**sminion.opts['grains']))
    os_versions = _pkg_targets_mapping.get(os_family, {})
    osmajorrelease = sminion.opts['grains']['osmajorrelease']
    target = os_versions.get(osmajorrelease)
    if not target:
        pytest.skip('Test not applicable for OS {osfinger}'.format(**sminion.opts['grains']))

    log.warning('Processing target %r', target)
    version = sminion.functions.pkg.latest_version(target)
    if not version:
        # The package might be installed
        version = sminion.functions.pkg.version(target)
        if version:
            # Be sure to uninstall it
            sminion.functions.pkg.remove(name=target)
    log.warning('Processing target %r. Version: %s', target, version)
    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so this package
    # needs to not be installed before we run the states below
    assert version
    yield Package(name=target, version=version)
    # Always uninstall packages
    sminion.functions.pkg.remove(name=target)


@pytest.mark.destructive_test
def test_pkg_008_epoch_in_version(states, pkg_epoch_target):
    '''
    This tests for the regression found in the following issue:
    https://github.com/saltstack/salt/issues/8614

    This is a destructive test as it installs a package
    '''
    ret = states.pkg.installed(name=pkg_epoch_target.name, version=pkg_epoch_target.version, refresh=False)
    assert ret.result is True


@pytest.fixture(scope='module')
def _pkg_latest_epoch_target(sminion):
    target = 'bash-completion'
    log.warning('Processing target %r', target)
    version = sminion.functions.pkg.latest_version(target)
    if not version:
        # The package might be installed
        version = sminion.functions.pkg.version(target)
        if version:
            # Be sure to uninstall it
            sminion.functions.pkg.remove(name=target)
    log.warning('Processing target %r. Version: %s', target, version)
    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so this package
    # needs to not be installed before we run the states below
    assert version
    yield Package(name=target, version=version)


@pytest.fixture
def pkg_latest_epoch_target(sminion, _pkg_latest_epoch_target):
    yield _pkg_latest_epoch_target
    # Always uninstall package
    sminion.functions.pkg.remove(name=_pkg_latest_epoch_target.name)


@pytest.mark.skipif('grains["os_family"] == "Windows"', reason='Test not applicable on Windows')
@pytest.mark.destructive_test
def test_pkg_009_latest_with_epoch(states, pkg_latest_epoch_target):
    '''
    This tests for the following issue:
    https://github.com/saltstack/salt/issues/31014

    This is a destructive test as it installs a package
    '''
    ret = states.pkg.installed(name=pkg_latest_epoch_target.name, refresh=False)
    assert ret.result is True


@pytest.mark.skipif('grains["os_family"] == "Windows"', reason='Test not applicable on Windows')
@pytest.mark.destructive_test
def test_pkg_010_latest_with_epoch_and_info_installed(states, modules, pkg_latest_epoch_target):
    '''
    This is a destructive test as it installs a package
    '''
    ret = states.pkg.installed(name=pkg_latest_epoch_target.name, refresh=False)
    assert ret.result is True
    ret = modules.pkg.info_installed(pkg_latest_epoch_target.name)
    assert ret
    assert pkg_latest_epoch_target.name in ret
    assert 'version' in ret[pkg_latest_epoch_target.name]


@pytest.mark.destructive_test
def test_pkg_011_latest(states, pkg_target_1):
    '''
    This tests pkg.latest with a package that has no epoch (or a zero epoch).
    '''
    ret = states.pkg.installed(name=pkg_target_1.name, refresh=False)
    assert ret.result is True


@pytest.mark.destructive_test
def test_pkg_012_latest_only_upgrade(states, modules, pkg_target_1):
    '''
    WARNING: This test will pick a package with an available upgrade (if
    there is one) and upgrade it to the latest version.
    '''
    ret = states.pkg.latest(name=pkg_target_1.name, refresh=False, only_upgrade=True)
    assert ret.result is True

    # Now look for updates and try to run the state on a package which is
    # already up-to-date.
    installed_pkgs = modules.pkg.list_pkgs()
    updates = modules.pkg.list_upgrades(refresh=False)

    for pkgname in updates:
        if pkgname in installed_pkgs:
            target = pkgname
            break
    else:
        pytest.skip(
            'No available upgrades to installed packages, skipping '
            'only_upgrade=True test with already-installed package. For '
            'best results run this test on a machine with upgrades '
            'available.'
        )

    ret = states.pkg.latest(name=target, refresh=False, only_upgrade=True)
    assert ret.result is True
    new_version = modules.pkg.version(target)
    assert new_version == updates[target]
    ret = states.pkg.latest(name=target, refresh=False, only_upgrade=True)
    assert ret.result is True
    state_id = 'pkg_|-{0}_|-{0}_|-latest'.format(target)
    assert ret == {state_id: {'comment': 'Package {0} is already up-to-date'.format(target)}}


@pytest.mark.skipif('grains["os_family"] not in ("Arch", "Debian", "RedHat")',
                    reason='Package version wildcards not supported')
@pytest.mark.destructive_test
def test_pkg_013_installed_with_wildcard_version(states, pkg_target_1):
    '''
    This is a destructive test as it installs and then removes a package
    '''
    ret = states.pkg.installed(name=pkg_target_1.name, version='*', refresh=False)
    assert ret.result is True

    # Repeat state, should pass
    ret = states.pkg.installed(name=pkg_target_1.name, version='*', refresh=False)
    assert ret.result is True
    expected_comment = (
        'All specified packages are already installed and are at the '
        'desired version'
    )
    state_id = 'pkg_|-{0}_|-{0}_|-installed'.format(pkg_target_1.name)
    assert ret == {state_id: {'comment': expected_comment}}

    # Repeat one more time with unavailable version, test should fail
    ret = states.pkg.installed(name=pkg_target_1.name, version='93413*', refresh=False)
    assert ret.result is False


@pytest.mark.skipif('grains["os_family"] not in ("Debian", "RedHat")',
                    reason='Package version comparissons not implemented')
@pytest.mark.destructive_test
def test_pkg_014_installed_with_comparison_operator(states, modules, pkg_target_1):
    '''
    This is a destructive test as it installs and then removes a package
    '''
    ret = states.pkg.installed(name=pkg_target_1.name, version='<9999999', refresh=False)
    assert ret.result is True
    # The version that was installed should be the latest available
    version = modules.pkg.version(pkg_target_1.name)
    assert version == pkg_target_1.version


@pytest.mark.skipif('grains["os_family"] != "RedHat"',
                    reason='Test only applicable to RedHat based distributions')
@pytest.mark.destructive_test
def test_pkg_014_installed_missing_release(states, pkg_target_1):
    '''
    Tests that a version number missing the release portion still resolves
    as correctly installed. For example, version 2.0.2 instead of 2.0.2-1.el7
    '''
    # XXX: Previously, tests/integration/states/test_pkg.py, this test evaluated version to an empty
    # string, which, when evalueated through:
    #    version = salt.utils.pkg.rpm.version_to_evr(pkg_target_1.version)[1]
    # would still evaluate to an empty string.
    # This does not seem like its what we're trying to test.
    # I believe the test should be trying to install something like 2.0.2 when the available
    # version is 2.0.2-1.el7. If we act on this assumption, the test fails because the versions don't match
    # So, is this a bad test, or a bad test with a bug in salt?

    # We maintain the old testing behaviour, which does't currently make sense to me
    # Signed: s0undt3ch
    ret = states.pkg.installed(name=pkg_target_1.name, version='', refresh=False)
    assert ret.result is True


@pytest.mark.skipif('grains["os_family"] == "Windows"', reason='Test not applicable on Windows')
@pytest.mark.requires_salt_modules('pkg.group_install')
@pytest.mark.destructive_test
def test_group_installed_handle_missing_package_group(states):
    '''
    Tests that a CommandExecutionError is caught and the state returns False when
    the package group is missing. Before this fix, the state would stacktrace.
    See Issue #35819 for bug report.
    '''
    # Group install not available message
    grp_install_msg = 'pkg.group_install not available for this platform'

    # Run the pkg.group_installed state with a fake package group
    state_id = 'pkg_|-handle_missing_pkg_group_|-handle_missing_pkg_group_|-group_installed'
    ret = states.pkg.group_installed(name='handle_missing_pkg_group', skip=['foo-bar-baz'])

    # Not all package managers support group_installed. Skip this test if not supported.
    if ret == {state_id: {'comment': grp_install_msg}}:
        pytest.skip(grp_install_msg)

    # Test state should return False and should have the right comment
    assert ret.result is False
    expected_comment = (
        'An error was encountered while installing/updating group '
        '\'handle_missing_pkg_group\': Group \'handle_missing_pkg_group\' not found.'
    )
    assert ret == {state_id: {'comment': expected_comment}}


@pytest.mark.skipif('grains["os_family"] not in ("Debian", "RedHat")',
                    reason='Test only runs on RedHat or Debian family')
@pytest.mark.requires_salt_modules('pkg.hold', 'pkg.unhold')
@pytest.mark.destructive_test
def test_pkg_015_installed_held(states, modules, grains, pkg_target_1):
    '''
    This is a destructive test as it installs and then removes a package
    '''
    # TODO: needs to be rewritten to allow for dnf on Fedora 30 and RHEL 8
    uninstall_yum_plugin_versionlock = False
    if grains['os_family'] == 'RedHat':
        # If we're in the Red Hat family first we ensure that
        # the yum-plugin-versionlock package is installed
        ret = modules.pkg.latest_version('yum-plugin-versionlock')
        if ret:
            ret = states.pkg.installed(name='yum-plugin-versionlock', refresh=False)
            assert ret.result is True
            uninstall_yum_plugin_versionlock = True

    # First we ensure that the package is installed
    ret = states.pkg.installed(name=pkg_target_1.name, refresh=False)
    assert ret.result is True

    # Then we check that the package is now held
    state_id = 'pkg_|-{0}_|-{0}_|-installed'.format(pkg_target_1.name)
    try:
        ret = states.pkg.installed(name=pkg_target_1.name, hold=True, refresh=False)
        assert ret.result is True

        # changes from pkg.hold for Red Hat family are different
        if grains['os_family'] == 'RedHat':
            target_changes = {'new': 'hold', 'old': ''}
        if grains['os_family'] == 'Debian':
            target_changes = {'new': 'hold', 'old': 'install'}
            if grains['osmajorrelease'] == 10:
                # XXX: Find out why
                target_changes['old'] = None

        assert ret == {state_id: {'changes': {pkg_target_1.name: target_changes}}}
    finally:
        # Clean up, unhold package and remove
        modules.pkg.unhold(name=pkg_target_1.name)
        if uninstall_yum_plugin_versionlock:
            ret = states.pkg.removed(name='yum-plugin-versionlock')
            assert ret.result is True


@pytest.fixture(scope='module')
def pkg_cap_target(sminion):
    _pkg_targets_mapping = {
        'Suse': [('perl(ZNC)', 'znc-perl')],
    }
    os_name = sminion.opts['grains'].get('os', '')
    target = _pkg_targets_mapping.get(os_name, '')
    if not target:
        pytest.skip('Test not applicable for OS {osfinger}'.format(**sminion.opts['grains']))

    target, realpkg = target
    log.warning('Processing target %s(%s)', target, realpkg)
    target_version = sminion.functions.pkg.latest_version(target)
    if not target_version:
        # The package might be installed
        target_version = sminion.functions.pkg.version(target)
        if target_version:
            # Be sure to uninstall it
            sminion.functions.pkg.remove(name=realpkg)
    log.warning('Processing target %r. Version: %s', target, target_version)
    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so this package
    # needs to not be installed before we run the states below
    assert target_version
    realpkg_version = sminion.functions.pkg.latest_version(realpkg)
    if not realpkg_version:
        # The package might be installed
        realpkg_version = sminion.functions.pkg.version(realpkg)
        if realpkg_version:
            # Be sure to uninstall it
            sminion.functions.pkg.remove(name=realpkg)
    log.warning('Processing realpkg %r. Version: %s', realpkg, realpkg_version)
    # If this assert fails, we need to find new targets, this test needs to
    # be able to test successful installation of packages, so this package
    # needs to not be installed before we run the states below
    assert realpkg_version
    yield PackageCap(Package(target, target_version), Package(realpkg, realpkg_version))
    # Always uninstall packages
    sminion.functions.pkg.remove(name=realpkg)


@pytest.mark.skipif('grains["os_family"] == "Windows"', reason='Test not applicable on Windows')
@pytest.mark.destructive_test
def test_pkg_cap_001_installed(states, pkg_cap_target):
    '''
    This is a destructive test as it installs and then removes a package
    '''
    state_id = 'pkg_|-{0}_|-{0}_|-installed'.format(pkg_cap_target.cap.name)
    ret = states.pkg.installed(name=pkg_cap_target.cap.name,
                               refresh=False,
                               resolve_capabilities=True,
                               test=True)
    expected_comment_regex = 'The following packages would be installed/updated: {}'.format(pkg_cap_target.realpkg.name)
    assert ret == {state_id: {'comment': expected_comment_regex}}
    ret = states.pkg.installed(name=pkg_cap_target.cap.name,
                               refresh=False,
                               resolve_capabilities=True)
    assert ret.result is True


@pytest.mark.skipif('grains["os_family"] == "Windows"', reason='Test not applicable on Windows')
@pytest.mark.destructive_test
def test_pkg_cap_002_already_installed(states, pkg_cap_target):
    '''
    This is a destructive test as it installs and then removes a package
    '''
    # Install the package
    ret = states.pkg.installed(name=pkg_cap_target.realpkg.name, refresh=False)
    assert ret.result is True
    # Try to install again. Nothing should be installed this time.
    state_id = 'pkg_|-{0}_|-{0}_|-installed'.format(pkg_cap_target.cap.name)
    ret = states.pkg.installed(name=pkg_cap_target.cap.name,
                               refresh=False,
                               resolve_capabilities=True,
                               test=True)
    assert ret.result is True
    expected_comment_regex = 'All specified packages are already installed'
    assert ret == {state_id: {'comment': expected_comment_regex}}
    ret = states.pkg.installed(name=pkg_cap_target.cap.name,
                               refresh=False,
                               resolve_capabilities=True)
    assert ret.result is True
    assert ret == {state_id: {'comment': expected_comment_regex}}


@pytest.mark.skipif('grains["os_family"] == "Windows"', reason='Test not applicable on Windows')
@pytest.mark.skipif('grains["os_family"] == "FreeBSD"', reason='Version specification is not supported in FreeBSD')
@pytest.mark.destructive_test
def test_pkg_cap_003_installed_multipkg_with_version(states, pkg_cap_target, pkg_targets):
    '''
    This is a destructive test as it installs and then removes a package
    '''
    pkgs = [
        {pkg_targets[0]: pkg_targets[0].version},
        pkg_targets[1].name,
        {pkg_cap_target.cap.name: pkg_cap_target.realpkg.version}
    ]
    ret = states.pkg.installed(name='test_pkg_cap_003_installed_multipkg_with_version-install',
                               pkgs=pkgs,
                               refresh=False)
    assert ret.result is False

    state_name = 'test_pkg_cap_003_installed_multipkg_with_version-install-capability'
    state_id = 'pkg_|-{0}_|-{0}_|-installed'.format(state_name)
    ret = states.pkg.installed(name=state_name,
                               pkgs=pkgs,
                               refresh=False,
                               resolve_capabilities=True,
                               test=True)
    assert ret == {state_id: {'comment': 'packages would be installed/updated'}}
    assert ret == {state_id: {'comment': '{}={}'.format(pkg_cap_target.realpkg.name, pkg_cap_target.cap.version)}}

    state_name = 'test_pkg_cap_003_installed_multipkg_with_version-install-capability'
    ret = states.pkg.installed(name=state_name,
                               pkgs=pkgs,
                               refresh=False,
                               resolve_capabilities=True)
    assert ret.result is True


@pytest.mark.skipif('grains["os_family"] == "Windows"', reason='Test not applicable on Windows')
@pytest.mark.destructive_test
def test_pkg_cap_004_latest(states, pkg_cap_target):
    '''
    This is a destructive test as it installs and then removes a package
    '''
    state_id = 'pkg_|-{0}_|-{0}_|-latest'.format(pkg_cap_target.cap.name)
    ret = states.pkg.latest(name=pkg_cap_target.cap.name,
                            refresh=False,
                            resolve_capabilities=True,
                            test=True)
    expected_comment_regex = 'The following packages would be installed/updated: {}'.format(pkg_cap_target.realpkg.name)
    assert ret == {state_id: {'comment': expected_comment_regex}}
    ret = states.pkg.latest(name=pkg_cap_target.cap.name,
                            refresh=False,
                            resolve_capabilities=True)
    assert ret.result is True


@pytest.mark.skipif('grains["os_family"] == "Windows"', reason='Test not applicable on Windows')
@pytest.mark.destructive_test
def test_pkg_cap_005_downloaded(states, pkg_cap_target):
    '''
    This is a destructive test as it installs and then removes a package
    '''
    state_id = 'pkg_|-{0}_|-{0}_|-downloaded'.format(pkg_cap_target.cap.name)
    ret = states.pkg.downloaded(name=pkg_cap_target.cap.name,
                                refresh=False,
                                resolve_capabilities=True,
                                test=True)
    expected_comment_regex = 'The following packages would be downloaded: {}'.format(pkg_cap_target.realpkg.name)
    assert ret == {state_id: {'comment': expected_comment_regex}}
    ret = states.pkg.downloaded(name=pkg_cap_target.cap.name,
                                refresh=False,
                                resolve_capabilities=True)
    assert ret.result is True


@pytest.mark.skipif('grains["os_family"] == "Windows"', reason='Test not applicable on Windows')
@pytest.mark.destructive_test
def test_pkg_cap_006_uptodate(states, pkg_cap_target):
    '''
    This is a destructive test as it installs and then removes a package
    '''
    pkgs = [
        {pkg_targets[0]: pkg_targets[0].version},
        pkg_targets[1].name,
        {pkg_cap_target.cap.name: pkg_cap_target.realpkg.version}
    ]
    ret = states.pkg.installed(pkg_cap_target.realpkg.name, refresh=False)
    assert ret.result is False

    state_name = 'test_pkg_cap_006_uptodate'
    state_id = 'pkg_|-{0}_|-{0}_|-uptodate'.format(state_name)
    ret = states.pkg.installed(name=state_name,
                               pkgs=[pkg_cap_target.cap.name],
                               refresh=False,
                               resolve_capabilities=True)
    assert ret.result is True
    assert ret == {state_id: {'comment': 'System is already up-to-date'}}
