# -*- coding: utf-8 -*-
# This code assumes vboxapi.py from VirtualBox distribution
# being in PYTHONPATH, or installed system-wide

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import socket

# Import Salt Libs
from salt.ext import six
from salt.ext.six.moves import range
from salt.utils.virtualbox import (
    HAS_LIBS,
    XPCOM_ATTRIBUTES,
    machine_get_machinestate_str,
    vb_clone_vm,
    vb_create_machine,
    vb_destroy_machine,
    vb_get_box,
    vb_get_network_addresses,
    vb_machine_exists,
    vb_start_vm,
    vb_stop_vm,
    vb_wait_for_network_address,
    vb_xpcom_to_attribute_dict,
)

# Import Salt Testing Libs
from tests.integration.cloud.helpers.cloud_test_base import (
    CloudTest,
    requires_provider_config,
)

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf

log = logging.getLogger(__name__)

# As described in the documentation of list_nodes (this may change with time)
BASE_BOX_NAME = "__temp_test_vm__"
BOOTABLE_BASE_BOX_NAME = "SaltMiniBuntuTest"
MINIMAL_MACHINE_ATTRIBUTES = [
    "id",
    "image",
    "size",
    "state",
    "private_ips",
    "public_ips",
]


@skipIf(not HAS_LIBS, "The 'vboxapi' library is not available")
@requires_provider_config("personal_access_token", "ssh_key_file", "ssh_key_names")
class VirtualboxProviderTest(CloudTest):
    """
    Integration tests for the Virtualbox cloud provider using the Virtualbox driver
    """

    @classmethod
    def setUpClass(cls):
        vb_create_machine(BASE_BOX_NAME)

    @classmethod
    def tearDownClass(cls):
        vb_destroy_machine(BASE_BOX_NAME)

    def test_instance(self):
        """
        Simply create a machine and make sure it was created
        """
        self.assertCreateInstance()
        self.assertDestroyInstance()

    def test_cloud_list(self):
        """
        List all machines in virtualbox and make sure the requested attributes are included
        """
        machines = self.run_cloud_function("list_nodes")

        expected_attributes = MINIMAL_MACHINE_ATTRIBUTES
        names = machines.keys()
        self.assertGreaterEqual(len(names), 1, "No machines found")
        for name, machine in six.iteritems(machines):
            if six.PY3:
                self.assertCountEqual(expected_attributes, machine.keys())
            else:
                self.assertItemsEqual(expected_attributes, machine.keys())

        self.assertIn(BASE_BOX_NAME, names)

    def test_cloud_list_full(self):
        """
        List all machines and make sure full information in included
        """
        machines = self.run_cloud_function("list_nodes_full")
        expected_minimal_attribute_count = len(MINIMAL_MACHINE_ATTRIBUTES)

        names = machines.keys()
        self.assertGreaterEqual(len(names), 1, "No machines found")
        for name, machine in six.iteritems(machines):
            self.assertGreaterEqual(
                len(machine.keys()), expected_minimal_attribute_count
            )

        self.assertIn(BASE_BOX_NAME, names)

    def test_cloud_list_select(self):
        """
        List selected attributes of all machines
        """
        machines = self.run_cloud_function("list_nodes_select")
        # TODO find out how to get query.selection from the  'cloud' config
        expected_attributes = ["id"]

        names = machines.keys()
        self.assertGreaterEqual(len(names), 1, "No machines found")
        for name, machine in six.iteritems(machines):
            if six.PY3:
                self.assertCountEqual(expected_attributes, machine.keys())
            else:
                self.assertItemsEqual(expected_attributes, machine.keys())

        self.assertIn(BASE_BOX_NAME, names)

    def test_function_show_instance(self):
        kw_function_args = {"image": BASE_BOX_NAME}
        machines = self.run_cloud_function("show_image", kw_function_args, timeout=30)
        expected_minimal_attribute_count = len(MINIMAL_MACHINE_ATTRIBUTES)
        self.assertIn(BASE_BOX_NAME, machines)
        machine = machines[BASE_BOX_NAME]
        self.assertGreaterEqual(len(machine.keys()), expected_minimal_attribute_count)

    def tearDown(self):
        """
        Clean up after tests
        """
        if vb_machine_exists(self.instance_name):
            vb_destroy_machine(self.instance_name)
            self.fail("Cleanup should happen in the test, not the TearDown")

        super(VirtualboxProviderTest, self).tearDown()


