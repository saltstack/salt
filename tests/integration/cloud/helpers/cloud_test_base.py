# -*- coding: utf-8 -*-
'''
Tests for the Openstack Cloud Provider
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
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
from salt.utils.yaml import safe_load

TIMEOUT = 600

log = logging.getLogger(__name__)


class CloudTest(ShellCase):
    PROVIDER = ''
    REQUIRED_PROVIDER_CONFIG_ITEMS = tuple()
    TMP_PROVIDER_DIR = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'cloud.providers.d')
    __RE_RUN_DELAY = 30
    __RE_TRIES = 12

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
        return set(x.strip(': ') for x in self.run_cloud('--query') if x.lstrip().lower().startswith('cloud-test-'))

    def _instance_exists(self, instance_name=None, query=None):
        '''
        :param instance_name: The name of the instance to check for in salt-cloud.
        For example this is may used when a test temporarily renames an instance
        :param query: The result of a salt-cloud --query run outside of this function
        '''
        if not instance_name:
            instance_name = self.instance_name
        if not query:
            query = self.query_instances()

        log.debug('Checking for "{}" in {}'.format(instance_name, query))
        if isinstance(query, set):
            return instance_name in query
        return any(instance_name == q.strip(': ') for q in query)

    def assertCreateInstance(self, profile=None, instance_name=None, timeout=None, args=None):
        if profile is None:
            profile = self.profile
        if args is None:
            args = []
        if timeout is None:
            timeout = TIMEOUT
        if not instance_name:
            instance_name = self.instance_name

        stdout, stderr = self.run_cloud('-p {0} {1} {2}'.format(profile, instance_name, ' '.join(args)),
                                        timeout=timeout, catch_stderr=True)
        self.assertInstanceExists(creation_ret=stdout, instance_name=instance_name, stderr=stderr)

    def assertInstanceExists(self, creation_ret=None, instance_name=None, stderr=None):
        '''
        :param instance_name: Override the checked instance name, otherwise the class default will be used.
        :param creation_ret: The return value from the run_cloud() function that created the instance
        :param stderr: When run_cloud is run with "catch_stderr=True" this is the stderr output
        '''
        if not instance_name:
            instance_name = self.instance_name

        if stderr:
            for line in stderr:
                if line.lstrip().startswith('[ERROR   ]'):
                    self.fail('\n'.join(stderr))

        # If it exists but doesn't show up in the creation_ret, there was probably an error during creation
        if creation_ret:
            self.assertIn(instance_name, [i.strip(': ') for i in creation_ret],
                          'An error occurred during instance creation:  |\n\t{}\n\t|'.format(
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
                            'Instance "{}" was not created successfully: {}'.format(self.instance_name,
                                                                                    ', '.join(query)))

            log.debug('Instance exists and was created: "{}"'.format(instance_name))

    def assertDestroyInstance(self, instance_name=None, deletion_ret=None, timeout=TIMEOUT):
        if not instance_name:
            instance_name = self.instance_name
        if not deletion_ret:
            log.debug('Deleting instance "{}"'.format(instance_name))
            deletion_ret = self.run_cloud('-d {0} --assume-yes --out=yaml'.format(instance_name), timeout=timeout)
        if deletion_ret:
            delete = safe_load('\n'.join(deletion_ret))
            self.assertIn(self.profile_str, delete)
            self.assertIn(self.PROVIDER, delete[self.profile_str])
            self.assertIn(instance_name, delete[self.profile_str][self.PROVIDER])

            delete_status = delete[self.profile_str][self.PROVIDER][instance_name]
            if isinstance(delete_status, str):
                self.assertEqual(delete_status, 'True')
                return
            elif isinstance(delete_status, dict):
                current_state = delete_status.get('currentState')
                if current_state:
                    if current_state.get('ACTION'):
                        self.assertIn('.delete', current_state.get('ACTION'))
                        return
                    else:
                        self.assertEqual(current_state.get('name'), 'shutting-down')
                        return
        # It's not clear from the delete string that deletion was successful, ask salt-cloud after a delay
        query = self.query_instances()
        # some instances take a while to report their destruction
        for tries in range(6):
            if self._instance_exists(query=query):
                sleep(30)
                log.debug('Instance "{}" still found in query after {} tries: {}'
                          .format(instance_name, tries, query))
                query = self.query_instances()
            else:
                break
        # The last query should have been successful
        self.assertNotIn(instance_name, query, 'Instance still exists after delete command. '
                                               'Is the timeout ({}s) long enough?'.format(timeout))

    @property
    def profile(self):
        if not hasattr(self, 'PROFILE'):
            self.PROFILE = self.PROVIDER + '-test'
        return self.PROFILE

    @property
    def instance_name(self):
        if not hasattr(self, '_instance_name'):
            # Create the cloud instance name to be used throughout the tests
            subclass = self.__class__.__name__.strip('Test')
            # Use the first three letters of the subclass, fill with '-' if too short, limit to 20 characters
            self._instance_name = generate_random_name('cloud-test-{:-<3}-'.format(subclass[:3])).lower()[:20]
        return self._instance_name

    @property
    def providers(self):
        if not hasattr(self, '_providers'):
            self._providers = [p.strip(':- ') for p in self.run_cloud('--list-providers') if p.strip(':- ')]
            log.debug('Available Providers: {}'.format(self._providers))
        return self._providers

    @property
    def provider_config_file(self):
        if not hasattr(self, 'PROVIDER_CONFIG'):
            self.PROVIDER_CONFIG = self.PROVIDER + '.conf'
        return self.PROVIDER_CONFIG

    @property
    def provider_config_path(self):
        return os.path.join(self.config_dir, 'cloud.providers.d', self.provider_config_file)

    @property
    def provider_config(self):
        if not hasattr(self, '_provider_config'):
            self._provider_config = cloud_providers_config(self.provider_config_path)
        return self._provider_config[self.profile_str][self.PROVIDER]

    @property
    def config_path(self):
        return os.path.join(self.config_dir, 'cloud.profiles.d', self.PROVIDER + '.conf')

    @property
    def config(self):
        if not hasattr(self, '_config'):
            self._config = cloud_config(self.config_path)
        return self._config

    @property
    def profile_str(self):
        if not hasattr(self, '_profile_str'):
            self._profile_str = self.PROVIDER + '-config'
            try:
                # There should be a single provider in the temporary directory,
                # Otherwise the setUpClass needs to be fixed
                self.assertEqual(self.providers[0], self._profile_str)
            except IndexError:
                self.skipTest(
                    'Configuration file \'{0}\' was not found. Check {1}.conf files '
                    'in tests/integration/files/conf/cloud.*.d/ to run these tests.'.format(self.profile_str,
                                                                                            self.PROVIDER)
                )
        return self._profile_str

    @expensiveTest
    def setUp(self):
        '''
        Sets up the test requirements.  In child classes, define PROVIDER and REQUIRED_CONFIG_ITEMS or this will fail
        '''
        super(CloudTest, self).setUp()

        if not self.PROVIDER:
            self.fail('A PROVIDER must be defined for this test')

        # check if appropriate cloud provider and profile files are present
        if self.profile_str not in self.providers:
            self.skipTest(
                'Configuration file \'{0}\' was not found in providers. Check {1}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.  {2}'.format(self.profile_str,
                                                                                             self.PROVIDER,
                                                                                             self.providers)
            )

        missing_conf_item = []
        for att in self.REQUIRED_PROVIDER_CONFIG_ITEMS:
            if not self.provider_config.get(att):
                missing_conf_item.append(att)

        if missing_conf_item:
            self.skipTest('Conf items are missing that must be provided to run these tests:  {}'
                          .format(', '.join(missing_conf_item)) +
                          '\nCheck tests/integration/files/conf/cloud.providers.d/{0}.conf'.format(self.PROVIDER))

    def _alt_names(self):
        '''
        Check for an instances created alongside this test's instance that weren't cleaned up
        '''
        query = self.query_instances()
        instances = set()
        for q in query:
            # Verify but this is a new name and not a shutting down ec2 instance
            if q.startswith(self.instance_name) and not q.split('-')[-1].startswith('DEL'):
                instances.add(q)
                log.debug('Adding "{}" to the set of instances that needs to be deleted'.format(q))
        return instances

    def _ensure_deletion(self, instance_name=None):
        '''
        Make sure that the instance absolutely gets deleted, but fail the test if it happens in the tearDown
        :return True if an instance was deleted, False if no instance was deleted; and a message
        '''
        destroyed = False
        if not instance_name:
            instance_name = self.instance_name

        if self._instance_exists(instance_name):
            for tries in range(3):
                try:
                    self.assertDestroyInstance(instance_name, timeout=TIMEOUT)
                    return False, 'The instance "{}" was deleted during the tearDown, not the test.'.format(
                        instance_name)
                except AssertionError as e:
                    log.error('Failed to delete instance "{}". Tries: {}\n{}'.format(instance_name, tries, str(e)))
                if not self._instance_exists():
                    destroyed = True
                    break
                else:
                    sleep(30)

            if not destroyed:
                # Destroying instances in the tearDown is a contingency, not the way things should work by default.
                return False, 'The Instance "{}" was not deleted after multiple attempts'.format(instance_name)

        return True, 'The instance "{}" cleaned up properly after the test'.format(instance_name)

    def tearDown(self):
        '''
        Clean up after tests, If the instance still exists for any reason, delete it.
        Instances should be destroyed before the tearDown, assertDestroyInstance() should be called exactly
        one time in a test for each instance created.  This is a failSafe and something went wrong
        if the tearDown is where an instance is destroyed.
        '''
        success = True
        fail_messages = []
        alt_names = self._alt_names()
        for instance in alt_names:
            alt_destroyed, alt_destroy_message = self._ensure_deletion(instance)
            if not alt_destroyed:
                success = False
                fail_messages.append(alt_destroy_message)
                log.error('Failed to destroy instance "{}": {}'.format(instance, alt_destroy_message))
        self.assertTrue(success, '\n'.join(fail_messages))
        self.assertFalse(alt_names, 'Cleanup should happen in the test, not the TearDown')

    @classmethod
    def tearDownClass(cls):
        cls.clean_cloud_dir(cls.TMP_PROVIDER_DIR)

    @classmethod
    def setUpClass(cls):
        if not cls.PROVIDER:
            raise ValueError('No provider was defined in child class')

        # clean up before setup
        cls.clean_cloud_dir(cls.TMP_PROVIDER_DIR)

        # add the provider config for only the cloud we are testing
        shutil.copyfile(os.path.join(FILES, 'conf', 'cloud.providers.d', cls.PROVIDER + '.conf'),
                        os.path.join(cls.TMP_PROVIDER_DIR, cls.PROVIDER + '.conf'))
