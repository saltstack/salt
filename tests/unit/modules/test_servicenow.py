# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.unit import ModuleTestCase, hasDependency
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
import salt.modules.servicenow as servicenow

SERVICE_NAME = 'servicenow'


class MockServiceNowClient(object):
    def __init__(self, instance_name, username, password):
        pass

    def get(self, query):
        return [{'query_size': len(query),
                 'query_value': query}]


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('servicenow_rest.api.Client', MockServiceNowClient)
class ServiceNowModuleTestCase(ModuleTestCase, LoaderModuleMockMixin):
    loader_module = servicenow

    def loader_module_globals(self):
        return {'Client': MockServiceNowClient}

    def setUp(self):
        hasDependency('servicenow_rest')

        def get_config(service):
            if service == SERVICE_NAME:
                return {
                    'instance_name': 'test',
                    'username': 'mr_test',
                    'password': 'test123'
                }
            else:
                raise KeyError("service name invalid")

        self.setup_loader()
        self.loader.set_result(servicenow, 'config.option', get_config)

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
