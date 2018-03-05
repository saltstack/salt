# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch
)

# Import Salt Libs
import salt.modules.rdp as rdp


class RdpTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.rdp
    '''
    def setup_loader_modules(self):
        return {rdp: {}}

    # 'enable' function tests: 1

    def test_enable(self):
        '''
        Test if it enables RDP the service on the server
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(rdp.__salt__, {'cmd.run': mock}), \
                patch('salt.modules.rdp._parse_return_code_powershell',
                      MagicMock(return_value=0)):
            self.assertTrue(rdp.enable())

    # 'disable' function tests: 1

    def test_disable(self):
        '''
        Test if it disables RDP the service on the server
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(rdp.__salt__, {'cmd.run': mock}), \
                patch('salt.modules.rdp._parse_return_code_powershell',
                      MagicMock(return_value=0)):
            self.assertTrue(rdp.disable())

    # 'status' function tests: 1

    def test_status(self):
        '''
        Test if it shows rdp is enabled on the server
        '''
        mock = MagicMock(return_value='1')
        with patch.dict(rdp.__salt__, {'cmd.run': mock}):
            self.assertTrue(rdp.status())
