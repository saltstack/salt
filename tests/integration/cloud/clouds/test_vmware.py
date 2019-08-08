# -*- coding: utf-8 -*-
'''
    :codeauthor: Megan Wilhite <mwilhite@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
from salt.config import cloud_config
from salt.ext import six

# Import Salt Testing LIbs
from tests.support.paths import FILES

# Create the cloud instance name to be used throughout the tests
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest


@skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
@expensiveTest
class VMWareTest(ShellCase):
    '''
    Integration tests for the vmware cloud provider in Salt-Cloud
    '''

    @expensiveTest
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
                FILES,
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

        self.assertEqual(self._instance_exists(), False,
                         'The instance "{}" exists before it was created by the test'.format(self.instance_name))

    def test_instance(self):
        '''
        Tests creating and deleting an instance on vmware and installing salt
        '''
        # create the instance
        profile = os.path.join(
            FILES,
            'conf',
            'cloud.profiles.d',
            self.PROVIDER_NAME + '.conf'
        )

        profile_config = cloud_config(profile)
        disk_datastore = profile_config['vmware-test']['devices']['disk']['Hard disk 2']['datastore']

        instance = self.run_cloud('-p vmware-test {0}'.format(self.instance_name), timeout=TIMEOUT)
        ret_str = '{0}:'.format(self.instance_name)
        disk_datastore_str = '                [{0}] {1}/Hard disk 2-flat.vmdk'.format(disk_datastore, self.instance_name)

        # check if instance returned with salt installed
        self.assertInstanceExists(ret_val)
        self.assertIn(disk_datastore_str, ret_val,
                      msg='Hard Disk 2 did not use the Datastore {0} '.format(disk_datastore))

        self.assertDestroyInstance()

    def test_snapshot(self):
        '''
        Tests creating snapshot and creating vm with --no-deploy
        '''
        # create the instance
        instance = self.run_cloud('-p vmware-test {0} --no-deploy'.format(self.instance_name),
                                  timeout=TIMEOUT)
        ret_str = '{0}:'.format(self.instance_name)

        # check if instance returned with salt installed
        self.assertInstanceExists(ret_val)

        create_snapshot = self.run_cloud('-a create_snapshot {0} \
                                         snapshot_name=\'Test Cloud\' \
                                         memdump=True -y'.format(self.instance_name),
                                         timeout=TIMEOUT)
        s_ret_str = 'Snapshot created successfully'

        self.assertIn(s_ret_str, six.text_type(create_snapshot))

        self.assertDestroyInstance()
