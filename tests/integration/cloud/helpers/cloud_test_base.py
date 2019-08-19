# -*- coding: utf-8 -*-
'''
Tests for the Openstack Cloud Provider
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
from ast import literal_eval
from time import sleep
import logging
import os
import shutil

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.support.helpers import generate_random_name, expensiveTest
from tests.support.paths import FILES
from tests.support.runtests import RUNTIME_VARS

# Import Salt Libs
from salt.config import cloud_config, cloud_providers_config
from salt.ext.six.moves import range
from salt.utils import yaml

TIMEOUT = 500

log = logging.getLogger(__name__)
TIMEOUT = 500


class CloudTest(ShellCase):
    PROVIDER = ''
    REQUIRED_PROVIDER_CONFIG_ITEMS = tuple()
    TMP_PROVIDER_DIR = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'cloud.providers.d')
    __RE_RUN_DELAY = 15
    __RE_TRIES = 3

    @staticmethod
    def clean_cloud_dir(tmp_dir):
        '''
        Clean the cloud.providers.d tmp directory
        '''
        # make sure old provider configs are deleted
        for i in os.listdir(tmp_dir):
            os.remove(os.path.join(tmp_dir, i))

    def query_instances(self):
        '''
        Standardize the data returned from a salt-cloud --query
        '''
        return literal_eval(self.run_cloud('--query --out=highstate')).keys()

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
            query = self.query_instances()

        log.debug('Checking for "{}" in {}'.format(instance_name, query))
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

        # If it exists but doesn't show up in the creation_ret, there was probably an error during creation
        if creation_ret:
            self.assertIn(instance_name, [i.strip(': ') for i in creation_ret],
                          'An error occured during instance creation:  |\n\t{}\n\t|'.format(
                              '\n\t'.join(creation_ret)
                          ))
        else:
            # Verify that the instance exists via query
            query = self.query_instances()
            for tries in range(self.__RE_TRIES):
                if self._instance_exists(instance_name, query):
                    log.debug(
                        'Instance "{}" reported after {} seconds'.format(instance_name, tries * self.__RE_RUN_DELAY))
                    break
                else:
                    sleep(self.__RE_RUN_DELAY)
                    query = self.query_instances()

            # Assert that the last query was successful
            self.assertTrue(self._instance_exists(instance_name, query),
                            'Instance "{}" was not created successfully: '.format(', '.join(query)))

            log.debug('Instance exists and was created: "{}"'.format(instance_name))

    def _destroy_instance(self):
        shutdown_delay = 30
        log.debug('Deleting instance "{}"'.format(self.instance_name))
        delete_str = self.run_cloud('-d {0} --assume-yes --out=yaml'.format(self.instance_name), timeout=TIMEOUT)
        delete = safe_load('\n'.join(delete_str))
        # example response: ['gce-config:', '----------', '    gce:', '----------', 'cloud-test-dq4e6c:', 'True', '']
        delete_str = ''.join(delete)
        log.debug('Deletion status: {}'.format(delete_str))

        if any([x in delete_str for x in (
            'True',
            'was successfully deleted'
        )]):
            destroyed = True
            log.debug('Instance "{}" was successfully deleted'.format(self.instance_name))
        elif any([x in delete_str for x in (
            'shutting-down',
            '.delete',
            self.instance_name + '-DEL'
        )]):
            sleep(shutdown_delay)
            destroyed = True
            log.debug('Instance "{}" is cleaning up'.format(self.instance_name))
        else:
            sleep(shutdown_delay)
            # It's not clear from the delete string that deletion was successful, ask salt-cloud
            query = self.query_instances()
            destroyed = self.instance_name in query
            delete_str += ' :: ' * bool(delete_str) + ', '.join(query)

        return destroyed, delete_str

    def assertDestroyInstance(self):
        success, delete_str = self._destroy_instance()
        self.assertTrue(success, 'Instance "{}" was not deleted: {}'.format(self.instance_name, delete_str))

    @property
    def INSTANCE_NAME(self):
        if not hasattr(self, '_instance_name'):
            # Create the cloud instance name to be used throughout the tests
            self._instance_name = generate_random_name('cloud-test-').lower()
        return self._instance_name

    @property
    def providers(self):
        if not hasattr(self, '_providers'):
            self._providers = self.run_cloud('--list-providers')
        return self._providers

    @property
    def provider_config(self):
        if not hasattr(self, '_provider_config'):
            self._provider_config = cloud_providers_config(
                os.path.join(
                    self.config_dir,
                    'cloud.providers.d',
                    self.PROVIDER + '.conf'
                )
            )
        return self._provider_config[self.profile_str][self.PROVIDER]

    @property
    def config(self):
        if not hasattr(self, '_config'):
            self._config = cloud_config(
                os.path.join(
                    self.config_dir,
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

    def _destroy_instance(self):
        delete = self.run_cloud('-d {0} --assume-yes'.format(self.INSTANCE_NAME), timeout=TIMEOUT)
        # example response: ['gce-config:', '----------', '    gce:', '----------', 'cloud-test-dq4e6c:', 'True', '']
        delete_str = ''.join(delete)

        # TODO assert that 'shutting-down' will be in the delete_str?
        if 'shutting-down' in delete_str:
            log.debug('Instance "{}" was deleted properly'.format(self.INSTANCE_NAME))
        else:
            log.warning('Instance "{}" was not deleted'.format(self.INSTANCE_NAME))
        self.assertEqual(self._instance_exists(), False)

    def tearDown(self):
        '''
        Clean up after tests, If the instance still exists for any reason, delete it.
        Instances should be destroyed before the tearDown, assertDestroyInstance() should be called exactly
        one time in a test for each instance created.  This is a failSafe and something went wrong
        if the tearDown is where an instance is destroyed.
        '''
        # Make sure that the instance for sure gets deleted, but fail the test if it happens in the tearDown
        destroyed = False
        if self._instance_exists():
            for _ in range(3):
                sleep(30)
                success, result_str = self._destroy_instance()
                if success:
                    self.fail('The instance "{}" was deleted during the tearDown, not the test.'.format(
                        self.instance_name))
                if not self._instance_exists():
                    destroyed = True
                    break

            if not destroyed:
                # Destroying instances in the tearDown is a contingency, not the way things should work by default.
                self.fail('The Instance "{}" was not deleted after multiple attempts'.format(self.instance_name))

    @classmethod
    def tearDownClass(cls):
        cls.clean_cloud_dir(cls, cls.TMP_PROVIDER_DIR)

    @classmethod
    def setUpClass(cls):
        # clean up before setup
        cls.clean_cloud_dir(cls, cls.TMP_PROVIDER_DIR)

        # add the provider config for only the cloud we are testing
        provider_file = cls.PROVIDER + '.conf'
        shutil.copyfile(os.path.join(os.path.join(FILES, 'conf', 'cloud.providers.d'), provider_file),
                        os.path.join(os.path.join(cls.TMP_PROVIDER_DIR, provider_file)))
