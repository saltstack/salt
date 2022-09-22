import pytest

import salt.exceptions
import salt.modules.vault as vault
import salt.utils.vault as vaultutil
from tests.support.mock import patch


@pytest.fixture()
def configure_loader_modules():
    return {
        vault: {
            "__grains__": {"id": "test-minion"},
        }
    }


@pytest.fixture()
def data():
    return {"foo": "bar"}


@pytest.fixture()
def data_list():
    return ["foo"]


@pytest.fixture()
def read_kv(data):
    with patch("salt.utils.vault.read_kv", autospec=True) as read:
        read.return_value = data
        yield read


@pytest.fixture()
def list_kv(data_list):
    with patch("salt.utils.vault.list_kv", autospec=True) as list:
        list.return_value = data_list
        yield list


@pytest.fixture()
def read_kv_not_found(read_kv):
    read_kv.side_effect = vaultutil.VaultNotFoundError
    yield read_kv


@pytest.fixture()
def list_kv_not_found(list_kv):
    list_kv.side_effect = vaultutil.VaultNotFoundError
    yield list_kv


@pytest.mark.parametrize("key,expected", [(None, {"foo": "bar"}), ("foo", "bar")])
def test_read_secret(read_kv, key, expected):
    """
    Ensure read_secret works as expected without and with specified key.
    KV v1/2 is handled in the utils module.
    """
    res = vault.read_secret("some/path", key=key)
    assert res == expected


@pytest.mark.parametrize("func", ["read_secret", "list_secrets"])
def test_read_list_secret_with_default(func, read_kv_not_found, list_kv_not_found):
    """
    Ensure read_secret and list_secrets with defaults set return those
    if the path was not found.
    """
    tgt = getattr(vault, func)
    res = tgt("some/path", default=["f"])
    assert res == ["f"]


@pytest.mark.parametrize("func", ["read_secret", "list_secrets"])
def test_read_list_secret_without_default(func, read_kv_not_found, list_kv_not_found):
    """
    Ensure read_secret and list_secrets without defaults set raise
    a CommandExecutionError when the path is not found.
    """
    tgt = getattr(vault, func)
    with pytest.raises(
        salt.exceptions.CommandExecutionError, match=".*VaultNotFoundError.*"
    ):
        tgt("some/path")
