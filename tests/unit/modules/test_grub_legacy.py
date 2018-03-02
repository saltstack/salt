# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

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
import salt.modules.grub_legacy as grub_legacy
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GrublegacyTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.grub_legacy
    '''
    def setup_loader_modules(self):
        return {grub_legacy: {}}

    def test_version(self):
        '''
        Test for Return server version from grub --version
        '''
        mock = MagicMock(return_value='out')
        with patch.dict(grub_legacy.__salt__, {'cmd.run': mock}):
            self.assertEqual(grub_legacy.version(), 'out')

    def test_conf(self):
        '''
        Test for Parse GRUB conf file
        '''
        mock = MagicMock(side_effect=IOError('foo'))
        with patch('salt.utils.files.fopen', mock):
            with patch.object(grub_legacy, '_detect_conf', return_value='A'):
                self.assertRaises(CommandExecutionError, grub_legacy.conf)

        file_data = salt.utils.stringutils.to_str('\n'.join(['#', 'A B C D,E,F G H']))
        with patch('salt.utils.files.fopen',
                   mock_open(read_data=file_data), create=True) as f_mock:
            f_mock.return_value.__iter__.return_value = file_data.splitlines()
            with patch.object(grub_legacy, '_detect_conf', return_value='A'):
                self.assertEqual(grub_legacy.conf(),
                                 {'A': 'B C D,E,F G H', 'stanzas': []})
