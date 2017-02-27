# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import devmap
import os.path


# Globals
devmap.__grains__ = {}
devmap.__salt__ = {}
devmap.__context__ = {}
devmap.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DevMapTestCase(TestCase):
    '''
    Test cases for salt.modules.devmap
    '''
    def test_multipath_list(self):
        '''
        Test for Device-Mapper Multipath list
        '''
        mock = MagicMock(return_value='A')
        with patch.dict(devmap.__salt__, {'cmd.run': mock}):
            self.assertEqual(devmap.multipath_list(), ['A'])

    def test_multipath_flush(self):
        '''
        Test for Device-Mapper Multipath flush
        '''
        mock = MagicMock(return_value=False)
        with patch.object(os.path, 'exists', mock):
            self.assertEqual(devmap.multipath_flush('device'),
                             'device does not exist')

        mock = MagicMock(return_value=True)
        with patch.object(os.path, 'exists', mock):
            mock = MagicMock(return_value='A')
            with patch.dict(devmap.__salt__, {'cmd.run': mock}):
                self.assertEqual(devmap.multipath_flush('device'), ['A'])
