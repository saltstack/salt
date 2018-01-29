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
import salt.modules.napalm_yang_mod as napalm_yang_mod  # NOQA
import salt.modules.napalm_network as napalm_network  # NOQA


TEST_DIFF = {
    'diff1': 'value'
}


class MockNapalmYangModel(object):
    def Root(self):
        return MagicMock()


class MockNapalmYangModels(object):
    openconfig_interfaces = MockNapalmYangModel()


class MockUtils(object):
    def diff(self, *args):
        return TEST_DIFF


class MockNapalmYangModule(object):
    base = MockNapalmYangModel()
    models = MockNapalmYangModels()
    utils = MockUtils()

TEST_CONFIG = {
    'comment': 'Configuration discarded.',
    'already_configured': False,
    'result': True,
    'diff': '[edit interfaces xe-0/0/5]+   description "Adding a description";'
}


def mock_net_load_config(**kwargs):
    return TEST_CONFIG


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NapalmYangModModuleTestCase(TestCase, LoaderModuleMockMixin):

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
                'random.hash': napalm_test_support.random_hash,
                'net.load_template': napalm_network.load_template,
                'net.load_config': mock_net_load_config
            }
        }
        module_globals['napalm_yang'] = MockNapalmYangModule()

        return {napalm_yang_mod: module_globals, napalm_network: module_globals}

    def test_diff(self):
        ret = napalm_yang_mod.diff({}, {'test': True}, 'models.openconfig_interfaces')
        assert ret == TEST_DIFF

    def test_diff_list(self):
        '''
        Test it with an actual list
        '''
        ret = napalm_yang_mod.diff({}, {'test': True}, ['models.openconfig_interfaces'])
        assert ret == TEST_DIFF

    def test_parse(self):
        ret = napalm_yang_mod.parse('models.openconfig_interfaces')
        assert ret is not None

    def test_get_config(self):
        ret = napalm_yang_mod.get_config({}, 'models.openconfig_interfaces')
        assert ret is not None

    def test_load_config(self):
        ret = napalm_yang_mod.load_config({}, 'models.openconfig_interfaces')
        assert ret is TEST_CONFIG

    def test_compliance_report(self):
        ret = napalm_yang_mod.compliance_report({}, 'models.openconfig_interfaces')
        assert ret is not None
