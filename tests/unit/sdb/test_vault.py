"""
Test case for the vault SDB module
"""


import salt.sdb.vault as vault
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase


class TestVaultSDB(LoaderModuleMockMixin, TestCase):
    """
    Test case for the vault SDB module
    """

    def setup_loader_modules(self):
        return {
            vault: {
                "__opts__": {
                    "vault": {
                        "url": "http://127.0.0.1",
                        "auth": {"token": "test", "method": "token"},
                    }
                }
            }
        }

    def test_set(self):
        """
        Test salt.sdb.vault.set function
        """
        version = {"v2": False, "data": None, "metadata": None, "type": None}
        mock_version = MagicMock(return_value=version)
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        with patch.dict(
            vault.__utils__, {"vault.make_request": mock_vault}
        ), patch.dict(vault.__utils__, {"vault.is_v2": mock_version}):
            vault.set_("sdb://myvault/path/to/foo/bar", "super awesome")

        self.assertEqual(
            mock_vault.call_args_list,
            [
                call(
                    "POST",
                    "v1/sdb://myvault/path/to/foo",
                    json={"bar": "super awesome"},
                )
            ],
        )

    def test_set_v2(self):
        """
        Test salt.sdb.vault.set function with kv v2 backend
        """
        version = {
            "v2": True,
            "data": "path/data/to/foo",
            "metadata": "path/metadata/to/foo",
            "type": "kv",
        }
        mock_version = MagicMock(return_value=version)
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        with patch.dict(
            vault.__utils__, {"vault.make_request": mock_vault}
        ), patch.dict(vault.__utils__, {"vault.is_v2": mock_version}):
            vault.set_("sdb://myvault/path/to/foo/bar", "super awesome")

        self.assertEqual(
            mock_vault.call_args_list,
            [
                call(
                    "POST",
                    "v1/path/data/to/foo",
                    json={"data": {"bar": "super awesome"}},
                )
            ],
        )

    def test_set_question_mark(self):
        """
        Test salt.sdb.vault.set_ while using the old
        deprecated solution with a question mark.
        """
        version = {"v2": False, "data": None, "metadata": None, "type": None}
        mock_version = MagicMock(return_value=version)
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        with patch.dict(
            vault.__utils__, {"vault.make_request": mock_vault}
        ), patch.dict(vault.__utils__, {"vault.is_v2": mock_version}):
            vault.set_("sdb://myvault/path/to/foo?bar", "super awesome")

        self.assertEqual(
            mock_vault.call_args_list,
            [
                call(
                    "POST",
                    "v1/sdb://myvault/path/to/foo",
                    json={"bar": "super awesome"},
                )
            ],
        )

    def test_get(self):
        """
        Test salt.sdb.vault.get function
        """
        version = {"v2": False, "data": None, "metadata": None, "type": None}
        mock_version = MagicMock(return_value=version)
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        mock_vault.return_value.json.return_value = {"data": {"bar": "test"}}
        with patch.dict(
            vault.__utils__, {"vault.make_request": mock_vault}
        ), patch.dict(vault.__utils__, {"vault.is_v2": mock_version}):
            self.assertEqual(vault.get("sdb://myvault/path/to/foo/bar"), "test")

        self.assertEqual(
            mock_vault.call_args_list,
            [call("GET", "v1/sdb://myvault/path/to/foo")],
        )

    def test_get_v2(self):
        """
        Test salt.sdb.vault.get function with kv v2 backend
        """
        version = {
            "v2": True,
            "data": "path/data/to/foo",
            "metadata": "path/metadata/to/foo",
            "type": "kv",
        }
        mock_version = MagicMock(return_value=version)
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        mock_vault.return_value.json.return_value = {"data": {"data": {"bar": "test"}}}
        with patch.dict(
            vault.__utils__, {"vault.make_request": mock_vault}
        ), patch.dict(vault.__utils__, {"vault.is_v2": mock_version}):
            self.assertEqual(vault.get("sdb://myvault/path/to/foo/bar"), "test")

        self.assertEqual(
            mock_vault.call_args_list, [call("GET", "v1/path/data/to/foo")]
        )

    def test_get_question_mark(self):
        """
        Test salt.sdb.vault.get while using the old
        deprecated solution with a question mark.
        """
        version = {"v2": False, "data": None, "metadata": None, "type": None}
        mock_version = MagicMock(return_value=version)
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        mock_vault.return_value.json.return_value = {"data": {"bar": "test"}}
        with patch.dict(
            vault.__utils__, {"vault.make_request": mock_vault}
        ), patch.dict(vault.__utils__, {"vault.is_v2": mock_version}):
            self.assertEqual(vault.get("sdb://myvault/path/to/foo?bar"), "test")
        self.assertEqual(
            mock_vault.call_args_list,
            [call("GET", "v1/sdb://myvault/path/to/foo")],
        )

    def test_get_missing(self):
        """
        Test salt.sdb.vault.get function returns None
        if vault does not have an entry
        """
        version = {"v2": False, "data": None, "metadata": None, "type": None}
        mock_version = MagicMock(return_value=version)
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 404
        with patch.dict(
            vault.__utils__, {"vault.make_request": mock_vault}
        ), patch.dict(vault.__utils__, {"vault.is_v2": mock_version}):
            self.assertIsNone(vault.get("sdb://myvault/path/to/foo/bar"))

        assert mock_vault.call_args_list == [
            call("GET", "v1/sdb://myvault/path/to/foo")
        ]

    def test_get_missing_key(self):
        """
        Test salt.sdb.vault.get function returns None
        if vault does not have the key but does have the entry
        """
        version = {"v2": False, "data": None, "metadata": None, "type": None}
        mock_version = MagicMock(return_value=version)
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        mock_vault.return_value.json.return_value = {"data": {"bar": "test"}}
        with patch.dict(
            vault.__utils__, {"vault.make_request": mock_vault}
        ), patch.dict(vault.__utils__, {"vault.is_v2": mock_version}):
            self.assertIsNone(vault.get("sdb://myvault/path/to/foo/foo"))

        assert mock_vault.call_args_list == [
            call("GET", "v1/sdb://myvault/path/to/foo")
        ]
