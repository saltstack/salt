# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''
# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salt.modules.inspectlib.collector import Inspector
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class InspectorCollectorTestCase(TestCase):
    '''
    Test inspectlib:collector:Inspector
    '''
    def test_env_loader(self):
        '''
        Get packages on the different distros.

        :return:
        '''
        inspector = Inspector(cachedir='/foo/cache', piddir='/foo/pid', pidfilename='bar.pid')
        self.assertEqual(inspector.dbfile, '/foo/cache/_minion_collector.db')
        self.assertEqual(inspector.pidfile, '/foo/pid/bar.pid')

    def test_get_unmanaged_files(self):
        '''
        Test get_unmanaged_files.

        :return:
        '''
        inspector = Inspector(cachedir='/test', piddir='/test', pidfilename='bar.pid')
        managed = (
            ['a', 'b', 'c'],
            ['d', 'e', 'f'],
            ['g', 'h', 'i'],
        )
        system_all = (
            ['a', 'b', 'c'],
            ['d', 'E', 'f'],
            ['G', 'H', 'i'],
        )
        self.assertEqual(inspector._get_unmanaged_files(managed=managed, system_all=system_all),
                         ([], ['E'], ['G', 'H']))


    def test_pkg_get(self):
        '''
        Test if grains switching the pkg get method.

        :return:
        '''
        debian_list = """
g++
g++-4.9
g++-5
gawk
gcc
gcc-4.9
gcc-4.9-base:amd64
gcc-4.9-base:i386
gcc-5
gcc-5-base:amd64
gcc-5-base:i386
gcc-6-base:amd64
gcc-6-base:i386
"""
        inspector = Inspector(cachedir='/test', piddir='/test', pidfilename='bar.pid')
        inspector.grains_core = MagicMock()
        inspector.grains_core.os_data = MagicMock()
        inspector.grains_core.os_data.get = MagicMock(return_value='Debian')
        with patch.object(inspector, '_Inspector__get_cfg_pkgs_dpkg', MagicMock(return_value='dpkg')):
            with patch.object(inspector, '_Inspector__get_cfg_pkgs_rpm', MagicMock(return_value='rpm')):
                inspector.grains_core = MagicMock()
                inspector.grains_core.os_data = MagicMock()
                inspector.grains_core.os_data().get = MagicMock(return_value='Debian')
                self.assertEqual(inspector._get_cfg_pkgs(), 'dpkg')
                inspector.grains_core.os_data().get = MagicMock(return_value='Suse')
                self.assertEqual(inspector._get_cfg_pkgs(), 'rpm')
                inspector.grains_core.os_data().get = MagicMock(return_value='redhat')
                self.assertEqual(inspector._get_cfg_pkgs(), 'rpm')
