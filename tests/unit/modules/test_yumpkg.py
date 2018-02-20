# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    Mock,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt libs
import salt.modules.yumpkg as yumpkg

LIST_REPOS = {
    'base': {
        'file': '/etc/yum.repos.d/CentOS-Base.repo',
        'gpgcheck': '1',
        'gpgkey': 'file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7',
        'mirrorlist': 'http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=os&infra=$infra',
        'name': 'CentOS-$releasever - Base'
    },
    'base-source': {
        'baseurl': 'http://vault.centos.org/centos/$releasever/os/Source/',
        'enabled': '0',
        'file': '/etc/yum.repos.d/CentOS-Sources.repo',
        'gpgcheck': '1',
        'gpgkey': 'file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7',
        'name': 'CentOS-$releasever - Base Sources'
    },
    'updates': {
        'file': '/etc/yum.repos.d/CentOS-Base.repo',
        'gpgcheck': '1',
        'gpgkey': 'file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7',
        'mirrorlist': 'http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=updates&infra=$infra',
        'name': 'CentOS-$releasever - Updates'
    },
    'updates-source': {
        'baseurl': 'http://vault.centos.org/centos/$releasever/updates/Source/',
        'enabled': '0',
        'file': '/etc/yum.repos.d/CentOS-Sources.repo',
        'gpgcheck': '1',
        'gpgkey': 'file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7',
        'name': 'CentOS-$releasever - Updates Sources'
    }
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class YumTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.yumpkg
    '''
    def setup_loader_modules(self):
        return {
            yumpkg: {
                '__context__': {
                    'yum_bin': 'yum',
                },
                '__grains__': {
                    'osarch': 'x86_64',
                    'os_family': 'RedHat',
                    'osmajorrelease': 7,
                },
            }
        }

    def test_latest_version_with_options(self):
        with patch.object(yumpkg, 'list_pkgs', MagicMock(return_value={})):

            # with fromrepo
            cmd = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
                yumpkg.latest_version(
                    'foo',
                    refresh=False,
                    fromrepo='good',
                    branch='foo')
                cmd.assert_called_once_with(
                    ['yum', '--quiet', '--disablerepo=*', '--enablerepo=good',
                     '--branch=foo', 'list', 'available', 'foo'],
                    ignore_retcode=True,
                    output_loglevel='trace',
                    python_shell=False)

            # without fromrepo
            cmd = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
                yumpkg.latest_version(
                    'foo',
                    refresh=False,
                    enablerepo='good',
                    disablerepo='bad',
                    branch='foo')
                cmd.assert_called_once_with(
                    ['yum', '--quiet', '--disablerepo=bad', '--enablerepo=good',
                     '--branch=foo', 'list', 'available', 'foo'],
                    ignore_retcode=True,
                    output_loglevel='trace',
                    python_shell=False)

    def test_list_repo_pkgs_with_options(self):
        '''
        Test list_repo_pkgs with and without fromrepo

        NOTE: mock_calls is a stack. The most recent call is indexed
        with 0, while the first call would have the highest index.
        '''
        really_old_yum = MagicMock(return_value='3.2.0')
        older_yum = MagicMock(return_value='3.4.0')
        newer_yum = MagicMock(return_value='3.4.5')
        list_repos_mock = MagicMock(return_value=LIST_REPOS)
        kwargs = {'output_loglevel': 'trace',
                  'ignore_retcode': True,
                  'python_shell': False}

        with patch.object(yumpkg, 'list_repos', list_repos_mock):

            # Test with really old yum. The fromrepo argument has no effect on
            # the yum commands we'd run.
            with patch.dict(yumpkg.__salt__, {'cmd.run': really_old_yum}):

                cmd = MagicMock(return_value={'retcode': 0, 'stdout': ''})
                with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
                    yumpkg.list_repo_pkgs('foo')
                    # We should have called cmd.run_all twice
                    self.assertEqual(len(cmd.mock_calls), 2)

                    # Check args from first call
                    self.assertEqual(
                        cmd.mock_calls[1][1],
                        (['yum', '--quiet', 'list', 'available'],)
                    )
                    # Check kwargs from first call
                    self.assertEqual(cmd.mock_calls[1][2], kwargs)

                    # Check args from second call
                    self.assertEqual(
                        cmd.mock_calls[0][1],
                        (['yum', '--quiet', 'list', 'installed'],)
                    )
                    # Check kwargs from second call
                    self.assertEqual(cmd.mock_calls[0][2], kwargs)

            # Test with really old yum. The fromrepo argument has no effect on
            # the yum commands we'd run.
            with patch.dict(yumpkg.__salt__, {'cmd.run': older_yum}):

                cmd = MagicMock(return_value={'retcode': 0, 'stdout': ''})
                with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
                    yumpkg.list_repo_pkgs('foo')
                    # We should have called cmd.run_all twice
                    self.assertEqual(len(cmd.mock_calls), 2)

                    # Check args from first call
                    self.assertEqual(
                        cmd.mock_calls[1][1],
                        (['yum', '--quiet', '--showduplicates', 'list', 'available'],)
                    )
                    # Check kwargs from first call
                    self.assertEqual(cmd.mock_calls[1][2], kwargs)

                    # Check args from second call
                    self.assertEqual(
                        cmd.mock_calls[0][1],
                        (['yum', '--quiet', '--showduplicates', 'list', 'installed'],)
                    )
                    # Check kwargs from second call
                    self.assertEqual(cmd.mock_calls[0][2], kwargs)

            # Test with newer yum. We should run one yum command per repo, so
            # fromrepo would limit how many calls we make.
            with patch.dict(yumpkg.__salt__, {'cmd.run': newer_yum}):

                # When fromrepo is used, we would only run one yum command, for
                # that specific repo.
                cmd = MagicMock(return_value={'retcode': 0, 'stdout': ''})
                with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
                    yumpkg.list_repo_pkgs('foo', fromrepo='base')
                    # We should have called cmd.run_all once
                    self.assertEqual(len(cmd.mock_calls), 1)

                    # Check args
                    self.assertEqual(
                        cmd.mock_calls[0][1],
                        (['yum', '--quiet', '--showduplicates',
                          'repository-packages', 'base', 'list', 'foo'],)
                    )
                    # Check kwargs
                    self.assertEqual(cmd.mock_calls[0][2], kwargs)

                # Test enabling base-source and disabling updates. We should
                # get two calls, one for each enabled repo. Because dict
                # iteration order will vary, different Python versions will be
                # do them in different orders, which is OK, but it will just
                # mean that we will have to check both the first and second
                # mock call both times.
                cmd = MagicMock(return_value={'retcode': 0, 'stdout': ''})
                with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
                    yumpkg.list_repo_pkgs(
                        'foo',
                        enablerepo='base-source',
                        disablerepo='updates')
                    # We should have called cmd.run_all twice
                    self.assertEqual(len(cmd.mock_calls), 2)

                    for repo in ('base', 'base-source'):
                        for index in (0, 1):
                            try:
                                # Check args
                                self.assertEqual(
                                    cmd.mock_calls[index][1],
                                    (['yum', '--quiet', '--showduplicates',
                                      'repository-packages', repo, 'list',
                                      'foo'],)
                                )
                                # Check kwargs
                                self.assertEqual(cmd.mock_calls[index][2], kwargs)
                                break
                            except AssertionError:
                                continue
                        else:
                            self.fail("repo '{0}' not checked".format(repo))

    def test_list_upgrades_dnf(self):
        '''
        The subcommand should be "upgrades" with dnf
        '''
        with patch.dict(yumpkg.__context__, {'yum_bin': 'dnf'}):
            # with fromrepo
            cmd = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
                yumpkg.list_upgrades(
                    refresh=False,
                    fromrepo='good',
                    branch='foo')
                cmd.assert_called_once_with(
                    ['dnf', '--quiet', '--disablerepo=*', '--enablerepo=good',
                     '--branch=foo', 'list', 'upgrades'],
                    output_loglevel='trace',
                    ignore_retcode=True,
                    python_shell=False)

            # without fromrepo
            cmd = MagicMock(return_value={'retcode': 0, 'stdout': ''})
            with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
                yumpkg.list_upgrades(
                    refresh=False,
                    enablerepo='good',
                    disablerepo='bad',
                    branch='foo')
                cmd.assert_called_once_with(
                    ['dnf', '--quiet', '--disablerepo=bad', '--enablerepo=good',
                     '--branch=foo', 'list', 'upgrades'],
                    output_loglevel='trace',
                    ignore_retcode=True,
                    python_shell=False)

    def test_list_upgrades_yum(self):
        '''
        The subcommand should be "updates" with yum
        '''
        # with fromrepo
        cmd = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
            yumpkg.list_upgrades(
                refresh=False,
                fromrepo='good',
                branch='foo')
            cmd.assert_called_once_with(
                ['yum', '--quiet', '--disablerepo=*', '--enablerepo=good',
                 '--branch=foo', 'list', 'updates'],
                output_loglevel='trace',
                ignore_retcode=True,
                python_shell=False)

        # without fromrepo
        cmd = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
            yumpkg.list_upgrades(
                refresh=False,
                enablerepo='good',
                disablerepo='bad',
                branch='foo')
            cmd.assert_called_once_with(
                ['yum', '--quiet', '--disablerepo=bad', '--enablerepo=good',
                 '--branch=foo', 'list', 'updates'],
                output_loglevel='trace',
                ignore_retcode=True,
                python_shell=False)

    def test_refresh_db_with_options(self):

        with patch('salt.utils.pkg.clear_rtag', Mock()):

            # With check_update=True we will do a cmd.run to run the clean_cmd, and
            # then a separate cmd.retcode to check for updates.

            # with fromrepo
            clean_cmd = Mock()
            update_cmd = MagicMock(return_value=0)
            with patch.dict(yumpkg.__salt__, {'cmd.run': clean_cmd,
                                              'cmd.retcode': update_cmd}):
                yumpkg.refresh_db(
                    check_update=True,
                    fromrepo='good',
                    branch='foo')
                clean_cmd.assert_called_once_with(
                    ['yum', '--quiet', '--assumeyes', 'clean', 'expire-cache', '--disablerepo=*',
                     '--enablerepo=good', '--branch=foo'],
                    python_shell=False)
                update_cmd.assert_called_once_with(
                    ['yum', '--quiet', '--assumeyes', 'check-update',
                     '--setopt=autocheck_running_kernel=false', '--disablerepo=*',
                     '--enablerepo=good', '--branch=foo'],
                    output_loglevel='trace',
                    ignore_retcode=True,
                    python_shell=False)

            # without fromrepo
            clean_cmd = Mock()
            update_cmd = MagicMock(return_value=0)
            with patch.dict(yumpkg.__salt__, {'cmd.run': clean_cmd,
                                              'cmd.retcode': update_cmd}):
                yumpkg.refresh_db(
                    check_update=True,
                    enablerepo='good',
                    disablerepo='bad',
                    branch='foo')
                clean_cmd.assert_called_once_with(
                    ['yum', '--quiet', '--assumeyes', 'clean', 'expire-cache', '--disablerepo=bad',
                     '--enablerepo=good', '--branch=foo'],
                    python_shell=False)
                update_cmd.assert_called_once_with(
                    ['yum', '--quiet', '--assumeyes', 'check-update',
                     '--setopt=autocheck_running_kernel=false', '--disablerepo=bad',
                     '--enablerepo=good', '--branch=foo'],
                    output_loglevel='trace',
                    ignore_retcode=True,
                    python_shell=False)

            # With check_update=False we will just do a cmd.run for the clean_cmd

            # with fromrepo
            clean_cmd = Mock()
            with patch.dict(yumpkg.__salt__, {'cmd.run': clean_cmd}):
                yumpkg.refresh_db(
                    check_update=False,
                    fromrepo='good',
                    branch='foo')
                clean_cmd.assert_called_once_with(
                    ['yum', '--quiet', '--assumeyes', 'clean', 'expire-cache', '--disablerepo=*',
                     '--enablerepo=good', '--branch=foo'],
                    python_shell=False)

            # without fromrepo
            clean_cmd = Mock()
            with patch.dict(yumpkg.__salt__, {'cmd.run': clean_cmd}):
                yumpkg.refresh_db(
                    check_update=False,
                    enablerepo='good',
                    disablerepo='bad',
                    branch='foo')
                clean_cmd.assert_called_once_with(
                    ['yum', '--quiet', '--assumeyes', 'clean', 'expire-cache', '--disablerepo=bad',
                     '--enablerepo=good', '--branch=foo'],
                    python_shell=False)

    def test_install_with_options(self):
        parse_targets = MagicMock(return_value=({'foo': None}, 'repository'))
        with patch.object(yumpkg, 'list_pkgs', MagicMock(return_value={})), \
                patch.object(yumpkg, 'list_holds', MagicMock(return_value=[])), \
                patch.dict(yumpkg.__salt__, {'pkg_resource.parse_targets': parse_targets}), \
                patch('salt.utils.systemd.has_scope', MagicMock(return_value=False)):

            # with fromrepo
            cmd = MagicMock(return_value={'retcode': 0})
            with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
                yumpkg.install(
                    refresh=False,
                    fromrepo='good',
                    branch='foo')
                cmd.assert_called_once_with(
                    ['yum', '-y', '--disablerepo=*', '--enablerepo=good',
                     '--branch=foo', 'install', 'foo'],
                    output_loglevel='trace',
                    python_shell=False,
                    redirect_stderr=True)

            # without fromrepo
            cmd = MagicMock(return_value={'retcode': 0})
            with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
                yumpkg.install(
                    refresh=False,
                    enablerepo='good',
                    disablerepo='bad',
                    branch='foo')
                cmd.assert_called_once_with(
                    ['yum', '-y', '--disablerepo=bad', '--enablerepo=good',
                     '--branch=foo', 'install', 'foo'],
                    output_loglevel='trace',
                    python_shell=False,
                    redirect_stderr=True)

    def test_upgrade_with_options(self):
        with patch.object(yumpkg, 'list_pkgs', MagicMock(return_value={})), \
                patch('salt.utils.systemd.has_scope', MagicMock(return_value=False)):

            # with fromrepo
            cmd = MagicMock(return_value={'retcode': 0})
            with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
                yumpkg.upgrade(
                    refresh=False,
                    fromrepo='good',
                    exclude='kernel*',
                    branch='foo')
                cmd.assert_called_once_with(
                    ['yum', '--quiet', '-y', '--disablerepo=*', '--enablerepo=good',
                     '--branch=foo', '--exclude=kernel*', 'upgrade'],
                    output_loglevel='trace',
                    python_shell=False)

            # without fromrepo
            cmd = MagicMock(return_value={'retcode': 0})
            with patch.dict(yumpkg.__salt__, {'cmd.run_all': cmd}):
                yumpkg.upgrade(
                    refresh=False,
                    enablerepo='good',
                    disablerepo='bad',
                    exclude='kernel*',
                    branch='foo')
                cmd.assert_called_once_with(
                    ['yum', '--quiet', '-y', '--disablerepo=bad', '--enablerepo=good',
                     '--branch=foo', '--exclude=kernel*', 'upgrade'],
                    output_loglevel='trace',
                    python_shell=False)
