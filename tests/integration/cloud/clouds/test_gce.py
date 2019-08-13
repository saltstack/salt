# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
    :codeauthor: Tomas Sirny <tsirny@gmail.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest
from tests.support.unit import skipIf

TIMEOUT = 500

@skipIf(True, 'WAR ROOM TEMPORARY SKIP')  # needs to be rewritten to allow for dnf on Fedora 30 and RHEL 8
class GCETest(CloudTest):
    '''
    Integration tests for the GCE cloud provider in Salt-Cloud
    '''
    PROVIDER = 'gce'
    REQUIRED_PROVIDER_CONFIG_ITEMS = ('project', 'service_account_email_address', 'service_account_private_key')

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
        self.INSTANCE_NAME = generate_random_name('cloud-test-').lower()

        if profile_str not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                .format(provider)
            )

        # check if project, service_account_email_address, service_account_private_key
        # and provider are present
        path = os.path.join(RUNTIME_VARS.FILES,
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

    @flaky
    def test_instance(self):
        '''
        Tests creating and deleting an instance on GCE
        '''

        # create the instance
        instance = self.run_cloud('-p gce-test {0}'.format(self.INSTANCE_NAME), timeout=TIMEOUT)
        ret_str = '{0}:'.format(self.INSTANCE_NAME)

        # check if instance returned with salt installed
        self.assertInstanceExists(ret_str)
        # Let the instance exist for half a minute before destroying it
        sleep(30)

        self._destroy_instance()

        self.assertDestroyInstance()

    @flaky
    def test_instance_extra(self):
        '''
        Tests creating and deleting an instance on GCE
        '''

        # create the instance
        ret_str = self.run_cloud('-p gce-test-extra {0}'.format(self.instance_name), timeout=TIMEOUT)

        # check if instance returned with salt installed
        self.assertInstanceExists(ret_str)

        self.assertDestroyInstance()
