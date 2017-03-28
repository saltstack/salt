# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    mock_open,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.utils
import salt.modules.puppet as puppet
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PuppetTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Test cases for salt.modules.puppet
    '''
    def setup_loader_modules(self):
        return {puppet: {}}

    def test_run(self):
        '''
            Test to execute a puppet run
        '''
        mock = MagicMock(return_value={"A": "B"})
        with patch.object(salt.utils, 'clean_kwargs', mock):
            mock = MagicMock(return_value={'retcode': 0})
            mock_lst = MagicMock(return_value=[])
            with patch.dict(puppet.__salt__, {'cmd.run_all': mock,
                                                'cmd.run': mock_lst}):
                self.assertTrue(puppet.run())

    def test_noop(self):
        '''
            Test to execute a puppet noop run
        '''
        mock = MagicMock(return_value={"stderr": "A", "stdout": "B"})
        with patch.object(puppet, 'run', mock):
            self.assertDictEqual(puppet.noop(), {'stderr': 'A', 'stdout': 'B'})

    def test_enable(self):
        '''
            Test to enable the puppet agent
        '''
        mock_lst = MagicMock(return_value=[])
        with patch.dict(puppet.__salt__, {'cmd.run': mock_lst}):
            mock = MagicMock(return_value=True)
            with patch.object(os.path, 'isfile', mock):
                mock = MagicMock(return_value=True)
                with patch.object(os, 'remove', mock):
                    self.assertTrue(puppet.enable())

                with patch.object(os, 'remove',
                                    MagicMock(side_effect=IOError)):
                    self.assertRaises(CommandExecutionError, puppet.enable)

            self.assertFalse(puppet.enable())

    def test_disable(self):
        '''
            Test to disable the puppet agent
        '''
        mock_lst = MagicMock(return_value=[])
        with patch.dict(puppet.__salt__, {'cmd.run': mock_lst}):
            mock = MagicMock(side_effect=[True, False])
            with patch.object(os.path, 'isfile', mock):
                self.assertFalse(puppet.disable())

                with patch('salt.utils.fopen', mock_open()):
                    self.assertTrue(puppet.disable())

                try:
                    with patch('salt.utils.fopen', mock_open()) as m_open:
                        m_open.side_effect = IOError(13, 'Permission denied:', '/file')
                        self.assertRaises(CommandExecutionError, puppet.disable)
                except StopIteration:
                    pass

    def test_status(self):
        '''
            Test to display puppet agent status
        '''
        mock_lst = MagicMock(return_value=[])
        with patch.dict(puppet.__salt__, {'cmd.run': mock_lst}):
            mock = MagicMock(side_effect=[True])
            with patch.object(os.path, 'isfile', mock):
                self.assertEqual(puppet.status(),
                                    "Administratively disabled")

            mock = MagicMock(side_effect=[False, True])
            with patch.object(os.path, 'isfile', mock):
                with patch('salt.utils.fopen', mock_open(read_data="1")):
                    mock = MagicMock(return_value=True)
                    with patch.object(os, 'kill', mock):
                        self.assertEqual(puppet.status(),
                                            "Applying a catalog")

            mock = MagicMock(side_effect=[False, True])
            with patch.object(os.path, 'isfile', mock):
                with patch('salt.utils.fopen', mock_open()):
                    mock = MagicMock(return_value=True)
                    with patch.object(os, 'kill', mock):
                        self.assertEqual(puppet.status(), "Stale lockfile")

            mock = MagicMock(side_effect=[False, False, True])
            with patch.object(os.path, 'isfile', mock):
                with patch('salt.utils.fopen', mock_open(read_data="1")):
                    mock = MagicMock(return_value=True)
                    with patch.object(os, 'kill', mock):
                        self.assertEqual(puppet.status(), "Idle daemon")

            mock = MagicMock(side_effect=[False, False, True])
            with patch.object(os.path, 'isfile', mock):
                with patch('salt.utils.fopen', mock_open()):
                    mock = MagicMock(return_value=True)
                    with patch.object(os, 'kill', mock):
                        self.assertEqual(puppet.status(), "Stale pidfile")

            mock = MagicMock(side_effect=[False, False, False])
            with patch.object(os.path, 'isfile', mock):
                self.assertEqual(puppet.status(), "Stopped")

    def test_summary(self):
        '''
            Test to show a summary of the last puppet agent run
        '''
        mock_lst = MagicMock(return_value=[])
        with patch.dict(puppet.__salt__, {'cmd.run': mock_lst}):
            with patch('salt.utils.fopen',
                        mock_open(read_data="resources: 1")):
                self.assertDictEqual(puppet.summary(), {'resources': 1})

            with patch('salt.utils.fopen', mock_open()) as m_open:
                m_open.side_effect = IOError(13, 'Permission denied:', '/file')
                self.assertRaises(CommandExecutionError, puppet.summary)

    def test_plugin_sync(self):
        '''
            Test to runs a plugin synch between the puppet master and agent
        '''
        mock_lst = MagicMock(return_value=[])
        with patch.dict(puppet.__salt__, {'cmd.run': mock_lst}):
            mock_lst = MagicMock(side_effect=[False, True])
            with patch.dict(puppet.__salt__, {'cmd.run': mock_lst}):
                self.assertEqual(puppet.plugin_sync(), "")

                self.assertTrue(puppet.plugin_sync())

    def test_facts(self):
        '''
            Test to run facter and return the results
        '''
        mock_lst = MagicMock(return_value=[])
        with patch.dict(puppet.__salt__, {'cmd.run': mock_lst}):
            mock_lst = MagicMock(return_value="True")
            with patch.dict(puppet.__salt__, {'cmd.run': mock_lst}):
                mock = MagicMock(return_value=["a", "b"])
                with patch.object(puppet, '_format_fact', mock):
                    self.assertDictEqual(puppet.facts(), {'a': 'b'})

    def test_fact(self):
        '''
            Test to run facter for a specific fact
        '''
        mock_lst = MagicMock(return_value=[])
        with patch.dict(puppet.__salt__, {'cmd.run': mock_lst}):
            mock_lst = MagicMock(side_effect=[False, True])
            with patch.dict(puppet.__salt__, {'cmd.run': mock_lst}):
                self.assertEqual(puppet.fact("salt"), "")

                self.assertTrue(puppet.fact("salt"))
