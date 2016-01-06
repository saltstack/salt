# This code assumes vboxapi.py from VirtualBox distribution
# being in PYTHONPATH, or installed system-wide

# Import Python Libs
from __future__ import absolute_import

import json
import os
import unittest
import logging

# Import Salt Testing Libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath

from integration.cloud.helpers import random_name
from integration.cloud.helpers.virtualbox import VirtualboxTestCase

ensure_in_syspath('../../../')

# Import Salt Libs
import integration
from salt.config import cloud_providers_config, vm_profiles_config
from utils.virtualbox import vb_xpcom_to_attribute_dict, vb_clone_vm, vb_destroy_machine, vb_create_machine, vb_get_box, \
    vb_machine_exists, HAS_LIBS, XPCOM_ATTRIBUTES, vb_start_vm, vb_stop_vm, machine_get_machinestate

# Setup logging
log = logging.getLogger()
log_handler = logging.StreamHandler()
log_handler.setLevel(logging.INFO)
log.addHandler(log_handler)
log.setLevel(logging.INFO)
info = log.info

# Create the cloud instance name to be used throughout the tests
INSTANCE_NAME = random_name()
PROVIDER_NAME = "virtualbox"
CONFIG_NAME = PROVIDER_NAME + "-config"
PROFILE_NAME = PROVIDER_NAME + "-test"
DRIVER_NAME = "virtualbox"
BASE_BOX_NAME = "__temp_test_vm__"
BOOTABLE_BASE_BOX_NAME = "SaltMiniBuntuTest"

# As described in the documentation of list_nodes (this may change with time)
MINIMAL_MACHINE_ATTRIBUTES = [
    "id",
    "image",
    "size",
    "state",
    "private_ips",
    "public_ips",
]


