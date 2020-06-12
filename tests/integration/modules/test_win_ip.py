# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import re

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

# Import Salt libs
import salt.utils.platform


@skipIf(not salt.utils.platform.is_windows(), 'windows test only')
class WinIPTest(ModuleCase):
    '''
    Tests for salt.modules.win_ip
    '''
    def test_get_default_gateway(self):
        '''
        Test getting default gateway
        '''
        ip = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
        ret = self.run_function('ip.get_default_gateway')
        assert ip.match(ret)

    def test_ip_is_enabled(self):
        '''
        Test ip.is_enabled
        '''
        assert self.run_function('ip.is_enabled', ['Ethernet'])
        assert 'not found' in self.run_function('ip.is_enabled', ['doesnotexist'])
