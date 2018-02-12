# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import
import os

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
import salt.modules.pkg_resource as pkg_resource

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
                'rpm': None,
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

    def test_list_pkgs(self):
        '''
        Test packages listing.

        :return:
        '''
        def _add_data(data, key, value):
            data.setdefault(key, []).append(value)

        rpm_out = [
            'python-urlgrabber_|-(none)_|-3.10_|-8.el7_|-noarch_|-(none)_|-1487838471',
            'alsa-lib_|-(none)_|-1.1.1_|-1.el7_|-x86_64_|-(none)_|-1487838475',
            'gnupg2_|-(none)_|-2.0.22_|-4.el7_|-x86_64_|-(none)_|-1487838477',
            'rpm-python_|-(none)_|-4.11.3_|-21.el7_|-x86_64_|-(none)_|-1487838477',
            'pygpgme_|-(none)_|-0.3_|-9.el7_|-x86_64_|-(none)_|-1487838478',
            'yum_|-(none)_|-3.4.3_|-150.el7.centos_|-noarch_|-(none)_|-1487838479',
            'lzo_|-(none)_|-2.06_|-8.el7_|-x86_64_|-(none)_|-1487838479',
            'qrencode-libs_|-(none)_|-3.4.1_|-3.el7_|-x86_64_|-(none)_|-1487838480',
            'ustr_|-(none)_|-1.0.4_|-16.el7_|-x86_64_|-(none)_|-1487838480',
            'shadow-utils_|-2_|-4.1.5.1_|-24.el7_|-x86_64_|-(none)_|-1487838481',
            'util-linux_|-(none)_|-2.23.2_|-33.el7_|-x86_64_|-(none)_|-1487838484',
            'openssh_|-(none)_|-6.6.1p1_|-33.el7_3_|-x86_64_|-(none)_|-1487838485',
            'virt-what_|-(none)_|-1.13_|-8.el7_|-x86_64_|-(none)_|-1487838486',
        ]
        with patch.dict(yumpkg.__grains__, {'osarch': 'x86_64'}), \
             patch.dict(yumpkg.__salt__, {'cmd.run': MagicMock(return_value=os.linesep.join(rpm_out))}), \
             patch.dict(yumpkg.__salt__, {'pkg_resource.add_pkg': _add_data}), \
             patch.dict(yumpkg.__salt__, {'pkg_resource.format_pkg_list': pkg_resource.format_pkg_list}), \
             patch.dict(yumpkg.__salt__, {'pkg_resource.stringify': MagicMock()}):
            pkgs = yumpkg.list_pkgs(versions_as_list=True)
            for pkg_name, pkg_version in {
                'python-urlgrabber': '3.10-8.el7',
                'alsa-lib': '1.1.1-1.el7',
                'gnupg2': '2.0.22-4.el7',
                'rpm-python': '4.11.3-21.el7',
                'pygpgme': '0.3-9.el7',
                'yum': '3.4.3-150.el7.centos',
                'lzo': '2.06-8.el7',
                'qrencode-libs': '3.4.1-3.el7',
                'ustr': '1.0.4-16.el7',
                'shadow-utils': '2:4.1.5.1-24.el7',
                'util-linux': '2.23.2-33.el7',
                'openssh': '6.6.1p1-33.el7_3',
                'virt-what': '1.13-8.el7'}.items():
                self.assertTrue(pkgs.get(pkg_name))
                self.assertEqual(pkgs[pkg_name], [pkg_version])

    def test_list_pkgs_with_attr(self):
        '''
        Test packages listing with the attr parameter

        :return:
        '''
        def _add_data(data, key, value):
            data.setdefault(key, []).append(value)

        rpm_out = [
            'python-urlgrabber_|-(none)_|-3.10_|-8.el7_|-noarch_|-(none)_|-1487838471',
            'alsa-lib_|-(none)_|-1.1.1_|-1.el7_|-x86_64_|-(none)_|-1487838475',
            'gnupg2_|-(none)_|-2.0.22_|-4.el7_|-x86_64_|-(none)_|-1487838477',
            'rpm-python_|-(none)_|-4.11.3_|-21.el7_|-x86_64_|-(none)_|-1487838477',
            'pygpgme_|-(none)_|-0.3_|-9.el7_|-x86_64_|-(none)_|-1487838478',
            'yum_|-(none)_|-3.4.3_|-150.el7.centos_|-noarch_|-(none)_|-1487838479',
            'lzo_|-(none)_|-2.06_|-8.el7_|-x86_64_|-(none)_|-1487838479',
            'qrencode-libs_|-(none)_|-3.4.1_|-3.el7_|-x86_64_|-(none)_|-1487838480',
            'ustr_|-(none)_|-1.0.4_|-16.el7_|-x86_64_|-(none)_|-1487838480',
            'shadow-utils_|-2_|-4.1.5.1_|-24.el7_|-x86_64_|-(none)_|-1487838481',
            'util-linux_|-(none)_|-2.23.2_|-33.el7_|-x86_64_|-(none)_|-1487838484',
            'openssh_|-(none)_|-6.6.1p1_|-33.el7_3_|-x86_64_|-(none)_|-1487838485',
            'virt-what_|-(none)_|-1.13_|-8.el7_|-x86_64_|-(none)_|-1487838486',
        ]
        with patch.dict(yumpkg.__grains__, {'osarch': 'x86_64'}), \
             patch.dict(yumpkg.__salt__, {'cmd.run': MagicMock(return_value=os.linesep.join(rpm_out))}), \
             patch.dict(yumpkg.__salt__, {'pkg_resource.add_pkg': _add_data}), \
             patch.dict(yumpkg.__salt__, {'pkg_resource.format_pkg_list': pkg_resource.format_pkg_list}), \
             patch.dict(yumpkg.__salt__, {'pkg_resource.stringify': MagicMock()}):
            pkgs = yumpkg.list_pkgs(attr=['epoch', 'release', 'arch', 'install_date_time_t'])
            for pkg_name, pkg_attr in {
                'python-urlgrabber': {
                    'version': '3.10',
                    'release': '8.el7',
                    'arch': 'noarch',
                    'install_date_time_t': 1487838471,
                },
                'alsa-lib': {
                    'version': '1.1.1',
                    'release': '1.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838475,
                },
                'gnupg2': {
                    'version': '2.0.22',
                    'release': '4.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838477,
                },
                'rpm-python': {
                    'version': '4.11.3',
                    'release': '21.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838477,
                },
                'pygpgme': {
                    'version': '0.3',
                    'release': '9.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838478,
                },
                'yum': {
                    'version': '3.4.3',
                    'release': '150.el7.centos',
                    'arch': 'noarch',
                    'install_date_time_t': 1487838479,
                },
                'lzo': {
                    'version': '2.06',
                    'release': '8.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838479,
                },
                'qrencode-libs': {
                    'version': '3.4.1',
                    'release': '3.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838480,
                },
                'ustr': {
                    'version': '1.0.4',
                    'release': '16.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838480,
                },
                'shadow-utils': {
                    'epoch': '2',
                    'version': '4.1.5.1',
                    'release': '24.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838481,
                },
                'util-linux': {
                    'version': '2.23.2',
                    'release': '33.el7',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838484,
                },
                'openssh': {
                    'version': '6.6.1p1',
                    'release': '33.el7_3',
                    'arch': 'x86_64',
                    'install_date_time_t': 1487838485,
                },
                'virt-what': {
                    'version': '1.13',
                    'release': '8.el7',
                    'install_date_time_t': 1487838486,
                    'arch': 'x86_64',
                }}.items():
                self.assertTrue(pkgs.get(pkg_name))
                self.assertEqual(pkgs[pkg_name], [pkg_attr])

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
                    ['yum', '--quiet', 'clean', 'expire-cache', '--disablerepo=*',
                     '--enablerepo=good', '--branch=foo'],
                    python_shell=False)
                update_cmd.assert_called_once_with(
                    ['yum', '--quiet', 'check-update',
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
                    ['yum', '--quiet', 'clean', 'expire-cache', '--disablerepo=bad',
                     '--enablerepo=good', '--branch=foo'],
                    python_shell=False)
                update_cmd.assert_called_once_with(
                    ['yum', '--quiet', 'check-update',
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
                    ['yum', '--quiet', 'clean', 'expire-cache', '--disablerepo=*',
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
                    ['yum', '--quiet', 'clean', 'expire-cache', '--disablerepo=bad',
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
