# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import os
import random
import string

# Import Salt Testing Libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath, expensiveTest

ensure_in_syspath('../../../')

# Import Salt Libs
import integration  # pylint: disable=import-error
from salt.config import cloud_providers_config

# Import Third-Party Libs
# pylint: disable=import-error
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin
try:
    import libcloud  # pylint: disable=unused-import
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False
# pylint: enable=import-error


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
        profile_str = 'rackspace-config:'
        provider = 'rackspace'
        providers = self.run_cloud('--list-providers')
        if profile_str not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(provider)
            )

        # check if api key, user, and tenant are present
        path = os.path.join(integration.FILES,
                            'conf',
                            'cloud.providers.d',
                            provider + '.conf')
        config = cloud_providers_config(path)
        user = config['rackspace-config']['openstack']['user']
        tenant = config['rackspace-config']['openstack']['tenant']
        api = config['rackspace-config']['openstack']['apikey']
        if api == '' or tenant == '' or user == '':
            self.skipTest(
                'A user, tenant, and an api key must be provided to run these '
                'tests. Check tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(provider)
            )

    def test_instance(self):
        '''
        Test creating an instance on rackspace with the openstack driver
        '''

        # create the instance
        instance = self.run_cloud('-p rackspace-test {0}'.format(INSTANCE_NAME))
        ret = '        {0}'.format(INSTANCE_NAME)

        # check if instance with salt installed returned successfully
        try:
            self.assertIn(ret, instance)
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
            raise

        # delete the instance
        delete = self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
        ret = '            True'
        try:
            self.assertIn(ret, delete)
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
    from integration import run_tests  # pylint: disable=import-error
    run_tests(RackspaceTest)
