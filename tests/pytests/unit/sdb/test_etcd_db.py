"""
Test cases for salt.sdb.etcd_db
"""

import pytest

import salt.sdb.etcd_db as etcd_db
import salt.utils.etcd_util
from salt.exceptions import CommandExecutionError
from tests.support.mock import patch


@pytest.fixture
def get_conn():
    with patch("salt.utils.etcd_util.get_conn") as get_conn:
        yield get_conn


@pytest.fixture
def client(get_conn):
    return get_conn.return_value


def test_virtual():
    with patch.object(salt.utils.etcd_util, "HAS_ETCD_V3", True):
        assert etcd_db.__virtual__() == "etcd"
    with patch.object(salt.utils.etcd_util, "HAS_ETCD_V3", False):
        assert etcd_db.__virtual__()[0] is False


def test_set(get_conn, client):
    client.set.return_value = "salt"
    profile = {"driver": "etcd", "etcd.port": 2379}
    assert etcd_db.set_("sdstack", "salt", profile=profile) == "salt"
    get_conn.assert_called_once_with(profile)
    client.set.assert_called_once_with("sdstack", "salt")


def test_get(client):
    client.get.return_value = "salt"
    assert etcd_db.get("sdstack", profile={}) == "salt"
    client.get.assert_called_once_with("sdstack")

    client.get.return_value = None
    assert etcd_db.get("missing", profile={}) is None


def test_delete(client):
    client.delete.return_value = True
    assert etcd_db.delete("sdstack", profile={}) is True
    client.delete.assert_called_once_with("sdstack")

    client.delete.return_value = None
    assert etcd_db.delete("missing", profile={}) is False


def test_errors_raise(client):
    client.get.side_effect = CommandExecutionError("etcd3: cannot read sdstack")
    with pytest.raises(CommandExecutionError):
        etcd_db.get("sdstack", profile={})


def test_missing_profile_uses_empty_config(get_conn):
    etcd_db.get("sdstack")
    get_conn.assert_called_once_with({})
