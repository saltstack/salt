# -*- coding: utf-8 -*-
'''
    :codeauthor: Megan Wilhite <mwilhite@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
from salt.ext import six

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = generate_random_name('CLOUD-TEST-')
PROVIDER_NAME = 'vmware'
TIMEOUT = 500


@skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
@expensiveTest
class VMWareTest(ShellCase):
    '''
    Integration tests for the vmware cloud provider in Salt-Cloud
    '''
    PROVIDER = 'vmware'
    REQUIRED_PROVIDER_CONFIG_ITEMS = ('password', 'user', 'url')

    def test_instance(self):
        '''
        Tests creating and deleting an instance on vmware and installing salt
        '''
        # create the instance
        profile_config = cloud_config(self.provider_config)
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

        self.assertDestroyInstance()

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

        self.assertDestroyInstance()
