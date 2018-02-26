# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Erik Johnson <erik@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os

# Import Salt Testing Libs
try:
    import pytest
except ImportError as import_error:
    pytest = None

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
import salt.utils.platform
import salt.grains.core as core

# Import 3rd-party libs
from salt.ext import six
if six.PY3:
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddress

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


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not pytest, False)
class CoreGrainsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for core grains
    '''
    def setup_loader_modules(self):
        return {core: {}}

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
        with patch.object(salt.utils.platform, 'is_proxy',
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

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    def test_suse_os_from_cpe_data(self):
        '''
        Test if 'os' grain is parsed from CPE_NAME of /etc/os-release
        '''
        _path_exists_map = {
            '/proc/1/cmdline': False
        }
        _path_isfile_map = {
            '/etc/os-release': True,
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
        path_isfile_mock = MagicMock(
            side_effect=lambda x: _path_isfile_map.get(x, False)
        )
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
        with patch.object(salt.utils.platform, 'is_proxy',
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
                            with patch.object(core, '_parse_os_release', os_release_mock):
                                # Mock linux_distribution to give us the OS
                                # name that we want.
                                distro_mock = MagicMock(
                                    return_value=('SUSE Linux Enterprise Server ', '12', 'x86_64')
                                )
                                with patch.object(core, 'linux_distribution', distro_mock):
                                    with patch.object(core, '_linux_gpu_data', empty_mock):
                                        with patch.object(core, '_hw_data', empty_mock):
                                            with patch.object(core, '_linux_cpudata', empty_mock):
                                                with patch.object(core, '_virtual', empty_mock):
                                                    # Mock the osarch
                                                    with patch.dict(core.__salt__, {'cmd.run': osarch_mock}):
                                                        os_grains = core.os_data()

        self.assertEqual(os_grains.get('os_family'), 'Suse')
        self.assertEqual(os_grains.get('os'), 'SUSE')

    def _run_suse_os_grains_tests(self, os_release_map):
        path_isfile_mock = MagicMock(side_effect=lambda x: x in os_release_map['files'])
        empty_mock = MagicMock(return_value={})
        osarch_mock = MagicMock(return_value="amd64")
        os_release_mock = MagicMock(return_value=os_release_map.get('os_release_file'))

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
        with patch.object(salt.utils.platform, 'is_proxy',
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
                                    return_value=('SUSE test', 'version', 'arch')
                                )
                                with patch('salt.utils.files.fopen', mock_open()) as suse_release_file:
                                    suse_release_file.return_value.__iter__.return_value = os_release_map.get('suse_release_file', '').splitlines()
                                    with patch.object(core, 'linux_distribution', distro_mock):
                                        with patch.object(core, '_linux_gpu_data', empty_mock):
                                            with patch.object(core, '_linux_cpudata', empty_mock):
                                                with patch.object(core, '_virtual', empty_mock):
                                                    # Mock the osarch
                                                    with patch.dict(core.__salt__, {'cmd.run': osarch_mock}):
                                                        os_grains = core.os_data()

        self.assertEqual(os_grains.get('os'), 'SUSE')
        self.assertEqual(os_grains.get('os_family'), 'Suse')
        self.assertEqual(os_grains.get('osfullname'), os_release_map['osfullname'])
        self.assertEqual(os_grains.get('oscodename'), os_release_map['oscodename'])
        self.assertEqual(os_grains.get('osrelease'), os_release_map['osrelease'])
        self.assertListEqual(list(os_grains.get('osrelease_info')), os_release_map['osrelease_info'])
        self.assertEqual(os_grains.get('osmajorrelease'), os_release_map['osmajorrelease'])

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    def test_suse_os_grains_sles11sp3(self):
        '''
        Test if OS grains are parsed correctly in SLES 11 SP3
        '''
        _os_release_map = {
            'suse_release_file': '''SUSE Linux Enterprise Server 11 (x86_64)
