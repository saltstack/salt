# -*- coding: utf-8 -*-
"""
    Tests for the Openstack Cloud Provider
    :codeauthor: Tyler Johnson <tjohnson@saltstack.com>
"""

from __future__ import absolute_import, print_function, unicode_literals

import functools
import inspect
import logging
import os
import shutil
import time
from time import sleep

# Import Salt Libs
import salt.utils.cloud
import salt.utils.files
import salt.utils.yaml
from salt.config import (
    cloud_config,
    cloud_providers_config,
    is_profile_configured,
    is_provider_configured,
)
from salt.ext.six.moves import range
from salt.utils.yaml import safe_load
from tests.support.case import ShellCase
from tests.support.helpers import expensiveTest, random_string
from tests.support.paths import FILES
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import SkipTest

log = logging.getLogger(__name__)


def requires_profile_config(profile_config_name=None):
    """
    Makes sure the passed profile config items are present. Skips the test if not

    .. versionadded:: 3001
    :param profile_config_name: The name of the profile to check if not the default, only works for decorating funcs
    :param names: The config items that must be present in the profile
    """

    def decorator(caller):
        # Only Decorate Functions
        @functools.wraps(caller)
        def wrapper(cls):
            assert isinstance(cls, CloudTest)
            # Access the profile config property first to define cls._full_profile_config

            if not cls._profile_configured(
                profile_config_name=profile_config_name
                if profile_config_name
                else cls.profile_config_name
            ):
                raise SkipTest(
                    "Conf items are missing that must be provided to run these tests"
                )

            return caller(cls)

        return wrapper

    return decorator


def requires_provider_config(*names, **any_groups):
    """
    :param names: The names of keys required to be in the provider config
    :param any_groups: dict which contain the names of keys, any one of which must be in the provider config

    Makes sure the passed provider config items are present. Skips the test if not

    .. versionadded:: 3001
    """

    def decorator(caller):
        if inspect.isclass(caller):
            # We're decorating a class
            old_setup = getattr(caller, "setUp", None)

            def setUp(self, *args, **kwargs):
                src = "tests/integration/files/conf/cloud.providers.d/{0}.conf".format(
                    self.PROVIDER
                )

                if not self.provider_config:
                    self.skipTest("Provider config is empty, check {}".format(src))

                opts = {"providers": self.provider_config}
                if not is_provider_configured(
                    opts=opts,
                    provider="{}:{}".format(self.provider_config_name, self.PROVIDER),
                    required_keys=(name for name in names if isinstance(name, str)),
                ):
                    self.skipTest(
                        "{} provider is not configured properly, requires: {}".format(
                            self.PROVIDER, names
                        )
                    )

                for require_any in any_groups.values():
                    if require_any and not any(
                        is_provider_configured(
                            opts=opts,
                            provider="{}:{}".format(
                                self.provider_config_name, self.PROVIDER
                            ),
                            required_keys=[name],
                        )
                        for name in require_any
                    ):
                        self.skipTest(
                            "{} provider is not configured properly, requires one of: {}".format(
                                self.PROVIDER, require_any
                            )
                        )
                if old_setup is not None:
                    old_setup(self, *args, **kwargs)

            caller.setUp = setUp
            return caller

        # We're simply decorating functions
        @functools.wraps(caller)
        def wrapper(cls):
            assert isinstance(cls, CloudTest)
            src = "tests/integration/files/conf/cloud.providers.d/{0}.conf".format(
                cls.PROVIDER
            )

            if not cls.provider_config:
                raise SkipTest("Provider config is empty, check {}".format(src))

            opts = {"providers": cls.provider_config}
            for require_any in any_groups.values():
                if not any(
                    is_provider_configured(
                        opts=opts,
                        provider="{}:{}".format(cls.provider_config_name, cls.PROVIDER),
                        required_keys=[name],
                    )
                    for name in require_any
                ):
                    raise SkipTest(
                        "{} provider is not configured properly, requires one of: {}".format(
                            cls.PROVIDER, require_any
                        )
                    )

                if not any(
                    is_provider_configured(
                        opts=opts,
                        provider="{}:{}".format(cls.provider_config_name, cls.PROVIDER),
                        required_keys=name,
                    )
                    for name in require_any
                ):
                    raise SkipTest(
                        "{} provider is not configured properly, requires one of: {}".format(
                            cls.PROVIDER, require_any
                        )
                    )
            return caller(cls)

        return wrapper

    return decorator


