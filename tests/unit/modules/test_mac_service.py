# -*- coding: utf-8 -*-
'''
    :codeauthor: Megan Wilhite<mwilhite@saltstack.com>
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.modules.mac_service as mac_service

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MacServiceTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.mac_service module
    '''
    def setup_loader_modules(self):
        return {mac_service: {}}

    def test_service_disabled_when_enabled(self):
        '''
        test service.disabled when service is enabled
        '''
        srv_name = 'com.apple.atrun'
        cmd = 'disabled services = {\n\t"com.saltstack.salt.minion" => false\n\t"com.apple.atrun" => false\n{'

        with patch.object(mac_service, 'launchctl', MagicMock(return_value=cmd)):
            self.assertFalse(mac_service.disabled(srv_name))

    def test_service_disabled_when_disabled(self):
        '''
        test service.disabled when service is disabled
        '''
        srv_name = 'com.apple.atrun'
        cmd = 'disabled services = {\n\t"com.saltstack.salt.minion" => false\n\t"com.apple.atrun" => true\n{'

        with patch.object(mac_service, 'launchctl', MagicMock(return_value=cmd)):
            self.assertTrue(mac_service.disabled(srv_name))

    def test_service_disabled_srvname_wrong(self):
        '''
        test service.disabled when service is just slightly wrong
        '''
        srv_names = ['com.apple.atru', 'com', 'apple']
        cmd = 'disabled services = {\n\t"com.saltstack.salt.minion" => false\n\t"com.apple.atrun" => true\n}'
        for name in srv_names:
            with patch.object(mac_service, 'launchctl', MagicMock(return_value=cmd)):
                self.assertFalse(mac_service.disabled(name))

    def test_service_disabled_status_upper_case(self):
        '''
        test service.disabled when disabled status is uppercase
        '''
        srv_name = 'com.apple.atrun'
        cmd = 'disabled services = {\n\t"com.saltstack.salt.minion" => false\n\t"com.apple.atrun" => True\n{'

        with patch.object(mac_service, 'launchctl', MagicMock(return_value=cmd)):
            self.assertTrue(mac_service.disabled(srv_name))
