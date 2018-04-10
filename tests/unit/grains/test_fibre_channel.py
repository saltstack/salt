# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Shane Lee <slee@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    mock_open,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.grains.fibre_channel as fibre_channel


@skipIf(NO_MOCK, NO_MOCK_REASON)
class FibreChannelGrainsTestCase(TestCase):
    '''
    Test cases for iscsi grains
    '''
    def test_windows_fibre_channel_wwns_grains(self):
        wwns = ['20:00:00:25:b5:11:11:4c',
                '20:00:00:25:b5:11:11:5c',
                '20:00:00:25:b5:44:44:4c',
                '20:00:00:25:b5:44:44:5c']
        cmd_run_mock = MagicMock(return_value=wwns)
        with patch('salt.modules.cmdmod.powershell', cmd_run_mock):
            ret = fibre_channel._windows_wwns()
        self.assertEqual(ret, wwns)

    def test_linux_fibre_channel_wwns_grains(self):

        def multi_mock_open(*file_contents):
            mock_files = [mock_open(read_data=content).return_value for content in file_contents]
            mock_opener = mock_open()
            mock_opener.side_effect = mock_files

            return mock_opener

        files = ['file1', 'file2']
        with patch('glob.glob', MagicMock(return_value=files)):
            with patch('salt.utils.files.fopen', multi_mock_open('0x500143802426baf4', '0x500143802426baf5')):
                ret = fibre_channel._linux_wwns()

        self.assertEqual(ret, ['500143802426baf4', '500143802426baf5'])
