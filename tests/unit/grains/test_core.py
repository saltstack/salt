# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Erik Johnson <erik@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import logging
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    mock_open,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.utils
import salt.grains.core as core

# Import 3rd-party libs
from salt.ext import six
if six.PY3:
    import ipaddress
else:
    from salt.ext import ipaddress

log = logging.getLogger(__name__)

# Globals
IP4_LOCAL = '127.0.0.1'
IP4_ADD1 = '10.0.0.1'
IP4_ADD2 = '10.0.0.2'
IP6_LOCAL = '::1'
IP6_ADD1 = '2001:4860:4860::8844'
IP6_ADD2 = '2001:4860:4860::8888'
IP6_ADD_SCOPE = 'fe80::6238:e0ff:fe06:3f6b%enp2s0'
OS_RELEASE_DIR = os.path.join(os.path.dirname(__file__), "os-releases")


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CoreGrainsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for core grains
    '''
    def setup_loader_modules(self):
        return {core: {}}

    @patch("os.path.isfile")
    def test_parse_etc_os_release(self, path_isfile_mock):
        path_isfile_mock.side_effect = lambda x: x == "/usr/lib/os-release"
        with salt.utils.fopen(os.path.join(OS_RELEASE_DIR, "ubuntu-17.10")) as os_release_file:
            os_release_content = os_release_file.readlines()
        with patch("salt.utils.fopen", mock_open()) as os_release_file:
            os_release_file.return_value.__iter__.return_value = os_release_content
            os_release = core._parse_os_release(["/etc/os-release", "/usr/lib/os-release"])
        self.assertEqual(os_release, {
            "NAME": "Ubuntu",
            "VERSION": "17.10 (Artful Aardvark)",
            "ID": "ubuntu",
            "ID_LIKE": "debian",
            "PRETTY_NAME": "Ubuntu 17.10",
            "VERSION_ID": "17.10",
            "HOME_URL": "https://www.ubuntu.com/",
            "SUPPORT_URL": "https://help.ubuntu.com/",
            "BUG_REPORT_URL": "https://bugs.launchpad.net/ubuntu/",
            "PRIVACY_POLICY_URL": "https://www.ubuntu.com/legal/terms-and-policies/privacy-policy",
            "VERSION_CODENAME": "artful",
            "UBUNTU_CODENAME": "artful",
        })

    @patch("os.path.isfile")
    def test_missing_os_release(self, path_isfile_mock):
        path_isfile_mock.return_value = False
        os_release = core._parse_os_release(["/etc/os-release", "/usr/lib/os-release"])
        self.assertEqual(os_release, {})

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_gnu_slash_linux_in_os_name(self):
        '''
        Test to return a list of all enabled services
        '''
        _path_exists_map = {
            '/proc/1/cmdline': False
        }
        _path_isfile_map = {}
        _cmd_run_map = {
            'dpkg --print-architecture': 'amd64'
        }

        path_exists_mock = MagicMock(side_effect=lambda x: _path_exists_map[x])
        path_isfile_mock = MagicMock(
            side_effect=lambda x: _path_isfile_map.get(x, False)
        )
        cmd_run_mock = MagicMock(
            side_effect=lambda x: _cmd_run_map[x]
        )
        empty_mock = MagicMock(return_value={})

        orig_import = __import__
        if six.PY2:
            built_in = '__builtin__'
        else:
            built_in = 'builtins'

        def _import_mock(name, *args):
            if name == 'lsb_release':
                raise ImportError('No module named lsb_release')
            return orig_import(name, *args)

        # Skip the first if statement
        with patch.object(salt.utils, 'is_proxy',
                          MagicMock(return_value=False)):
            # Skip the selinux/systemd stuff (not pertinent)
            with patch.object(core, '_linux_bin_exists',
                              MagicMock(return_value=False)):
                # Skip the init grain compilation (not pertinent)
                with patch.object(os.path, 'exists', path_exists_mock):
                    # Ensure that lsb_release fails to import
                    with patch('{0}.__import__'.format(built_in),
                               side_effect=_import_mock):
                        # Skip all the /etc/*-release stuff (not pertinent)
                        with patch.object(os.path, 'isfile', path_isfile_mock):
                            # Mock linux_distribution to give us the OS name
                            # that we want.
                            distro_mock = MagicMock(
                                return_value=('Debian GNU/Linux', '8.3', '')
                            )
                            with patch.object(
                                    core,
                                    'linux_distribution',
                                    distro_mock):
                                # Make a bunch of functions return empty dicts,
                                # we don't care about these grains for the
                                # purposes of this test.
                                with patch.object(
                                        core,
                                        '_linux_cpudata',
                                        empty_mock):
                                    with patch.object(
                                            core,
                                            '_linux_gpu_data',
                                            empty_mock):
                                        with patch.object(
                                                core,
                                                '_memdata',
                                                empty_mock):
                                            with patch.object(
                                                    core,
                                                    '_hw_data',
                                                    empty_mock):
                                                with patch.object(
                                                        core,
                                                        '_virtual',
                                                        empty_mock):
                                                    with patch.object(
                                                            core,
                                                            '_ps',
                                                            empty_mock):
                                                        # Mock the osarch
                                                        with patch.dict(
                                                                core.__salt__,
                                                                {'cmd.run': cmd_run_mock}):
                                                            os_grains = core.os_data()

        self.assertEqual(os_grains.get('os_family'), 'Debian')

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_suse_os_from_cpe_data(self):
        '''
        Test if 'os' grain is parsed from CPE_NAME of /etc/os-release
        '''
        _path_exists_map = {
            '/proc/1/cmdline': False
        }
        _os_release_map = {
            'NAME': 'SLES',
            'VERSION': '12-SP1',
            'VERSION_ID': '12.1',
            'PRETTY_NAME': 'SUSE Linux Enterprise Server 12 SP1',
            'ID': 'sles',
            'ANSI_COLOR': '0;32',
            'CPE_NAME': 'cpe:/o:suse:sles:12:sp1'
        }

        path_exists_mock = MagicMock(side_effect=lambda x: _path_exists_map[x])
        empty_mock = MagicMock(return_value={})
        osarch_mock = MagicMock(return_value="amd64")
        os_release_mock = MagicMock(return_value=_os_release_map)

        orig_import = __import__
        if six.PY2:
            built_in = '__builtin__'
        else:
            built_in = 'builtins'

        def _import_mock(name, *args):
            if name == 'lsb_release':
                raise ImportError('No module named lsb_release')
            return orig_import(name, *args)

        # Skip the first if statement
        with patch.object(salt.utils, 'is_proxy',
                          MagicMock(return_value=False)):
            # Skip the selinux/systemd stuff (not pertinent)
            with patch.object(core, '_linux_bin_exists',
                              MagicMock(return_value=False)):
                # Skip the init grain compilation (not pertinent)
                with patch.object(os.path, 'exists', path_exists_mock):
                    # Ensure that lsb_release fails to import
                    with patch('{0}.__import__'.format(built_in),
                               side_effect=_import_mock):
                        # Skip all the /etc/*-release stuff (not pertinent)
                        with patch.object(os.path, 'isfile', MagicMock(return_value=False)):
                            with patch.object(core, '_parse_os_release', os_release_mock):
                                # Mock linux_distribution to give us the OS
                                # name that we want.
                                distro_mock = MagicMock(
                                    return_value=('SUSE Linux Enterprise Server ', '12', 'x86_64')
                                )
                                with patch.object(core, 'linux_distribution', distro_mock):
                                    with patch.object(core, '_linux_gpu_data', empty_mock):
                                        with patch.object(core, '_linux_cpudata', empty_mock):
                                            with patch.object(core, '_virtual', empty_mock):
                                                # Mock the osarch
                                                with patch.dict(core.__salt__, {'cmd.run': osarch_mock}):
                                                    os_grains = core.os_data()

        self.assertEqual(os_grains.get('os_family'), 'Suse')
        self.assertEqual(os_grains.get('os'), 'SUSE')

    def _run_os_grains_tests(self, os_release_filename, os_release_map, expectation):
        path_isfile_mock = MagicMock(side_effect=lambda x: x in os_release_map.get('files', []))
        empty_mock = MagicMock(return_value={})
        osarch_mock = MagicMock(return_value="amd64")
        if os_release_filename:
            os_release_data = core._parse_os_release(
                [os.path.join(OS_RELEASE_DIR, os_release_filename)])
        else:
            os_release_data = os_release_map.get('os_release_file', {})
        os_release_mock = MagicMock(return_value=os_release_data)

        orig_import = __import__
        if six.PY2:
            built_in = '__builtin__'
        else:
            built_in = 'builtins'

        def _import_mock(name, *args):
            if name == 'lsb_release':
                raise ImportError('No module named lsb_release')
            return orig_import(name, *args)

        # Skip the first if statement
        with patch.object(salt.utils, 'is_proxy',
                          MagicMock(return_value=False)):
            # Skip the selinux/systemd stuff (not pertinent)
            with patch.object(core, '_linux_bin_exists',
                              MagicMock(return_value=False)):
                # Skip the init grain compilation (not pertinent)
                with patch.object(os.path, 'exists', path_isfile_mock):
                    # Ensure that lsb_release fails to import
                    with patch('{0}.__import__'.format(built_in),
                               side_effect=_import_mock):
                        # Skip all the /etc/*-release stuff (not pertinent)
                        with patch.object(os.path, 'isfile', path_isfile_mock):
                            with patch.object(core, '_parse_os_release', os_release_mock):
                                # Mock linux_distribution to give us the OS
                                # name that we want.
                                distro_mock = MagicMock(
                                    return_value=os_release_map['linux_distribution']
                                )
                                with patch("salt.utils.fopen", mock_open()) as suse_release_file:
                                    suse_release_file.return_value.__iter__.return_value = \
                                        os_release_map.get('suse_release_file', '').splitlines()
                                    with patch.object(core, 'linux_distribution', distro_mock):
                                        with patch.object(core, '_linux_gpu_data', empty_mock):
                                            with patch.object(core, '_linux_cpudata', empty_mock):
                                                with patch.object(core, '_virtual', empty_mock):
                                                    # Mock the osarch
                                                    with patch.dict(core.__salt__, {'cmd.run': osarch_mock}):
                                                        os_grains = core.os_data()

        grains = {k: v for k, v in os_grains.items()
                  if k in set(["os", "os_family", "osfullname", "oscodename", "osfinger",
                               "osrelease", "osrelease_info", "osmajorrelease"])}
        self.assertEqual(grains, expectation)

    def _run_suse_os_grains_tests(self, os_release_map, expectation):
        os_release_map['linux_distribution'] = ('SUSE test', 'version', 'arch')
        expectation['os'] = 'SUSE'
        expectation['os_family'] = 'Suse'
        self._run_os_grains_tests(None, os_release_map, expectation)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_suse_os_grains_sles11sp3(self):
        '''
        Test if OS grains are parsed correctly in SLES 11 SP3
        '''
        _os_release_map = {
            'suse_release_file': '''SUSE Linux Enterprise Server 11 (x86_64)
