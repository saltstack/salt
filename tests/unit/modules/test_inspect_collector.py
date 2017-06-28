# -*- coding: utf-8 -*-
#
# Copyright 2016 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''
# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import salt libs
from salt.modules.inspectlib.collector import Inspector


@skipIf(NO_MOCK, NO_MOCK_REASON)
class InspectorCollectorTestCase(TestCase):
    '''
    Test inspectlib:collector:Inspector
    '''
    def setUp(self):
        patcher = patch("os.mkdir", MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_env_loader(self):
        '''
        Get packages on the different distros.

        :return:
        '''
        inspector = Inspector(cachedir='/foo/cache', piddir='/foo/pid', pidfilename='bar.pid')
        self.assertEqual(inspector.dbfile, '/foo/cache/_minion_collector.db')
        self.assertEqual(inspector.pidfile, '/foo/pid/bar.pid')

    def test_file_tree(self):
        '''
        Test file tree.

        :return:
        '''

        inspector = Inspector(cachedir='/test', piddir='/test', pidfilename='bar.pid')
        tree_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inspectlib', 'tree_test')
        expected_tree = (['/a/a/dummy.a', '/a/b/dummy.b', '/b/b.1', '/b/b.2', '/b/b.3'],
                         ['/a', '/a/a', '/a/b', '/a/c', '/b', '/c'],
                         ['/a/a/dummy.ln.a', '/a/b/dummy.ln.b', '/a/c/b.1', '/b/b.4',
                          '/b/b.5', '/c/b.1', '/c/b.2', '/c/b.3'])
        tree_result = []
        for chunk in inspector._get_all_files(tree_root):
            buff = []
            for pth in chunk:
                buff.append(pth.replace(tree_root, ''))
            tree_result.append(buff)
        tree_result = tuple(tree_result)
        self.assertEqual(expected_tree, tree_result)

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
                inspector.grains_core.os_data().get = MagicMock(return_value='SUSE')
                self.assertEqual(inspector._get_cfg_pkgs(), 'rpm')
                inspector.grains_core.os_data().get = MagicMock(return_value='redhat')
                self.assertEqual(inspector._get_cfg_pkgs(), 'rpm')
