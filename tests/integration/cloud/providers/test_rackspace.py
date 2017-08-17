# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.paths import FILES
from tests.support.unit import skipIf
from tests.support.helpers import expensiveTest, generate_random_name

# Import Salt Libs
from salt.config import cloud_providers_config

# Import Third-Party Libs
try:
    import libcloud  # pylint: disable=unused-import
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('CLOUD-TEST-')
PROVIDER_NAME = 'rackspace'
DRIVER_NAME = 'openstack'


@skipIf(HAS_LIBCLOUD is False, 'salt-cloud requires >= libcloud 0.13.2')
class RackspaceTest(ShellCase):
    '''
    Integration tests for the Rackspace cloud provider using the Openstack driver
    '''

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(RackspaceTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'rackspace-config'
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
                FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )

        user = config[profile_str][DRIVER_NAME]['user']
        tenant = config[profile_str][DRIVER_NAME]['tenant']
        api = config[profile_str][DRIVER_NAME]['apikey']
        if api == '' or tenant == '' or user == '':
            self.skipTest(
                'A user, tenant, and an api key must be provided to run these '
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