class OverrideCloudConfig:
    """
    Override a cloud config with new values,
    Return the profile back to normal afterwards
    """

    def __init__(self, config_path, config_name, **data):
        """
        :param config_path: Profile or Provider config path
        :param config_name: Profile or Provider config name
        :param data: all other keyword arguments will be converted to yaml and override the config yaml key values
        """
        self.config_path = config_path
        self.config_name = config_name
        self.data = data

        with salt.utils.files.fopen(config_path, "r") as fp:
            self.original_conf_yaml = salt.utils.yaml.safe_load(fp)

    def __enter__(self):
        conf = self.original_conf_yaml.copy()
        conf[self.config_name].update(self.data)
        with salt.utils.files.fopen(self.config_path, "w") as fp:
            salt.utils.yaml.safe_dump(conf, fp)
        return conf

    def __exit__(self, exc_type, exc_value, traceback):
        with salt.utils.files.fopen(self.config_path, "w") as fp:
            salt.utils.yaml.safe_dump(self.original_conf_yaml, fp)


@expensiveTest
class CloudTest(ShellCase):
    TEST_TIMEOUT = 600
    TMP_PROVIDER_DIR = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "cloud.providers.d")
    PROVIDER = None
    PROVIDER_CONFIG_FILE = None
    PROFILE_CONFIG_FILE = None
    PROFILE_CONFIG_NAME = None
    _providers = None
    _provider_config_name = None
    _instance_name = None
    __RE_RUN_DELAY = 30
    __RE_TRIES = 12

    @staticmethod
    def clean_cloud_dir(tmp_dir):
        """
        Clean the cloud.providers.d tmp directory
        """
        # make sure old provider opts configs are deleted
        for file in os.listdir(tmp_dir):
            path = os.path.join(tmp_dir, file)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

    def query_instances(self):
        """
        Standardize the data returned from a salt-cloud --query
        """
        return set(
            x.strip(": ")
            for x in self.run_cloud("--query", timeout=self.TEST_TIMEOUT)
            if x.lstrip().lower().startswith("cloud-test-")
        )

    def _instance_exists(self, instance_name=None, query=None):
        """
        :param instance_name: The name of the instance to check for in salt-cloud.
        For example this is may used when a test temporarily renames an instance
        :param query: The result of a salt-cloud --query run outside of this function
        """
        if not instance_name:
            instance_name = self.instance_name
        if not query:
            query = self.query_instances()

        log.debug('Checking for "{}" in {}'.format(instance_name, query))
        if isinstance(query, set):
            return instance_name in query
        return any(instance_name == q.strip(": ") for q in query)

    def assertCreateInstance(
        self, profile_config_name=None, instance_name=None, args=None
    ):
        if profile_config_name is None:
            profile_config_name = self.profile_config_name
        if args is None:
            args = []
        if not instance_name:
            instance_name = self.instance_name

        stdout, stderr = self.run_cloud(
            "-p {0} {1} {2}".format(profile_config_name, instance_name, " ".join(args)),
            timeout=self.TEST_TIMEOUT,
            catch_stderr=True,
        )
        self.assertInstanceExists(
            creation_ret=stdout, instance_name=instance_name, stderr=stderr
        )

    def assertInstanceExists(self, creation_ret=None, instance_name=None, stderr=None):
        """
        :param instance_name: Override the checked instance name, otherwise the class default will be used.
        :param creation_ret: The return value from the run_cloud() function that created the instance
        :param stderr: When run_cloud is run with "catch_stderr=True" this is the stderr output
        """
        if not instance_name:
            instance_name = self.instance_name

        if stderr:
            # Verify that no errors were returned in the log
            self.assertFalse(
                [line for line in stderr if line.lstrip().startswith("[ERROR   ]")],
                stderr,
            )

        # If it exists but doesn't show up in the creation_ret, there was probably an error during creation
        if creation_ret:
            self.assertIn(
                instance_name,
                [i.strip(": ") for i in creation_ret],
                "An error occurred during instance creation:  |\n\t{}\n\t|".format(
                    "\n\t".join(creation_ret)
                ),
            )
        else:
            # Verify that the instance exists via query
            query = self.query_instances()
            for tries in range(self.__RE_TRIES):
                if self._instance_exists(instance_name, query):
                    log.debug(
                        'Instance "{}" reported after {} seconds'.format(
                            instance_name, tries * self.__RE_RUN_DELAY
                        )
                    )
                    break
                else:
                    time.sleep(self.__RE_RUN_DELAY)
                    query = self.query_instances()

            # Assert that the last query was successful
            self.assertTrue(
                self._instance_exists(instance_name, query),
                'Instance "{}" was not created successfully: {}'.format(
                    self.instance_name, ", ".join(query)
                ),
            )

            log.debug('Instance exists and was created: "{}"'.format(instance_name))

    def assertDestroyInstance(self, instance_name=None, deletion_ret=None):
        if not instance_name:
            instance_name = self.instance_name
        if not deletion_ret:
            log.debug('Deleting instance "{}"'.format(instance_name))
            deletion_ret = self.run_cloud(
                "-d {0} --assume-yes --out=yaml".format(instance_name),
                timeout=self.TEST_TIMEOUT,
            )
        if deletion_ret:
            delete = safe_load("\n".join(deletion_ret))
            self.assertIn(self.provider_config_name, delete)
            self.assertIn(self.PROVIDER, delete[self.provider_config_name])
            self.assertIn(
                instance_name, delete[self.provider_config_name][self.PROVIDER]
            )

            delete_status = delete[self.provider_config_name][self.PROVIDER][
                instance_name
            ]
            if isinstance(delete_status, str):
                self.assertEqual(delete_status, "True")
                return
            elif isinstance(delete_status, dict):
                current_state = delete_status.get("currentState")
                if current_state:
                    if current_state.get("ACTION"):
                        self.assertIn(".delete", current_state.get("ACTION"))
                        return
                    else:
                        self.assertEqual(current_state.get("name"), "shutting-down")
                        return
        # It's not clear from the delete string that deletion was successful, ask salt-cloud after a delay
        query = self.query_instances()
        # some instances take a while to report their destruction
        for tries in range(6):
            if self._instance_exists(query=query):
                time.sleep(30)
                log.debug(
                    'Instance "{}" still found in query after {} tries: {}'.format(
                        instance_name, tries, query
                    )
                )
                query = self.query_instances()
            else:
                break
        # The last query should have been successful
        self.assertNotIn(
            instance_name,
            query,
            "Instance still exists after delete command. "
            "Is the timeout ({}s) long enough?".format(self.TEST_TIMEOUT),
        )

    @property
    def instance_name(self):
        if not self._instance_name:
            # Create the cloud instance name to be used throughout the tests
            subclass = self.__class__.__name__.strip("Test")
            # Use the first three letters of the subclass, fill with '-' if too short, limit to 20 characters
            self._instance_name = generate_random_name(
                "cloud-test-{:-<3}-".format(subclass[:3])
            ).lower()[:20]
        return self._instance_name

    @property
    def providers(self):
        """
        Return a list of the available providers
        """
        if not self._providers:
            self._providers = [
                p.strip(":- ")
                for p in self.run_cloud("--list-providers", timeout=self.TEST_TIMEOUT)
                if p.strip(":- ")
            ]
            log.debug("Available Providers: {}".format(self._providers))
        return self._providers

    @property
    def provider_config_file(self):
        if not self.PROVIDER_CONFIG_FILE:
            self.PROVIDER_CONFIG_FILE = self.PROVIDER + ".conf"
        return self.PROVIDER_CONFIG_FILE

    @property
    def provider_config_path(self):
        return os.path.join(
            self.config_dir, "cloud.providers.d", self.provider_config_file
        )

    @property
    def provider_config(self):
        # If this value is saved as a class variable then it risks getting logged
        return cloud_providers_config(self.provider_config_path)

    @property
    def provider_config_name(self):
        if not self._provider_config_name:
            self._provider_config_name = self.PROVIDER + "-config"
        return self._provider_config_name

    @property
    def profile_config_file(self):
        if not self.PROFILE_CONFIG_FILE:
            self.PROFILE_CONFIG_FILE = self.PROVIDER + ".conf"
        return self.PROFILE_CONFIG_FILE

    @property
    def profile_config_path(self):
        return os.path.join(
            self.config_dir, "cloud.profiles.d", self.profile_config_file
        )

    @property
    def profiles(self):
        # Don't store this because it can change with overrides
        return cloud_config(
            self.profile_config_path, profiles_config_path=self.profile_config_path
        )

    @property
    def profile_config(self):
        return self.profiles[self.profile_config_name]

    @property
    def profile_config_name(self):
        if not self.PROFILE_CONFIG_NAME:
            self.PROFILE_CONFIG_NAME = self.PROVIDER + "-test"
        return self.PROFILE_CONFIG_NAME

    def setUp(self):
        """
        Sets up the test requirements.  In child classes, define PROVIDER and REQUIRED_CONFIG_ITEMS or this will fail
        """
        super(CloudTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        if self.provider_config_name not in self.providers:
            self.skipTest(
                'Provider "{0}" was not found in "{1}". Check conf files '
                "in tests/integration/files/conf/cloud.providers.d/ to run these tests.".format(
                    self.PROVIDER, self.providers
                )
            )

        if not self._profile_configured():
            self.skipTest(
                "{} profile is missing required configuration items".format(
                    self.profile_config_name
                )
            )

    def _profile_configured(self, profile_config_name=None):
        if profile_config_name is None:
            profile_config_name = self.profile_config_name

        self.assertIn(profile_config_name, self.profiles.keys())

        opts = {
            "providers": {
                self.PROVIDER: {self.provider_config_name: {"profiles": self.profiles}}
            }
        }
        return is_profile_configured(
            provider="{}:{}".format(self.PROVIDER, self.provider_config_name),
            profile_name=profile_config_name,
            opts=opts,
        )

    def _alt_names(self):
        """
        Check for an instances created alongside this test's instance that weren't cleaned up
        """
        query = self.query_instances()
        instances = set()
        for q in query:
            # Verify but this is a new name and not a shutting down ec2 instance
            if q.startswith(self.instance_name) and not q.split("-")[-1].startswith(
                "DEL"
            ):
                instances.add(q)
                log.debug(
                    'Adding "{}" to the set of instances that needs to be deleted'.format(
                        q
                    )
                )
        return instances

    def _ensure_deletion(self, instance_name=None):
        """
        Make sure that the instance absolutely gets deleted, but fail the test if it happens in the tearDown
        :return True if an instance was deleted, False if no instance was deleted; and a message
        """
        destroyed = False
        if not instance_name:
            instance_name = self.instance_name

        if self._instance_exists(instance_name):
            for tries in range(3):
                try:
                    self.assertDestroyInstance(instance_name)
                    return (
                        False,
                        'The instance "{}" was deleted during the tearDown, not the test.'.format(
                            instance_name
                        ),
                    )
                except AssertionError as e:
                    log.error(
                        'Failed to delete instance "{}". Tries: {}\n{}'.format(
                            instance_name, tries, str(e)
                        )
                    )
                if not self._instance_exists():
                    destroyed = True
                    break
                else:
                    time.sleep(30)

            if not destroyed:
                # Destroying instances in the tearDown is a contingency, not the way things should work by default.
                return (
                    False,
                    'The Instance "{}" was not deleted after multiple attempts'.format(
                        instance_name
                    ),
                )

        return (
            True,
            'The instance "{}" cleaned up properly after the test'.format(
                instance_name
            ),
        )

    def tearDown(self):
        """
        Clean up after tests, If the instance still exists for any reason, delete it.
        Instances should be destroyed before the tearDown, assertDestroyInstance() should be called exactly
        one time in a test for each instance created.  This is a failSafe and something went wrong
        if the tearDown is where an instance is destroyed.
        """
        success = True
        fail_messages = []
        alt_names = self._alt_names()
        for instance in alt_names:
            alt_destroyed, alt_destroy_message = self._ensure_deletion(instance)
            if not alt_destroyed:
                success = False
                fail_messages.append(alt_destroy_message)
                log.error(
                    'Failed to destroy instance "{}": {}'.format(
                        instance, alt_destroy_message
                    )
                )
        self.assertTrue(success, "\n".join(fail_messages))
        if alt_names:
            log.error("Cleanup should happen in the test, not the TearDown")
            # TODO The tests should fail if this happens
            # self.assertFalse(alt_names, 'Cleanup should happen in the test, not the TearDown')

    @classmethod
    def tearDownClass(cls):
        cls.clean_cloud_dir(cls.TMP_PROVIDER_DIR)

    @classmethod
    def setUpClass(cls):
        super(CloudTest, cls).setUpClass()

        if not cls.PROVIDER:
            raise ValueError(
                'Provider "{}" was not defined in child class'.format(cls.PROVIDER)
            )

        # clean up before setup
        cls.clean_cloud_dir(cls.TMP_PROVIDER_DIR)

        source_file = os.path.join(
            FILES, "conf", "cloud.providers.d", cls.PROVIDER + ".conf"
        )
        # This is the exact same as cls.provider_config_path, but properties don't work properly in class methods
        destination = os.path.join(cls.TMP_PROVIDER_DIR, cls.PROVIDER + ".conf")

        if os.path.exists(source_file):
            # add the provider config for only the cloud we are testing
            shutil.copyfile(source_file, destination)