VERSION = 11
PATCHLEVEL = 3
''',
            'files': ["/etc/SuSE-release"],
        }
        expectation = {
            'oscodename': 'SUSE Linux Enterprise Server 11 SP3',
            'osfullname': "SLES",
            'osrelease': '11.3',
            'osrelease_info': (11, 3),
            'osmajorrelease': 11,
            'osfinger': 'SLES-11',
        }
        self._run_suse_os_grains_tests(_os_release_map, expectation)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_suse_os_grains_sles11sp4(self):
        '''
        Test if OS grains are parsed correctly in SLES 11 SP4
        '''
        _os_release_map = {
            'os_release_file': {
                'NAME': 'SLES',
                'VERSION': '11.4',
                'VERSION_ID': '11.4',
                'PRETTY_NAME': 'SUSE Linux Enterprise Server 11 SP4',
                'ID': 'sles',
                'ANSI_COLOR': '0;32',
                'CPE_NAME': 'cpe:/o:suse:sles:11:4'
            },
        }
        expectation = {
            'oscodename': 'SUSE Linux Enterprise Server 11 SP4',
            'osfullname': "SLES",
            'osrelease': '11.4',
            'osrelease_info': (11, 4),
            'osmajorrelease': 11,
            'osfinger': 'SLES-11',
        }
        self._run_suse_os_grains_tests(_os_release_map, expectation)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_suse_os_grains_sles12(self):
        '''
        Test if OS grains are parsed correctly in SLES 12
        '''
        _os_release_map = {
            'os_release_file': {
                'NAME': 'SLES',
                'VERSION': '12',
                'VERSION_ID': '12',
                'PRETTY_NAME': 'SUSE Linux Enterprise Server 12',
                'ID': 'sles',
                'ANSI_COLOR': '0;32',
                'CPE_NAME': 'cpe:/o:suse:sles:12'
            },
        }
        expectation = {
            'oscodename': 'SUSE Linux Enterprise Server 12',
            'osfullname': "SLES",
            'osrelease': '12',
            'osrelease_info': (12,),
            'osmajorrelease': 12,
            'osfinger': 'SLES-12',
        }
        self._run_suse_os_grains_tests(_os_release_map, expectation)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_suse_os_grains_sles12sp1(self):
        '''
        Test if OS grains are parsed correctly in SLES 12 SP1
        '''
        _os_release_map = {
            'os_release_file': {
                'NAME': 'SLES',
                'VERSION': '12-SP1',
                'VERSION_ID': '12.1',
                'PRETTY_NAME': 'SUSE Linux Enterprise Server 12 SP1',
                'ID': 'sles',
                'ANSI_COLOR': '0;32',
                'CPE_NAME': 'cpe:/o:suse:sles:12:sp1'
            },
        }
        expectation = {
            'oscodename': 'SUSE Linux Enterprise Server 12 SP1',
            'osfullname': "SLES",
            'osrelease': '12.1',
            'osrelease_info': (12, 1),
            'osmajorrelease': 12,
            'osfinger': 'SLES-12',
        }
        self._run_suse_os_grains_tests(_os_release_map, expectation)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_suse_os_grains_opensuse_leap_42_1(self):
        '''
        Test if OS grains are parsed correctly in openSUSE Leap 42.1
        '''
        _os_release_map = {
            'os_release_file': {
                'NAME': 'openSUSE Leap',
                'VERSION': '42.1',
                'VERSION_ID': '42.1',
                'PRETTY_NAME': 'openSUSE Leap 42.1 (x86_64)',
                'ID': 'opensuse',
                'ANSI_COLOR': '0;32',
                'CPE_NAME': 'cpe:/o:opensuse:opensuse:42.1'
            },
        }
        expectation = {
            'oscodename': 'openSUSE Leap 42.1 (x86_64)',
            'osfullname': "Leap",
            'osrelease': '42.1',
            'osrelease_info': (42, 1),
            'osmajorrelease': 42,
            'osfinger': 'Leap-42',
        }
        self._run_suse_os_grains_tests(_os_release_map, expectation)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_suse_os_grains_tumbleweed(self):
        '''
        Test if OS grains are parsed correctly in openSUSE Tumbleweed
        '''
        _os_release_map = {
            'os_release_file': {
                'NAME': 'openSUSE',
                'VERSION': 'Tumbleweed',
                'VERSION_ID': '20160504',
                'PRETTY_NAME': 'openSUSE Tumbleweed (20160504) (x86_64)',
                'ID': 'opensuse',
                'ANSI_COLOR': '0;32',
                'CPE_NAME': 'cpe:/o:opensuse:opensuse:20160504'
            },
        }
        expectation = {
            'oscodename': 'openSUSE Tumbleweed (20160504) (x86_64)',
            'osfullname': "Tumbleweed",
            'osrelease': '20160504',
            'osrelease_info': (20160504,),
            'osmajorrelease': 20160504,
            'osfinger': 'Tumbleweed-20160504',
        }
        self._run_suse_os_grains_tests(_os_release_map, expectation)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_debian_7_os_grains(self):
        '''
        Test if OS grains are parsed correctly in Debian 7 "wheezy"
        '''
        _os_release_map = {
            'linux_distribution': ('debian', '7.11', ''),
        }
        expectation = {
            'os': 'Debian',
            'os_family': 'Debian',
            'oscodename': 'wheezy',
            'osfullname': 'Debian GNU/Linux',
            'osrelease': '7',
            'osrelease_info': (7,),
            'osmajorrelease': 7,
            'osfinger': 'Debian-7',
        }
        self._run_os_grains_tests("debian-7", _os_release_map, expectation)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_debian_8_os_grains(self):
        '''
        Test if OS grains are parsed correctly in Debian 8 "jessie"
        '''
        _os_release_map = {
            'linux_distribution': ('debian', '8.10', ''),
        }
        expectation = {
            'os': 'Debian',
            'os_family': 'Debian',
            'oscodename': 'jessie',
            'osfullname': 'Debian GNU/Linux',
            'osrelease': '8',
            'osrelease_info': (8,),
            'osmajorrelease': 8,
            'osfinger': 'Debian-8',
        }
        self._run_os_grains_tests("debian-8", _os_release_map, expectation)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_debian_9_os_grains(self):
        '''
        Test if OS grains are parsed correctly in Debian 9 "stretch"
        '''
        _os_release_map = {
            'linux_distribution': ('debian', '9.3', ''),
        }
        expectation = {
            'os': 'Debian',
            'os_family': 'Debian',
            'oscodename': 'stretch',
            'osfullname': 'Debian GNU/Linux',
            'osrelease': '9',
            'osrelease_info': (9,),
            'osmajorrelease': 9,
            'osfinger': 'Debian-9',
        }
        self._run_os_grains_tests("debian-9", _os_release_map, expectation)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_ubuntu_xenial_os_grains(self):
        '''
        Test if OS grains are parsed correctly in Ubuntu 16.04 "Xenial Xerus"
        '''
        _os_release_map = {
            'linux_distribution': ('Ubuntu', '16.04', 'xenial'),
        }
        expectation = {
            'os': 'Ubuntu',
            'os_family': 'Debian',
            'oscodename': 'xenial',
            'osfullname': 'Ubuntu',
            'osrelease': '16.04',
            'osrelease_info': (16, 4),
            'osmajorrelease': 16,
            'osfinger': 'Ubuntu-16.04',
        }
        self._run_os_grains_tests("ubuntu-16.04", _os_release_map, expectation)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_ubuntu_artful_os_grains(self):
        '''
        Test if OS grains are parsed correctly in Ubuntu 17.10 "Artful Aardvark"
        '''
        _os_release_map = {
            'linux_distribution': ('Ubuntu', '17.10', 'artful'),
        }
        expectation = {
            'os': 'Ubuntu',
            'os_family': 'Debian',
            'oscodename': 'artful',
            'osfullname': 'Ubuntu',
            'osrelease': '17.10',
            'osrelease_info': (17, 10),
            'osmajorrelease': 17,
            'osfinger': 'Ubuntu-17.10',
        }
        self._run_os_grains_tests("ubuntu-17.10", _os_release_map, expectation)

    def test_docker_virtual(self):
        '''
        Test if OS grains are parsed correctly in Ubuntu Xenial Xerus
        '''
        with patch.object(os.path, 'isdir', MagicMock(return_value=False)):
            with patch.object(os.path,
                              'isfile',
                              MagicMock(side_effect=lambda x: True if x == '/proc/1/cgroup' else False)):
                for cgroup_substr in (':/system.slice/docker', ':/docker/',
                                       ':/docker-ce/'):
                    cgroup_data = \
                        '10:memory{0}a_long_sha256sum'.format(cgroup_substr)
                    log.debug(
                        'Testing Docker cgroup substring \'%s\'', cgroup_substr)
                    with patch('salt.utils.fopen', mock_open(read_data=cgroup_data)):
                        with patch.dict(core.__salt__, {'cmd.run_all': MagicMock()}):
                            self.assertEqual(
                                core._virtual({'kernel': 'Linux'}).get('virtual_subtype'),
                                'Docker'
                            )

    def _check_ipaddress(self, value, ip_v):
        '''
        check if ip address in a list is valid
        '''
        for val in value:
            assert isinstance(val, six.string_types)
            ip_method = 'is_ipv{0}'.format(ip_v)
            self.assertTrue(getattr(salt.utils.network, ip_method)(val))

    def _check_empty(self, key, value, empty):
        '''
        if empty is False and value does not exist assert error
        if empty is True and value exists assert error
        '''
        if not empty and not value:
            raise Exception("{0} is empty, expecting a value".format(key))
        elif empty and value:
            raise Exception("{0} is suppose to be empty. value: {1} \
                            exists".format(key, value))

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_fqdn_return(self):
        '''
        test ip4 and ip6 return values
        '''
        net_ip4_mock = [IP4_LOCAL, IP4_ADD1, IP4_ADD2]
        net_ip6_mock = [IP6_LOCAL, IP6_ADD1, IP6_ADD2]

        self._run_fqdn_tests(net_ip4_mock, net_ip6_mock,
                             ip4_empty=False, ip6_empty=False)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_fqdn6_empty(self):
        '''
        test when ip6 is empty
        '''
        net_ip4_mock = [IP4_LOCAL, IP4_ADD1, IP4_ADD2]
        net_ip6_mock = []

        self._run_fqdn_tests(net_ip4_mock, net_ip6_mock,
                             ip4_empty=False)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_fqdn4_empty(self):
        '''
        test when ip4 is empty
        '''
        net_ip4_mock = []
        net_ip6_mock = [IP6_LOCAL, IP6_ADD1, IP6_ADD2]

        self._run_fqdn_tests(net_ip4_mock, net_ip6_mock,
                             ip6_empty=False)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_fqdn_all_empty(self):
        '''
        test when both ip4 and ip6 are empty
        '''
        net_ip4_mock = []
        net_ip6_mock = []

        self._run_fqdn_tests(net_ip4_mock, net_ip6_mock)

    def _run_fqdn_tests(self, net_ip4_mock, net_ip6_mock,
                        ip6_empty=True, ip4_empty=True):

        def _check_type(key, value, ip4_empty, ip6_empty):
            '''
            check type and other checks
            '''
            assert isinstance(value, list)

            if '4' in key:
                self._check_empty(key, value, ip4_empty)
                self._check_ipaddress(value, ip_v='4')
            elif '6' in key:
                self._check_empty(key, value, ip6_empty)
                self._check_ipaddress(value, ip_v='6')

        ip4_mock = [(2, 1, 6, '', (IP4_ADD1, 0)),
                    (2, 3, 0, '', (IP4_ADD2, 0))]
        ip6_mock = [(10, 1, 6, '', (IP6_ADD1, 0, 0, 0)),
                    (10, 3, 0, '', (IP6_ADD2, 0, 0, 0))]

        with patch.dict(core.__opts__, {'ipv6': False}):
            with patch.object(salt.utils.network, 'ip_addrs',
                             MagicMock(return_value=net_ip4_mock)):
                with patch.object(salt.utils.network, 'ip_addrs6',
                                 MagicMock(return_value=net_ip6_mock)):
                    with patch.object(core.socket, 'getaddrinfo', side_effect=[ip4_mock, ip6_mock]):
                        get_fqdn = core.ip_fqdn()
                        ret_keys = ['fqdn_ip4', 'fqdn_ip6', 'ipv4', 'ipv6']
                        for key in ret_keys:
                            value = get_fqdn[key]
                            _check_type(key, value, ip4_empty, ip6_empty)

    @skipIf(not salt.utils.is_linux(), 'System is not Linux')
    def test_dns_return(self):
        '''
        test the return for a dns grain. test for issue:
        https://github.com/saltstack/salt/issues/41230
        '''
        resolv_mock = {'domain': '', 'sortlist': [], 'nameservers':
                   [ipaddress.IPv4Address(IP4_ADD1),
                    ipaddress.IPv6Address(IP6_ADD1),
                    IP6_ADD_SCOPE], 'ip4_nameservers':
                   [ipaddress.IPv4Address(IP4_ADD1)],
                   'search': ['test.saltstack.com'], 'ip6_nameservers':
                   [ipaddress.IPv6Address(IP6_ADD1),
                    IP6_ADD_SCOPE], 'options': []}
        ret = {'dns': {'domain': '', 'sortlist': [], 'nameservers':
                       [IP4_ADD1, IP6_ADD1,
                        IP6_ADD_SCOPE], 'ip4_nameservers':
                       [IP4_ADD1], 'search': ['test.saltstack.com'],
                       'ip6_nameservers': [IP6_ADD1, IP6_ADD_SCOPE],
                       'options': []}}
        self._run_dns_test(resolv_mock, ret)

    def _run_dns_test(self, resolv_mock, ret):
        with patch.object(salt.utils, 'is_windows',
                          MagicMock(return_value=False)):
            with patch.dict(core.__opts__, {'ipv6': False}):
                with patch.object(salt.utils.dns, 'parse_resolv',
                                  MagicMock(return_value=resolv_mock)):
                    get_dns = core.dns()
                    self.assertEqual(get_dns, ret)
