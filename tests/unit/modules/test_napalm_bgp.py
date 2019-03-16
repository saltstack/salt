# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)

import tests.support.napalm as napalm_test_support
import salt.modules.napalm_bgp as napalm_bgp  # NOQA


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NapalmBgpModuleTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        module_globals = {
            '__salt__': {
                'config.option': MagicMock(return_value={
                    'test': {
                        'driver': 'test',
                        'key': '2orgk34kgk34g'
                    }
                }),
                'file.file_exists': napalm_test_support.true,
                'file.join': napalm_test_support.join,
                'file.get_managed': napalm_test_support.get_managed_file,
                'random.hash': napalm_test_support.random_hash
            }
        }

        return {napalm_bgp: module_globals}

    def test_config(self):
        ret = napalm_bgp.config("test_group")
        assert ret['out'] is napalm_test_support.TEST_BGP_CONFIG

    def test_neighbors(self):
        ret = napalm_bgp.neighbors("test_address")
        assert ret['out'] is napalm_test_support.TEST_BGP_NEIGHBORS