VERSION = 11
PATCHLEVEL = 3
''',
            'oscodename': 'SUSE Linux Enterprise Server 11 SP3',
            'osfullname': "SLES",
            'osrelease': '11.3',
            'osrelease_info': [11, 3],
            'osmajorrelease': 11,
            'files': ["/etc/SuSE-release"],
        }
        self._run_suse_os_grains_tests(_os_release_map)

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
            'oscodename': 'SUSE Linux Enterprise Server 11 SP4',
            'osfullname': "SLES",
            'osrelease': '11.4',
            'osrelease_info': [11, 4],
            'osmajorrelease': 11,
            'files': ["/etc/os-release"],
        }
        self._run_suse_os_grains_tests(_os_release_map)

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
            'oscodename': 'SUSE Linux Enterprise Server 12',
            'osfullname': "SLES",
            'osrelease': '12',
            'osrelease_info': [12],
            'osmajorrelease': 12,
            'files': ["/etc/os-release"],
        }
        self._run_suse_os_grains_tests(_os_release_map)

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
            'oscodename': 'SUSE Linux Enterprise Server 12 SP1',
            'osfullname': "SLES",
            'osrelease': '12.1',
            'osrelease_info': [12, 1],
            'osmajorrelease': 12,
            'files': ["/etc/os-release"],
        }
        self._run_suse_os_grains_tests(_os_release_map)

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
            'oscodename': 'openSUSE Leap 42.1 (x86_64)',
            'osfullname': "Leap",
            'osrelease': '42.1',
            'osrelease_info': [42, 1],
            'osmajorrelease': 42,
            'files': ["/etc/os-release"],
        }
        self._run_suse_os_grains_tests(_os_release_map)

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
            'oscodename': 'openSUSE Tumbleweed (20160504) (x86_64)',
            'osfullname': "Tumbleweed",
            'osrelease': '20160504',
            'osrelease_info': [20160504],
            'osmajorrelease': 20160504,
            'files': ["/etc/os-release"],
        }
        self._run_suse_os_grains_tests(_os_release_map)

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    def test_ubuntu_os_grains(self):
        '''
        Test if OS grains are parsed correctly in Ubuntu Xenial Xerus
        '''
        _os_release_map = {
            'os_release_file': {
                'NAME': 'Ubuntu',
                'VERSION': '16.04.1 LTS (Xenial Xerus)',
                'VERSION_ID': '16.04',
                'PRETTY_NAME': '',
                'ID': 'ubuntu',
            },
            'oscodename': 'xenial',
            'osfullname': 'Ubuntu',
            'osrelease': '16.04',
            'osrelease_info': [16, 4],
            'osmajorrelease': 16,
            'osfinger': 'Ubuntu-16.04',
        }
        self._run_ubuntu_os_grains_tests(_os_release_map)

    def _run_ubuntu_os_grains_tests(self, os_release_map):
        path_isfile_mock = MagicMock(side_effect=lambda x: x in ['/etc/os-release'])
        empty_mock = MagicMock(return_value={})
        osarch_mock = MagicMock(return_value="amd64")
        os_release_mock = MagicMock(return_value=os_release_map.get('os_release_file'))

        if six.PY2:
            built_in = '__builtin__'
        else:
            built_in = 'builtins'

        orig_import = __import__

        def _import_mock(name, *args):
            if name == 'lsb_release':
                raise ImportError('No module named lsb_release')
            return orig_import(name, *args)

        # Skip the first if statement
        with patch.object(salt.utils.platform, 'is_proxy',
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
                                distro_mock = MagicMock(return_value=('Ubuntu', '16.04', 'xenial'))
                                with patch('salt.utils.files.fopen', mock_open()) as suse_release_file:
                                    suse_release_file.return_value.__iter__.return_value = os_release_map.get(
                                        'suse_release_file', '').splitlines()
                                    with patch.object(core, 'linux_distribution', distro_mock):
                                        with patch.object(core, '_linux_gpu_data', empty_mock):
                                            with patch.object(core, '_linux_cpudata', empty_mock):
                                                with patch.object(core, '_virtual', empty_mock):
                                                    # Mock the osarch
                                                    with patch.dict(core.__salt__, {'cmd.run': osarch_mock}):
                                                        os_grains = core.os_data()

        self.assertEqual(os_grains.get('os'), 'Ubuntu')
        self.assertEqual(os_grains.get('os_family'), 'Debian')
        self.assertEqual(os_grains.get('osfullname'), os_release_map['osfullname'])
        self.assertEqual(os_grains.get('oscodename'), os_release_map['oscodename'])
        self.assertEqual(os_grains.get('osrelease'), os_release_map['osrelease'])
        self.assertListEqual(list(os_grains.get('osrelease_info')), os_release_map['osrelease_info'])
        self.assertEqual(os_grains.get('osmajorrelease'), os_release_map['osmajorrelease'])

    def test_windows_iscsi_iqn_grains(self):
        cmd_run_mock = MagicMock(
            return_value={'stdout': 'iSCSINodeName\niqn.1991-05.com.microsoft:simon-x1\n'}
        )

        with patch.object(salt.utils.platform, 'is_linux',
                          MagicMock(return_value=False)):
            with patch.object(salt.utils.platform, 'is_windows',
                              MagicMock(return_value=True)):
                with patch.dict(core.__salt__, {'run_all': cmd_run_mock}):
                    with patch.object(salt.utils.path, 'which',
                                      MagicMock(return_value=True)):
                        with patch.dict(core.__salt__, {'cmd.run_all': cmd_run_mock}):
                            _grains = core.iscsi_iqn()

        self.assertEqual(_grains.get('iscsi_iqn'),
                         ['iqn.1991-05.com.microsoft:simon-x1'])

    @skipIf(salt.utils.platform.is_windows(), 'System is Windows')
    def test_aix_iscsi_iqn_grains(self):
        cmd_run_mock = MagicMock(
            return_value='initiator_name iqn.localhost.hostid.7f000001'
        )

        with patch.object(salt.utils.platform, 'is_linux',
                          MagicMock(return_value=False)):
            with patch.object(salt.utils.platform, 'is_aix',
                              MagicMock(return_value=True)):
                with patch.dict(core.__salt__, {'cmd.run': cmd_run_mock}):
                    _grains = core.iscsi_iqn()

        self.assertEqual(_grains.get('iscsi_iqn'),
                         ['iqn.localhost.hostid.7f000001'])

    @patch('salt.grains.core.os.path.isfile', MagicMock(return_value=True))
    @patch('salt.grains.core.os.access', MagicMock(return_value=True))
    def test_linux_iscsi_iqn_grains(self):
        _iscsi_file = '## DO NOT EDIT OR REMOVE THIS FILE!\n' \
                      '## If you remove this file, the iSCSI daemon will not start.\n' \
                      '## If you change the InitiatorName, existing access control lists\n' \
                      '## may reject this initiator.  The InitiatorName must be unique\n' \
                      '## for each iSCSI initiator.  Do NOT duplicate iSCSI InitiatorNames.\n' \
                      'InitiatorName=iqn.1993-08.org.debian:01:d12f7aba36\n'

        with patch('salt.utils.files.fopen', mock_open()) as iscsi_initiator_file:
            iscsi_initiator_file.return_value.__iter__.return_value = _iscsi_file.splitlines()
            iqn = core._linux_iqn()

        assert isinstance(iqn, list)
        assert len(iqn) == 1
        assert iqn == ['iqn.1993-08.org.debian:01:d12f7aba36']

    @skipIf(not salt.utils.platform.is_linux(), 'System is not Linux')
    def test_linux_memdata(self):
        '''
        Test memdata on Linux systems
        '''
        _path_exists_map = {
            '/proc/1/cmdline': False,
            '/proc/meminfo': True
        }
        _path_isfile_map = {
            '/proc/meminfo': True
        }
        _cmd_run_map = {
            'dpkg --print-architecture': 'amd64',
            'rpm --eval %{_host_cpu}': 'x86_64'
        }

        path_exists_mock = MagicMock(side_effect=lambda x: _path_exists_map[x])
        path_isfile_mock = MagicMock(
            side_effect=lambda x: _path_isfile_map.get(x, False)
        )
        cmd_run_mock = MagicMock(
            side_effect=lambda x: _cmd_run_map[x]
        )
        empty_mock = MagicMock(return_value={})

        _proc_meminfo_file = '''MemTotal:       16277028 kB
