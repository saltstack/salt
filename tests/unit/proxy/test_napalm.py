# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

import tests.support.napalm as napalm_test_support
import salt.proxy.napalm as napalm_proxy  # NOQA


TEST_OPTS = {
    'proxytype': 'napalm',
    'driver': 'junos',
    'host': 'core05.nrt02'
}


def mock_get_device(opts, *args, **kwargs):
    assert opts == TEST_OPTS
    return {
        'DRIVER': napalm_test_support.MockNapalmDevice(),
        'UP': True
    }


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.utils.napalm.get_device', mock_get_device)
class NapalmProxyTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
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
        module_globals['napalm_base'] = MagicMock()
        return {napalm_proxy: module_globals}

    def test_init(self):
        ret = napalm_proxy.init(TEST_OPTS)
        assert ret is True

    def test_alive(self):
        ret = napalm_proxy.alive(TEST_OPTS)
        assert ret is True

    def test_ping(self):
        napalm_proxy.init(TEST_OPTS)
        ret = napalm_proxy.ping()
        assert ret is True

    def test_initialized(self):
        napalm_proxy.init(TEST_OPTS)
        ret = napalm_proxy.initialized()
        assert ret is True

    def test_get_device(self):
        napalm_proxy.init(TEST_OPTS)
        ret = napalm_proxy.get_device()
        assert ret['UP'] is True

    def test_get_grains(self):
        napalm_proxy.init(TEST_OPTS)
        ret = napalm_proxy.get_grains()
        assert ret['out'] == napalm_test_support.TEST_FACTS

    def test_grains_refresh(self):
        napalm_proxy.init(TEST_OPTS)
        ret = napalm_proxy.grains_refresh()
        assert ret['out'] == napalm_test_support.TEST_FACTS

    def test_fns(self):
        ret = napalm_proxy.fns()
        assert 'details' in ret.keys()

    def test_shutdown(self):
        ret = napalm_proxy.shutdown(TEST_OPTS)
        assert ret is True

    def test_call(self):
        napalm_proxy.init(TEST_OPTS)
        ret = napalm_proxy.call('get_arp_table')
        assert ret['out'] == napalm_test_support.TEST_ARP_TABLE
