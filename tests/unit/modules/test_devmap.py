# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import os.path

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
import salt.modules.devmap as devmap


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DevMapTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.devmap
    '''
    loader_module = devmap

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
