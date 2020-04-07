# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.win_dism as dism

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class WinDismTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {dism: {}}

    def test_capability_installed(self):
        """
            Test capability installed state
        """
        expected = {
            "comment": "Installed Capa2",
            "changes": {"capability": {"new": ["Capa2"]}, "retcode": 0},
            "name": "Capa2",
            "result": True,
        }

        mock_installed = MagicMock(side_effect=[["Capa1"], ["Capa1", "Capa2"]])
        mock_add = MagicMock(return_value={"retcode": 0})

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_capabilities": mock_installed,
                "dism.add_capability": mock_add,
            },
        ):
            with patch.dict(dism.__opts__, {"test": False}):

                out = dism.capability_installed("Capa2", "somewhere", True)

                mock_installed.assert_called_with()
                mock_add.assert_called_once_with(
                    "Capa2", "somewhere", True, None, False
                )
                self.assertEqual(out, expected)

    def test_capability_installed_failure(self):
        """
            Test installing a capability which fails with DISM
        """
        expected = {
            "comment": "Failed to install Capa2: Failed",
            "changes": {},
            "name": "Capa2",
            "result": False,
        }

        mock_installed = MagicMock(side_effect=[["Capa1"], ["Capa1"]])
        mock_add = MagicMock(return_value={"retcode": 67, "stdout": "Failed"})

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_capabilities": mock_installed,
                "dism.add_capability": mock_add,
            },
        ):
            with patch.dict(dism.__opts__, {"test": False}):

                out = dism.capability_installed("Capa2", "somewhere", True)

                mock_installed.assert_called_with()
                mock_add.assert_called_once_with(
                    "Capa2", "somewhere", True, None, False
                )
                self.assertEqual(out, expected)

    def test_capability_installed_installed(self):
        """
            Test installing a capability already installed
        """
        expected = {
            "comment": "The capability Capa2 is already installed",
            "changes": {},
            "name": "Capa2",
            "result": True,
        }

        mock_installed = MagicMock(return_value=["Capa1", "Capa2"])
        mock_add = MagicMock()

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_capabilities": mock_installed,
                "dism.add_capability": mock_add,
            },
        ):

            with patch.dict(dism.__opts__, {"test": False}):
                out = dism.capability_installed("Capa2", "somewhere", True)

                mock_installed.assert_called_once_with()
                assert not mock_add.called
                self.assertEqual(out, expected)

    def test_capability_removed(self):
        """
            Test capability removed state
        """
        expected = {
            "comment": "Removed Capa2",
            "changes": {"capability": {"old": ["Capa2"]}, "retcode": 0},
            "name": "Capa2",
            "result": True,
        }

        mock_removed = MagicMock(side_effect=[["Capa1", "Capa2"], ["Capa1"]])
        mock_remove = MagicMock(return_value={"retcode": 0})

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_capabilities": mock_removed,
                "dism.remove_capability": mock_remove,
            },
        ):
            with patch.dict(dism.__opts__, {"test": False}):

                out = dism.capability_removed("Capa2")

                mock_removed.assert_called_with()
                mock_remove.assert_called_once_with("Capa2", None, False)
                self.assertEqual(out, expected)

    def test_capability_removed_failure(self):
        """
            Test removing a capability which fails with DISM
        """
        expected = {
            "comment": "Failed to remove Capa2: Failed",
            "changes": {},
            "name": "Capa2",
            "result": False,
        }

        mock_removed = MagicMock(side_effect=[["Capa1", "Capa2"], ["Capa1", "Capa2"]])
        mock_remove = MagicMock(return_value={"retcode": 67, "stdout": "Failed"})

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_capabilities": mock_removed,
                "dism.remove_capability": mock_remove,
            },
        ):
            with patch.dict(dism.__opts__, {"test": False}):

                out = dism.capability_removed("Capa2")

                mock_removed.assert_called_with()
                mock_remove.assert_called_once_with("Capa2", None, False)
                self.assertEqual(out, expected)

    def test_capability_removed_removed(self):
        """
            Test removing a capability already removed
        """
        expected = {
            "comment": "The capability Capa2 is already removed",
            "changes": {},
            "name": "Capa2",
            "result": True,
        }

        mock_removed = MagicMock(return_value=["Capa1"])
        mock_remove = MagicMock()

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_capabilities": mock_removed,
                "dism.add_capability": mock_remove,
            },
        ):

            out = dism.capability_removed("Capa2", "somewhere", True)

            mock_removed.assert_called_once_with()
            assert not mock_remove.called
            self.assertEqual(out, expected)

    def test_feature_installed(self):
        """
            Test installing a feature with DISM
        """
        expected = {
            "comment": "Installed Feat2",
            "changes": {"feature": {"new": ["Feat2"]}, "retcode": 0},
            "name": "Feat2",
            "result": True,
        }

        mock_installed = MagicMock(side_effect=[["Feat1"], ["Feat1", "Feat2"]])
        mock_add = MagicMock(return_value={"retcode": 0})

        with patch.dict(
            dism.__salt__,
            {"dism.installed_features": mock_installed, "dism.add_feature": mock_add},
        ):
            with patch.dict(dism.__opts__, {"test": False}):

                out = dism.feature_installed("Feat2")

                mock_installed.assert_called_with()
                mock_add.assert_called_once_with(
                    "Feat2", None, None, False, False, None, False
                )
                self.assertEqual(out, expected)

    def test_feature_installed_failure(self):
        """
            Test installing a feature which fails with DISM
        """
        expected = {
            "comment": "Failed to install Feat2: Failed",
            "changes": {},
            "name": "Feat2",
            "result": False,
        }

        mock_installed = MagicMock(side_effect=[["Feat1"], ["Feat1"]])
        mock_add = MagicMock(return_value={"retcode": 67, "stdout": "Failed"})

        with patch.dict(
            dism.__salt__,
            {"dism.installed_features": mock_installed, "dism.add_feature": mock_add},
        ):
            with patch.dict(dism.__opts__, {"test": False}):

                out = dism.feature_installed("Feat2")

                mock_installed.assert_called_with()
                mock_add.assert_called_once_with(
                    "Feat2", None, None, False, False, None, False
                )
                self.assertEqual(out, expected)

    def test_feature_installed_installed(self):
        """
            Test installing a feature already installed
        """
        expected = {
            "comment": "The feature Feat1 is already installed",
            "changes": {},
            "name": "Feat1",
            "result": True,
        }

        mock_installed = MagicMock(side_effect=[["Feat1", "Feat2"], ["Feat1", "Feat2"]])
        mock_add = MagicMock()

        with patch.dict(
            dism.__salt__,
            {"dism.installed_features": mock_installed, "dism.add_feature": mock_add},
        ):

            out = dism.feature_installed("Feat1")

            mock_installed.assert_called_once_with()
            assert not mock_add.called
            self.assertEqual(out, expected)

    def test_feature_removed(self):
        """
            Test removing a feature with DISM
        """
        expected = {
            "comment": "Removed Feat2",
            "changes": {"feature": {"old": ["Feat2"]}, "retcode": 0},
            "name": "Feat2",
            "result": True,
        }

        mock_removed = MagicMock(side_effect=[["Feat1", "Feat2"], ["Feat1"]])
        mock_remove = MagicMock(return_value={"retcode": 0})

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_features": mock_removed,
                "dism.remove_feature": mock_remove,
            },
        ):
            with patch.dict(dism.__opts__, {"test": False}):

                out = dism.feature_removed("Feat2")

                mock_removed.assert_called_with()
                mock_remove.assert_called_once_with("Feat2", False, None, False)
                self.assertEqual(out, expected)

    def test_feature_removed_failure(self):
        """
            Test removing a feature which fails with DISM
        """
        expected = {
            "comment": "Failed to remove Feat2: Failed",
            "changes": {},
            "name": "Feat2",
            "result": False,
        }

        mock_removed = MagicMock(side_effect=[["Feat1", "Feat2"], ["Feat1", "Feat2"]])
        mock_remove = MagicMock(return_value={"retcode": 67, "stdout": "Failed"})

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_features": mock_removed,
                "dism.remove_feature": mock_remove,
            },
        ):
            with patch.dict(dism.__opts__, {"test": False}):

                out = dism.feature_removed("Feat2")

                mock_removed.assert_called_with()
                mock_remove.assert_called_once_with("Feat2", False, None, False)
                self.assertEqual(out, expected)

    def test_feature_removed_removed(self):
        """
            Test removing a feature already removed
        """
        expected = {
            "comment": "The feature Feat2 is already removed",
            "changes": {},
            "name": "Feat2",
            "result": True,
        }

        mock_removed = MagicMock(side_effect=[["Feat1"], ["Feat1"]])
        mock_remove = MagicMock()

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_features": mock_removed,
                "dism.remove_feature": mock_remove,
            },
        ):

            out = dism.feature_removed("Feat2")

            mock_removed.assert_called_once_with()
            assert not mock_remove.called
            self.assertEqual(out, expected)

    def test_package_installed(self):
        """
            Test installing a package with DISM
        """
        expected = {
            "comment": "Installed Pack2",
            "changes": {"package": {"new": ["Pack2"]}, "retcode": 0},
            "name": "Pack2",
            "result": True,
        }

        mock_installed = MagicMock(side_effect=[["Pack1"], ["Pack1", "Pack2"]])
        mock_add = MagicMock(return_value={"retcode": 0})
        mock_info = MagicMock(return_value={"Package Identity": "Pack2"})

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_packages": mock_installed,
                "dism.add_package": mock_add,
                "dism.package_info": mock_info,
            },
        ):
            with patch.dict(dism.__opts__, {"test": False}):
                with patch("os.path.exists"):

                    out = dism.package_installed("Pack2")

                    mock_installed.assert_called_with()
                    mock_add.assert_called_once_with("Pack2", False, False, None, False)
                    self.assertEqual(out, expected)

    def test_package_installed_failure(self):
        """
            Test installing a package which fails with DISM
        """
        expected = {
            "comment": "Failed to install Pack2: Failed",
            "changes": {},
            "name": "Pack2",
            "result": False,
        }

        mock_installed = MagicMock(side_effect=[["Pack1"], ["Pack1"]])
        mock_add = MagicMock(return_value={"retcode": 67, "stdout": "Failed"})
        mock_info = MagicMock(return_value={"Package Identity": "Pack2"})

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_packages": mock_installed,
                "dism.add_package": mock_add,
                "dism.package_info": mock_info,
            },
        ):
            with patch.dict(dism.__opts__, {"test": False}):
                with patch("os.path.exists"):

                    out = dism.package_installed("Pack2")

                    mock_installed.assert_called_with()
                    mock_add.assert_called_once_with("Pack2", False, False, None, False)
                    self.assertEqual(out, expected)

    def test_package_installed_installed(self):
        """
            Test installing a package already installed
        """
        expected = {
            "comment": "The package Pack2 is already installed: Pack2",
            "changes": {},
            "name": "Pack2",
            "result": True,
        }

        mock_installed = MagicMock(side_effect=[["Pack1", "Pack2"], ["Pack1", "Pack2"]])
        mock_add = MagicMock()
        mock_info = MagicMock(return_value={"Package Identity": "Pack2"})

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_packages": mock_installed,
                "dism.add_package": mock_add,
                "dism.package_info": mock_info,
            },
        ):
            with patch.dict(dism.__opts__, {"test": False}):
                with patch("os.path.exists"):

                    out = dism.package_installed("Pack2")

                    mock_installed.assert_called_once_with()
                    assert not mock_add.called
                    self.assertEqual(out, expected)

    def test_package_removed(self):
        """
            Test removing a package with DISM
        """
        expected = {
            "comment": "Removed Pack2",
            "changes": {"package": {"old": ["Pack2"]}, "retcode": 0},
            "name": "Pack2",
            "result": True,
        }

        mock_removed = MagicMock(side_effect=[["Pack1", "Pack2"], ["Pack1"]])
        mock_remove = MagicMock(return_value={"retcode": 0})
        mock_info = MagicMock(return_value={"Package Identity": "Pack2"})

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_packages": mock_removed,
                "dism.remove_package": mock_remove,
                "dism.package_info": mock_info,
            },
        ):
            with patch.dict(dism.__opts__, {"test": False}):
                with patch("os.path.exists"):

                    out = dism.package_removed("Pack2")

                    mock_removed.assert_called_with()
                    mock_remove.assert_called_once_with("Pack2", None, False)
                    self.assertEqual(out, expected)

    def test_package_removed_failure(self):
        """
            Test removing a package which fails with DISM
        """
        expected = {
            "comment": "Failed to remove Pack2: Failed",
            "changes": {},
            "name": "Pack2",
            "result": False,
        }

        mock_removed = MagicMock(side_effect=[["Pack1", "Pack2"], ["Pack1", "Pack2"]])
        mock_remove = MagicMock(return_value={"retcode": 67, "stdout": "Failed"})
        mock_info = MagicMock(return_value={"Package Identity": "Pack2"})

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_packages": mock_removed,
                "dism.remove_package": mock_remove,
                "dism.package_info": mock_info,
            },
        ):
            with patch.dict(dism.__opts__, {"test": False}):
                with patch("os.path.exists"):

                    out = dism.package_removed("Pack2")

                    mock_removed.assert_called_with()
                    mock_remove.assert_called_once_with("Pack2", None, False)
                    self.assertEqual(out, expected)

    def test_package_removed_removed(self):
        """
            Test removing a package already removed
        """
        expected = {
            "comment": "The package Pack2 is already removed",
            "changes": {},
            "name": "Pack2",
            "result": True,
        }

        mock_removed = MagicMock(side_effect=[["Pack1"], ["Pack1"]])
        mock_remove = MagicMock()
        mock_info = MagicMock(return_value={"Package Identity": "Pack2"})

        with patch.dict(
            dism.__salt__,
            {
                "dism.installed_packages": mock_removed,
                "dism.remove_package": mock_remove,
                "dism.package_info": mock_info,
            },
        ):

            with patch.dict(dism.__opts__, {"test": False}):
                with patch("os.path.exists"):
                    out = dism.package_removed("Pack2")

                    mock_removed.assert_called_once_with()
                    assert not mock_remove.called
                    self.assertEqual(out, expected)
