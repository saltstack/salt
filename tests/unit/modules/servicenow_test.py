# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON
)
from salttesting.helpers import ensure_in_syspath
from salt.modules import servicenow

ensure_in_syspath('../../')

SERVICE_NAME = 'servicenow'


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ServiceNowModuleTestCase(TestCase):
    def setUp(self):
        __salt__['config.option'][SERVICE_NAME] = {
            'instance_name': 'test',
            'username': 'mr_test',
            'password': 'test123'
        }

    def test_module_creation(self):
        client = servicenow._get_client()
        self.assertNotNone(client)

if __name__ == '__main__':
    from unit import run_tests
    run_tests(ServiceNowModuleTestCase)
