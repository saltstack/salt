# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
    :codeauthor: :email:`Tomas Sirny <tsirny@gmail.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import os
import random
import string

# Import Salt Libs
import integration
from salt.config import cloud_providers_config

# Import Salt Testing Libs
from salttesting.helpers import ensure_in_syspath, expensiveTest

ensure_in_syspath('../../../')

# Import Third-Party Libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin


def _random_name(size=6):
    '''
    Generates a radom cloud instance name
    '''
    return 'cloud-test-' + ''.join(
        random.choice(string.ascii_lowercase + string.digits)
        for x in range(size)
    )


class GCETest(integration.ShellCase):
    '''
    Integration tests for the GCE cloud provider in Salt-Cloud
    '''

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements
        '''
        super(GCETest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'gce-config:'
        provider = 'gce'
        providers = self.run_cloud('--list-providers')
        # Create the cloud instance name to be used throughout the tests
        self.INSTANCE_NAME = _random_name()

        if profile_str not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(provider)
            )

        # check if project, service_account_email_address, service_account_private_key
        # and provider are present
        path = os.path.join(integration.FILES,
                            'conf',
                            'cloud.providers.d',
                            provider + '.conf')
        config = cloud_providers_config(path)

        project = config['gce-config']['gce']['project']
        service_account_email_address = config['gce-config']['gce']['service_account_email_address']
        service_account_private_key = config['gce-config']['gce']['service_account_private_key']

        conf_items = [project, service_account_email_address, service_account_private_key]
        missing_conf_item = []

        for item in conf_items:
            if item == '':
                missing_conf_item.append(item)

        if missing_conf_item:
            self.skipTest(
                'An project, service_account_email_address, service_account_private_key must '
                'be provided to run these tests. One or more of these elements is '
                'missing. Check tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(provider)
            )

    def test_instance(self):
        '''
        Tests creating and deleting an instance on GCE
        '''

        # create the instance
        instance = self.run_cloud('-p gce-test {0}'.format(self.INSTANCE_NAME))
        ret_str = '{0}:'.format(self.INSTANCE_NAME)

        # check if instance returned with salt installed
        try:
            self.assertIn(ret_str, instance)
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(self.INSTANCE_NAME))
            raise

        # delete the instance
        delete = self.run_cloud('-d {0} --assume-yes'.format(self.INSTANCE_NAME))
        # example response: ['gce-config:', '----------', '    gce:', '----------', 'cloud-test-dq4e6c:', 'True', '']
        delete_str = ''.join(delete)

        # check if deletion was performed appropriately
        try:
            self.assertIn(self.INSTANCE_NAME, delete_str)
            self.assertIn('True', delete_str)
        except AssertionError:
            raise

    def test_instance_extra(self):
        '''
        Tests creating and deleting an instance on GCE
        '''

        # create the instance
        instance = self.run_cloud('-p gce-test-extra {0}'.format(self.INSTANCE_NAME))
        ret_str = '{0}:'.format(self.INSTANCE_NAME)

        # check if instance returned with salt installed
        try:
            self.assertIn(ret_str, instance)
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(self.INSTANCE_NAME))
            raise

        # delete the instance
        delete = self.run_cloud('-d {0} --assume-yes'.format(self.INSTANCE_NAME))
        # example response: ['gce-config:', '----------', '    gce:', '----------', 'cloud-test-dq4e6c:', 'True', '']
        delete_str = ''.join(delete)

        # check if deletion was performed appropriately
        try:
            self.assertIn(self.INSTANCE_NAME, delete_str)
            self.assertIn('True', delete_str)
        except AssertionError:
            raise

    def tearDown(self):
        '''
        Clean up after tests
        '''
        # salt-cloud -a show_instance myinstance
        query = self.run_cloud('--query')
        ret_str = '        {0}:'.format(self.INSTANCE_NAME)

        # if test instance is still present, delete it
        if ret_str in query:
            self.run_cloud('-d {0} --assume-yes'.format(self.INSTANCE_NAME))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GCETest)
