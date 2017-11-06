# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)
from functools import wraps


# Test data
TEST_FACTS = {
    '__opts__': {},
    'OPTIONAL_ARGS': {},
    'uptime': 'Forever',
    'UP': True,
    'HOSTNAME': 'test-device.com'
}

TEST_ENVIRONMENT = {
    'hot': 'yes'
}

TEST_COMMAND_RESPONSE = 'all the command output'


class MockNapalmDevice(object):
    '''Setup a mock device for our tests'''
    def get_facts(self):
        return TEST_FACTS

    def get_environment(self):
        return TEST_ENVIRONMENT

    def get(self, key, default=None, *args, **kwargs):
        try:
            if key == 'DRIVER':
                return self
            return TEST_FACTS[key]
        except KeyError:
            return default

    def cli(self, commands, *args, **kwargs):
        assert commands[0] == 'show run'
        return TEST_COMMAND_RESPONSE


def mock_proxy_napalm_wrap(func):
    '''
    The proper decorator checks for proxy minions. We don't care
    so just pass back to the origination function
    '''

    @wraps(func)
    def func_wrapper(*args, **kwargs):
        func.__globals__['napalm_device'] = MockNapalmDevice()
        return func(*args, **kwargs)
    return func_wrapper


import salt.utils.napalm as napalm_utils
napalm_utils.proxy_napalm_wrap = mock_proxy_napalm_wrap

import salt.modules.napalm_network as napalm_network


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NapalmNetworkModuleTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        # TODO: Determine configuration best case
        module_globals = {
            '__salt__': {
                'config.option': MagicMock(return_value={
                    'test': {
                        'driver': 'test',
                        'key': '2orgk34kgk34g'
                    }
                })
            }
        }

        return {napalm_network: module_globals}

    def test_connected_pass(self):
        ret = napalm_network.connected()
        assert ret['out'] is True

    def test_facts(self):
        ret = napalm_network.facts()
        assert ret['out'] == TEST_FACTS

    def test_environment(self):
        ret = napalm_network.environment()
        assert ret['out'] == TEST_ENVIRONMENT

    def test_cli_single_command(self):
        '''
        Test that CLI works with 1 arg
        '''
        ret = napalm_network.cli("show run")
        assert ret['out'] == TEST_COMMAND_RESPONSE
