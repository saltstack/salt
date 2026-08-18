"""
    :synopsis: Unit Tests for 'module.yumkernelpkg'
    :platform: Linux
    :maturity: develop
    .. versionadded:: 2018.3.0
"""

# pylint: disable=invalid-name,no-member

import pytest

from salt.exceptions import CommandExecutionError
from tests.support.kernelpkg import KernelPkgTestCase
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

try:
    import salt.modules.kernelpkg_linux_yum as kernelpkg
    import salt.modules.yumpkg as pkg

    HAS_MODULES = True
except ImportError:
    HAS_MODULES = False


@pytest.mark.skipif(not HAS_MODULES, reason="Salt modules could not be loaded")
class YumKernelPkgTestCase(KernelPkgTestCase, TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.kernelpkg_linux_yum
    """

    _kernelpkg = kernelpkg
    KERNEL_LIST = ["3.10.0-327.el7", "3.11.0-327.el7", "4.9.1-100.el7"]
    LATEST = KERNEL_LIST[-1]
    OS_ARCH = "x86_64"
    OS_NAME = "RedHat"
    OS_MAJORRELEASE = "7"

    def setup_loader_modules(self):
        return {
            kernelpkg: {
                "__grains__": {
                    "os": self.OS_NAME,
                    "osmajorrelease": self.OS_MAJORRELEASE,
                    "kernelrelease": f"{self.KERNEL_LIST[0]}.{self.OS_ARCH}",
                },
                "__salt__": {
                    "pkg.normalize_name": pkg.normalize_name,
                    "pkg.upgrade": MagicMock(return_value={}),
                    "pkg.list_pkgs": MagicMock(return_value={}),
                    "pkg.version": MagicMock(return_value=self.KERNEL_LIST),
                    "system.reboot": MagicMock(return_value=None),
                    "config.get": MagicMock(return_value=True),
                },
            },
            pkg: {"__grains__": {"osarch": self.OS_ARCH}},
        }

    def test_list_installed(self):
        """
        Test - Return the latest installed kernel version
        """
        mock = MagicMock(return_value=self.KERNEL_LIST)
        with patch.dict(self._kernelpkg.__salt__, {"pkg.version": mock}):
            self.assertListEqual(self._kernelpkg.list_installed(), self.KERNEL_LIST)

    def test_list_installed_none(self):
        """
        Test - Return the latest installed kernel version
        """
        mock = MagicMock(return_value=None)
        with patch.dict(self._kernelpkg.__salt__, {"pkg.version": mock}):
            self.assertListEqual(self._kernelpkg.list_installed(), [])

    def test_remove_success(self):
        """
        Test - remove kernel package
        """
        mock = MagicMock(return_value={"retcode": 0, "stderr": []})
        with patch.dict(self._kernelpkg.__salt__, {"cmd.run_all": mock}):
            with patch.object(
                self._kernelpkg, "active", return_value=self.KERNEL_LIST[-1]
            ):
                with patch.object(
                    self._kernelpkg, "list_installed", return_value=self.KERNEL_LIST
                ):
                    result = self._kernelpkg.remove(release=self.KERNEL_LIST[0])
                    self.assertIn("removed", result)
                    target = "{}-{}".format(
                        self._kernelpkg._package_name(), self.KERNEL_LIST[0]
                    )  # pylint: disable=protected-access
                    self.assertListEqual(result["removed"], [target])

    def test_remove_error(self):
        """
        Test - remove kernel package
        """
        mock = MagicMock(return_value={"retcode": -1, "stderr": []})
        with patch.dict(self._kernelpkg.__salt__, {"cmd.run_all": mock}):
            with patch.object(
                self._kernelpkg, "active", return_value=self.KERNEL_LIST[-1]
            ):
                with patch.object(
                    self._kernelpkg, "list_installed", return_value=self.KERNEL_LIST
                ):
                    self.assertRaises(
                        CommandExecutionError,
                        self._kernelpkg.remove,
                        release=self.KERNEL_LIST[0],
                    )
