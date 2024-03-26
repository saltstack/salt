"""
Test case for the vault execution module
"""

import pytest

import salt.modules.vault as vault
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        vault: {
            "__grains__": {"id": "foo"},
            "__utils__": {
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


@pytest.fixture
def path():
    return "foo/bar/"


def test_read_secret_v1():
    """
    Test salt.modules.vault.read_secret function
    """
    version = {"v2": False, "data": None, "metadata": None, "type": None}
    mock_version = MagicMock(return_value=version)
    mock_vault = MagicMock()
    mock_vault.return_value.status_code = 200
    mock_vault.return_value.json.return_value = {"data": {"key": "test"}}
    with patch.dict(vault.__utils__, {"vault.make_request": mock_vault}), patch.dict(
        vault.__utils__, {"vault.is_v2": mock_version}
    ):
        vault_return = vault.read_secret("/secret/my/secret")

    assert vault_return == {"key": "test"}


def test_read_secret_v1_key():
    """
    Test salt.modules.vault.read_secret function specifying key
    """
    version = {"v2": False, "data": None, "metadata": None, "type": None}
    mock_version = MagicMock(return_value=version)
    mock_vault = MagicMock()
    mock_vault.return_value.status_code = 200
    mock_vault.return_value.json.return_value = {"data": {"key": "somevalue"}}
    with patch.dict(vault.__utils__, {"vault.make_request": mock_vault}), patch.dict(
        vault.__utils__, {"vault.is_v2": mock_version}
    ):
        vault_return = vault.read_secret("/secret/my/secret", "key")

    assert vault_return == "somevalue"


def test_read_secret_v2():
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
    with patch.dict(vault.__utils__, {"vault.make_request": mock_vault}), patch.dict(
        vault.__utils__, {"vault.is_v2": mock_version}
    ):
        # Validate metadata returned
        vault_return = vault.read_secret("/secret/my/secret", metadata=True)
        assert "data" in vault_return
        assert "metadata" in vault_return
        # Validate just data returned
        vault_return = vault.read_secret("/secret/my/secret")
        assert "akey" in vault_return


def test_read_secret_v2_key():
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
    with patch.dict(vault.__utils__, {"vault.make_request": mock_vault}), patch.dict(
        vault.__utils__, {"vault.is_v2": mock_version}
    ):
        vault_return = vault.read_secret("/secret/my/secret", "akey")

    assert vault_return == "avalue"


def test_read_secret_with_default(path):
    assert vault.read_secret(path, default="baz") == "baz"


def test_read_secret_no_default(path):
    with pytest.raises(CommandExecutionError):
        vault.read_secret(path)


def test_list_secrets_with_default(path):
    assert vault.list_secrets(path, default=["baz"]) == ["baz"]


def test_list_secrets_no_default(path):
    with pytest.raises(CommandExecutionError):
        vault.list_secrets(path)
