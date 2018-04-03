# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

# Import Salt Libs
import salt.modules.bridge as bridge


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BridgeTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.bridge
    '''
    def setup_loader_modules(self):
        return {bridge: {}}

    def test_show(self):
        '''
        Test for Returns bridges interfaces
        along with enslaved physical interfaces
        '''
        mock = MagicMock(return_value=True)
        with patch.object(bridge, '_os_dispatch', mock):
            self.assertTrue(bridge.show('br'))

    def test_list_(self):
        '''
        Test for Returns the machine's bridges list
        '''
        mock = MagicMock(return_value=None)
        with patch.object(bridge, '_os_dispatch', mock):
            self.assertEqual(bridge.list_(), None)

        mock = MagicMock(return_value=['A', 'B'])
        with patch.object(bridge, '_os_dispatch', mock):
            self.assertEqual(bridge.list_(), ['A', 'B'])

    def test_interfaces(self):
        '''
        Test for Returns interfaces attached to a bridge
        '''
        self.assertEqual(bridge.interfaces(), None)

        mock = MagicMock(return_value={'interfaces': 'A'})
        with patch.object(bridge, '_os_dispatch', mock):
            self.assertEqual(bridge.interfaces('br'), 'A')

    def test_find_interfaces(self):
        '''
        Test for Returns the bridge to which the interfaces are bond to
        '''
        mock = MagicMock(return_value=None)
        with patch.object(bridge, '_os_dispatch', mock):
            self.assertEqual(bridge.find_interfaces(), None)

        mock = MagicMock(return_value={'interfaces': 'A'})
        with patch.object(bridge, '_os_dispatch', mock):
            self.assertEqual(bridge.find_interfaces(), {})

    def test_add(self):
        '''
        Test for Creates a bridge
        '''
        mock = MagicMock(return_value='A')
        with patch.object(bridge, '_os_dispatch', mock):
            self.assertEqual(bridge.add(), 'A')

    def test_delete(self):
        '''
        Test for Deletes a bridge
        '''
        mock = MagicMock(return_value='A')
        with patch.object(bridge, '_os_dispatch', mock):
            self.assertEqual(bridge.delete(), 'A')

    def test_addif(self):
        '''
        Test for Adds an interface to a bridge
        '''
        mock = MagicMock(return_value='A')
        with patch.object(bridge, '_os_dispatch', mock):
            self.assertEqual(bridge.addif(), 'A')

    def test_delif(self):
        '''
        Test for Removes an interface from a bridge
        '''
        mock = MagicMock(return_value='A')
        with patch.object(bridge, '_os_dispatch', mock):
            self.assertEqual(bridge.delif(), 'A')

    def test_stp(self):
        '''
        Test for Sets Spanning Tree Protocol state for a bridge
        '''
        with patch.dict(bridge.__grains__, {'kernel': 'Linux'}):
            mock = MagicMock(return_value='Linux')
            with patch.object(bridge, '_os_dispatch', mock):
                self.assertEqual(bridge.stp(), 'Linux')

        with patch.dict(bridge.__grains__, {'kernel': 'FreeBSD'}):
            mock = MagicMock(return_value='FreeBSD')
            with patch.object(bridge, '_os_dispatch', mock):
                self.assertEqual(bridge.stp(), 'FreeBSD')

        with patch.dict(bridge.__grains__, {'kernel': None}):
            self.assertFalse(bridge.stp())
