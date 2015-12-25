# This code assumes vboxapi.py from VirtualBox distribution
# being in PYTHONPATH, or installed system-wide
import unittest
import logging

from integration.cloud.helpers.virtualbox import VirtualboxTestCase
from cloud.clouds import virtualbox

log = logging.getLogger()
log_handler = logging.StreamHandler()
log_handler.setLevel(logging.DEBUG)
log.addHandler(log_handler)
log.setLevel(logging.DEBUG)
info = log.info


class BaseVirtualboxTests(unittest.TestCase):
    def test_get_manager(self):
        self.assertIsNotNone(virtualbox.vb_get_manager())


class CreationDestructionVirtualboxTests(VirtualboxTestCase):
    def setUp(self):
        super(CreationDestructionVirtualboxTests, self).setUp()

    def test_vm_creation_and_destruction(self):
        vm_name = "__temp_test_vm__"
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


if __name__ == '__main__':
    unittest.main()
