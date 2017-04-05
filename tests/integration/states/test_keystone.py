# -*- coding: utf-8 -*-
'''
Tests for the Keystone states
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest
from tests.support.mixins import SaltReturnAssertsMixin

log = logging.getLogger(__name__)

NO_KEYSTONE = False
try:
    import keystoneclient  # pylint: disable=import-error,unused-import
except ImportError:
    NO_KEYSTONE = True


@skipIf(
    NO_KEYSTONE,
    'Please install keystoneclient and a keystone server before running'
    'keystone integration tests.'
)
class KeystoneStateTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the keystone state
    '''
    endpoint = 'http://localhost:35357/v2.0'
    token = 'administrator'

    @destructiveTest
    def setUp(self):
        ret = self.run_state('keystone.service_present',
                             name='keystone',
                             description='OpenStack Identity',
                             service_type='identity',
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-keystone_|-keystone_|-service_present']['result'])

        ret = self.run_state('keystone.endpoint_present',
                             name='keystone',
                             region='RegionOne',
                             publicurl='http://localhost:5000/v2.0',
                             internalurl='http://localhost:5000/v2.0',
                             adminurl='http://localhost:35357/v2.0',
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-keystone_|-keystone_|-endpoint_present']['result'])

        ret = self.run_state('keystone.tenant_present',
                             name='admin',
                             description='Admin Project',
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-admin_|-admin_|-tenant_present']['result'])

        ret = self.run_state('keystone.tenant_present',
                             name='demo',
                             description='Demo Project',
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-demo_|-demo_|-tenant_present']['result'])

        ret = self.run_state('keystone.role_present',
                             name='admin',
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-admin_|-admin_|-role_present']['result'])

        ret = self.run_state('keystone.role_present',
                             name='user',
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-user_|-user_|-role_present']['result'])

        ret = self.run_state('keystone.user_present',
                             name='admin',
                             email='admin@example.com',
                             password='adminpass',
                             tenant='admin',
                             roles={'admin': ['admin']},
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-admin_|-admin_|-user_present']['result'])

        ret = self.run_state('keystone.user_present',
                             name='demo',
                             email='demo@example.com',
                             password='demopass',
                             tenant='demo',
                             roles={'demo': ['user']},
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-demo_|-demo_|-user_present']['result'])

    @destructiveTest
    def test_keystone_v2(self):
        ret = self.run_state('keystone.service_present',
                             name='testv2',
                             description='Nova Service',
                             service_type='compute',
                             profile='adminv2')
        self.assertTrue(ret['keystone_|-testv2_|-testv2_|-service_present']['result'])

        ret = self.run_state('keystone.endpoint_present',
                             name='nova',
                             description='Nova Service',
                             publicurl='http://localhost:8774/v2.1/%(tenant_id)s',
                             internalurl='http://localhost:8774/v2.1/%(tenant_id)s',
                             adminurl='http://localhost:8774/v2.1/%(tenant_id)s',
                             region='RegionOne',
                             profile='adminv2')
        self.assertTrue(ret['keystone_|-nova_|-nova_|-endpoint_present']['result'])

        ret = self.run_state('keystone.tenant_present',
                             name='test',
                             description='Test Tenant',
                             profile='adminv2')
        self.assertTrue(ret['keystone_|-test_|-test_|-tenant_present']['result'])

        ret = self.run_state('keystone.role_present',
                             name='user',
                             profile='adminv2')
        self.assertTrue(ret['keystone_|-user_|-user_|-role_present']['result'])

        ret = self.run_state('keystone.user_present',
                             name='test',
                             email='test@example.com',
                             tenant='test',
                             password='testpass',
                             roles={'test': ['user']},
                             profile='adminv2')
        self.assertTrue(ret['keystone_|-test_|-test_|-user_present']['result'])

        ret = self.run_state('keystone.service_absent',
                             name='testv2',
                             profile='adminv2')
        self.assertTrue(ret['keystone_|-testv2_|-testv2_|-service_absent']['result'])

    @destructiveTest
    def test_keystone_v3(self):
        ret = self.run_state('keystone.service_present',
                             name='testv3',
                             description='Image Service',
                             service_type='image',
                             profile='adminv3')
        self.assertTrue(ret['keystone_|-testv3_|-testv3_|-service_present']['result'])

        ret = self.run_state('keystone.endpoint_present',
                             name='testv3',
                             description='Glance Service',
                             interface='public',
                             url='http://localhost:9292',
                             region='RegionOne',
                             profile='adminv3')
        self.assertTrue(ret['keystone_|-testv3_|-testv3_|-endpoint_present']['result'])

        ret = self.run_state('keystone.endpoint_present',
                             name='testv3',
                             description='Glance Service',
                             interface='internal',
                             url='http://localhost:9292',
                             region='RegionOne',
                             profile='adminv3')
        self.assertTrue(ret['keystone_|-testv3_|-testv3_|-endpoint_present']['result'])

        ret = self.run_state('keystone.endpoint_present',
                             name='testv3',
                             description='Glance Service',
                             interface='admin',
                             url='http://localhost:9292',
                             region='RegionOne',
                             profile='adminv3')
        self.assertTrue(ret['keystone_|-testv3_|-testv3_|-endpoint_present']['result'])

        ret = self.run_state('keystone.project_present',
                             name='testv3',
                             description='Test v3 Tenant',
                             profile='adminv3')
        self.assertTrue(ret['keystone_|-testv3_|-testv3_|-project_present']['result'])

        ret = self.run_state('keystone.role_present',
                             name='user',
                             profile='adminv3')
        self.assertTrue(ret['keystone_|-user_|-user_|-role_present']['result'])

        ret = self.run_state('keystone.user_present',
                             name='testv3',
                             email='testv3@example.com',
                             project='testv3',
                             password='testv3pass',
                             roles={'testv3': ['user']},
                             profile='adminv3')
        self.assertTrue(ret['keystone_|-testv3_|-testv3_|-user_present']['result'])

        ret = self.run_state('keystone.service_absent',
                             name='testv3',
                             profile='adminv3')
        self.assertTrue(ret['keystone_|-testv3_|-testv3_|-service_absent']['result'])
