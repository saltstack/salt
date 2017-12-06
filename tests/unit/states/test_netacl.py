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

import salt.states.netacl as napalm_acl  # NOQA

TEST_RET = {
    'comment': 'test'
}


def mock_load_term_config(filter_name, term_name, *args, **kwargs):
    assert filter_name == 'test_filter'
    assert term_name == 'test_term'
    return TEST_RET


def mock_load_filter_config(filter_name, *args, **kwargs):
    assert filter_name == 'test_filter'
    return TEST_RET


def mock_load_policy_config(*args, **kwargs):
    return TEST_RET


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
                'netacl.load_term_config': mock_load_term_config,
                'netacl.load_filter_config': mock_load_filter_config,
                'netacl.load_policy_config': mock_load_policy_config
            },
            '__opts__': {
                'test': False
            }
        }

        return {napalm_acl: module_globals}

    def test_term(self):
        ret = napalm_acl.term('test_name', 'test_filter', 'test_term')
        assert ret['comment'] == 'test'

    def test_filter(self):
        ret = napalm_acl.filter('test_name', 'test_filter')
        assert ret['comment'] == 'test'

    def test_managed(self):
        ret = napalm_acl.managed('test_name')
        assert ret['comment'] == 'test'
