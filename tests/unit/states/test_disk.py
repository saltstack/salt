# -*- coding: utf-8 -*-
"""
Tests for disk state
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

from os import path

# Import Salt Libs
import salt.states.disk as disk

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class DiskTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test disk state
    """

    def setup_loader_modules(self):
        self.mock_data = {
            "/": {
                "1K-blocks": "41147472",
                "available": "37087976",
                "capacity": "6%",
                "filesystem": "/dev/xvda1",
                "used": "2172880",
            },
            "/dev": {
                "1K-blocks": "10240",
                "available": "10240",
                "capacity": "0%",
                "filesystem": "udev",
                "used": "0",
            },
            "/run": {
                "1K-blocks": "410624",
                "available": "379460",
                "capacity": "8%",
                "filesystem": "tmpfs",
                "used": "31164",
            },
            "/sys/fs/cgroup": {
                "1K-blocks": "1026556",
                "available": "1026556",
                "capacity": "0%",
                "filesystem": "tmpfs",
                "used": "0",
            },
        }

        self.mock_data_path = {"/foo": {"available": "42", "total": "100"}}

        self.addCleanup(delattr, self, "mock_data")
        self.addCleanup(delattr, self, "mock_data_path")
        return {
            disk: {
                "__salt__": {
                    "disk.usage": MagicMock(return_value=self.mock_data),
                    "status.diskusage": MagicMock(return_value=self.mock_data_path),
                }
            }
        }

    def test_status_missing(self):
        """
        Test disk.status when name not found
        """
        mock_fs = "/mnt/cheese"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk mount /mnt/cheese not present. Directory /mnt/cheese does not exist or is not a directory",
            "changes": {},
            "data": {},
        }

        ret = disk.status(mock_fs)
        self.assertEqual(ret, mock_ret)

    def test_status_type_error(self):
        """
        Test disk.status with incorrectly formatted arguments
        """
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "",
            "changes": {},
            "data": {},
        }

        mock_ret["comment"] = "maximum must be an integer "
        ret = disk.status(mock_fs, maximum=r"e^{i\pi}")
        self.assertEqual(ret, mock_ret)

        mock_ret["comment"] = "minimum must be an integer "
        ret = disk.status(mock_fs, minimum=r"\cos\pi + i\sin\pi")
        self.assertEqual(ret, mock_ret)

    def test_status_range_error(self):
        """
        Test disk.status with excessive extrema
        """
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "",
            "changes": {},
            "data": {},
        }

        mock_ret["comment"] = "maximum must be in the range [0, 100] "
        ret = disk.status(mock_fs, maximum="-1")
        self.assertEqual(ret, mock_ret)

        mock_ret["comment"] = "minimum must be in the range [0, 100] "
        ret = disk.status(mock_fs, minimum="101")
        self.assertEqual(ret, mock_ret)

    def test_status_inverted_range(self):
        """
        Test disk.status when minimum > maximum
        """
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "minimum must be less than maximum ",
            "changes": {},
            "data": {},
        }

        ret = disk.status(mock_fs, maximum="0", minimum="1")
        self.assertEqual(ret, mock_ret)

    def test_status_threshold(self):
        """
        Test disk.status when filesystem triggers thresholds
        """
        mock_min = 100
        mock_max = 0
        mock_fs = "/"
        mock_used = int(self.mock_data[mock_fs]["capacity"].strip("%"))
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }

        mock_ret[
            "comment"
        ] = "Disk used space is below minimum of {0} % at {1} %".format(
            mock_min, mock_used
        )
        ret = disk.status(mock_fs, minimum=mock_min)
        self.assertEqual(ret, mock_ret)

        mock_ret[
            "comment"
        ] = "Disk used space is above maximum of {0} % at {1} %".format(
            mock_max, mock_used
        )
        ret = disk.status(mock_fs, maximum=mock_max)
        self.assertEqual(ret, mock_ret)

    def test_status_strip(self):
        """
        Test disk.status appropriately strips unit info from numbers
        """
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": True,
            "comment": "Disk used space in acceptable range",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }

        ret = disk.status(mock_fs, minimum="0%")
        self.assertEqual(ret, mock_ret)

        ret = disk.status(mock_fs, minimum="0 %")
        self.assertEqual(ret, mock_ret)

        ret = disk.status(mock_fs, maximum="100%")
        self.assertEqual(ret, mock_ret)

        ret = disk.status(mock_fs, minimum="1024K", absolute=True)
        self.assertEqual(ret, mock_ret)

        ret = disk.status(mock_fs, minimum="1024KB", absolute=True)
        self.assertEqual(ret, mock_ret)

        ret = disk.status(mock_fs, maximum="4194304 KB", absolute=True)
        self.assertEqual(ret, mock_ret)

    def test_status(self):
        """
        Test disk.status when filesystem meets thresholds
        """
        mock_min = 0
        mock_max = 100
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": True,
            "comment": "Disk used space in acceptable range",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }

        ret = disk.status(mock_fs, minimum=mock_min)
        self.assertEqual(ret, mock_ret)

        ret = disk.status(mock_fs, maximum=mock_max)
        self.assertEqual(ret, mock_ret)

        # Reset mock because it's an iterator to run the tests with the
        # absolute flag
        ret = {
            "name": mock_fs,
            "result": False,
            "comment": "",
            "changes": {},
            "data": {},
        }

        data_1 = {"capacity": "8 %", "used": "8", "available": "92"}
        data_2 = {"capacity": "22 %", "used": "22", "available": "78"}
        data_3 = {"capacity": "15 %", "used": "15", "available": "85"}
        mock = MagicMock(
            side_effect=[[], {mock_fs: data_1}, {mock_fs: data_2}, {mock_fs: data_3}]
        )
        with patch.dict(disk.__salt__, {"disk.usage": mock}):
            mock = MagicMock(return_value=False)
            with patch.object(path, "isdir", mock):
                comt = "Disk mount / not present. Directory / does not exist or is not a directory"
                ret.update({"comment": comt})
                self.assertDictEqual(disk.status(mock_fs), ret)

                comt = "minimum must be less than maximum "
                ret.update({"comment": comt})
                self.assertDictEqual(
                    disk.status(mock_fs, "10", "20", absolute=True), ret
                )

                comt = "Disk used space is below minimum of 10 KB at 8 KB"
                ret.update({"comment": comt, "data": data_1})
                self.assertDictEqual(
                    disk.status(mock_fs, "20", "10", absolute=True), ret
                )

                comt = "Disk used space is above maximum of 20 KB at 22 KB"
                ret.update({"comment": comt, "data": data_2})
                self.assertDictEqual(
                    disk.status(mock_fs, "20", "10", absolute=True), ret
                )

                comt = "Disk used space in acceptable range"
                ret.update({"comment": comt, "result": True, "data": data_3})
                self.assertDictEqual(
                    disk.status(mock_fs, "20", "10", absolute=True), ret
                )

    def test_path_missing(self):
        mock_fs = "/bar"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk mount {0} not present. Directory {0} does not exist or is not a directory".format(
                mock_fs
            ),
            "changes": {},
            "data": {},
        }
        mock = MagicMock(return_value=False)
        with patch.object(path, "isdir", mock):
            self.assertDictEqual(
                disk.status(mock_fs, "58", "55", absolute=True, free=False), mock_ret
            )

    # acceptable range
    def test_path_used_absolute_acceptable(self):
        mock_fs = "/foo"
        mock_ret = {
            "name": mock_fs,
            "result": True,
            "comment": "Disk used space in acceptable range",
            "changes": {},
            "data": self.mock_data_path,
        }
        mock = MagicMock(return_value=True)
        with patch.object(path, "isdir", mock):
            self.assertDictEqual(
                disk.status(mock_fs, "58", "55", absolute=True, free=False), mock_ret
            )

    def test_path_used_relative_acceptable(self):
        mock_fs = "/foo"
        mock_ret = {
            "name": mock_fs,
            "result": True,
            "comment": "Disk used space in acceptable range",
            "changes": {},
            "data": self.mock_data_path,
        }
        mock = MagicMock(return_value=True)
        with patch.object(path, "isdir", mock):
            self.assertDictEqual(
                disk.status(mock_fs, "100%", "57%", absolute=False, free=False),
                mock_ret,
            )

    def test_path_free_absolute_acceptable(self):
        mock_fs = "/foo"
        mock_ret = {
            "name": mock_fs,
            "result": True,
            "comment": "Disk used space in acceptable range",
            "changes": {},
            "data": self.mock_data_path,
        }
        mock = MagicMock(return_value=True)
        with patch.object(path, "isdir", mock):
            self.assertDictEqual(
                disk.status(mock_fs, "100", "42", absolute=True, free=True), mock_ret
            )

    def test_path_free_relative_acceptable(self):
        mock_fs = "/foo"
        mock_ret = {
            "name": mock_fs,
            "result": True,
            "comment": "Disk used space in acceptable range",
            "changes": {},
            "data": self.mock_data_path,
        }
        mock = MagicMock(return_value=True)
        with patch.object(path, "isdir", mock):
            self.assertDictEqual(
                disk.status(mock_fs, "42%", "41%", absolute=False, free=True), mock_ret
            )

    def test_mount_used_absolute_acceptable(self):
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": True,
            "comment": "Disk used space in acceptable range",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }
        self.assertDictEqual(
            disk.status(mock_fs, "2172881", "2172880", absolute=True, free=False),
            mock_ret,
        )

    def test_mount_used_relative_acceptable(self):
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": True,
            "comment": "Disk used space in acceptable range",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }

        self.assertDictEqual(
            disk.status(mock_fs, "7%", "6%", absolute=False, free=False), mock_ret
        )

    def test_mount_free_absolute_acceptable(self):
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": True,
            "comment": "Disk used space in acceptable range",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }
        self.assertDictEqual(
            disk.status(mock_fs, "37087976", "37087975", absolute=True, free=True),
            mock_ret,
        )

    def test_mount_free_relative_acceptable(self):
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": True,
            "comment": "Disk used space in acceptable range",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }

        self.assertDictEqual(
            disk.status(mock_fs, "100%", "94%", absolute=False, free=True), mock_ret
        )

    # below minimum
    def test_path_used_absolute_below(self):
        mock_fs = "/foo"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk used space is below minimum of 59 KB at 58 KB",
            "changes": {},
            "data": self.mock_data_path,
        }
        mock = MagicMock(return_value=True)
        with patch.object(path, "isdir", mock):
            self.assertDictEqual(
                disk.status(mock_fs, "60", "59", absolute=True, free=False), mock_ret
            )

    def test_path_used_relative_below(self):
        mock_fs = "/foo"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk used space is below minimum of 59 % at 58.0 %",
            "changes": {},
            "data": self.mock_data_path,
        }
        mock = MagicMock(return_value=True)
        with patch.object(path, "isdir", mock):
            self.assertDictEqual(
                disk.status(mock_fs, "60%", "59%", absolute=False, free=False), mock_ret
            )

    def test_path_free_absolute_below(self):
        mock_fs = "/foo"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk available space is below minimum of 43 KB at 42 KB",
            "changes": {},
            "data": self.mock_data_path,
        }
        mock = MagicMock(return_value=True)
        with patch.object(path, "isdir", mock):
            self.assertDictEqual(
                disk.status(mock_fs, "100", "43", absolute=True, free=True), mock_ret
            )

    def test_path_free_relative_below(self):
        mock_fs = "/foo"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk available space is below minimum of 43 % at 42.0 %",
            "changes": {},
            "data": self.mock_data_path,
        }
        mock = MagicMock(return_value=True)
        with patch.object(path, "isdir", mock):
            self.assertDictEqual(
                disk.status(mock_fs, "100%", "43%", absolute=False, free=True), mock_ret
            )

    def test_mount_used_absolute_below(self):
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk used space is below minimum of 2172881 KB at 2172880 KB",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }
        self.assertDictEqual(
            disk.status(mock_fs, "2172882", "2172881", absolute=True, free=False),
            mock_ret,
        )

    def test_mount_used_relative_below(self):
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk used space is below minimum of 7 % at 6 %",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }

        self.assertDictEqual(
            disk.status(mock_fs, "8%", "7%", absolute=False, free=False), mock_ret
        )

    def test_mount_free_absolute_below(self):
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk available space is below minimum of 37087977 KB at 37087976 KB",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }
        self.assertDictEqual(
            disk.status(mock_fs, "37087978", "37087977", absolute=True, free=True),
            mock_ret,
        )

    def test_mount_free_relative_below(self):
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk available space is below minimum of 95 % at 94 %",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }

        self.assertDictEqual(
            disk.status(mock_fs, "100%", "95%", absolute=False, free=True), mock_ret
        )

    # above maximum
    def test_path_used_absolute_above(self):
        mock_fs = "/foo"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk used space is above maximum of 57 KB at 58 KB",
            "changes": {},
            "data": self.mock_data_path,
        }
        mock = MagicMock(return_value=True)
        with patch.object(path, "isdir", mock):
            self.assertDictEqual(
                disk.status(mock_fs, "57", "56", absolute=True, free=False), mock_ret
            )

    def test_path_used_relative_above(self):
        mock_fs = "/foo"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk used space is above maximum of 57 % at 58.0 %",
            "changes": {},
            "data": self.mock_data_path,
        }
        mock = MagicMock(return_value=True)
        with patch.object(path, "isdir", mock):
            self.assertDictEqual(
                disk.status(mock_fs, "57%", "56%", absolute=False, free=False), mock_ret
            )

    def test_path_free_absolute_above(self):
        mock_fs = "/foo"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk available space is above maximum of 41 KB at 42 KB",
            "changes": {},
            "data": self.mock_data_path,
        }
        mock = MagicMock(return_value=True)
        with patch.object(path, "isdir", mock):
            self.assertDictEqual(
                disk.status(mock_fs, "41", "40", absolute=True, free=True), mock_ret
            )

    def test_path_free_relative_above(self):
        mock_fs = "/foo"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk available space is above maximum of 41 % at 42.0 %",
            "changes": {},
            "data": self.mock_data_path,
        }
        mock = MagicMock(return_value=True)
        with patch.object(path, "isdir", mock):
            self.assertDictEqual(
                disk.status(mock_fs, "41%", "40%", absolute=False, free=True), mock_ret
            )

    def test_mount_used_absolute_above(self):
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk used space is above maximum of 2172879 KB at 2172880 KB",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }
        self.assertDictEqual(
            disk.status(mock_fs, "2172879", "2172878", absolute=True, free=False),
            mock_ret,
        )

    def test_mount_used_relative_above(self):
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk used space is above maximum of 5 % at 6 %",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }

        self.assertDictEqual(
            disk.status(mock_fs, "5%", "4%", absolute=False, free=False), mock_ret
        )

    def test_mount_free_absolute_above(self):
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk available space is above maximum of 37087975 KB at 37087976 KB",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }
        self.assertDictEqual(
            disk.status(mock_fs, "37087975", "37087974", absolute=True, free=True),
            mock_ret,
        )

    def test_mount_free_relative_above(self):
        mock_fs = "/"
        mock_ret = {
            "name": mock_fs,
            "result": False,
            "comment": "Disk available space is above maximum of 93 % at 94 %",
            "changes": {},
            "data": self.mock_data[mock_fs],
        }

        self.assertDictEqual(
            disk.status(mock_fs, "93%", "92%", absolute=False, free=True), mock_ret
        )
