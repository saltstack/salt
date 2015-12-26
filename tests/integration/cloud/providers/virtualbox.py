# This code assumes vboxapi.py from VirtualBox distribution
# being in PYTHONPATH, or installed system-wide

# Import Python Libs
from __future__ import absolute_import

import os
import unittest
import logging

# Import Salt Testing Libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath

from integration.cloud.helpers import random_name
from integration.cloud.helpers.virtualbox import VirtualboxTestCase
from cloud.clouds import virtualbox

ensure_in_syspath('../../../')

# Import Salt Libs
import integration
from salt.config import cloud_providers_config, vm_profiles_config

log = logging.getLogger()
log_handler = logging.StreamHandler()
log_handler.setLevel(logging.INFO)
log.addHandler(log_handler)
log.setLevel(logging.INFO)
info = log.info

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = random_name()
PROVIDER_NAME = "virtualbox"
PROFILE_NAME = PROVIDER_NAME + "-test"
DRIVER_NAME = "virtualbox"
BASE_BOX_NAME = "__temp_test_vm__"


@skipIf(virtualbox.HAS_LIBS is False, 'salt-cloud requires virtualbox to be installed')
class VirtualboxProviderTest(integration.ShellCase):
    """
    Integration tests for the Virtualbox cloud provider using the Virtualbox driver
    TODO tests that create with salt cloud and the delete with vb_* functions
    TODO Keep implementing the new salt-cloud functions while replacing the vb_* calls
    """

    def run_cloud(self, arg_str, catch_stderr=False, timeout=None):
        """
        Execute salt-cloud
        """
        config_path = os.path.join(
            integration.FILES,
            'conf'
        )
        arg_str = '-c {0} {1}'.format(config_path, arg_str)
        # arg_str = "%s --log-level=error" % arg_str
        log.debug("running salt-cloud with %s" % arg_str)
        return self.run_script('salt-cloud', arg_str, catch_stderr, timeout)

    def setUp(self):
        """
        Sets up the test requirements
        """
        super(VirtualboxProviderTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'virtualbox-config'
        providers = self.run_cloud('--list-providers')
        log.debug("providers: %s" % providers)

        if profile_str + ':' not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'
                    .format(PROVIDER_NAME)
            )

        # check if personal access token, ssh_key_file, and ssh_key_names are present
        config_path = os.path.join(
            integration.FILES,
            'conf',
            'cloud.providers.d',
            PROVIDER_NAME + '.conf'
        )
        log.debug("config_path: %s" % config_path)
        providers = cloud_providers_config(config_path)
        log.debug("config: %s" % providers)
        config_path = os.path.join(
            integration.FILES,
            'conf',
            'cloud.profiles.d',
            PROVIDER_NAME + '.conf'
        )
        profiles = vm_profiles_config(config_path, providers)
        profile = profiles.get(PROFILE_NAME)
        if not profile:
            self.skipTest(
                'Profile {0} was not found. Check {1}.conf files '
                'in tests/integration/files/conf/cloud.profiles.d/ to run these tests.'
                    .format(PROFILE_NAME, PROVIDER_NAME)
            )
        base_box_name = profile.get("clonefrom")

        if base_box_name != BASE_BOX_NAME:
            self.skipTest(
                'Profile {0} does not have a base box to clone from. Check {1}.conf files '
                'in tests/integration/files/conf/cloud.profiles.d/ to run these tests.'
                'And add a "clone_from: {2}" to the profile'
                    .format(PROFILE_NAME, PROVIDER_NAME, BASE_BOX_NAME)
            )

    @classmethod
    def setUpClass(cls):
        virtualbox.vb_create_machine(BASE_BOX_NAME)

    @classmethod
    def tearDownClass(cls):
        virtualbox.vb_destroy_machine(BASE_BOX_NAME)

    def test_cloud_create(self):
        """
        Simply create a machine and make sure it was created
        """
        try:

            self.assertIn(
                INSTANCE_NAME,
                [i.strip() for i in self.run_cloud('-p {0} {1} --log-level=debug'.format(PROFILE_NAME, INSTANCE_NAME))]
            )
        except AssertionError:
            self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
            raise

    # def test_instance(self):
    #     """
    #     Test creating an instance on virtualbox with the virtualbox driver
    #     """
    #     # check if instance with salt installed returned
    #     try:
    #         self.assertIn(
    #             INSTANCE_NAME,
    #             [i.strip() for i in self.run_cloud('-p {0} {1} --log-level=debug'.format(PROFILE_NAME, INSTANCE_NAME))]
    #         )
    #     except AssertionError:
    #         self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
    #         raise
    #
    #     # delete the instance
    #     try:
    #         self.assertIn(
    #             INSTANCE_NAME + ':',
    #             [i.strip() for i in self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))]
    #         )
    #     except AssertionError:
    #         raise

    def tearDown(self):
        """
        Clean up after tests
        """
        # query = self.run_cloud('--query')
        # ret = '        {0}:'.format(INSTANCE_NAME)
        #
        # log.info("query: %s" % query)
        #
        # # if test instance is still present, delete it
        # if ret in query:
        #     # self.run_cloud('-d {0} --assume-yes'.format(INSTANCE_NAME))
        if virtualbox.vb_machine_exists(INSTANCE_NAME):
            virtualbox.vb_destroy_machine(INSTANCE_NAME)


