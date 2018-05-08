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
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)

import salt.states.netntp as napalm_ntp  # NOQA

TEST_RET = {
    'comment': 'test'
}

TEST_PEERS = [
    '192.168.0.1',
    '168.250.255.1'
]


def mock_load_policy_config(*args, **kwargs):
    return TEST_RET


def mock_ntp_peers(*args, **kwargs):
    return {
        'result': TEST_PEERS
    }


def mock_set_ntp_peers(*peers, **kwargs):
    for peer in peers:
        assert peer in TEST_PEERS
    return {
        'result': TEST_PEERS
    }


def mock_net_config_control():
    return (True, '')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NapalmAclStateTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        module_globals = {
            '__salt__': {
                'config.option': MagicMock(return_value={
                    'test': {
                        'driver': 'test',
                        'key': '2orgk34kgk34g'
                    }
                }),
                'ntp.peers': mock_ntp_peers,
                'ntp.set_peers': mock_set_ntp_peers,
                'net.config_control': mock_net_config_control
            },
            '__opts__': {
                'test': False
            }
        }

        return {napalm_ntp: module_globals}

    def test_managed_default_response(self):
        ret = napalm_ntp.managed('test_name')
        assert ret['comment'] == ''
        assert ret['result'] is False

    def test_managed_invalid_peers(self):
        ret = napalm_ntp.managed('test_name', ['banana'])
        assert ret['comment'] == ''
        assert ret['result'] is False

    def test_managed_peers(self):
        ret = napalm_ntp.managed('test_name', TEST_PEERS)
        assert ret['comment'] != ''
        assert ret['result'] is True
