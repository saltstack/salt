# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.win_wusa as wusa
from salt.exceptions import SaltInvocationError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class WinWusaTestCase(TestCase, LoaderModuleMockMixin):
    """
    test the function in the win_wusa state module
    """

    kb = "KB123456"

    def setup_loader_modules(self):
        return {wusa: {"__opts__": {"test": False}, "__env__": "base"}}

    def test_installed_no_source(self):
        """
        test wusa.installed without passing source
        """
        with self.assertRaises(SaltInvocationError) as excinfo:
            wusa.installed(name="KB123456", source=None)

        self.assertEqual(
            excinfo.exception.strerror, 'Must specify a "source" file to install'
        )

    def test_installed_existing(self):
        """
        test wusa.installed when the kb is already installed
        """
        mock_installed = MagicMock(return_value=True)
        with patch.dict(wusa.__salt__, {"wusa.is_installed": mock_installed}):
            returned = wusa.installed(
                name=self.kb, source="salt://{0}.msu".format(self.kb)
            )
            expected = {
                "changes": {},
                "comment": "{0} already installed".format(self.kb),
                "name": self.kb,
                "result": True,
            }
            self.assertDictEqual(expected, returned)

    def test_installed_test_true(self):
        """
        test wusa.installed with test=True
        """
        mock_installed = MagicMock(return_value=False)
        with patch.dict(
            wusa.__salt__, {"wusa.is_installed": mock_installed}
        ), patch.dict(wusa.__opts__, {"test": True}):
            returned = wusa.installed(
                name=self.kb, source="salt://{0}.msu".format(self.kb)
            )
            expected = {
                "changes": {},
                "comment": "{0} would be installed".format(self.kb),
                "name": self.kb,
                "result": None,
            }
            self.assertDictEqual(expected, returned)

    def test_installed_cache_fail(self):
        """
        test wusa.install when it fails to cache the file
        """
        mock_installed = MagicMock(return_value=False)
        mock_cache = MagicMock(return_value="")
        with patch.dict(
            wusa.__salt__,
            {"wusa.is_installed": mock_installed, "cp.cache_file": mock_cache},
        ):
            returned = wusa.installed(
                name=self.kb, source="salt://{0}.msu".format(self.kb)
            )
            expected = {
                "changes": {},
                "comment": "Unable to cache salt://{0}.msu from "
                'saltenv "base"'.format(self.kb),
                "name": self.kb,
                "result": False,
            }
            self.assertDictEqual(expected, returned)

    def test_installed(self):
        """
        test wusa.installed assuming success
        """
        mock_installed = MagicMock(side_effect=[False, True])
        mock_cache = MagicMock(return_value="C:\\{0}.msu".format(self.kb))
        with patch.dict(
            wusa.__salt__,
            {
                "wusa.is_installed": mock_installed,
                "cp.cache_file": mock_cache,
                "wusa.install": MagicMock(),
            },
        ):
            returned = wusa.installed(
                name=self.kb, source="salt://{0}.msu".format(self.kb)
            )
            expected = {
                "changes": {"new": True, "old": False},
                "comment": "{0} was installed. ".format(self.kb),
                "name": self.kb,
                "result": True,
            }
            self.assertDictEqual(expected, returned)

    def test_installed_failed(self):
        """
        test wusa.installed with a failure
        """
        mock_installed = MagicMock(side_effect=[False, False])
        mock_cache = MagicMock(return_value="C:\\{0}.msu".format(self.kb))
        with patch.dict(
            wusa.__salt__,
            {
                "wusa.is_installed": mock_installed,
                "cp.cache_file": mock_cache,
                "wusa.install": MagicMock(),
            },
        ):
            returned = wusa.installed(
                name=self.kb, source="salt://{0}.msu".format(self.kb)
            )
            expected = {
                "changes": {},
                "comment": "{0} failed to install. ".format(self.kb),
                "name": self.kb,
                "result": False,
            }
            self.assertDictEqual(expected, returned)

    def test_uninstalled_non_existing(self):
        """
        test wusa.uninstalled when the kb is not installed
        """
        mock_installed = MagicMock(return_value=False)
        with patch.dict(wusa.__salt__, {"wusa.is_installed": mock_installed}):
            returned = wusa.uninstalled(name=self.kb)
            expected = {
                "changes": {},
                "comment": "{0} already uninstalled".format(self.kb),
                "name": self.kb,
                "result": True,
            }
            self.assertDictEqual(expected, returned)

    def test_uninstalled_test_true(self):
        """
        test wusa.uninstalled with test=True
        """
        mock_installed = MagicMock(return_value=True)
        with patch.dict(
            wusa.__salt__, {"wusa.is_installed": mock_installed}
        ), patch.dict(wusa.__opts__, {"test": True}):
            returned = wusa.uninstalled(name=self.kb)
            expected = {
                "changes": {},
                "comment": "{0} would be uninstalled".format(self.kb),
                "name": self.kb,
                "result": None,
            }
            self.assertDictEqual(expected, returned)

    def test_uninstalled(self):
        """
        test wusa.uninstalled assuming success
        """
        mock_installed = MagicMock(side_effect=[True, False])
        with patch.dict(
            wusa.__salt__,
            {"wusa.is_installed": mock_installed, "wusa.uninstall": MagicMock()},
        ):
            returned = wusa.uninstalled(name=self.kb)
            expected = {
                "changes": {"new": False, "old": True},
                "comment": "{0} was uninstalled".format(self.kb),
                "name": self.kb,
                "result": True,
            }
            self.assertDictEqual(expected, returned)

    def test_uninstalled_failed(self):
        """
        test wusa.uninstalled with a failure
        """
        mock_installed = MagicMock(side_effect=[True, True])
        with patch.dict(
            wusa.__salt__,
            {"wusa.is_installed": mock_installed, "wusa.uninstall": MagicMock()},
        ):
            returned = wusa.uninstalled(name=self.kb)
            expected = {
                "changes": {},
                "comment": "{0} failed to uninstall".format(self.kb),
                "name": self.kb,
                "result": False,
            }
            self.assertDictEqual(expected, returned)
