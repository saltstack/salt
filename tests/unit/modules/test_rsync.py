# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.modules.rsync as rsync
from salt.exceptions import CommandExecutionError, SaltInvocationError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RsyncTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.rsync
    '''
    def setup_loader_modules(self):
        return {rsync: {}}

    def test_rsync(self):
        '''
        Test for rsync files from src to dst
        '''
        with patch.dict(rsync.__salt__, {'config.option':
                                         MagicMock(return_value=False)}):
            self.assertRaises(SaltInvocationError, rsync.rsync, '', '')

        with patch.dict(rsync.__salt__,
                        {'config.option': MagicMock(return_value='A'),
                         'cmd.run_all': MagicMock(side_effect=[OSError(1, 'f'),
                                                               'A'])}):
            with patch.object(rsync, '_check', return_value=['A']):
                self.assertRaises(CommandExecutionError, rsync.rsync, 'a', 'b')

                self.assertEqual(rsync.rsync('src', 'dst'), 'A')

    def test_version(self):
        '''
        Test for return rsync version
        '''
        mock = MagicMock(side_effect=[OSError(1, 'f'), 'A B C\n'])
        with patch.dict(rsync.__salt__, {'cmd.run_stdout': mock}):
            self.assertRaises(CommandExecutionError, rsync.version)

            self.assertEqual(rsync.version(), 'C')
