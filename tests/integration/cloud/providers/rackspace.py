# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
import os
import random
import string

# Import Salt Testing Libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath, expensiveTest

ensure_in_syspath('../../../')

# Import Salt Libs
import integration
from salt.config import cloud_providers_config

# Import Third-Party Libs
try:
    import libcloud  # pylint: disable=W0611
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False


def __random_name(size=6):
    '''
    Generates a random cloud instance name
    '''
    return 'CLOUD-TEST-' + ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for x in range(size)
    )

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = __random_name()
PROVIDER_NAME = 'rackspace'
DRIVER = 'openstack'


@skipIf(HAS_LIBCLOUD is False, 'salt-cloud requires >= libcloud 0.13.2')
class RackspaceTest(integration.ShellCase):
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

        # check if api key, user, and tenant are present
        config = cloud_providers_config(
            os.path.join(
                integration.FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )
        user = config[profile_str][DRIVER]['user']
        tenant = config[profile_str][DRIVER]['tenant']
        api = config[profile_str][DRIVER]['apikey']
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
                [i.strip() for i in self.run_cloud('-p rackspace-test {0}'.format(INSTANCE_NAME))]
            )
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
            raise

        # delete the instance
        try:
            self.assertIn(
                INSTANCE_NAME + ':',
                [i.strip() for i in self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))]
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
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RackspaceTest)
