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

import tests.support.napalm as napalm_test_support
import salt.modules.napalm_probes as napalm_probes  # NOQA


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NapalmProbesModuleTestCase(TestCase, LoaderModuleMockMixin):

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

        return {napalm_probes: module_globals}

    def test_probes_config(self):
        ret = napalm_probes.config()
        assert ret['out'] == napalm_test_support.TEST_PROBES_CONFIG

    def test_probes_results(self):
        ret = napalm_probes.results()
        assert ret['out'] == napalm_test_support.TEST_PROBES_RESULTS
