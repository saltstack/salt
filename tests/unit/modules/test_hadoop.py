# -*- coding: utf-8 -*-
'''
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch,
)

# Import Salt Libs
import salt.modules.hadoop as hadoop


class HadoopTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.hadoop
    '''
    def setup_loader_modules(self):
        return {hadoop: {}}

    def test_version(self):
        '''
        Test for Return version from hadoop version
        '''
        mock = MagicMock(return_value="A \nB \n")
        with patch.dict(hadoop.__salt__, {'cmd.run': mock}):
            assert hadoop.version() == 'B'

    def test_dfs(self):
        '''
        Test for Execute a command on DFS
        '''
        with patch.object(hadoop, '_hadoop_cmd', return_value='A'):
            assert hadoop.dfs('command') == 'A'

        assert hadoop.dfs() == 'Error: command must be provided'

    def test_dfs_present(self):
        '''
        Test for Check if a file or directory is present on the distributed FS.
        '''
        with patch.object(hadoop, '_hadoop_cmd',
                          side_effect=['No such file or directory', 'A']):
            assert not hadoop.dfs_present('path')
            assert hadoop.dfs_present('path')

    def test_dfs_absent(self):
        '''
        Test for Check if a file or directory is absent on the distributed FS.
        '''
        with patch.object(hadoop, '_hadoop_cmd',
                          side_effect=['No such file or directory', 'A']):
            assert hadoop.dfs_absent('path')
            assert not hadoop.dfs_absent('path')

    def test_namenode_format(self):
        '''
        Test for Format a name node
        '''
        with patch.object(hadoop, '_hadoop_cmd', return_value='A'):
            assert hadoop.namenode_format('force') == 'A'