SwapTotal:       4789244 kB'''

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
        with patch.object(salt.utils.platform, 'is_proxy',
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
                                    with patch('salt.utils.files.fopen', mock_open()) as _proc_meminfo:
                                        _proc_meminfo.return_value.__iter__.return_value = _proc_meminfo_file.splitlines()
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

        self.assertEqual(os_grains.get('mem_total'), 15895)
        self.assertEqual(os_grains.get('swap_total'), 4676)

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
                    with patch('salt.utils.files.fopen', mock_open(read_data=cgroup_data)):
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
                    ipaddress.IPv6Address(IP6_ADD1)], 'ip4_nameservers':
                   [ipaddress.IPv4Address(IP4_ADD1)],
                   'search': ['test.saltstack.com'], 'ip6_nameservers':
                   [ipaddress.IPv6Address(IP6_ADD1)], 'options': []}
        ret = {'dns': {'domain': '', 'sortlist': [], 'nameservers':
                       [IP4_ADD1, IP6_ADD1], 'ip4_nameservers':
                       [IP4_ADD1], 'search': ['test.saltstack.com'],
                       'ip6_nameservers': [IP6_ADD1], 'options':
                       []}}
        with patch.object(salt.utils.dns, 'parse_resolv', MagicMock(return_value=resolv_mock)):
            assert core.dns() == ret

    @patch('salt.utils.files.fopen', MagicMock(side_effect=IOError(os.errno.EPERM,
                                                                   'The cables are not the same length.')))
    @patch('salt.grains.core.log', MagicMock())
    def test_linux_iqn_non_root(self):
        '''
        Test if linux_iqn is running on salt-master as non-root
        and handling access denial properly.
        :return:
        '''
        assert core._linux_iqn() == []
        core.log.debug.assert_called()
        assert 'Error while accessing' in core.log.debug.call_args[0][0]
        assert 'cables are not the same' in core.log.debug.call_args[0][2].strerror
        assert core.log.debug.call_args[0][2].errno == os.errno.EPERM
        assert core.log.debug.call_args[0][1] == '/etc/iscsi/initiatorname.iscsi'

    @patch('salt.utils.files.fopen', MagicMock(side_effect=IOError(os.errno.ENOENT, '')))
    @patch('salt.grains.core.log', MagicMock())
    def test_linux_iqn_no_iscsii_initiator(self):
        '''
        Test if linux_iqn is running on salt-master as root.
        iscsii initiator is not there accessible or is not supported.
        :return:
        '''
        assert core._linux_iqn() == []
        core.log.debug.assert_not_called()
