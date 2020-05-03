# -*- coding: utf-8 -*-
"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
    :codeauthor: Tomas Sirny <tsirny@gmail.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.runtests import RUNTIME_VARS
from tests.support.helpers import expensiveTest, generate_random_name, flaky

TIMEOUT = 500


@expensiveTest
class GCETest(ShellCase):
    '''
    Integration tests for the GCE cloud provider in Salt-Cloud
    '''

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

    PROVIDER = "gce"
    REQUIRED_PROVIDER_CONFIG_ITEMS = (
        "project",
        "service_account_email_address",
        "service_account_private_key",
    )

    def test_instance(self):
        """
        Tests creating and deleting an instance on GCE
        """

        # create the instance
        ret_str = self.run_cloud(
            "-p gce-test {0}".format(self.instance_name), timeout=TIMEOUT
        )

        # check if instance returned with salt installed
        self.assertInstanceExists(ret_str)
        self.assertDestroyInstance()

    def test_instance_extra(self):
        """
        Tests creating and deleting an instance on GCE
        """

        # create the instance
        ret_str = self.run_cloud(
            "-p gce-test-extra {0}".format(self.instance_name), timeout=TIMEOUT
        )

        # check if instance returned with salt installed
        self.assertInstanceExists(ret_str)
        self.assertDestroyInstance()
