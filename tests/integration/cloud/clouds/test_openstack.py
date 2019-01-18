# -*- coding: utf-8 -*-
'''
Tests for the Openstack Cloud Provider
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os

# Import Salt Testing libs
from tests.support.case import ModuleCase, ShellCase
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest, expensiveTest, generate_random_name
from tests.support.mixins import SaltReturnAssertsMixin

# Import Salt Libs
from salt.config import cloud_providers_config

log = logging.getLogger(__name__)

try:
    import keystoneclient  # pylint: disable=import-error,unused-import
    from libcloud.common.openstack_identity import OpenStackIdentity_3_0_Connection
    from libcloud.common.openstack_identity import OpenStackIdentityTokenScope
    HAS_KEYSTONE = True
except ImportError:
    HAS_KEYSTONE = False

# Import Third-Party Libs
try:
    import shade  # pylint: disable=unused-import
    HAS_SHADE = True
except ImportError:
    HAS_SHADE = False

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('CLOUD-TEST-')
PROVIDER_NAME = 'openstack'
DRIVER_NAME = 'openstack'


@skipIf(
    not HAS_KEYSTONE,
    'Please install keystoneclient and a keystone server before running'
    'openstack integration tests.'
)
@expensiveTest
class OpenstackTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the keystone state
    '''
    endpoint = 'http://localhost:35357/v2.0'
    token = 'administrator'

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


@skipIf(not HAS_SHADE, 'openstack driver requires `shade`')
@expensiveTest
class RackspaceTest(ShellCase):
    '''
    Integration tests for the Rackspace cloud provider using the Openstack driver
    '''

    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(RackspaceTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'openstack-config'
        providers = self.run_cloud('--list-providers')
        if profile_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(PROVIDER_NAME)
            )

        # check if personal access token, ssh_key_file, and ssh_key_names are present
        config = cloud_providers_config(
            os.path.join(
                RUNTIME_VARS.FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )

        region_name = config[profile_str][DRIVER_NAME].get('region_name')
        auth = config[profile_str][DRIVER_NAME].get('auth')
        cloud = config[profile_str][DRIVER_NAME].get('cloud')
        if not region_name or not (auth or cloud):
            self.skipTest(
                'A region_name and (auth or cloud) must be provided to run these '
                'tests. Check tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(PROVIDER_NAME)
            )

    def test_instance(self):
        '''
        Test creating an instance on rackspace with the openstack driver
        '''
        # check if instance with salt installed returned
        try:
            self.assertIn(
                INSTANCE_NAME,
                [i.strip() for i in self.run_cloud('-p rackspace-test {0}'.format(INSTANCE_NAME), timeout=500)]
            )
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)
            raise

        # delete the instance
        try:
            self.assertIn(
                INSTANCE_NAME + ':',
                [i.strip() for i in self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)]
            )
        except AssertionError:
            raise

    def tearDown(self):
        '''
        Clean up after tests
        '''
        query = self.run_cloud('--query')
        ret = '        {0}:'.format(INSTANCE_NAME)

        # if test instance is still present, delete it
        if ret in query:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=500)
