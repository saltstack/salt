"""
Test case for the vault execution module
"""


import salt.modules.vault as vault
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class TestVaultModule(LoaderModuleMockMixin, TestCase):
    """
    Test case for the vault execution module
    """

    def setup_loader_modules(self):
        return {
            vault: {
                "__opts__": {
                    "vault": {
                        "url": "http://127.0.0.1",
                        "auth": {"token": "test", "method": "token"},
                    }
                },
                "__grains__": {"id": "test-minion"},
            }
        }

    def test_read_secret_v1(self):
        """
        Test salt.modules.vault.read_secret function
        """
        version = {"v2": False, "data": None, "metadata": None, "type": None}
        mock_version = MagicMock(return_value=version)
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        mock_vault.return_value.json.return_value = {"data": {"key": "test"}}
        with patch.dict(
            vault.__utils__, {"vault.make_request": mock_vault}
        ), patch.dict(vault.__utils__, {"vault.is_v2": mock_version}):
            vault_return = vault.read_secret("/secret/my/secret")

        self.assertDictEqual(vault_return, {"key": "test"})

    def test_read_secret_v1_key(self):
        """
        Test salt.modules.vault.read_secret function specifying key
        """
        version = {"v2": False, "data": None, "metadata": None, "type": None}
        mock_version = MagicMock(return_value=version)
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        mock_vault.return_value.json.return_value = {"data": {"key": "somevalue"}}
        with patch.dict(
            vault.__utils__, {"vault.make_request": mock_vault}
        ), patch.dict(vault.__utils__, {"vault.is_v2": mock_version}):
            vault_return = vault.read_secret("/secret/my/secret", "key")

        self.assertEqual(vault_return, "somevalue")

    def test_read_secret_v2(self):
        """
        Test salt.modules.vault.read_secret function for v2 of kv secret backend
        """
        # given path secrets/mysecret generate v2 output
        version = {
            "v2": True,
            "data": "secrets/data/mysecret",
            "metadata": "secrets/metadata/mysecret",
            "type": "kv",
        }
        mock_version = MagicMock(return_value=version)
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        v2_return = {
            "data": {
                "data": {"akey": "avalue"},
                "metadata": {
                    "created_time": "2018-10-23T20:21:55.042755098Z",
                    "destroyed": False,
                    "version": 13,
                    "deletion_time": "",
                },
            }
        }

        mock_vault.return_value.json.return_value = v2_return
        with patch.dict(
            vault.__utils__, {"vault.make_request": mock_vault}
        ), patch.dict(vault.__utils__, {"vault.is_v2": mock_version}):
            # Validate metadata returned
            vault_return = vault.read_secret("/secret/my/secret", metadata=True)
            self.assertDictContainsSubset({"data": {"akey": "avalue"}}, vault_return)
            # Validate just data returned
            vault_return = vault.read_secret("/secret/my/secret")
            self.assertDictContainsSubset({"akey": "avalue"}, vault_return)

    def test_read_secret_v2_key(self):
        """
        Test salt.modules.vault.read_secret function for v2 of kv secret backend
        with specified key
        """
        # given path secrets/mysecret generate v2 output
        version = {
            "v2": True,
            "data": "secrets/data/mysecret",
            "metadata": "secrets/metadata/mysecret",
            "type": "kv",
        }
        mock_version = MagicMock(return_value=version)
        mock_vault = MagicMock()
        mock_vault.return_value.status_code = 200
        v2_return = {
            "data": {
                "data": {"akey": "avalue"},
                "metadata": {
                    "created_time": "2018-10-23T20:21:55.042755098Z",
                    "destroyed": False,
                    "version": 13,
                    "deletion_time": "",
                },
            }
        }

        mock_vault.return_value.json.return_value = v2_return
        with patch.dict(
            vault.__utils__, {"vault.make_request": mock_vault}
        ), patch.dict(vault.__utils__, {"vault.is_v2": mock_version}):
            vault_return = vault.read_secret("/secret/my/secret", "akey")

        self.assertEqual(vault_return, "avalue")


class VaultDefaultTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for the default argument in the vault module

    NOTE: This test class is crafted such that the vault.make_request call will
    always fail. If you want to add other unit tests, you should put them in a
    separate class.
    """

    def setup_loader_modules(self):
        return {
            vault: {
                "__grains__": {"id": "foo"},
                "__utils__": {
                    "vault.make_request": MagicMock(side_effect=Exception("FAILED")),
                    "vault.is_v2": MagicMock(
                        return_value={
                            "v2": True,
                            "data": "secrets/data/mysecret",
                            "metadata": "secrets/metadata/mysecret",
                            "type": "kv",
                        }
                    ),
                },
            },
        }

    def setUp(self):
        self.path = "foo/bar/"

    def test_read_secret_with_default(self):
        assert vault.read_secret(self.path, default="baz") == "baz"

    def test_read_secret_no_default(self):
        try:
            vault.read_secret(self.path)
        except CommandExecutionError:
            # This is expected
            pass
        else:
            raise Exception("Should have raised a CommandExecutionError")

    def test_list_secrets_with_default(self):
        assert vault.list_secrets(self.path, default=["baz"]) == ["baz"]

    def test_list_secrets_no_default(self):
        try:
            vault.list_secrets(self.path)
        except CommandExecutionError:
            # This is expected
            pass
        else:
            raise Exception("Should have raised a CommandExecutionError")
