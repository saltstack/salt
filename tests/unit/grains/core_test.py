# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Erik Johnson <erik@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import os
import platform

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
import salt.utils
from salt.grains import core

# Globals
core.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CoreGrainsTestCase(TestCase):
    '''
    Test cases for core grains
    '''
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
                    with patch('__builtin__.__import__',
                               side_effect=_import_mock):
                        # Skip all the /etc/*-release stuff (not pertinent)
                        with patch.object(os.path, 'isfile', path_isfile_mock):
                            # Mock platform.linux_distribution to give us the
                            # OS name that we want.
                            distro_mock = MagicMock(
                                return_value=('Debian GNU/Linux', '8.3', '')
                            )
                            with patch.object(
                                    platform,
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CoreGrainsTestCase, needs_daemon=False)
