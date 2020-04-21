# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt libs
import salt.beacons.smartos_vmadm as vmadm
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch

# Salt testing libs
from tests.support.unit import TestCase

# Mock Results
MOCK_CLEAN_STATE = {"first_run": True, "vms": []}
MOCK_VM_NONE = {}
MOCK_VM_ONE = {
    "00000000-0000-0000-0000-000000000001": {
        "state": "running",
        "alias": "vm1",
        "hostname": "vm1",
        "dns_domain": "example.org",
    },
}
MOCK_VM_TWO_STOPPED = {
    "00000000-0000-0000-0000-000000000001": {
        "state": "running",
        "alias": "vm1",
        "hostname": "vm1",
        "dns_domain": "example.org",
    },
    "00000000-0000-0000-0000-000000000002": {
        "state": "stopped",
        "alias": "vm2",
        "hostname": "vm2",
        "dns_domain": "example.org",
    },
}
MOCK_VM_TWO_STARTED = {
    "00000000-0000-0000-0000-000000000001": {
        "state": "running",
        "alias": "vm1",
        "hostname": "vm1",
        "dns_domain": "example.org",
    },
    "00000000-0000-0000-0000-000000000002": {
        "state": "running",
        "alias": "vm2",
        "hostname": "vm2",
        "dns_domain": "example.org",
    },
}


class SmartOSImgAdmBeaconTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test case for salt.beacons.vmadm
    """

    def setup_loader_modules(self):
        return {vmadm: {"__context__": {}, "__salt__": {}}}

    def test_non_list_config(self):
        """
        We only have minimal validation so we test that here
        """
        config = {}

        ret = vmadm.validate(config)

        self.assertEqual(ret, (False, "Configuration for vmadm beacon must be a list!"))

    def test_created_startup(self):
        """
        Test with one vm and startup_create_event
        """
        # NOTE: this should yield 1 created event + one state event
        with patch.dict(vmadm.VMADM_STATE, MOCK_CLEAN_STATE), patch.dict(
            vmadm.__salt__, {"vmadm.list": MagicMock(return_value=MOCK_VM_ONE)}
        ):

            config = [{"startup_create_event": True}]

            ret = vmadm.validate(config)
            self.assertEqual(ret, (True, "Valid beacon configuration"))

            ret = vmadm.beacon(config)
            res = [
                {
                    "alias": "vm1",
                    "tag": "created/00000000-0000-0000-0000-000000000001",
                    "hostname": "vm1",
                    "dns_domain": "example.org",
                },
                {
                    "alias": "vm1",
                    "tag": "running/00000000-0000-0000-0000-000000000001",
                    "hostname": "vm1",
                    "dns_domain": "example.org",
                },
            ]
            self.assertEqual(ret, res)

    def test_created_nostartup(self):
        """
        Test with one image and startup_import_event unset/false
        """
        # NOTE: this should yield 0 created event _ one state event
        with patch.dict(vmadm.VMADM_STATE, MOCK_CLEAN_STATE), patch.dict(
            vmadm.__salt__, {"vmadm.list": MagicMock(return_value=MOCK_VM_ONE)}
        ):

            config = []

            ret = vmadm.validate(config)
            self.assertEqual(ret, (True, "Valid beacon configuration"))

            ret = vmadm.beacon(config)
            res = [
                {
                    "alias": "vm1",
                    "tag": "running/00000000-0000-0000-0000-000000000001",
                    "hostname": "vm1",
                    "dns_domain": "example.org",
                }
            ]

            self.assertEqual(ret, res)

    def test_created(self):
        """
        Test with one vm, create a 2nd one
        """
        # NOTE: this should yield 1 created event + state event
        with patch.dict(vmadm.VMADM_STATE, MOCK_CLEAN_STATE), patch.dict(
            vmadm.__salt__,
            {"vmadm.list": MagicMock(side_effect=[MOCK_VM_ONE, MOCK_VM_TWO_STARTED])},
        ):

            config = []

            ret = vmadm.validate(config)
            self.assertEqual(ret, (True, "Valid beacon configuration"))

            # Initial pass (Initialized state and do not yield created events at startup)
            ret = vmadm.beacon(config)

            # Second pass (After create a new vm)
            ret = vmadm.beacon(config)
            res = [
                {
                    "alias": "vm2",
                    "tag": "created/00000000-0000-0000-0000-000000000002",
                    "hostname": "vm2",
                    "dns_domain": "example.org",
                },
                {
                    "alias": "vm2",
                    "tag": "running/00000000-0000-0000-0000-000000000002",
                    "hostname": "vm2",
                    "dns_domain": "example.org",
                },
            ]

            self.assertEqual(ret, res)

    def test_deleted(self):
        """
        Test with two vms and one gets destroyed
        """
        # NOTE: this should yield 1 destroyed event
        with patch.dict(vmadm.VMADM_STATE, MOCK_CLEAN_STATE), patch.dict(
            vmadm.__salt__,
            {"vmadm.list": MagicMock(side_effect=[MOCK_VM_TWO_STOPPED, MOCK_VM_ONE])},
        ):

            config = []

            ret = vmadm.validate(config)
            self.assertEqual(ret, (True, "Valid beacon configuration"))

            # Initial pass (Initialized state and do not yield created vms at startup)
            ret = vmadm.beacon(config)

            # Second pass (Destroying one vm)
            ret = vmadm.beacon(config)
            res = [
                {
                    "alias": "vm2",
                    "tag": "deleted/00000000-0000-0000-0000-000000000002",
                    "hostname": "vm2",
                    "dns_domain": "example.org",
                }
            ]

            self.assertEqual(ret, res)

    def test_complex(self):
        """
        Test with two vms, stop one, delete one
        """
        # NOTE: this should yield 1 delete and 2 import events
        with patch.dict(vmadm.VMADM_STATE, MOCK_CLEAN_STATE), patch.dict(
            vmadm.__salt__,
            {
                "vmadm.list": MagicMock(
                    side_effect=[MOCK_VM_TWO_STARTED, MOCK_VM_TWO_STOPPED, MOCK_VM_ONE]
                )
            },
        ):

            config = []

            ret = vmadm.validate(config)
            self.assertEqual(ret, (True, "Valid beacon configuration"))

            # Initial pass (Initialized state and do not yield created events at startup)
            ret = vmadm.beacon(config)

            # Second pass (Stop one vm)
            ret = vmadm.beacon(config)
            res = [
                {
                    "alias": "vm2",
                    "tag": "stopped/00000000-0000-0000-0000-000000000002",
                    "hostname": "vm2",
                    "dns_domain": "example.org",
                }
            ]

            self.assertEqual(ret, res)

            # Third pass (Delete one vm)
            ret = vmadm.beacon(config)
            res = [
                {
                    "alias": "vm2",
                    "tag": "deleted/00000000-0000-0000-0000-000000000002",
                    "hostname": "vm2",
                    "dns_domain": "example.org",
                }
            ]

            self.assertEqual(ret, res)
