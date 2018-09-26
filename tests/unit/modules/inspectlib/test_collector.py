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
    :codeauthor: Bo Maryniuk <bo@suse.de>
'''
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.helpers import no_symlinks
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import salt libs
from salt.modules.inspectlib.collector import Inspector


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(no_symlinks(), "Git missing 'core.symlinks=true' config")
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
        cachedir = os.sep + os.sep.join(['foo', 'cache'])
        piddir = os.sep + os.sep.join(['foo', 'pid'])
        inspector = Inspector(cachedir=cachedir, piddir=piddir, pidfilename='bar.pid')
        self.assertEqual(
            inspector.dbfile,
            os.sep + os.sep.join(['foo', 'cache', '_minion_collector.db']))
        self.assertEqual(
            inspector.pidfile,
            os.sep + os.sep.join(['foo', 'pid', 'bar.pid']))

    def test_file_tree(self):
        '''
        Test file tree.

        :return:
        '''

        inspector = Inspector(cachedir=os.sep + 'test',
                              piddir=os.sep + 'test',
                              pidfilename='bar.pid')
        tree_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tree_test')
        expected_tree = ([os.sep + os.sep.join(['a', 'a', 'dummy.a']),
                          os.sep + os.sep.join(['a', 'b', 'dummy.b']),
                          os.sep + os.sep.join(['b', 'b.1']),
                          os.sep + os.sep.join(['b', 'b.2']),
                          os.sep + os.sep.join(['b', 'b.3'])],
                         [os.sep + 'a',
                          os.sep + os.sep.join(['a', 'a']),
                          os.sep + os.sep.join(['a', 'b']),
                          os.sep + os.sep.join(['a', 'c']),
                          os.sep + 'b',
                          os.sep + 'c'],
                         [os.sep + os.sep.join(['a', 'a', 'dummy.ln.a']),
                          os.sep + os.sep.join(['a', 'b', 'dummy.ln.b']),
                          os.sep + os.sep.join(['a', 'c', 'b.1']),
                          os.sep + os.sep.join(['b', 'b.4']),
                          os.sep + os.sep.join(['b', 'b.5']),
                          os.sep + os.sep.join(['c', 'b.1']),
                          os.sep + os.sep.join(['c', 'b.2']),
                          os.sep + os.sep.join(['c', 'b.3'])])
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
                inspector.grains_core.os_data().get = MagicMock(return_value='Suse')
                self.assertEqual(inspector._get_cfg_pkgs(), 'rpm')
                inspector.grains_core.os_data().get = MagicMock(return_value='redhat')
                self.assertEqual(inspector._get_cfg_pkgs(), 'rpm')
