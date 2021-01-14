# -*- coding: utf-8 -*-
"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.xapi_virt as xapi

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase


class Mockxapi(object):
    """
        Mock xapi class
    """

    def __init__(self):
        pass

    class Session(object):
        """
            Mock Session class
        """

        def __init__(self, xapi_uri):
            pass

        class xenapi(object):
            """
                Mock xenapi class
            """

            def __init__(self):
                pass

            @staticmethod
            def login_with_password(xapi_login, xapi_password):
                """
                    Mock login_with_password method
                """
                return xapi_login, xapi_password

            class session(object):
                """
                    Mock session class
                """

                def __init__(self):
                    pass

                @staticmethod
                def logout():
                    """
                        Mock logout method
                    """
                    return Mockxapi()


class XapiTestCase(TestCase, LoaderModuleMockMixin):
    """
        Test cases for salt.modules.xapi
    """

    def setup_loader_modules(self):
        return {xapi: {}}

    def test_list_domains(self):
        """
            Test to return a list of domain names on the minion
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            self.assertListEqual(xapi.list_domains(), [])

    def test_vm_info(self):
        """
            Test to return detailed information about the vms
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(return_value=False)
            with patch.object(xapi, "_get_record_by_label", mock):
                self.assertDictEqual(xapi.vm_info(True), {True: False})

    def test_vm_state(self):
        """
            Test to return list of all the vms and their state.
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(return_value={"power_state": "1"})
            with patch.object(xapi, "_get_record_by_label", mock):
                self.assertDictEqual(xapi.vm_state("salt"), {"salt": "1"})

                self.assertDictEqual(xapi.vm_state(), {})

    def test_get_nics(self):
        """
            Test to return info about the network interfaces of a named vm
        """
        ret = {"Stack": {"device": "ETH0", "mac": "Stack", "mtu": 1}}
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(side_effect=[False, {"VIFs": "salt"}])
            with patch.object(xapi, "_get_record_by_label", mock):
                self.assertFalse(xapi.get_nics("salt"))

                mock = MagicMock(
                    return_value={"MAC": "Stack", "device": "ETH0", "MTU": 1}
                )
                with patch.object(xapi, "_get_record", mock):
                    self.assertDictEqual(xapi.get_nics("salt"), ret)

    def test_get_macs(self):
        """
            Test to return a list off MAC addresses from the named vm
        """
        mock = MagicMock(side_effect=[None, ["a", "b", "c"]])
        with patch.object(xapi, "get_nics", mock):
            self.assertIsNone(xapi.get_macs("salt"))

            self.assertListEqual(xapi.get_macs("salt"), ["a", "b", "c"])

    def test_get_disks(self):
        """
            Test to return the disks of a named vm
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(side_effect=[False, ["a", "b", "c"]])
            with patch.object(xapi, "_get_label_uuid", mock):
                self.assertFalse(xapi.get_disks("salt"))

                self.assertDictEqual(xapi.get_disks("salt"), {})

    def test_setmem(self):
        """
            Test to changes the amount of memory allocated to VM.
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(side_effect=[False, ["a", "b", "c"]])
            with patch.object(xapi, "_get_label_uuid", mock):
                self.assertFalse(xapi.setmem("salt", "1"))

                self.assertTrue(xapi.setmem("salt", "1"))

        with patch.object(xapi, "_check_xenapi", MagicMock(return_value=Mockxapi)):
            mock = MagicMock(return_value=True)
            with patch.dict(xapi.__salt__, {"config.option": mock}):
                with patch.object(xapi, "_get_label_uuid", mock):
                    self.assertFalse(xapi.setmem("salt", "1"))

    def test_setvcpus(self):
        """
            Test to changes the amount of vcpus allocated to VM.
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(side_effect=[False, ["a", "b", "c"]])
            with patch.object(xapi, "_get_label_uuid", mock):
                self.assertFalse(xapi.setvcpus("salt", "1"))

                self.assertTrue(xapi.setvcpus("salt", "1"))

        with patch.object(xapi, "_check_xenapi", MagicMock(return_value=Mockxapi)):
            mock = MagicMock(return_value=True)
            with patch.dict(xapi.__salt__, {"config.option": mock}):
                with patch.object(xapi, "_get_label_uuid", mock):
                    self.assertFalse(xapi.setvcpus("salt", "1"))

    def test_vcpu_pin(self):
        """
            Test to Set which CPUs a VCPU can use.
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(side_effect=[False, ["a", "b", "c"]])
            with patch.object(xapi, "_get_label_uuid", mock):
                self.assertFalse(xapi.vcpu_pin("salt", "1", "2"))

                self.assertTrue(xapi.vcpu_pin("salt", "1", "2"))

        with patch.object(xapi, "_check_xenapi", MagicMock(return_value=Mockxapi)):
            mock = MagicMock(return_value=True)
            with patch.dict(xapi.__salt__, {"config.option": mock}):
                with patch.object(xapi, "_get_label_uuid", mock):
                    with patch.dict(xapi.__salt__, {"cmd.run": mock}):
                        self.assertTrue(xapi.vcpu_pin("salt", "1", "2"))

    def test_freemem(self):
        """
            Test to return an int representing the amount of memory
            that has not been given to virtual machines on this node
        """
        mock = MagicMock(return_value={"free_memory": 1024})
        with patch.object(xapi, "node_info", mock):
            self.assertEqual(xapi.freemem(), 1024)

    def test_freecpu(self):
        """
            Test to return an int representing the number
            of unallocated cpus on this hypervisor
        """
        mock = MagicMock(return_value={"free_cpus": 1024})
        with patch.object(xapi, "node_info", mock):
            self.assertEqual(xapi.freecpu(), 1024)

    def test_full_info(self):
        """
            Test to return the node_info, vm_info and freemem
        """
        mock = MagicMock(return_value="salt")
        with patch.object(xapi, "node_info", mock):
            mock = MagicMock(return_value="stack")
            with patch.object(xapi, "vm_info", mock):
                self.assertDictEqual(
                    xapi.full_info(), {"node_info": "salt", "vm_info": "stack"}
                )

    def test_shutdown(self):
        """
            Test to send a soft shutdown signal to the named vm
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(side_effect=[False, ["a", "b", "c"]])
            with patch.object(xapi, "_get_label_uuid", mock):
                self.assertFalse(xapi.shutdown("salt"))

                self.assertTrue(xapi.shutdown("salt"))

        with patch.object(xapi, "_check_xenapi", MagicMock(return_value=Mockxapi)):
            mock = MagicMock(return_value=True)
            with patch.dict(xapi.__salt__, {"config.option": mock}):
                with patch.object(xapi, "_get_label_uuid", mock):
                    self.assertFalse(xapi.shutdown("salt"))

    def test_pause(self):
        """
            Test to pause the named vm
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(side_effect=[False, ["a", "b", "c"]])
            with patch.object(xapi, "_get_label_uuid", mock):
                self.assertFalse(xapi.pause("salt"))

                self.assertTrue(xapi.pause("salt"))

        with patch.object(xapi, "_check_xenapi", MagicMock(return_value=Mockxapi)):
            mock = MagicMock(return_value=True)
            with patch.dict(xapi.__salt__, {"config.option": mock}):
                with patch.object(xapi, "_get_label_uuid", mock):
                    self.assertFalse(xapi.pause("salt"))

    def test_resume(self):
        """
            Test to resume the named vm
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(side_effect=[False, ["a", "b", "c"]])
            with patch.object(xapi, "_get_label_uuid", mock):
                self.assertFalse(xapi.resume("salt"))

                self.assertTrue(xapi.resume("salt"))

        with patch.object(xapi, "_check_xenapi", MagicMock(return_value=Mockxapi)):
            mock = MagicMock(return_value=True)
            with patch.dict(xapi.__salt__, {"config.option": mock}):
                with patch.object(xapi, "_get_label_uuid", mock):
                    self.assertFalse(xapi.resume("salt"))

    def test_start(self):
        """
            Test to reboot a domain via ACPI request
        """
        mock = MagicMock(return_value=True)
        with patch.object(xapi, "start", mock):
            self.assertTrue(xapi.start("salt"))

    def test_reboot(self):
        """
            Test to reboot a domain via ACPI request
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(side_effect=[False, ["a", "b", "c"]])
            with patch.object(xapi, "_get_label_uuid", mock):
                self.assertFalse(xapi.reboot("salt"))

                self.assertTrue(xapi.reboot("salt"))

        with patch.object(xapi, "_check_xenapi", MagicMock(return_value=Mockxapi)):
            mock = MagicMock(return_value=True)
            with patch.dict(xapi.__salt__, {"config.option": mock}):
                with patch.object(xapi, "_get_label_uuid", mock):
                    self.assertFalse(xapi.reboot("salt"))

    def test_reset(self):
        """
            Test to reset a VM by emulating the
            reset button on a physical machine
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(side_effect=[False, ["a", "b", "c"]])
            with patch.object(xapi, "_get_label_uuid", mock):
                self.assertFalse(xapi.reset("salt"))

                self.assertTrue(xapi.reset("salt"))

        with patch.object(xapi, "_check_xenapi", MagicMock(return_value=Mockxapi)):
            mock = MagicMock(return_value=True)
            with patch.dict(xapi.__salt__, {"config.option": mock}):
                with patch.object(xapi, "_get_label_uuid", mock):
                    self.assertFalse(xapi.reset("salt"))

    def test_migrate(self):
        """
            Test to migrates the virtual machine to another hypervisor
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(side_effect=[False, ["a", "b", "c"]])
            with patch.object(xapi, "_get_label_uuid", mock):
                self.assertFalse(xapi.migrate("salt", "stack"))

                self.assertTrue(xapi.migrate("salt", "stack"))

        with patch.object(xapi, "_check_xenapi", MagicMock(return_value=Mockxapi)):
            mock = MagicMock(return_value=True)
            with patch.dict(xapi.__salt__, {"config.option": mock}):
                with patch.object(xapi, "_get_label_uuid", mock):
                    self.assertFalse(xapi.migrate("salt", "stack"))

    def test_stop(self):
        """
            Test to Hard power down the virtual machine,
            this is equivalent to pulling the power
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(side_effect=[False, ["a", "b", "c"]])
            with patch.object(xapi, "_get_label_uuid", mock):
                self.assertFalse(xapi.stop("salt"))

                self.assertTrue(xapi.stop("salt"))

        with patch.object(xapi, "_check_xenapi", MagicMock(return_value=Mockxapi)):
            mock = MagicMock(return_value=True)
            with patch.dict(xapi.__salt__, {"config.option": mock}):
                with patch.object(xapi, "_get_label_uuid", mock):
                    self.assertFalse(xapi.stop("salt"))

    def test_is_hyper(self):
        """
            Test to returns a bool whether or not
            this node is a hypervisor of any kind
        """
        with patch.dict(xapi.__grains__, {"virtual_subtype": "Dom0"}):
            self.assertFalse(xapi.is_hyper())

        with patch.dict(xapi.__grains__, {"virtual": "Xen Dom0"}):
            self.assertFalse(xapi.is_hyper())

        with patch.dict(xapi.__grains__, {"virtual_subtype": "Xen Dom0"}):
            with patch("salt.utils.files.fopen", mock_open(read_data="salt")):
                self.assertFalse(xapi.is_hyper())

            with patch("salt.utils.files.fopen", mock_open()) as mock_read:
                mock_read.side_effect = IOError
                self.assertFalse(xapi.is_hyper())

            with patch("salt.utils.files.fopen", mock_open(read_data="xen_")):
                with patch.dict(xapi.__grains__, {"ps": "salt"}):
                    mock = MagicMock(return_value={"xenstore": "salt"})
                    with patch.dict(xapi.__salt__, {"cmd.run": mock}):
                        self.assertTrue(xapi.is_hyper())

    def test_vm_cputime(self):
        """
            Test to Return cputime used by the vms
        """
        ret = {"1": {"cputime_percent": 0, "cputime": 1}}
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            mock = MagicMock(return_value={"host_CPUs": "1"})
            with patch.object(xapi, "_get_record_by_label", mock):
                mock = MagicMock(
                    return_value={"VCPUs_number": "1", "VCPUs_utilisation": {"0": "1"}}
                )
                with patch.object(xapi, "_get_metrics_record", mock):
                    self.assertDictEqual(xapi.vm_cputime("1"), ret)

            mock = MagicMock(return_value={})
            with patch.object(xapi, "list_domains", mock):
                self.assertDictEqual(xapi.vm_cputime(""), {})

    def test_vm_netstats(self):
        """
            Test to return combined network counters used by the vms
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            self.assertDictEqual(xapi.vm_netstats(""), {})

    def test_vm_diskstats(self):
        """
            Test to return disk usage counters used by the vms
        """
        with patch.object(xapi, "_get_xapi_session", MagicMock()):
            self.assertDictEqual(xapi.vm_diskstats(""), {})