@requires_provider_config("personal_access_token", "ssh_key_file", "ssh_key_names")
@skipIf(not HAS_LIBS, "The 'vboxapi' library is not available")
class VirtualboxProviderHeavyTests(CloudTest):
    """
    Tests that include actually booting a machine and doing operations on it that might be lengthy.
    """

    PROVIDER = "virtualbox"
    DEPLOY_PROFILE = PROVIDER + "-deploy-test"

    def assertIsIpAddress(self, ip_str):
        """
        Is it either a IPv4 or IPv6 address

        @param ip_str:
        @type ip_str: str
        @raise AssertionError
        """
        try:
            socket.inet_aton(ip_str)
        except Exception:  # pylint: disable=broad-except
            try:
                socket.inet_pton(socket.AF_INET6, ip_str)
            except Exception:  # pylint: disable=broad-except
                self.fail("{0} is not a valid IP address".format(ip_str))

    def assertDestroyMachine(self):
        try:
            vb_stop_vm(BOOTABLE_BASE_BOX_NAME)
        except Exception:  # pylint: disable=broad-except
            pass

        vb_stop_vm(self.instance_name)
        vb_destroy_machine(self.instance_name)

        self.assertDestroyInstance()

    def test_instance(self):
        ret_val = self.run_cloud(
            "-p {0} {1} --log-level=debug".format(
                self.DEPLOY_PROFILE, self.instance_name
            ),
            timeout=self.TEST_TIMEOUT,
        )
        self.assertInstanceExists(ret_val)
        machine = ret_val[self.instance_name]
        self.assertIn("deployed", machine)
        self.assertTrue(machine["deployed"], "Machine wasn't deployed :(")

        self.assertDestroyMachine()

    def test_start_stop_action(self):
        res = self.run_cloud_action("start", BOOTABLE_BASE_BOX_NAME, timeout=10)
        log.info(res)

        machine = res.get(BOOTABLE_BASE_BOX_NAME)
        self.assertIsNotNone(machine)
        expected_state = "Running"
        state = machine.get("state")
        self.assertEqual(state, expected_state)

        res = self.run_cloud_action("stop", BOOTABLE_BASE_BOX_NAME, timeout=10)
        log.info(res)

        machine = res.get(BOOTABLE_BASE_BOX_NAME)
        self.assertIsNotNone(machine)

        expected_state = "PoweredOff"
        state = machine.get("state")
        self.assertEqual(state, expected_state)

        self.assertDestroyMachine()

    def test_restart_action(self):
        self.assertDestroyMachine()

    def test_network_addresses(self):
        # Machine is off
        ip_addresses = vb_get_network_addresses(machine_name=BOOTABLE_BASE_BOX_NAME)

        network_count = len(ip_addresses)
        self.assertEqual(network_count, 0)

        # Machine is up again
        vb_start_vm(BOOTABLE_BASE_BOX_NAME)
        ip_addresses = vb_wait_for_network_address(
            20, machine_name=BOOTABLE_BASE_BOX_NAME
        )
        network_count = len(ip_addresses)
        self.assertGreater(network_count, 0)

        for ip_address in ip_addresses:
            self.assertIsIpAddress(ip_address)

        self.assertDestroyMachine()


