# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf
from tests.unit import ModuleTestCase, hasDependency
from salttesting.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
from salttesting.helpers import ensure_in_syspath
from salt.modules import servicenow

ensure_in_syspath('../../')

SERVICE_NAME = 'servicenow'
servicenow.__salt__ = {}


class MockServiceNowClient(object):
    def __init__(self, instance_name, username, password):
        pass


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('servicenow_rest.api.Client', MockServiceNowClient)
class ServiceNowModuleTestCase(ModuleTestCase):
    def setUp(self):
        hasDependency('servicenow_rest')
        servicenow.Client = MockServiceNowClient

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

if __name__ == '__main__':
    from unit import run_tests
    run_tests(ServiceNowModuleTestCase)