@skipIf(HAS_LIBS is False, 'salt-cloud requires virtualbox to be installed')
class VirtualboxProviderTest(integration.ShellCase):
    """
    Integration tests for the Virtualbox cloud provider using the Virtualbox driver
    TODO tests that create with salt cloud and the delete with vb_* functions
    TODO Keep implementing the new salt-cloud functions while replacing the vb_* calls
    """

    def run_cloud(self, arg_str, catch_stderr=False, timeout=None):
        """
        Execute salt-cloud with json output and try to interpret it

        @return:
        @rtype: dict
        """
        config_path = os.path.join(
            integration.FILES,
            'conf'
        )
        arg_str = '--out=json -c {0} {1}'.format(config_path, arg_str)
        # arg_str = "%s --log-level=error" % arg_str
        log.debug("running salt-cloud with %s" % arg_str)
        output = self.run_script('salt-cloud', arg_str, catch_stderr, timeout)

        # Sometimes tuples are returned???
        if isinstance(output, tuple) and len(output) == 2:
            output = output[0]

        # Attempt to clean json output before fix of https://github.com/saltstack/salt/issues/27629
        valid_initial_chars = ['{', '[', '"']
        i = 0
        for line in output[:]:
            if len(line) > 0 and (line[0] not in valid_initial_chars):
                output.pop(i)
                i += 1
            else:
                break

        return json.loads("".join(output))

    def run_cloud_function(self, function, kw_function_args=None, **kwargs):
        """
        A helper to call `salt-cloud -f function provider`

        @param function:
        @type function:
        @param kw_function_args: Keyword arguments for the argument string in the commandline
        @type dict:
        @param kwargs: For the `run_cloud` function
        @type kwargs:
        @return:
        @rtype: dict
        """
        args = []
        # Args converted in the form of key1='value1' ... keyN='valueN'
        if kw_function_args:
            args = [
                "%s='%s'" % (key, value)
                for key, value in kw_function_args.iteritems()
                ]

        output = self.run_cloud("-f %s %s %s" % (function, CONFIG_NAME, " ".join(args)), **kwargs)
        return output.get(CONFIG_NAME, {}).get(PROVIDER_NAME, {})

    def run_cloud_destroy(self, machine_name):
        """
        Calls salt-cloud to destroy a machine and returns the destroyed machine object (should be None)
        @param machine_name:
        @type str:
        @return:
        @rtype: dict
        """
        output = self.run_cloud('-d {0} --assume-yes --log-level=debug'.format(machine_name))
        return output.get(CONFIG_NAME, {}).get(PROVIDER_NAME, {})

    def setUp(self):
        """
        Sets up the test requirements
        """
        super(VirtualboxProviderTest, self).setUp()

        # check if appropriate cloud provider and profile files are present
        profile_str = 'virtualbox-config'
        providers = self.run_cloud('--list-providers')
        log.debug("providers: %s" % providers)

        if profile_str not in providers:
            self.skipTest(
                'Configuration file for {0} was not found. Check {0}.conf files '
                'in tests/integration/files/conf/cloud.*.d/ to run these tests.'.format(PROVIDER_NAME)
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
                'in tests/integration/files/conf/cloud.profiles.d/ to run these tests.'.format(PROFILE_NAME,
                                                                                               PROVIDER_NAME)
            )
        base_box_name = profile.get("clonefrom")

        if base_box_name != BASE_BOX_NAME:
            self.skipTest(
                'Profile {0} does not have a base box to clone from. Check {1}.conf files '
                'in tests/integration/files/conf/cloud.profiles.d/ to run these tests.'
                'And add a "clone_from: {2}" to the profile'.format(PROFILE_NAME, PROVIDER_NAME, BASE_BOX_NAME)
            )

    @classmethod
    def setUpClass(cls):
        vb_create_machine(BASE_BOX_NAME)

    @classmethod
    def tearDownClass(cls):
        vb_destroy_machine(BASE_BOX_NAME)

    def test_cloud_create(self):
        """
        Simply create a machine and make sure it was created
        """
        machines = self.run_cloud('-p {0} {1} --log-level=debug'.format(PROFILE_NAME, INSTANCE_NAME))
        self.assertIn(INSTANCE_NAME, machines.keys())

    def test_cloud_list(self):
        """
        List all machines in virtualbox and make sure the requested attributes are included
        """
        machines = self.run_cloud_function('list_nodes')

        expected_attributes = MINIMAL_MACHINE_ATTRIBUTES
        names = machines.keys()
        self.assertGreaterEqual(len(names), 1, "No machines found")
        for name, machine in machines.iteritems():
            self.assertItemsEqual(expected_attributes, machine.keys())

        self.assertIn(BASE_BOX_NAME, names)

    def test_cloud_list_full(self):
        """
        List all machines and make sure full information in included
        """
        machines = self.run_cloud_function('list_nodes_full')
        expected_minimal_attribute_count = len(MINIMAL_MACHINE_ATTRIBUTES)

        names = machines.keys()
        self.assertGreaterEqual(len(names), 1, "No machines found")
        for name, machine in machines.iteritems():
            self.assertGreaterEqual(len(machine.keys()), expected_minimal_attribute_count)

        self.assertIn(BASE_BOX_NAME, names)

    def test_cloud_list_select(self):
        """
        List selected attributes of all machines
        """
        machines = self.run_cloud_function('list_nodes_select')
        # TODO find out how to get query.selection from the  "cloud" config
        expected_attributes = ["id"]

        names = machines.keys()
        self.assertGreaterEqual(len(names), 1, "No machines found")
        for name, machine in machines.iteritems():
            self.assertItemsEqual(expected_attributes, machine.keys())

        self.assertIn(BASE_BOX_NAME, names)

    def test_cloud_destroy(self):
        """
        Test creating an instance on virtualbox with the virtualbox driver
        """
        # check if instance with salt installed returned
        self.test_cloud_create()
        ret = self.run_cloud_destroy(INSTANCE_NAME)

        # destroy the instance
        self.assertIn(INSTANCE_NAME, ret.keys())

    def test_function_show_instance(self):
        kw_function_args = {
            "image": BASE_BOX_NAME
        }
        machines = self.run_cloud_function('show_image', kw_function_args, timeout=30)
        expected_minimal_attribute_count = len(MINIMAL_MACHINE_ATTRIBUTES)
        self.assertIn(BASE_BOX_NAME, machines)
        machine = machines[BASE_BOX_NAME]
        self.assertGreaterEqual(len(machine.keys()), expected_minimal_attribute_count)

    def tearDown(self):
        """
        Clean up after tests
        """
        if vb_machine_exists(INSTANCE_NAME):
            vb_destroy_machine(INSTANCE_NAME)


@skipIf(vb_machine_exists(BOOTABLE_BASE_BOX_NAME) is False,
        "Bootable VM '%s' not found. Cannot run tests." % BOOTABLE_BASE_BOX_NAME
        )
class VirtualboxProviderHeavyTests(integration.ShellCase):
    def test_start_action(self):
        pass

    def test_stop_action(self):
        pass

    def test_restart_action(self):
        pass


