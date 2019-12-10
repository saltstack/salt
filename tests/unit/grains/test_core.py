# -*- coding: utf-8 -*-
'''
    :codeauthor: Erik Johnson <erik@saltstack.com>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import socket
import textwrap
import platform

# Import Salt Testing Libs
try:
    import pytest
except ImportError as import_error:
    pytest = None

from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    Mock,
    MagicMock,
    patch,
    mock_open,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.utils.dns
import salt.utils.files
import salt.utils.network
import salt.utils.platform
import salt.utils.path
import salt.modules.cmdmod
import salt.modules.smbios
import salt.grains.core as core

# Import 3rd-party libs
from salt.ext import six
from salt._compat import ipaddress

log = logging.getLogger(__name__)

# Globals
IPv4Address = ipaddress.IPv4Address
IPv6Address = ipaddress.IPv6Address
IP4_LOCAL = '127.0.0.1'
IP4_ADD1 = '10.0.0.1'
IP4_ADD2 = '10.0.0.2'
IP6_LOCAL = '::1'
IP6_ADD1 = '2001:4860:4860::8844'
IP6_ADD2 = '2001:4860:4860::8888'
IP6_ADD_SCOPE = 'fe80::6238:e0ff:fe06:3f6b%enp2s0'
OS_RELEASE_DIR = os.path.join(os.path.dirname(__file__), "os-releases")
SOLARIS_DIR = os.path.join(os.path.dirname(__file__), 'solaris')


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not pytest, False)
class CoreGrainsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for core grains
    '''
    def setup_loader_modules(self):
        return {core: {}}

    @patch("os.path.isfile")
    def test_parse_etc_os_release(self, path_isfile_mock):
        path_isfile_mock.side_effect = lambda x: x == "/usr/lib/os-release"
        with salt.utils.files.fopen(os.path.join(OS_RELEASE_DIR, "ubuntu-17.10")) as os_release_file:
            os_release_content = os_release_file.read()
        with patch("salt.utils.files.fopen", mock_open(read_data=os_release_content)):
            os_release = core._parse_os_release(
                '/etc/os-release',
                '/usr/lib/os-release')
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

    def test_parse_cpe_name_wfn(self):
        '''
        Parse correct CPE_NAME data WFN formatted
        :return:
        '''
        for cpe, cpe_ret in [('cpe:/o:opensuse:leap:15.0',
                              {'phase': None, 'version': '15.0', 'product': 'leap',
                               'vendor': 'opensuse', 'part': 'operating system'}),
                             ('cpe:/o:vendor:product:42:beta',
                              {'phase': 'beta', 'version': '42', 'product': 'product',
                               'vendor': 'vendor', 'part': 'operating system'})]:
            ret = core._parse_cpe_name(cpe)
            for key in cpe_ret:
                assert key in ret
                assert cpe_ret[key] == ret[key]

    def test_parse_cpe_name_v23(self):
        '''
        Parse correct CPE_NAME data v2.3 formatted
        :return:
        '''
        for cpe, cpe_ret in [('cpe:2.3:o:microsoft:windows_xp:5.1.601:beta:*:*:*:*:*:*',
                              {'phase': 'beta', 'version': '5.1.601', 'product': 'windows_xp',
                               'vendor': 'microsoft', 'part': 'operating system'}),
                             ('cpe:2.3:h:corellian:millenium_falcon:1.0:*:*:*:*:*:*:*',
                              {'phase': None, 'version': '1.0', 'product': 'millenium_falcon',
                               'vendor': 'corellian', 'part': 'hardware'}),
                             ('cpe:2.3:*:dark_empire:light_saber:3.0:beta:*:*:*:*:*:*',
                              {'phase': 'beta', 'version': '3.0', 'product': 'light_saber',
                               'vendor': 'dark_empire', 'part': None})]:
            ret = core._parse_cpe_name(cpe)
            for key in cpe_ret:
                assert key in ret
                assert cpe_ret[key] == ret[key]

    def test_parse_cpe_name_broken(self):
        '''
        Parse broken CPE_NAME data
        :return:
        '''
        for cpe in ['cpe:broken', 'cpe:broken:in:all:ways:*:*:*:*',
                    'cpe:x:still:broken:123', 'who:/knows:what:is:here']:
            assert core._parse_cpe_name(cpe) == {}

    def test_missing_os_release(self):
        with patch('salt.utils.files.fopen', mock_open(read_data={})):
            os_release = core._parse_os_release('/etc/os-release', '/usr/lib/os-release')
        self.assertEqual(os_release, {})

    @skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
    def test__windows_platform_data(self):
        grains = core._windows_platform_data()
        keys = ['biosversion',
                'osrelease',
                'kernelrelease',
                'motherboard',
                'serialnumber',
                'timezone',
                'manufacturer',
                'kernelversion',
                'osservicepack',
                'virtual',
                'productname',
                'osfullname',
                'osmanufacturer',
                'osversion',
                'windowsdomain']
        for key in keys:
            self.assertIn(key, grains)

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    def test_gnu_slash_linux_in_os_name(self):
        '''
        Test to return a list of all enabled services
        '''
        _path_exists_map = {
            '/proc/1/cmdline': False
        }
        _path_isfile_map = {}
        _cmd_run_map = {
            'dpkg --print-architecture': 'amd64',
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

        # - Skip the first if statement
        # - Skip the selinux/systemd stuff (not pertinent)
        # - Skip the init grain compilation (not pertinent)
        # - Ensure that lsb_release fails to import
        # - Skip all the /etc/*-release stuff (not pertinent)
        # - Mock linux_distribution to give us the OS name that we want
        # - Make a bunch of functions return empty dicts, we don't care about
        #   these grains for the purposes of this test.
        # - Mock the osarch
        distro_mock = MagicMock(return_value=('Debian GNU/Linux', '8.3', ''))
        with patch.object(salt.utils.platform, 'is_proxy',
                          MagicMock(return_value=False)), \
                patch.object(core, '_linux_bin_exists',
                             MagicMock(return_value=False)), \
                patch.object(os.path, 'exists', path_exists_mock), \
                patch('{0}.__import__'.format(built_in), side_effect=_import_mock), \
                patch.object(os.path, 'isfile', path_isfile_mock), \
                patch.object(core, '_parse_lsb_release', empty_mock), \
                patch.object(core, '_parse_os_release', empty_mock), \
                patch.object(core, '_parse_lsb_release', empty_mock), \
                patch.object(core, 'linux_distribution', distro_mock), \
                patch.object(core, '_linux_cpudata', empty_mock), \
                patch.object(core, '_linux_gpu_data', empty_mock), \
                patch.object(core, '_memdata', empty_mock), \
                patch.object(core, '_hw_data', empty_mock), \
                patch.object(core, '_virtual', empty_mock), \
                patch.object(core, '_ps', empty_mock), \
                patch.dict(core.__salt__, {'cmd.run': cmd_run_mock}):
            os_grains = core.os_data()

        self.assertEqual(os_grains.get('os_family'), 'Debian')

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
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

        distro_mock = MagicMock(
            return_value=('SUSE Linux Enterprise Server ', '12', 'x86_64')
        )

        # - Skip the first if statement
        # - Skip the selinux/systemd stuff (not pertinent)
        # - Skip the init grain compilation (not pertinent)
        # - Ensure that lsb_release fails to import
        # - Skip all the /etc/*-release stuff (not pertinent)
        # - Mock linux_distribution to give us the OS name that we want
        # - Mock the osarch
        with patch.object(salt.utils.platform, 'is_proxy',
                          MagicMock(return_value=False)), \
                patch.object(core, '_linux_bin_exists',
                             MagicMock(return_value=False)), \
                patch.object(os.path, 'exists', path_exists_mock), \
                patch('{0}.__import__'.format(built_in),
                      side_effect=_import_mock), \
                patch.object(os.path, 'isfile', MagicMock(return_value=False)), \
                patch.object(core, '_parse_os_release', os_release_mock), \
                patch.object(core, '_parse_lsb_release', empty_mock), \
                patch.object(core, 'linux_distribution', distro_mock), \
                patch.object(core, '_linux_gpu_data', empty_mock), \
                patch.object(core, '_hw_data', empty_mock), \
                patch.object(core, '_linux_cpudata', empty_mock), \
                patch.object(core, '_virtual', empty_mock), \
                patch.dict(core.__salt__, {'cmd.run': osarch_mock}):
            os_grains = core.os_data()

        self.assertEqual(os_grains.get('os_family'), 'Suse')
        self.assertEqual(os_grains.get('os'), 'SUSE')

    def _run_os_grains_tests(self, os_release_filename, os_release_map, expectation):
        path_isfile_mock = MagicMock(side_effect=lambda x: x in os_release_map.get('files', []))
        empty_mock = MagicMock(return_value={})
        osarch_mock = MagicMock(return_value="amd64")
        if os_release_filename:
            os_release_data = core._parse_os_release(
                os.path.join(OS_RELEASE_DIR, os_release_filename)
            )
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

        suse_release_file = os_release_map.get('suse_release_file')

        file_contents = {'/proc/1/cmdline': ''}
        if suse_release_file:
            file_contents['/etc/SuSE-release'] = suse_release_file

        # - Skip the first if statement
        # - Skip the selinux/systemd stuff (not pertinent)
        # - Skip the init grain compilation (not pertinent)
        # - Ensure that lsb_release fails to import
        # - Skip all the /etc/*-release stuff (not pertinent)
        # - Mock linux_distribution to give us the OS name that we want
        # - Mock the osarch
        distro_mock = MagicMock(return_value=os_release_map['linux_distribution'])
        with patch.object(salt.utils.platform, 'is_proxy', MagicMock(return_value=False)), \
                patch.object(core, '_linux_bin_exists', MagicMock(return_value=False)), \
                patch.object(os.path, 'exists', path_isfile_mock), \
                patch('{0}.__import__'.format(built_in), side_effect=_import_mock), \
                patch.object(os.path, 'isfile', path_isfile_mock), \
                patch.object(core, '_parse_os_release', os_release_mock), \
                patch.object(core, '_parse_lsb_release', empty_mock), \
                patch('salt.utils.files.fopen', mock_open(read_data=file_contents)), \
                patch.object(core, 'linux_distribution', distro_mock), \
                patch.object(core, '_linux_gpu_data', empty_mock), \
                patch.object(core, '_linux_cpudata', empty_mock), \
                patch.object(core, '_virtual', empty_mock), \
                patch.dict(core.__salt__, {'cmd.run': osarch_mock}):
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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    def test_suse_os_grains_sles11sp3(self):
        '''
        Test if OS grains are parsed correctly in SLES 11 SP3
        '''
        _os_release_map = {
            'suse_release_file': textwrap.dedent('''
                SUSE Linux Enterprise Server 11 (x86_64)
                VERSION = 11
                PATCHLEVEL = 3
                '''),
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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
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

    @skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
    def test_windows_platform_data(self):
        '''
        Test the _windows_platform_data function
        '''
        grains = ['biosversion', 'kernelrelease', 'kernelversion',
                  'manufacturer', 'motherboard', 'osfullname', 'osmanufacturer',
                  'osrelease', 'osservicepack', 'osversion', 'productname',
                  'serialnumber', 'timezone', 'virtual', 'windowsdomain',
                  'windowsdomaintype']
        returned_grains = core._windows_platform_data()
        for grain in grains:
            self.assertIn(grain, returned_grains)

        valid_types = ['Unknown', 'Unjoined', 'Workgroup', 'Domain']
        self.assertIn(returned_grains['windowsdomaintype'], valid_types)
        valid_releases = ['Vista', '7', '8', '8.1', '10', '2008Server',
                          '2008ServerR2', '2012Server', '2012ServerR2',
                          '2016Server', '2019Server']
        self.assertIn(returned_grains['osrelease'], valid_releases)

    def test__windows_os_release_grain(self):
        versions = {
            'Windows 10 Home': '10',
            'Windows 10 Pro': '10',
            'Windows 10 Pro for Workstations': '10',
            'Windows 10 Pro Education': '10',
            'Windows 10 Enterprise': '10',
            'Windows 10 Enterprise LTSB': '10',
            'Windows 10 Education': '10',
            'Windows 10 IoT Core': '10',
            'Windows 10 IoT Enterprise': '10',
            'Windows 10 S': '10',
            'Windows 8.1': '8.1',
            'Windows 8.1 Pro': '8.1',
            'Windows 8.1 Enterprise': '8.1',
            'Windows 8.1 OEM': '8.1',
            'Windows 8.1 with Bing': '8.1',
            'Windows 8': '8',
            'Windows 8 Pro': '8',
            'Windows 8 Enterprise': '8',
            'Windows 8 OEM': '8',
            'Windows 7 Starter': '7',
            'Windows 7 Home Basic': '7',
            'Windows 7 Home Premium': '7',
            'Windows 7 Professional': '7',
            'Windows 7 Enterprise': '7',
            'Windows 7 Ultimate': '7',
            'Windows Thin PC': 'Thin',
            'Windows Vista Starter': 'Vista',
            'Windows Vista Home Basic': 'Vista',
            'Windows Vista Home Premium': 'Vista',
            'Windows Vista Business': 'Vista',
            'Windows Vista Enterprise': 'Vista',
            'Windows Vista Ultimate': 'Vista',
            'Windows Server 2019 Essentials': '2019Server',
            'Windows Server 2019 Standard': '2019Server',
            'Windows Server 2019 Datacenter': '2019Server',
            'Windows Server 2016 Essentials': '2016Server',
            'Windows Server 2016 Standard': '2016Server',
            'Windows Server 2016 Datacenter': '2016Server',
            'Windows Server 2012 R2 Foundation': '2012ServerR2',
            'Windows Server 2012 R2 Essentials': '2012ServerR2',
            'Windows Server 2012 R2 Standard': '2012ServerR2',
            'Windows Server 2012 R2 Datacenter': '2012ServerR2',
            'Windows Server 2012 Foundation': '2012Server',
            'Windows Server 2012 Essentials': '2012Server',
            'Windows Server 2012 Standard': '2012Server',
            'Windows Server 2012 Datacenter': '2012Server',
            'Windows MultiPoint Server 2012': '2012Server',
            'Windows Small Business Server 2011': '2011Server',
            'Windows MultiPoint Server 2011': '2011Server',
            'Windows Home Server 2011': '2011Server',
            'Windows MultiPoint Server 2010': '2010Server',
            'Windows Server 2008 R2 Foundation': '2008ServerR2',
            'Windows Server 2008 R2 Standard': '2008ServerR2',
            'Windows Server 2008 R2 Enterprise': '2008ServerR2',
            'Windows Server 2008 R2 Datacenter': '2008ServerR2',
            'Windows Server 2008 R2 for Itanium-based Systems': '2008ServerR2',
            'Windows Web Server 2008 R2': '2008ServerR2',
            'Windows Storage Server 2008 R2': '2008ServerR2',
            'Windows HPC Server 2008 R2': '2008ServerR2',
            'Windows Server 2008 Standard': '2008Server',
            'Windows Server 2008 Enterprise': '2008Server',
            'Windows Server 2008 Datacenter': '2008Server',
            'Windows Server 2008 for Itanium-based Systems': '2008Server',
            'Windows Server Foundation 2008': '2008Server',
            'Windows Essential Business Server 2008': '2008Server',
            'Windows HPC Server 2008': '2008Server',
            'Windows Small Business Server 2008': '2008Server',
            'Windows Storage Server 2008': '2008Server',
            'Windows Web Server 2008': '2008Server'
        }
        for caption in versions:
            version = core._windows_os_release_grain(caption, 1)
            self.assertEqual(
                version,
                versions[caption],
                'version: {0}\n'
                'found: {1}\n'
                'caption: {2}'.format(version, versions[caption], caption)
            )

        embedded_versions = {
            'Windows Embedded 8.1 Industry Pro': '8.1',
            'Windows Embedded 8 Industry Pro': '8',
            'Windows POSReady 7': '7',
            'Windows Embedded Standard 7': '7',
            'Windows Embedded POSReady 2009': '2009',
            'Windows Embedded Standard 2009': '2009',
            'Windows XP Embedded': 'XP',
        }
        for caption in embedded_versions:
            version = core._windows_os_release_grain(caption, 1)
            self.assertEqual(
                version,
                embedded_versions[caption],
                '{0} != {1}\n'
                'version: {0}\n'
                'found: {1}\n'
                'caption: {2}'.format(version, embedded_versions[caption], caption)
            )

        # Special Cases
        # Windows Embedded Standard is Windows 7
        caption = 'Windows Embedded Standard'
        with patch('platform.release', MagicMock(return_value='7')):
            version = core._windows_os_release_grain(caption, 1)
            self.assertEqual(version, '7')

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    def test_linux_memdata(self):
        '''
        Test memdata on Linux systems
        '''
        _proc_meminfo = textwrap.dedent('''\
            MemTotal:       16277028 kB
            SwapTotal:       4789244 kB''')
        with patch('salt.utils.files.fopen', mock_open(read_data=_proc_meminfo)):
            memdata = core._linux_memdata()
        self.assertEqual(memdata.get('mem_total'), 15895)
        self.assertEqual(memdata.get('swap_total'), 4676)

    @skipIf(salt.utils.platform.is_windows(), 'System is Windows')
    def test_bsd_memdata(self):
        '''
        Test to memdata on *BSD systems
        '''
        _path_exists_map = {}
        _path_isfile_map = {}
        _cmd_run_map = {
            'freebsd-version -u': '10.3-RELEASE',
            '/sbin/sysctl -n hw.physmem': '2121781248',
            '/sbin/sysctl -n vm.swap_total': '419430400'
        }

        path_exists_mock = MagicMock(side_effect=lambda x: _path_exists_map[x])
        path_isfile_mock = MagicMock(
            side_effect=lambda x: _path_isfile_map.get(x, False)
        )
        cmd_run_mock = MagicMock(
            side_effect=lambda x: _cmd_run_map[x]
        )
        empty_mock = MagicMock(return_value={})

        mock_freebsd_uname = ('FreeBSD',
                              'freebsd10.3-hostname-8148',
                              '10.3-RELEASE',
                              'FreeBSD 10.3-RELEASE #0 r297264: Fri Mar 25 02:10:02 UTC 2016     root@releng1.nyi.freebsd.org:/usr/obj/usr/src/sys/GENERIC',
                              'amd64',
                              'amd64')

        with patch('platform.uname',
                   MagicMock(return_value=mock_freebsd_uname)):
            with patch.object(salt.utils.platform, 'is_linux',
                              MagicMock(return_value=False)):
                with patch.object(salt.utils.platform, 'is_freebsd',
                                  MagicMock(return_value=True)):
                    # Skip the first if statement
                    with patch.object(salt.utils.platform, 'is_proxy',
                                      MagicMock(return_value=False)):
                        # Skip the init grain compilation (not pertinent)
                        with patch.object(os.path, 'exists', path_exists_mock):
                            with patch('salt.utils.path.which') as mock:
                                mock.return_value = '/sbin/sysctl'
                                # Make a bunch of functions return empty dicts,
                                # we don't care about these grains for the
                                # purposes of this test.
                                with patch.object(
                                        core,
                                        '_bsd_cpudata',
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

        self.assertEqual(os_grains.get('mem_total'), 2023)
        self.assertEqual(os_grains.get('swap_total'), 400)

    @skipIf(salt.utils.platform.is_windows(), 'System is Windows')
    def test_docker_virtual(self):
        '''
        Test if virtual grains are parsed correctly in Docker.
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
                    with patch('salt.utils.files.fopen', mock_open(read_data=cgroup_data)):
                        with patch.dict(core.__salt__, {'cmd.run_all': MagicMock()}):
                            grains = core._virtual({'kernel': 'Linux'})
                            self.assertEqual(
                                grains.get('virtual_subtype'),
                                'Docker'
                            )
                            self.assertEqual(
                                grains.get('virtual'),
                                'container',
                            )

    @skipIf(salt.utils.platform.is_windows(), 'System is Windows')
    def test_lxc_virtual(self):
        '''
        Test if virtual grains are parsed correctly in LXC.
        '''
        with patch.object(os.path, 'isdir', MagicMock(return_value=False)):
            with patch.object(os.path,
                              'isfile',
                              MagicMock(side_effect=lambda x: True if x == '/proc/1/cgroup' else False)):
                cgroup_data = '10:memory:/lxc/a_long_sha256sum'
                with patch('salt.utils.files.fopen', mock_open(read_data=cgroup_data)):
                    with patch.dict(core.__salt__, {'cmd.run_all': MagicMock()}):
                        grains = core._virtual({'kernel': 'Linux'})
                        self.assertEqual(
                            grains.get('virtual_subtype'),
                            'LXC'
                        )
                        self.assertEqual(
                            grains.get('virtual'),
                            'container',
                        )

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    def test_xen_virtual(self):
        '''
        Test if OS grains are parsed correctly in Ubuntu Xenial Xerus
        '''
        with patch.multiple(os.path, isdir=MagicMock(side_effect=lambda x: x == '/sys/bus/xen'),
                            isfile=MagicMock(side_effect=lambda x:
                                             x == '/sys/bus/xen/drivers/xenconsole')):
            with patch.dict(core.__salt__, {'cmd.run': MagicMock(return_value='')}):
                log.debug('Testing Xen')
                self.assertEqual(
                    core._virtual({'kernel': 'Linux'}).get('virtual_subtype'),
                    'Xen PV DomU'
                )

    def test_if_virtual_subtype_exists_virtual_should_fallback_to_virtual(self):
        def mockstat(path):
            if path == '/':
                return 'fnord'
            elif path == '/proc/1/root/.':
                return 'roscivs'
            return None
        with patch.dict(
            core.__salt__,
            {
                'cmd.run': MagicMock(return_value=''),
                'cmd.run_all': MagicMock(return_value={'retcode': 0, 'stdout': ''}),
            }
        ):
            with patch.multiple(
                os.path,
                isfile=MagicMock(return_value=False),
                isdir=MagicMock(side_effect=lambda x: x == '/proc'),
            ):
                with patch.multiple(
                    os,
                    stat=MagicMock(side_effect=mockstat),
                ):
                    grains = core._virtual({'kernel': 'Linux'})
                    assert grains.get('virtual_subtype') is not None
                    assert grains.get('virtual') == 'virtual'

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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    def test_fqdn_return(self):
        '''
        test ip4 and ip6 return values
        '''
        net_ip4_mock = [IP4_LOCAL, IP4_ADD1, IP4_ADD2]
        net_ip6_mock = [IP6_LOCAL, IP6_ADD1, IP6_ADD2]

        self._run_fqdn_tests(net_ip4_mock, net_ip6_mock,
                             ip4_empty=False, ip6_empty=False)

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    def test_fqdn6_empty(self):
        '''
        test when ip6 is empty
        '''
        net_ip4_mock = [IP4_LOCAL, IP4_ADD1, IP4_ADD2]
        net_ip6_mock = []

        self._run_fqdn_tests(net_ip4_mock, net_ip6_mock,
                             ip4_empty=False)

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    def test_fqdn4_empty(self):
        '''
        test when ip4 is empty
        '''
        net_ip4_mock = []
        net_ip6_mock = [IP6_LOCAL, IP6_ADD1, IP6_ADD2]

        self._run_fqdn_tests(net_ip4_mock, net_ip6_mock,
                             ip6_empty=False)

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    @patch.object(salt.utils.platform, 'is_windows', MagicMock(return_value=False))
    @patch('salt.grains.core.__opts__', {'ipv6': False})
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
        with patch.object(salt.utils.dns, 'parse_resolv', MagicMock(return_value=resolv_mock)):
            assert core.dns() == ret

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    @patch.object(salt.utils, 'is_windows', MagicMock(return_value=False))
    @patch('salt.utils.network.ip_addrs', MagicMock(return_value=['1.2.3.4', '5.6.7.8']))
    @patch('salt.utils.network.ip_addrs6',
           MagicMock(return_value=['fe80::a8b2:93ff:fe00:0', 'fe80::a8b2:93ff:dead:beef']))
    @patch('salt.utils.network.socket.getfqdn', MagicMock(side_effect=lambda v: v))  # Just pass-through
    def test_fqdns_return(self):
        '''
        test the return for a dns grain. test for issue:
        https://github.com/saltstack/salt/issues/41230
        '''
        reverse_resolv_mock = [('foo.bar.baz', [], ['1.2.3.4']),
                               ('rinzler.evil-corp.com', [], ['5.6.7.8']),
                               ('foo.bar.baz', [], ['fe80::a8b2:93ff:fe00:0']),
                               ('bluesniff.foo.bar', [], ['fe80::a8b2:93ff:dead:beef'])]
        ret = {'fqdns': ['bluesniff.foo.bar', 'foo.bar.baz', 'rinzler.evil-corp.com']}
        with patch.object(socket, 'gethostbyaddr', side_effect=reverse_resolv_mock):
            fqdns = core.fqdns()
            self.assertIn('fqdns', fqdns)
            self.assertEqual(len(fqdns['fqdns']), len(ret['fqdns']))
            self.assertEqual(set(fqdns['fqdns']), set(ret['fqdns']))

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    @patch.object(salt.utils, 'is_windows', MagicMock(return_value=False))
    @patch('salt.utils.network.ip_addrs', MagicMock(return_value=['1.2.3.4']))
    @patch('salt.utils.network.ip_addrs6', MagicMock(return_value=[]))
    def test_fqdns_socket_error(self):
        '''
        test the behavior on non-critical socket errors of the dns grain
        '''
        def _gen_gethostbyaddr(errno):
            def _gethostbyaddr(_):
                herror = socket.herror()
                herror.errno = errno
                raise herror
            return _gethostbyaddr

        for errno in (0, core.HOST_NOT_FOUND, core.NO_DATA):
            mock_log = MagicMock()
            with patch.object(socket, 'gethostbyaddr',
                              side_effect=_gen_gethostbyaddr(errno)):
                with patch('salt.grains.core.log', mock_log):
                    self.assertEqual(core.fqdns(), {'fqdns': []})
                    mock_log.debug.assert_called_once()
                    mock_log.error.assert_not_called()

        mock_log = MagicMock()
        with patch.object(socket, 'gethostbyaddr',
                          side_effect=_gen_gethostbyaddr(-1)):
            with patch('salt.grains.core.log', mock_log):
                self.assertEqual(core.fqdns(), {'fqdns': []})
                mock_log.debug.assert_not_called()
                mock_log.error.assert_called_once()

    def test_core_virtual(self):
        '''
        test virtual grain with cmd virt-what
        '''
        virt = 'kvm'
        with patch.object(salt.utils.platform, 'is_windows',
                          MagicMock(return_value=False)):
            with patch.object(salt.utils.path, 'which',
                              MagicMock(return_value=True)):
                with patch.dict(core.__salt__, {'cmd.run_all':
                                                MagicMock(return_value={'pid': 78,
                                                                        'retcode': 0,
                                                                        'stderr': '',
                                                                        'stdout': virt})}):
                    osdata = {'kernel': 'test', }
                    ret = core._virtual(osdata)
                    self.assertEqual(ret['virtual'], virt)

    def test_solaris_sparc_s7zone(self):
        '''
        verify productname grain for s7 zone
        '''
        expectation = {
                'productname': 'SPARC S7-2',
                'product': 'SPARC S7-2',
        }
        with salt.utils.files.fopen(os.path.join(SOLARIS_DIR, 'prtconf.s7-zone')) as sparc_return_data:
            this_sparc_return_data = '\n'.join(sparc_return_data.readlines())
            this_sparc_return_data += '\n'
        self._check_solaris_sparc_productname_grains(this_sparc_return_data, expectation)

    def test_solaris_sparc_s7(self):
        '''
        verify productname grain for s7
        '''
        expectation = {
                'productname': 'SPARC S7-2',
                'product': 'SPARC S7-2',
        }
        with salt.utils.files.fopen(os.path.join(SOLARIS_DIR, 'prtdiag.s7')) as sparc_return_data:
            this_sparc_return_data = '\n'.join(sparc_return_data.readlines())
            this_sparc_return_data += '\n'
        self._check_solaris_sparc_productname_grains(this_sparc_return_data, expectation)

    def test_solaris_sparc_t5220(self):
        '''
        verify productname grain for t5220
        '''
        expectation = {
                'productname': 'SPARC Enterprise T5220',
                'product': 'SPARC Enterprise T5220',
        }
        with salt.utils.files.fopen(os.path.join(SOLARIS_DIR, 'prtdiag.t5220')) as sparc_return_data:
            this_sparc_return_data = '\n'.join(sparc_return_data.readlines())
            this_sparc_return_data += '\n'
        self._check_solaris_sparc_productname_grains(this_sparc_return_data, expectation)

    def test_solaris_sparc_t5220zone(self):
        '''
        verify productname grain for t5220 zone
        '''
        expectation = {
                'productname': 'SPARC Enterprise T5220',
                'product': 'SPARC Enterprise T5220',
        }
        with salt.utils.files.fopen(os.path.join(SOLARIS_DIR, 'prtconf.t5220-zone')) as sparc_return_data:
            this_sparc_return_data = '\n'.join(sparc_return_data.readlines())
            this_sparc_return_data += '\n'
        self._check_solaris_sparc_productname_grains(this_sparc_return_data, expectation)

    def _check_solaris_sparc_productname_grains(self, prtdata, expectation):
        '''
        verify product grains on solaris sparc
        '''
        import platform
        path_isfile_mock = MagicMock(side_effect=lambda x: x in ['/etc/release'])
        with salt.utils.files.fopen(os.path.join(OS_RELEASE_DIR, "solaris-11.3")) as os_release_file:
            os_release_content = os_release_file.readlines()
        uname_mock = MagicMock(return_value=(
            'SunOS', 'testsystem', '5.11', '11.3', 'sunv4', 'sparc'
        ))
        with patch.object(platform, 'uname', uname_mock), \
                patch.object(salt.utils.platform, 'is_proxy',
                             MagicMock(return_value=False)), \
                patch.object(salt.utils.platform, 'is_linux',
                             MagicMock(return_value=False)), \
                patch.object(salt.utils.platform, 'is_windows',
                             MagicMock(return_value=False)), \
                patch.object(salt.utils.platform, 'is_smartos',
                             MagicMock(return_value=False)), \
                patch.object(salt.utils.path, 'which_bin',
                             MagicMock(return_value=None)), \
                patch.object(os.path, 'isfile', path_isfile_mock), \
                patch('salt.utils.files.fopen',
                      mock_open(read_data=os_release_content)) as os_release_file, \
                patch.object(core, '_sunos_cpudata',
                             MagicMock(return_value={
                                 'cpuarch': 'sparcv9',
                                 'num_cpus': '1',
                                 'cpu_model': 'MOCK_CPU_MODEL',
                                 'cpu_flags': []})), \
                patch.object(core, '_memdata',
                             MagicMock(return_value={'mem_total': 16384})), \
                patch.object(core, '_virtual',
                             MagicMock(return_value={})), \
                patch.object(core, '_ps', MagicMock(return_value={})), \
                patch.object(salt.utils.path, 'which',
                             MagicMock(return_value=True)), \
                patch.dict(core.__salt__,
                           {'cmd.run': MagicMock(return_value=prtdata)}):
            os_grains = core.os_data()
        grains = {k: v for k, v in os_grains.items()
                  if k in set(['product', 'productname'])}
        self.assertEqual(grains, expectation)

    @patch('os.path.isfile')
    @patch('os.path.isdir')
    def test_core_virtual_unicode(self, mock_file, mock_dir):
        '''
        test virtual grain with unicode character in product_name file
        '''
        def path_side_effect(path):
            if path == '/sys/devices/virtual/dmi/id/product_name':
                return True
            return False

        virt = 'kvm'
        mock_file.side_effect = path_side_effect
        mock_dir.side_effect = path_side_effect
        with patch.object(salt.utils.platform, 'is_windows',
                          MagicMock(return_value=False)):
            with patch.object(salt.utils.path, 'which',
                              MagicMock(return_value=True)):
                with patch.dict(core.__salt__, {'cmd.run_all':
                                                MagicMock(return_value={'pid': 78,
                                                                        'retcode': 0,
                                                                        'stderr': '',
                                                                        'stdout': virt})}):
                    with patch('salt.utils.files.fopen',
                               mock_open(read_data='嗨')):
                        osdata = {'kernel': 'Linux', }
                        ret = core._virtual(osdata)
                        self.assertEqual(ret['virtual'], virt)

    @patch('salt.utils.path.which', MagicMock(return_value='/usr/sbin/sysctl'))
    def test_osx_memdata_with_comma(self):
        '''
        test osx memdata method when comma returns
        '''
        def _cmd_side_effect(cmd):
            if 'hw.memsize' in cmd:
                return '4294967296'
            elif 'vm.swapusage' in cmd:
                return 'total = 1024,00M  used = 160,75M  free = 863,25M  (encrypted)'
        with patch.dict(core.__salt__, {'cmd.run': MagicMock(side_effect=_cmd_side_effect)}):
            ret = core._osx_memdata()
            assert ret['swap_total'] == 1024
            assert ret['mem_total'] == 4096

    @patch('salt.utils.path.which', MagicMock(return_value='/usr/sbin/sysctl'))
    def test_osx_memdata(self):
        '''
        test osx memdata
        '''
        def _cmd_side_effect(cmd):
            if 'hw.memsize' in cmd:
                return '4294967296'
            elif 'vm.swapusage' in cmd:
                return 'total = 0.00M  used = 0.00M  free = 0.00M  (encrypted)'
        with patch.dict(core.__salt__, {'cmd.run': MagicMock(side_effect=_cmd_side_effect)}):
            ret = core._osx_memdata()
            assert ret['swap_total'] == 0
            assert ret['mem_total'] == 4096

    @skipIf(not core._DATEUTIL_TZ, 'Missing dateutil.tz')
    def test_locale_info_tzname(self):
        # mock datetime.now().tzname()
        # cant just mock now because it is read only
        tzname = Mock(return_value='MDT_FAKE')
        now_ret_object = Mock(tzname=tzname)
        now = Mock(return_value=now_ret_object)
        datetime = Mock(now=now)

        with patch.object(core, 'datetime', datetime=datetime) as datetime_module:
            with patch.object(core.dateutil.tz, 'tzlocal', return_value=object) as tzlocal:
                with patch.object(salt.utils.platform, 'is_proxy', return_value=False) as is_proxy:
                    ret = core.locale_info()

                    tzname.assert_called_once_with()
                    self.assertEqual(len(now_ret_object.method_calls), 1)
                    now.assert_called_once_with(object)
                    self.assertEqual(len(datetime.method_calls), 1)
                    self.assertEqual(len(datetime_module.method_calls), 1)
                    tzlocal.assert_called_once_with()
                    is_proxy.assert_called_once_with()

                    self.assertEqual(ret['locale_info']['timezone'], 'MDT_FAKE')

    @skipIf(not core._DATEUTIL_TZ, 'Missing dateutil.tz')
    def test_locale_info_unicode_error_tzname(self):
        # UnicodeDecodeError most have the default string encoding
        unicode_error = UnicodeDecodeError(str('fake'), b'\x00\x00', 1, 2, str('fake'))

        # mock datetime.now().tzname()
        # cant just mock now because it is read only
        tzname = Mock(return_value='MDT_FAKE')
        now_ret_object = Mock(tzname=tzname)
        now = Mock(return_value=now_ret_object)
        datetime = Mock(now=now)

        # mock tzname[0].decode()
        decode = Mock(return_value='CST_FAKE')
        tzname2 = (Mock(decode=decode,),)

        with patch.object(core, 'datetime', datetime=datetime) as datetime_module:
            with patch.object(core.dateutil.tz, 'tzlocal', side_effect=unicode_error) as tzlocal:
                with patch.object(salt.utils.platform, 'is_proxy', return_value=False) as is_proxy:
                    with patch.object(core.salt.utils.platform, 'is_windows', return_value=True) as is_windows:
                        with patch.object(core, 'time', tzname=tzname2):
                            ret = core.locale_info()

                            tzname.assert_not_called()
                            self.assertEqual(len(now_ret_object.method_calls), 0)
                            now.assert_not_called()
                            self.assertEqual(len(datetime.method_calls), 0)
                            decode.assert_called_once_with('mbcs')
                            self.assertEqual(len(tzname2[0].method_calls), 1)
                            self.assertEqual(len(datetime_module.method_calls), 0)
                            tzlocal.assert_called_once_with()
                            is_proxy.assert_called_once_with()
                            is_windows.assert_called_once_with()

                            self.assertEqual(ret['locale_info']['timezone'], 'CST_FAKE')

    @skipIf(core._DATEUTIL_TZ, 'Not Missing dateutil.tz')
    def test_locale_info_no_tz_tzname(self):
        with patch.object(salt.utils.platform, 'is_proxy', return_value=False) as is_proxy:
            with patch.object(core.salt.utils.platform, 'is_windows', return_value=True) as is_windows:
                ret = core.locale_info()
                is_proxy.assert_called_once_with()
                is_windows.assert_not_called()
                self.assertEqual(ret['locale_info']['timezone'], 'unknown')

    def test_cwd_exists(self):
        cwd_grain = core.cwd()

        self.assertIsInstance(cwd_grain, dict)
        self.assertTrue('cwd' in cwd_grain)
        self.assertEqual(cwd_grain['cwd'], os.getcwd())

    def test_cwd_is_cwd(self):
        cwd = os.getcwd()

        try:
            # change directory
            new_dir = os.path.split(cwd)[0]
            os.chdir(new_dir)

            cwd_grain = core.cwd()

            self.assertEqual(cwd_grain['cwd'], new_dir)
        finally:
            # change back to original directory
            os.chdir(cwd)

    def test_virtual_set_virtual_grain(self):
        osdata = {}

        (osdata['kernel'], osdata['nodename'],
         osdata['kernelrelease'], osdata['kernelversion'], osdata['cpuarch'], _) = platform.uname()

        with patch.dict(core.__salt__, {'cmd.run': salt.modules.cmdmod.run,
                                        'cmd.run_all': salt.modules.cmdmod.run_all,
                                        'cmd.retcode': salt.modules.cmdmod.retcode,
                                        'smbios.get': salt.modules.smbios.get}):

            virtual_grains = core._virtual(osdata)

        self.assertIn('virtual', virtual_grains)

    def test_virtual_has_virtual_grain(self):
        osdata = {'virtual': 'something'}

        (osdata['kernel'], osdata['nodename'],
         osdata['kernelrelease'], osdata['kernelversion'], osdata['cpuarch'], _) = platform.uname()

        with patch.dict(core.__salt__, {'cmd.run': salt.modules.cmdmod.run,
                                        'cmd.run_all': salt.modules.cmdmod.run_all,
                                        'cmd.retcode': salt.modules.cmdmod.retcode,
                                        'smbios.get': salt.modules.smbios.get}):

            virtual_grains = core._virtual(osdata)

        self.assertIn('virtual', virtual_grains)
        self.assertNotEqual(virtual_grains['virtual'], 'physical')

    @skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
    def test_osdata_virtual_key_win(self):
        with patch.dict(core.__salt__, {'cmd.run': salt.modules.cmdmod.run,
                                        'cmd.run_all': salt.modules.cmdmod.run_all,
                                        'cmd.retcode': salt.modules.cmdmod.retcode,
                                        'smbios.get': salt.modules.smbios.get}):
            with patch.object(core,
                              '_windows_virtual',
                              return_value={'virtual': 'something'}) as _windows_virtual:
                osdata_grains = core.os_data()
                _windows_virtual.assert_called_once()

            self.assertIn('virtual', osdata_grains)
            self.assertNotEqual(osdata_grains['virtual'], 'physical')
