# This code assumes vboxapi.py from VirtualBox distribution
# being in PYTHONPATH, or installed system-wide
import unittest
import logging
import time

import virtualbox

log = logging.getLogger()
log_handler = logging.StreamHandler()
log_handler.setLevel(logging.DEBUG)
log.addHandler(log_handler)
log.setLevel(logging.DEBUG)
info = log.info


class BaseVirtualboxTests(unittest.TestCase):

    def test_get_manager(self):
        self.assertIsNotNone(virtualbox.vb_get_manager())


class CloneVirtualboxTests(unittest.TestCase):

    def setUp(self):
        self.name = "SaltCloudVirtualboxTestVM"

    def tearDown(self):
        pass

    def test_create_machine(self):
        return
        vb_name = "NewTestMachine"
        virtualbox.vb_clone_vm(
            name=vb_name,
            clone_from=self.name
        )

if __name__ == '__main__':
    unittest.main()
