# -*- coding: utf-8 -*-
'''
    :codeauthor: Megan Wilhite <mwilhite@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Libs
from salt.config import cloud_providers_config, cloud_config
from salt.ext import six

# Import Salt Testing LIbs
from tests.support.case import ShellCase
from tests.support.runtests import RUNTIME_VARS
from tests.support.helpers import expensiveTest, generate_random_name

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('CLOUD-TEST-')
PROVIDER_NAME = 'vmware'
TIMEOUT = 500


@expensiveTest
class VMWareTest(ShellCase):
    '''
    Integration tests for the vmware cloud provider in Salt-Cloud
    '''

    def setUp(self):
        '''
        Sets up the test requirements
        '''

        # check if appropriate cloud provider and profile files are present
        profile_str = 'vmware-config'
        providers = self.run_cloud('--list-providers')

        if profile_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(PROVIDER_NAME)
            )

        # check if user, password, url and provider are present
        config = cloud_providers_config(
            os.path.join(
                RUNTIME_VARS.FILES,
                'conf',
                'cloud.providers.d',
                PROVIDER_NAME + '.conf'
            )
        )

        user = config[profile_str][PROVIDER_NAME]['user']
        password = config[profile_str][PROVIDER_NAME]['password']
        url = config[profile_str][PROVIDER_NAME]['url']

        conf_items = [user, password, url]
        missing_conf_item = []

        for item in conf_items:
            if item == '':
                missing_conf_item.append(item)

        if missing_conf_item:
            self.skipTest(
                'A user, password, and url must be provided to run these tests.'
                'One or more of these elements is missing. Check'
                'tests/integration/files/conf/cloud.providers.d/{0}.conf'
                .format(PROVIDER_NAME)
            )

    def test_instance(self):
        '''
        Tests creating and deleting an instance on vmware and installing salt
        '''
        # create the instance
        profile = os.path.join(
                RUNTIME_VARS.FILES,
                'conf',
                'cloud.profiles.d',
                PROVIDER_NAME + '.conf'
            )

        profile_config = cloud_config(profile)
        disk_datastore = profile_config['vmware-test']['devices']['disk']['Hard disk 2']['datastore']

        instance = self.run_cloud('-p vmware-test {0}'.format(INSTANCE_NAME), timeout=TIMEOUT)
        ret_str = '{0}:'.format(INSTANCE_NAME)
        disk_datastore_str = '                [{0}] {1}/Hard disk 2-flat.vmdk'.format(disk_datastore, INSTANCE_NAME)

        # check if instance returned with salt installed
        try:
            self.assertIn(ret_str, instance)
            self.assertIn(disk_datastore_str, instance,
                          msg='Hard Disk 2 did not use the Datastore {0} '.format(disk_datastore))
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=TIMEOUT)
            raise

        # delete the instance
        delete = self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=TIMEOUT)
        ret_str = '{0}:\', \'            True'.format(INSTANCE_NAME)

        # check if deletion was performed appropriately
        self.assertIn(ret_str, six.text_type(delete))

    def test_snapshot(self):
        '''
        Tests creating snapshot and creating vm with --no-deploy
        '''
        # create the instance
        instance = self.run_cloud('-p vmware-test {0} --no-deploy'.format(INSTANCE_NAME),
                                  timeout=TIMEOUT)
        ret_str = '{0}:'.format(INSTANCE_NAME)

        # check if instance returned with salt installed
        try:
            self.assertIn(ret_str, instance)
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=TIMEOUT)
            raise

        create_snapshot = self.run_cloud('-a create_snapshot {0} \
                                         snapshot_name=\'Test Cloud\' \
                                         memdump=True -y'.format(INSTANCE_NAME),
                                         timeout=TIMEOUT)
        s_ret_str = 'Snapshot created successfully'

        self.assertIn(s_ret_str, six.text_type(create_snapshot))

        # delete the instance
        delete = self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=TIMEOUT)
        ret_str = '{0}:\', \'            True'.format(INSTANCE_NAME)

        self.assertIn(ret_str, six.text_type(delete))

    def tearDown(self):
        '''
        Clean up after tests
        '''
        query = self.run_cloud('--query')
        ret_str = '        {0}:'.format(INSTANCE_NAME)

        # if test instance is still present, delete it
        if ret_str in query:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME), timeout=TIMEOUT)
