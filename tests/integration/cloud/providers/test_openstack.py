# -*- coding: utf-8 -*-
'''
Tests for the Openstack Cloud Provider
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest
from tests.support.mixins import SaltReturnAssertsMixin

log = logging.getLogger(__name__)

NO_KEYSTONE = False
try:
    import keystoneclient  # pylint: disable=import-error,unused-import
    from libcloud.common.openstack_identity import OpenStackIdentity_3_0_Connection
    from libcloud.common.openstack_identity import OpenStackIdentityTokenScope
except ImportError:
    NO_KEYSTONE = True


@skipIf(
    NO_KEYSTONE,
    'Please install keystoneclient and a keystone server before running'
    'openstack integration tests.'
)
class OpenstackTest(integration.ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the keystone state
    '''
    endpoint = 'http://localhost:35357/v2.0'
    token = 'administrator'

    @destructiveTest
    def test_aaa_setup_keystone_endpoint(self):
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
    def test_zzz_teardown_keystone_endpoint(self):
        ret = self.run_state('keystone.user_absent',
                             name='admin',
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-admin_|-admin_|-user_absent']['result'])

        ret = self.run_state('keystone.user_absent',
                             name='demo',
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-demo_|-demo_|-user_absent']['result'])

        ret = self.run_state('keystone.role_absent',
                             name='admin',
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-admin_|-admin_|-role_absent']['result'])

        ret = self.run_state('keystone.role_absent',
                             name='user',
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-user_|-user_|-role_absent']['result'])

        ret = self.run_state('keystone.tenant_absent',
                             name='admin',
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-admin_|-admin_|-tenant_absent']['result'])

        ret = self.run_state('keystone.tenant_absent',
                             name='demo',
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-demo_|-demo_|-tenant_absent']['result'])

        ret = self.run_state('keystone.service_absent',
                             name='keystone',
                             connection_endpoint=self.endpoint,
                             connection_token=self.token)
        self.assertTrue(ret['keystone_|-keystone_|-keystone_|-service_absent']['result'])

    @destructiveTest
    def test_libcloud_auth_v3(self):
        driver = OpenStackIdentity_3_0_Connection(auth_url='http://localhost:5000',
                                                  user_id='admin',
                                                  key='adminpass',
                                                  token_scope=OpenStackIdentityTokenScope.PROJECT,
                                                  domain_name='Default',
                                                  tenant_name='admin')
        driver.authenticate()
        self.assertTrue(driver.auth_token)
