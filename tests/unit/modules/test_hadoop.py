# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.hadoop as hadoop


@skipIf(NO_MOCK, NO_MOCK_REASON)
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
            self.assertEqual(hadoop.version(), 'B')

    def test_dfs(self):
        '''
        Test for Execute a command on DFS
        '''
        with patch.object(hadoop, '_hadoop_cmd', return_value='A'):
            self.assertEqual(hadoop.dfs('command'), 'A')

        self.assertEqual(hadoop.dfs(), 'Error: command must be provided')

    def test_dfs_present(self):
        '''
        Test for Check if a file or directory is present on the distributed FS.
        '''
        with patch.object(hadoop, '_hadoop_cmd',
                          side_effect=['No such file or directory', 'A']):
            self.assertFalse(hadoop.dfs_present('path'))
            self.assertTrue(hadoop.dfs_present('path'))

    def test_dfs_absent(self):
        '''
        Test for Check if a file or directory is absent on the distributed FS.
        '''
        with patch.object(hadoop, '_hadoop_cmd',
                          side_effect=['No such file or directory', 'A']):
            self.assertTrue(hadoop.dfs_absent('path'))
            self.assertFalse(hadoop.dfs_absent('path'))

    def test_namenode_format(self):
        '''
        Test for Format a name node
        '''
        with patch.object(hadoop, '_hadoop_cmd', return_value='A'):
            self.assertEqual(hadoop.namenode_format('force'), 'A')