class BaseVirtualboxTests(unittest.TestCase):
    def test_get_manager(self):
        self.assertIsNotNone(virtualbox.vb_get_manager())


class CreationDestructionVirtualboxTests(VirtualboxTestCase):
    def setUp(self):
        super(CreationDestructionVirtualboxTests, self).setUp()

    def test_vm_creation_and_destruction(self):
        vm_name = BASE_BOX_NAME
        virtualbox.vb_create_machine(vm_name)
        self.assertMachineExists(vm_name)

        virtualbox.vb_destroy_machine(vm_name)
        self.assertMachineDoesNotExist(vm_name)


class CloneVirtualboxTests(VirtualboxTestCase):
    def setUp(self):
        self.vbox = virtualbox.vb_get_manager()

        self.name = "SaltCloudVirtualboxTestVM"
        virtualbox.vb_create_machine(self.name)
        self.assertMachineExists(self.name)

    def tearDown(self):
        virtualbox.vb_destroy_machine(self.name)
        self.assertMachineDoesNotExist(self.name)

    def test_create_machine(self):
        vb_name = "NewTestMachine"
        virtualbox.vb_clone_vm(
            name=vb_name,
            clone_from=self.name
        )
        self.assertMachineExists(vb_name)

        virtualbox.vb_destroy_machine(vb_name)
        self.assertMachineDoesNotExist(vb_name)


class XpcomConversionTests(unittest.TestCase):
    @classmethod
    def _mock_xpcom_object(self, interface_name=None, attributes=None):
        class XPCOM(object):

            def __str__(self):
                return "<XPCOM component '<unknown>' (implementing %s)>" % interface_name

        o = XPCOM()

        if attributes and isinstance(attributes, dict):
            for key, value in attributes.iteritems():
                setattr(o, key, value)
        return o

    def test_unknown_object(self):
        xpcom = XpcomConversionTests._mock_xpcom_object()

        ret = virtualbox.vb_xpcom_to_attribute_dict(xpcom)
        self.assertDictEqual(ret, dict())

    def test_imachine_object_default(self):

        interface = "IMachine"
        imachine = XpcomConversionTests._mock_xpcom_object(interface)

        ret = virtualbox.vb_xpcom_to_attribute_dict(imachine)
        expected_attributes = virtualbox.XPCOM_ATTRIBUTES[interface]

        self.assertIsNotNone(expected_attributes, "%s is unknown")

        for key in ret.keys():
            self.assertIn(key, expected_attributes)

    def test_override_attributes(self):

        expected_dict = {
            "herp": "derp",
            "lol": "rofl",
            "something": 12345
        }

        imachine = XpcomConversionTests._mock_xpcom_object(attributes=expected_dict)

        ret = virtualbox.vb_xpcom_to_attribute_dict(imachine, attributes=expected_dict.keys())
        self.assertDictEqual(ret, expected_dict)


if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error

    run_tests(VirtualboxProviderTest)
    # unittest.main()
