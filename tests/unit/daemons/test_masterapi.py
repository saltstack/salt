# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import salt.config
import salt.daemons.masterapi as masterapi

# Import Salt Testing Libs
from tests.support.unit import TestCase
from tests.support.mock import (
    patch,
    MagicMock,
)


class FakeCache(object):

    def __init__(self):
        self.data = {}

    def store(self, bank, key, value):
        self.data[bank, key] = value

    def fetch(self, bank, key):
        return self.data[bank, key]


class RemoteFuncsTestCase(TestCase):
    '''
    TestCase for salt.daemons.masterapi.RemoteFuncs class
    '''

    def setUp(self):
        opts = salt.config.master_config(None)
        self.funcs = masterapi.RemoteFuncs(opts)
        self.funcs.cache = FakeCache()

    def test_mine_get(self, tgt_type_key='tgt_type'):
        '''
        Asserts that ``mine_get`` gives the expected results.

        Actually this only tests that:

        - the correct check minions method is called
        - the correct cache key is subsequently used
        '''
        self.funcs.cache.store('minions/webserver', 'mine',
                               dict(ip_addr='2001:db8::1:3'))
        with patch('salt.utils.minions.CkMinions._check_compound_minions',
                   MagicMock(return_value=['webserver'])):
            ret = self.funcs._mine_get(
                {
                    'id': 'requester_minion',
                    'tgt': 'G@roles:web',
                    'fun': 'ip_addr',
                    tgt_type_key: 'compound',
                }
            )
        self.assertDictEqual(ret, dict(webserver='2001:db8::1:3'))

    def test_mine_get_pre_nitrogen_compat(self):
        '''
        Asserts that pre-Nitrogen API key ``expr_form`` is still accepted.

        This is what minions before Nitrogen would issue.
        '''
        self.test_mine_get(tgt_type_key='expr_form')