class BaseVirtualboxTests(unittest.TestCase):
    def test_get_manager(self):
        self.assertIsNotNone(vb_get_box())


class CreationDestructionVirtualboxTests(VirtualboxTestCase):
    def setUp(self):
        super(CreationDestructionVirtualboxTests, self).setUp()

    def test_vm_creation_and_destruction(self):
        vm_name = BASE_BOX_NAME
        vb_create_machine(vm_name)
        self.assertMachineExists(vm_name)

        vb_destroy_machine(vm_name)
        self.assertMachineDoesNotExist(vm_name)


class CloneVirtualboxTests(VirtualboxTestCase):
    def setUp(self):
        self.vbox = vb_get_box()

        self.name = "SaltCloudVirtualboxTestVM"
        vb_create_machine(self.name)
        self.assertMachineExists(self.name)

    def tearDown(self):
        vb_destroy_machine(self.name)
        self.assertMachineDoesNotExist(self.name)

    def test_create_machine(self):
        vb_name = "NewTestMachine"
        vb_clone_vm(
            name=vb_name,
            clone_from=self.name
        )
        self.assertMachineExists(vb_name)

        vb_destroy_machine(vb_name)
        self.assertMachineDoesNotExist(vb_name)


@skipIf(vb_machine_exists(BOOTABLE_BASE_BOX_NAME) is False,
        "Bootable VM '%s' not found. Cannot run tests." % BOOTABLE_BASE_BOX_NAME
        )
class BootVirtualboxTests(VirtualboxTestCase):
    def test_start_stop(self):
        machine = vb_start_vm(BOOTABLE_BASE_BOX_NAME)
        self.assertEqual(machine_get_machinestate(machine)[0], "Running")

        machine = vb_stop_vm(BOOTABLE_BASE_BOX_NAME)
        self.assertEqual(machine_get_machinestate(machine)[0], "PoweredOff")


class XpcomConversionTests(unittest.TestCase):
    @classmethod
    def _mock_xpcom_object(cls, interface_name=None, attributes=None):
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

        ret = vb_xpcom_to_attribute_dict(xpcom)
        self.assertDictEqual(ret, dict())

    def test_imachine_object_default(self):

        interface = "IMachine"
        imachine = XpcomConversionTests._mock_xpcom_object(interface)

        ret = vb_xpcom_to_attribute_dict(imachine, interface_name=interface)
        expected_attributes = XPCOM_ATTRIBUTES[interface]

        self.assertIsNotNone(expected_attributes, "%s is unknown")

        for key in ret.keys():
            self.assertIn(key, expected_attributes)

    def test_override_attributes(self):

        expected_dict = {
            "herp": "derp",
            "lol": "rofl",
            "something": 12345
        }

        xpc = XpcomConversionTests._mock_xpcom_object(attributes=expected_dict)

        ret = vb_xpcom_to_attribute_dict(xpc, attributes=expected_dict.keys())
        self.assertDictEqual(ret, expected_dict)

    def test_extra_attributes(self):

        interface = "IMachine"
        expected_extras = {
            "extra": "extra",
        }
        expected_machine = dict([(attribute, attribute) for attribute in XPCOM_ATTRIBUTES[interface]])
        expected_machine.update(expected_extras)

        imachine = XpcomConversionTests._mock_xpcom_object(interface, attributes=expected_machine)

        ret = vb_xpcom_to_attribute_dict(
            imachine,
            interface_name=interface,
            extra_attributes=expected_extras.keys()
        )
        self.assertDictEqual(ret, expected_machine)

        ret_keys = ret.keys()
        for key in expected_extras.keys():
            self.assertIn(key, ret_keys)

    def test_extra_nonexistant_attributes(self):
        expected_extra_dict = {
            "nonexistant": ""
        }
        xpcom = XpcomConversionTests._mock_xpcom_object()

        ret = vb_xpcom_to_attribute_dict(xpcom, extra_attributes=expected_extra_dict.keys())
        self.assertDictEqual(ret, expected_extra_dict)

    def test_extra_nonexistant_attribute_with_default(self):
        expected_extras = [("nonexistant", list)]
        expected_extra_dict = {
            "nonexistant": []
        }
        xpcom = XpcomConversionTests._mock_xpcom_object()

        ret = vb_xpcom_to_attribute_dict(xpcom, extra_attributes=expected_extras)
        self.assertDictEqual(ret, expected_extra_dict)


if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error

    run_tests(VirtualboxProviderTest)
    # unittest.main()
