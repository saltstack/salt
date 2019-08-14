# -*- coding: utf-8 -*-
'''
Tests for the Openstack Cloud Provider
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
from os import path
from time import sleep

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.support.helpers import generate_random_name, expensiveTest
from tests.support.paths import FILES

# Import Salt Libs
from salt.config import cloud_config, cloud_providers_config
from salt.ext.six.moves import range

TIMEOUT = 500

log = logging.getLogger(__name__)


class CloudTest(ShellCase):
    PROVIDER = ''
    REQUIRED_PROVIDER_CONFIG_ITEMS = tuple()
    __RE_RUN_DELAY = 15
    __RE_TRIES = 12

    def _instance_exists(self, instance_name=None, query=None):
        '''
        :param instance_name: The name of the instance to check for in salt-cloud.
        For example this is may used when a test temporarily renames an instance
        :param query: The result of a salt-cloud --query run outside of this function
        '''
        # salt-cloud -a show_instance myinstance
        if not instance_name:
            instance_name = self.instance_name
        if not query:
            query = self.run_cloud('--query')
        log.debug('Checking for "{}" in => {}'.format(instance_name, query))
        if isinstance(query, set):
            return instance_name in query
        return any(instance_name == q.strip(': ') for q in query)

    def assertInstanceExists(self, creation_ret=None, instance_name=None):
        '''
        :param instance_name: Override the checked instance name, otherwise the class default will be used.
        :param creation_ret: The return value from the run_cloud() function that created the instance
        '''
        if not instance_name:
            instance_name = self.instance_name

        # Verify that the instance exists via query
        self.assertTrue(self._instance_exists(instance_name), 'Instance "{}" was not created successfully: `{}`'
                        .format(instance_name, creation_ret))

        # If it exists but doesn't show up in the creation_ret, there was an error during creation
        if creation_ret:
            self.assertIn(instance_name, [i.strip(': ') for i in creation_ret])
        self.assertTrue(self._instance_exists(instance_name), 'Instance "{}" was not created successfully: `{}`'
                        .format(instance_name, creation_ret))

    def _destroy_instance(self):
        log.debug('Deleting instance "{}"'.format(self.instance_name))
        delete = self.run_cloud('-d {0} --assume-yes'.format(self.instance_name), timeout=TIMEOUT)
        # example response: ['gce-config:', '----------', '    gce:', '----------', 'cloud-test-dq4e6c:', 'True', '']
        delete_str = ''.join(delete)
        log.debug('Deletion status: {}'.format(delete_str))

        if any([x in delete_str for x in (
            'True',
            'was successfully deleted'
        )]):
            log.debug('Instance "{}" was successfully deleted'.format(self.instance_name))
        elif any([x in delete_str for x in (
            'shutting-down',
            '.delete',
        )]):
            log.debug('Instance "{}" is cleaning up'.format(self.instance_name))
            sleep(30)
        else:
            log.warning('Instance "{}" may not have been deleted properly'.format(self.instance_name))

        return delete_str

    def assertDestroyInstance(self):
        delete_str = self._destroy_instance()
        self.assertFalse(self._instance_exists(), 'Could not destroy "{}".  Delete_str: `{}`'
                         .format(self.instance_name, delete_str))
        log.debug('Instance "{}" no longer exists'.format(self.instance_name))

    @property
    def instance_name(self):
        if not hasattr(self, '_instance_name'):
            # Create the cloud instance name to be used throughout the tests
            subclass = self.__class__.__bases__[0].__name__.strip('Test')
            # Use the first three letters of the subclass, fill with '-' if too short
            self.__instance_name = generate_random_name('cloud-test-{:-<3}-'.format(subclass[:3])).lower()
        return self.__instance_name

    @property
    def providers(self):
        if not hasattr(self, '_providers'):
            self._providers = self.run_cloud('--list-providers')
        return self._providers

    @property
    def provider_config(self):
        if not hasattr(self, '_provider_config'):
            self._provider_config = cloud_providers_config(
                path.join(
                    FILES,
                    'conf',
                    'cloud.providers.d',
                    self.PROVIDER + '.conf'
                )
            )
        return self._provider_config[self.profile_str][self.PROVIDER]

    @property
    def config(self):
        if not hasattr(self, '_config'):
            self._config = cloud_config(
                path.join(
                    FILES,
                    'conf',
                    'cloud.profiles.d',
                    self.PROVIDER + '.conf'
                )
            )
        return self._config

    @property
    def profile_str(self):
        return self.PROVIDER + '-config'

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements.  In child classes, define PROVIDER and REQUIRED_CONFIG_ITEMS or this will fail
        '''
        super(CloudTest, self).setUp()

        if not self.PROVIDER:
            self.fail('A PROVIDER must be defined for this test')

        # check if appropriate cloud provider and profile files are present
        if self.profile_str + ':' not in self.providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                    .format(self.PROVIDER)
            )

        missing_conf_item = []
        for att in self.REQUIRED_PROVIDER_CONFIG_ITEMS:
            if not self.provider_config.get(att):
                missing_conf_item.append(att)

        if missing_conf_item:
            self.skipTest('Conf items are missing that must be provided to run these tests:  {}'
                          .format(', '.join(missing_conf_item)) +
                          '\nCheck tests/integration/files/conf/cloud.providers.d/{0}.conf'.format(self.PROVIDER))

        self.assertFalse(self._instance_exists(),
                         'The instance "{}" exists before it was created by the test'.format(self.instance_name))

    def tearDown(self):
        '''
        Clean up after tests, If the instance still exists for any reason, delete it.
        Instances should be destroyed before the tearDown, _destroy_instance() should be called exactly
        one time in a test for each instance created.  This is a failSafe and something went wrong
        if the tearDown is where an instance is destroyed.
        '''
        # Make sure that the instance for sure gets deleted, but fail the test if it happens in the tearDown
        instance_deleted_before_teardown = True
        for _ in range(12):
            if self._instance_exists():
                sleep(30)
                instance_deleted_before_teardown = False
                self._destroy_instance()

        self.assertFalse(self._instance_exists(), 'Instance exists after multiple attempts to delete: {}'
                         .format(self.instance_name))

        # Destroying instances in the tearDown is a contingency, not the way things should work by default.
        self.assertTrue(instance_deleted_before_teardown,
                        'The Instance "{}" was deleted during the tearDown, not the test.'.format(self.instance_name))
