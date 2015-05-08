# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import rsync
from salt.exceptions import CommandExecutionError
import os

# Globals
rsync.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RsyncTestCase(TestCase):
    '''
    Test cases for salt.modules.rsync
    '''
    def test_rsync(self):
        '''
        Test for rsync files from src to dst
        '''
        with patch.dict(rsync.__salt__, {'config.option':
                                         MagicMock(return_value=False)}):
            self.assertRaises(CommandExecutionError, rsync.rsync, False, False)

        with patch.dict(rsync.__salt__,
                        {'config.option': MagicMock(return_value='A'),
                         'cmd.run_all': MagicMock(side_effect=[IOError('f'),
                                                               'A'])}):
            with patch.object(rsync, '_check', return_value='A'):
                self.assertRaises(CommandExecutionError, rsync.rsync, 'a', 'b')

                self.assertEqual(rsync.rsync('src', 'dst'), 'A')

    def test_version(self):
        '''
        Test for return rsync version
        '''
        mock = MagicMock(side_effect=[IOError('f'), {'stdout': 'A B C\n'}])
        with patch.dict(rsync.__salt__, {'cmd.run_all': mock}):
            self.assertRaises(CommandExecutionError, rsync.version)

            self.assertEqual(rsync.version(), {'stdout': 'C'})

    def test_config(self):
        '''
        Test for return rsync config
        '''
        mock_file = MagicMock(side_effect=[False, True, True])
        with patch.object(os.path, 'isfile', mock_file):
            self.assertRaises(CommandExecutionError, rsync.config)

            mock = MagicMock(side_effect=[IOError('f'), 'A'])
            with patch.dict(rsync.__salt__, {'cmd.run_all': mock}):
                self.assertRaises(CommandExecutionError, rsync.config)

                self.assertEqual(rsync.config('confile'), 'A')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RsyncTestCase, needs_daemon=False)
