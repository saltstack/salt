# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.modules.vmctl as vmctl

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class VmctlTestCase(TestCase, LoaderModuleMockMixin):
    """
    test modules.vmctl functions
    """

    def setup_loader_modules(self):
        return {vmctl: {}}

    def test_create_disk(self):
        """
        Tests creating a new disk image.
        """
        ret = {}
        ret["stdout"] = "vmctl: imagefile created"
        ret["stderr"] = ""
        ret["retcode"] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
            self.assertTrue(vmctl.create_disk("/path/to/disk.img", "1G"))

    def test_load(self):
        """
        Tests loading a configuration file.
        """
        ret = {}
        ret["retcode"] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
            self.assertTrue(vmctl.load("/etc/vm.switches.conf"))

    def test_reload(self):
        """
        Tests reloading the configuration.
        """
        ret = {}
        ret["retcode"] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
            self.assertTrue(vmctl.reload())

    def test_reset(self):
        """
        Tests resetting VMM.
        """
        ret = {}
        ret["retcode"] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
            res = vmctl.reset()
            mock_cmd.assert_called_once_with(
                ["vmctl", "reset"], output_loglevel="trace", python_shell=False
            )
            self.assertTrue(res)

    def test_reset_vms(self):
        """
        Tests resetting VMs.
        """
        ret = {}
        ret["retcode"] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
            res = vmctl.reset(vms=True)
            mock_cmd.assert_called_once_with(
                ["vmctl", "reset", "vms"], output_loglevel="trace", python_shell=False
            )
            self.assertTrue(res)

    def test_reset_switches(self):
        """
        Tests resetting switches.
        """
        ret = {}
        ret["retcode"] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
            res = vmctl.reset(switches=True)
            mock_cmd.assert_called_once_with(
                ["vmctl", "reset", "switches"],
                output_loglevel="trace",
                python_shell=False,
            )
            self.assertTrue(res)

    def test_reset_all(self):
        """
        Tests resetting all.
        """
        ret = {}
        ret["retcode"] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
            res = vmctl.reset(all=True)
            mock_cmd.assert_called_once_with(
                ["vmctl", "reset", "all"], output_loglevel="trace", python_shell=False
            )
            self.assertTrue(res)

    def test_start_existing_vm(self):
        """
        Tests starting a VM that is already defined.
        """
        ret = {}
        ret["stderr"] = "vmctl: started vm 4 successfully, tty /dev/ttyp4"
        ret["retcode"] = 0
        mock_cmd = MagicMock(return_value=ret)
        expected = {"changes": True, "console": "/dev/ttyp4"}
        with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
            self.assertDictEqual(expected, vmctl.start("4"))

    def test_start_new_vm(self):
        """
        Tests starting a new VM.
        """
        ret = {}
        ret["stderr"] = "vmctl: started vm 4 successfully, tty /dev/ttyp4"
        ret["retcode"] = 0
        mock_cmd = MagicMock(return_value=ret)
        mock_status = MagicMock(return_value={})
        expected = {"changes": True, "console": "/dev/ttyp4"}
        with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
            with patch("salt.modules.vmctl.status", mock_status):
                res = vmctl.start("web1", bootpath="/bsd.rd", nics=2, disk="/disk.img")
                mock_cmd.assert_called_once_with(
                    [
                        "vmctl",
                        "start",
                        "web1",
                        "-i 2",
                        "-b",
                        "/bsd.rd",
                        "-d",
                        "/disk.img",
                    ],
                    output_loglevel="trace",
                    python_shell=False,
                )
                self.assertDictEqual(expected, res)

    def test_status(self):
        """
        Tests getting status for all VMs.
        """
        ret = {}
        ret["stdout"] = (
            "   ID   PID VCPUS  MAXMEM  CURMEM     TTY        OWNER NAME\n"
            "    1   123     1    2.9G     150M  ttyp5       john web1 - stopping\n"
            "    2   456     1    512M     301M  ttyp4       paul web2\n"
            "    3     -     1    512M       -       -       george web3\n"
        )
        ret["retcode"] = 0
        mock_cmd = MagicMock(return_value=ret)
        expected = {
            "web1": {
                "curmem": "150M",
                "id": "1",
                "maxmem": "2.9G",
                "owner": "john",
                "pid": "123",
                "state": "stopping",
                "tty": "ttyp5",
                "vcpus": "1",
            },
            "web2": {
                "curmem": "301M",
                "id": "2",
                "maxmem": "512M",
                "owner": "paul",
                "pid": "456",
                "state": "running",
                "tty": "ttyp4",
                "vcpus": "1",
            },
            "web3": {
                "curmem": "-",
                "id": "3",
                "maxmem": "512M",
                "owner": "george",
                "pid": "-",
                "state": "stopped",
                "tty": "-",
                "vcpus": "1",
            },
        }
        with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
            self.assertEqual(expected, vmctl.status())

    def test_status_single(self):
        """
        Tests getting status for a single VM.
        """
        ret = {}
        ret["stdout"] = (
            "   ID   PID VCPUS  MAXMEM  CURMEM     TTY        OWNER NAME\n"
            "    1   123     1    2.9G     150M  ttyp5       ringo web4\n"
            "    2     -     1    512M       -       -       george web3\n"
        )
        ret["retcode"] = 0
        mock_cmd = MagicMock(return_value=ret)
        expected = {
            "web4": {
                "curmem": "150M",
                "id": "1",
                "maxmem": "2.9G",
                "owner": "ringo",
                "pid": "123",
                "state": "running",
                "tty": "ttyp5",
                "vcpus": "1",
            },
        }
        with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
            self.assertEqual(expected, vmctl.status("web4"))

    def test_stop_when_running(self):
        """
        Tests stopping a VM that is running.
        """
        ret = {}
        ret["stdout"] = ""
        ret["stderr"] = "vmctl: sent request to terminate vm 14"
        ret["retcode"] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
            res = vmctl.stop("web1")
            mock_cmd.assert_called_once_with(
                ["vmctl", "stop", "web1"], output_loglevel="trace", python_shell=False
            )
            self.assertTrue(res["changes"])

    def test_stop_when_stopped(self):
        """
        Tests stopping a VM that is already stopped/stopping.
        """
        ret = {}
        ret["stdout"] = ""
        ret["stderr"] = "vmctl: terminate vm command failed: Invalid argument"
        ret["retcode"] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(vmctl.__salt__, {"cmd.run_all": mock_cmd}):
            res = vmctl.stop("web1")
            mock_cmd.assert_called_once_with(
                ["vmctl", "stop", "web1"], output_loglevel="trace", python_shell=False
            )
            self.assertFalse(res["changes"])
