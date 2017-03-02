# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch
)

# Import Salt Libs
from salt.modules import rdp

# Globals
rdp.__salt__ = {}

# Make sure this module runs on Windows system
IS_RDP = rdp.__virtual__()


@skipIf(not IS_RDP, "This test case runs only on Windows system")
class RdpTestCase(TestCase):
    '''
    Test cases for salt.modules.rdp
    '''
    # 'enable' function tests: 1

    @patch('salt.modules.rdp._parse_return_code_powershell',
           MagicMock(return_value=0))
    def test_enable(self):
        '''
        Test if it enables RDP the service on the server
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(rdp.__salt__, {'cmd.run': mock}):
            self.assertTrue(rdp.enable())

    # 'disable' function tests: 1

    @patch('salt.modules.rdp._parse_return_code_powershell',
           MagicMock(return_value=0))
    def test_disable(self):
        '''
        Test if it disables RDP the service on the server
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(rdp.__salt__, {'cmd.run': mock}):
            self.assertTrue(rdp.disable())

    # 'status' function tests: 1

    def test_status(self):
        '''
        Test if it shows rdp is enabled on the server
        '''
        mock = MagicMock(return_value='1')
        with patch.dict(rdp.__salt__, {'cmd.run': mock}):
            self.assertTrue(rdp.status())
