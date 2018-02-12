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
    NO_MOCK_REASON
)
import salt.modules.servicenow as servicenow


class MockServiceNowClient(object):
    def __init__(self, instance_name, username, password):
        pass

    def get(self, query):
        return [{'query_size': len(query),
                 'query_value': query}]


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ServiceNowModuleTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        module_globals = {
            'Client': MockServiceNowClient,
            '__salt__': {
                'config.option': MagicMock(return_value={
                    'instance_name': 'test',
                    'username': 'mr_test',
                    'password': 'test123'
                })
            }
        }
        if servicenow.HAS_LIBS is False:
            module_globals['sys.modules'] = {'servicenow_rest': MagicMock()}
            module_globals['sys.modules']['servicenow_rest'].api.Client = MockServiceNowClient
        return {servicenow: module_globals}

    def test_module_creation(self):
        client = servicenow._get_client()
        self.assertFalse(client is None)

    def test_non_structured_query(self):
        result = servicenow.non_structured_query('tests', 'role=web')
        self.assertFalse(result is None)
        self.assertEqual(result[0]['query_size'], 8)
        self.assertEqual(result[0]['query_value'], 'role=web')

    def test_non_structured_query_kwarg(self):
        result = servicenow.non_structured_query('tests', role='web')
        self.assertFalse(result is None)
        self.assertEqual(result[0]['query_size'], 8)
        self.assertEqual(result[0]['query_value'], 'role=web')

    def test_non_structured_query_kwarg_multi(self):
        result = servicenow.non_structured_query('tests', role='web',
                                                 type='computer')
        self.assertFalse(result is None)
        self.assertEqual(result[0]['query_size'], 22)
