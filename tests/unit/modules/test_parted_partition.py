# -*- coding: utf-8 -*-
"""
    :codeauthor: Dave Rawks (dave@pandora.com)


    tests.unit.modules.parted_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.modules.parted_partition as parted

# Import Salt libs
from salt.exceptions import CommandExecutionError

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PartedTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        self.cmdrun = MagicMock()
        self.cmdrun_stdout = MagicMock()
        self.addCleanup(delattr, self, "cmdrun")
        self.addCleanup(delattr, self, "cmdrun_stdout")
        return {
            parted: {
                "__salt__": {
                    "cmd.run": self.cmdrun,
                    "cmd.run_stdout": self.cmdrun_stdout,
                }
            }
        }

    # Test __virtual__ function for module registration

    def test_virtual_bails_on_windows(self):
        """
        If running windows, __virtual__ shouldn't register module
        """
        with patch("salt.utils.platform.is_windows", lambda: True):
            ret = parted.__virtual__()
            err = (
                False,
                "The parted execution module failed to load Windows systems are not supported.",
            )
            self.assertEqual(err, ret)

    def test_virtual_bails_without_parted(self):
        """
        If parted not in PATH, __virtual__ shouldn't register module
        """
        with patch("salt.utils.path.which", lambda exe: not exe == "parted"), patch(
            "salt.utils.platform.is_windows", return_value=False
        ):
            ret = parted.__virtual__()
            err = (
                False,
                "The parted execution module failed to load parted binary is not in the path.",
            )
            self.assertEqual(err, ret)

    def test_virtual_bails_without_lsblk(self):
        """
        If lsblk not in PATH, __virtual__ shouldn't register module
        """
        with patch("salt.utils.path.which", lambda exe: not exe == "lsblk"), patch(
            "salt.utils.platform.is_windows", return_value=False
        ):
            ret = parted.__virtual__()
            err = (
                False,
                "The parted execution module failed to load lsblk binary is not in the path.",
            )
            self.assertEqual(err, ret)

    def test_virtual_bails_without_partprobe(self):
        """
        If partprobe not in PATH, __virtual__ shouldn't register module
        """
        with patch("salt.utils.path.which", lambda exe: not exe == "partprobe"), patch(
            "salt.utils.platform.is_windows", return_value=False
        ):
            ret = parted.__virtual__()
            err = (
                False,
                "The parted execution module failed to load partprobe binary is not in the path.",
            )
            self.assertEqual(err, ret)

    def test_virtual(self):
        """
        On expected platform with correct utils in PATH, register "partition" module
        """
        with patch("salt.utils.platform.is_windows", lambda: False), patch(
            "salt.utils.path.which", lambda exe: exe in ("parted", "lsblk", "partprobe")
        ):
            ret = parted.__virtual__()
            expect = "partition"
            self.assertEqual(ret, expect)

    # Test probe function

    def test_probe_wo_args(self):
        parted.probe()
        self.cmdrun.assert_called_once_with("partprobe -- ")

    def test_probe_w_single_arg(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            parted.probe("/dev/sda")
            self.cmdrun.assert_called_once_with("partprobe -- /dev/sda")

    def test_probe_w_multiple_args(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            parted.probe("/dev/sda", "/dev/sdb")
            self.cmdrun.assert_called_once_with("partprobe -- /dev/sda /dev/sdb")

    # Test _list function

    @staticmethod
    def parted_print_output(k):
        output = {
            "valid": (
                """BYT;\n"""
                """/dev/sda:4000GB:scsi:512:512:gpt:AMCC 9650SE-24M DISK:;\n"""
                """1:17.4kB:150MB:150MB:ext3::boot;\n"""
                """2:3921GB:4000GB:79.3GB:linux-swap(v1)::;\n"""
            ),
            "valid chs": (
                """CHS;\n"""
                """/dev/sda:3133,0,2:scsi:512:512:gpt:AMCC 9650SE-24M DISK:;\n"""
                """1:0,0,34:2431,134,43:ext3::boot;\n"""
                """2:2431,134,44:2492,80,42:linux-swap(v1)::;\n"""
            ),
            "valid_legacy": (
                """BYT;\n"""
                """/dev/sda:4000GB:scsi:512:512:gpt:AMCC 9650SE-24M DISK;\n"""
                """1:17.4kB:150MB:150MB:ext3::boot;\n"""
                """2:3921GB:4000GB:79.3GB:linux-swap(v1)::;\n"""
            ),
            "empty": "",
            "bad_label_info": (
                """BYT;\n"""
                """badbadbadbad\n"""
                """1:17.4kB:150MB:150MB:ext3::boot;\n"""
                """2:3921GB:4000GB:79.3GB:linux-swap(v1)::;\n"""
            ),
            "bad_header": (
                """badbadbadbad\n"""
                """/dev/sda:4000GB:scsi:512:512:gpt:AMCC 9650SE-24M DISK:;\n"""
                """1:17.4kB:150MB:150MB:ext3::boot;\n"""
                """2:3921GB:4000GB:79.3GB:linux-swap(v1)::;\n"""
            ),
            "bad_partition": (
                """BYT;\n"""
                """/dev/sda:4000GB:scsi:512:512:gpt:AMCC 9650SE-24M DISK:;\n"""
                """badbadbadbad\n"""
                """2:3921GB:4000GB:79.3GB:linux-swap(v1)::;\n"""
            ),
        }
        return output[k]

    def test_list__without_device(self):
        self.assertRaises(TypeError, parted.list_)

    def test_list__empty_cmd_output(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            self.cmdrun_stdout.return_value = self.parted_print_output("empty")
            output = parted.list_("/dev/sda")
            self.cmdrun_stdout.assert_called_once_with("parted -m -s /dev/sda print")
            expected = {"info": {}, "partitions": {}}
            self.assertEqual(output, expected)

    def test_list__valid_unit_empty_cmd_output(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            self.cmdrun_stdout.return_value = self.parted_print_output("empty")
            output = parted.list_("/dev/sda", unit="s")
            self.cmdrun_stdout.assert_called_once_with(
                "parted -m -s /dev/sda unit s print"
            )
            expected = {"info": {}, "partitions": {}}
            self.assertEqual(output, expected)

    def test_list__invalid_unit(self):
        self.assertRaises(
            CommandExecutionError, parted.list_, "/dev/sda", unit="badbadbad"
        )
        self.assertFalse(self.cmdrun.called)

    def test_list__bad_header(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            self.cmdrun_stdout.return_value = self.parted_print_output("bad_header")
            self.assertRaises(CommandExecutionError, parted.list_, "/dev/sda")
            self.cmdrun_stdout.assert_called_once_with("parted -m -s /dev/sda print")

    def test_list__bad_label_info(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            self.cmdrun_stdout.return_value = self.parted_print_output("bad_label_info")
            self.assertRaises(CommandExecutionError, parted.list_, "/dev/sda")
            self.cmdrun_stdout.assert_called_once_with("parted -m -s /dev/sda print")

    def test_list__bad_partition(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            self.cmdrun_stdout.return_value = self.parted_print_output("bad_partition")
            self.assertRaises(CommandExecutionError, parted.list_, "/dev/sda")
            self.cmdrun_stdout.assert_called_once_with("parted -m -s /dev/sda print")

    def test_list__valid_cmd_output(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            self.cmdrun_stdout.return_value = self.parted_print_output("valid")
            output = parted.list_("/dev/sda")
            self.cmdrun_stdout.assert_called_once_with("parted -m -s /dev/sda print")
            expected = {
                "info": {
                    "logical sector": "512",
                    "physical sector": "512",
                    "interface": "scsi",
                    "model": "AMCC 9650SE-24M DISK",
                    "disk": "/dev/sda",
                    "disk flags": "",
                    "partition table": "gpt",
                    "size": "4000GB",
                },
                "partitions": {
                    "1": {
                        "end": "150MB",
                        "number": "1",
                        "start": "17.4kB",
                        "file system": "ext3",
                        "flags": "boot",
                        "name": "",
                        "size": "150MB",
                    },
                    "2": {
                        "end": "4000GB",
                        "number": "2",
                        "start": "3921GB",
                        "file system": "linux-swap(v1)",
                        "flags": "",
                        "name": "",
                        "size": "79.3GB",
                    },
                },
            }
            self.assertEqual(output, expected)

    def test_list__valid_unit_valid_cmd_output(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            self.cmdrun_stdout.return_value = self.parted_print_output("valid")
            output = parted.list_("/dev/sda", unit="s")
            self.cmdrun_stdout.assert_called_once_with(
                "parted -m -s /dev/sda unit s print"
            )
            expected = {
                "info": {
                    "logical sector": "512",
                    "physical sector": "512",
                    "interface": "scsi",
                    "model": "AMCC 9650SE-24M DISK",
                    "disk": "/dev/sda",
                    "disk flags": "",
                    "partition table": "gpt",
                    "size": "4000GB",
                },
                "partitions": {
                    "1": {
                        "end": "150MB",
                        "number": "1",
                        "start": "17.4kB",
                        "file system": "ext3",
                        "flags": "boot",
                        "name": "",
                        "size": "150MB",
                    },
                    "2": {
                        "end": "4000GB",
                        "number": "2",
                        "start": "3921GB",
                        "file system": "linux-swap(v1)",
                        "flags": "",
                        "name": "",
                        "size": "79.3GB",
                    },
                },
            }
            self.assertEqual(output, expected)

    def test_list__valid_unit_chs_valid_cmd_output(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            self.cmdrun_stdout.return_value = self.parted_print_output("valid chs")
            output = parted.list_("/dev/sda", unit="chs")
            self.cmdrun_stdout.assert_called_once_with(
                "parted -m -s /dev/sda unit chs print"
            )
            expected = {
                "info": {
                    "logical sector": "512",
                    "physical sector": "512",
                    "interface": "scsi",
                    "model": "AMCC 9650SE-24M DISK",
                    "disk": "/dev/sda",
                    "disk flags": "",
                    "partition table": "gpt",
                    "size": "3133,0,2",
                },
                "partitions": {
                    "1": {
                        "end": "2431,134,43",
                        "number": "1",
                        "start": "0,0,34",
                        "file system": "ext3",
                        "flags": "boot",
                        "name": "",
                    },
                    "2": {
                        "end": "2492,80,42",
                        "number": "2",
                        "start": "2431,134,44",
                        "file system": "linux-swap(v1)",
                        "flags": "",
                        "name": "",
                    },
                },
            }
            self.assertEqual(output, expected)

    def test_list__valid_legacy_cmd_output(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            self.cmdrun_stdout.return_value = self.parted_print_output("valid_legacy")
            output = parted.list_("/dev/sda")
            self.cmdrun_stdout.assert_called_once_with("parted -m -s /dev/sda print")
            expected = {
                "info": {
                    "logical sector": "512",
                    "physical sector": "512",
                    "interface": "scsi",
                    "model": "AMCC 9650SE-24M DISK",
                    "disk": "/dev/sda",
                    "partition table": "gpt",
                    "size": "4000GB",
                },
                "partitions": {
                    "1": {
                        "end": "150MB",
                        "number": "1",
                        "start": "17.4kB",
                        "file system": "ext3",
                        "flags": "boot",
                        "name": "",
                        "size": "150MB",
                    },
                    "2": {
                        "end": "4000GB",
                        "number": "2",
                        "start": "3921GB",
                        "file system": "linux-swap(v1)",
                        "flags": "",
                        "name": "",
                        "size": "79.3GB",
                    },
                },
            }
            self.assertEqual(output, expected)

    def test_list__valid_unit_valid_legacy_cmd_output(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            self.cmdrun_stdout.return_value = self.parted_print_output("valid_legacy")
            output = parted.list_("/dev/sda", unit="s")
            self.cmdrun_stdout.assert_called_once_with(
                "parted -m -s /dev/sda unit s print"
            )
            expected = {
                "info": {
                    "logical sector": "512",
                    "physical sector": "512",
                    "interface": "scsi",
                    "model": "AMCC 9650SE-24M DISK",
                    "disk": "/dev/sda",
                    "partition table": "gpt",
                    "size": "4000GB",
                },
                "partitions": {
                    "1": {
                        "end": "150MB",
                        "number": "1",
                        "start": "17.4kB",
                        "file system": "ext3",
                        "flags": "boot",
                        "name": "",
                        "size": "150MB",
                    },
                    "2": {
                        "end": "4000GB",
                        "number": "2",
                        "start": "3921GB",
                        "file system": "linux-swap(v1)",
                        "flags": "",
                        "name": "",
                        "size": "79.3GB",
                    },
                },
            }
            self.assertEqual(output, expected)

    def test_disk_set(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            self.cmdrun.return_value = ""
            output = parted.disk_set("/dev/sda", "pmbr_boot", "on")
            self.cmdrun.assert_called_once_with(
                ["parted", "-m", "-s", "/dev/sda", "disk_set", "pmbr_boot", "on"]
            )
            assert output == []

    def test_disk_toggle(self):
        with patch("salt.modules.parted_partition._validate_device", MagicMock()):
            self.cmdrun.return_value = ""
            output = parted.disk_toggle("/dev/sda", "pmbr_boot")
            self.cmdrun.assert_called_once_with(
                ["parted", "-m", "-s", "/dev/sda", "disk_toggle", "pmbr_boot"]
            )
            assert output == []