@skipIf(not HAS_LIBS, "The 'vboxapi' library is not available")
class VirtualboxTests(CloudTest):
    def test_instance(self):
        vm_name = BASE_BOX_NAME
        vb_create_machine(vm_name)
        self.vbox.findMachine(vm_name)

        vb_destroy_machine(vm_name)
        self.assertRaisesRegex(
            Exception,
            "Could not find a registered machine",
            self.vbox.findMachine,
            vm_name,
        )

    def test_get_manager(self):
        self.assertIsNotNone(vb_get_box())

    def test_clone(self):
        # Setup
        vbox = vb_get_box()
        clone = self.instance_name + "_clone"

        # Execute
        vb_create_machine(self.instance_name)
        vbox.findMachine(self.instance_name)

        machine = vb_clone_vm(host=clone, clone_from=self.instance_name)

        # Verify
        self.assertEqual(machine.get("name"), clone)
        vbox.findMachine(clone)

        # Cleanup
        vb_destroy_machine(clone)
        self.assertRaisesRegex(
            Exception, "Could not find a registered machine", vbox.findMachine, clone
        )

        vb_destroy_machine(self.instance_name)
        self.assertRaisesRegex(
            Exception,
            "Could not find a registered machine",
            vbox.findMachine,
            self.instance_name,
        )

    def test_start_stop(self):
        vbox = vb_get_box()
        vb_create_machine(self.instance_name)
        vbox.findMachine(self.instance_name)

        # Execute & Verify
        for _ in range(2):
            machine = vb_start_vm(self.instance_name, 20000)
            self.assertEqual(machine_get_machinestate_str(machine), "Running")

            machine = vb_stop_vm(self.instance_name)
            self.assertEqual(machine_get_machinestate_str(machine), "PoweredOff")

        # Cleanup
        vb_destroy_machine(self.instance_name)
        self.assertRaisesRegex(
            Exception,
            "Could not find a registered machine",
            vbox.findMachine,
            self.instance_name,
        )


class XpcomConversionTests(TestCase):
    @classmethod
    def _mock_xpcom_object(cls, interface_name=None, attributes=None):
        class XPCOM(object):
            def __str__(self):
                return "<XPCOM component '<unknown>' (implementing {0})>".format(
                    interface_name
                )

        o = XPCOM()

        if attributes and isinstance(attributes, dict):
            for key, value in six.iteritems(attributes):
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

        for key in ret:
            self.assertIn(key, expected_attributes)

    def test_override_attributes(self):

        expected_dict = {"herp": "derp", "lol": "rofl", "something": 12345}

        xpc = XpcomConversionTests._mock_xpcom_object(attributes=expected_dict)

        ret = vb_xpcom_to_attribute_dict(xpc, attributes=expected_dict.keys())
        self.assertDictEqual(ret, expected_dict)

    def test_extra_attributes(self):

        interface = "IMachine"
        expected_extras = {
            "extra": "extra",
        }
        expected_machine = dict(
            [(attribute, attribute) for attribute in XPCOM_ATTRIBUTES[interface]]
        )
        expected_machine.update(expected_extras)

        imachine = XpcomConversionTests._mock_xpcom_object(
            interface, attributes=expected_machine
        )

        ret = vb_xpcom_to_attribute_dict(
            imachine, interface_name=interface, extra_attributes=expected_extras.keys()
        )
        self.assertDictEqual(ret, expected_machine)

        ret_keys = ret.keys()
        for key in expected_extras:
            self.assertIn(key, ret_keys)

    def test_extra_nonexistent_attributes(self):
        expected_extra_dict = {"nonexistent": ""}
        xpcom = XpcomConversionTests._mock_xpcom_object()

        ret = vb_xpcom_to_attribute_dict(
            xpcom, extra_attributes=expected_extra_dict.keys()
        )
        self.assertDictEqual(ret, expected_extra_dict)

    def test_extra_nonexistent_attribute_with_default(self):
        expected_extras = [("nonexistent", list)]
        expected_extra_dict = {"nonexistent": []}
        xpcom = XpcomConversionTests._mock_xpcom_object()

        ret = vb_xpcom_to_attribute_dict(xpcom, extra_attributes=expected_extras)
        self.assertDictEqual(ret, expected_extra_dict)
