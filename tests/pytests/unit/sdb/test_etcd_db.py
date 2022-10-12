"""
Test case for the etcd SDB module
"""

import logging

import pytest

import salt.sdb.etcd_db as etcd_db
import salt.utils.etcd_util as etcd_util
from tests.support.mock import MagicMock, create_autospec, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {
        etcd_db: {
            "__opts__": {
                "myetcd": {
                    "url": "http://127.0.0.1",
                    "auth": {"token": "test", "method": "token"},
                }
            }
        }
    }


@pytest.fixture
def instance():
    return create_autospec(etcd_util.EtcdBase)


@pytest.fixture
def etcd_client_mock(instance):
    mocked_client = MagicMock()
    mocked_client.return_value = instance
    return mocked_client


def test_set(etcd_client_mock, instance):
    """
    Test salt.sdb.etcd_db.set function
    """
    with patch("salt.sdb.etcd_db._get_conn", etcd_client_mock):
        instance.get.return_value = "super awesome"

        assert (
            etcd_db.set_("sdb://myetcd/path/to/foo/bar", "super awesome")
            == "super awesome"
        )
        instance.set.assert_called_with("sdb://myetcd/path/to/foo/bar", "super awesome")
        instance.get.assert_called_with("sdb://myetcd/path/to/foo/bar")

        assert (
            etcd_db.set_(
                "sdb://myetcd/path/to/foo/bar", "super awesome", service="Pablo"
            )
            == "super awesome"
        )
        instance.set.assert_called_with("sdb://myetcd/path/to/foo/bar", "super awesome")
        instance.get.assert_called_with("sdb://myetcd/path/to/foo/bar")

        assert (
            etcd_db.set_(
                "sdb://myetcd/path/to/foo/bar", "super awesome", profile="Picasso"
            )
            == "super awesome"
        )
        instance.set.assert_called_with("sdb://myetcd/path/to/foo/bar", "super awesome")
        instance.get.assert_called_with("sdb://myetcd/path/to/foo/bar")

        instance.get.side_effect = Exception
        pytest.raises(Exception, etcd_db.set_, "bad key", "bad value")


def test_get(etcd_client_mock, instance):
    """
    Test salt.sdb.etcd_db.get function
    """
    with patch("salt.sdb.etcd_db._get_conn", etcd_client_mock):
        instance.get.return_value = "super awesome"
        assert etcd_db.get("sdb://myetcd/path/to/foo/bar") == "super awesome"
        instance.get.assert_called_with("sdb://myetcd/path/to/foo/bar")

        assert (
            etcd_db.get("sdb://myetcd/path/to/foo/bar", service="salt")
            == "super awesome"
        )
        instance.get.assert_called_with("sdb://myetcd/path/to/foo/bar")

        assert (
            etcd_db.get("sdb://myetcd/path/to/foo/bar", profile="stack")
            == "super awesome"
        )
        instance.get.assert_called_with("sdb://myetcd/path/to/foo/bar")

        instance.get.side_effect = Exception
        pytest.raises(Exception, etcd_db.get, "bad key")


def test_delete(etcd_client_mock, instance):
    """
    Test salt.sdb.etcd_db.delete function
    """
    with patch("salt.sdb.etcd_db._get_conn", etcd_client_mock):
        instance.delete.return_value = True
        assert etcd_db.delete("sdb://myetcd/path/to/foo/bar")
        instance.delete.assert_called_with("sdb://myetcd/path/to/foo/bar")

        assert etcd_db.delete("sdb://myetcd/path/to/foo/bar", service="salt")
        instance.delete.assert_called_with("sdb://myetcd/path/to/foo/bar")

        assert etcd_db.delete("sdb://myetcd/path/to/foo/bar", profile="stack")
        instance.delete.assert_called_with("sdb://myetcd/path/to/foo/bar")

        instance.delete.side_effect = Exception
        assert not etcd_db.delete("sdb://myetcd/path/to/foo/bar")


def test__get_conn(etcd_client_mock):
    """
    Test salt.sdb.etcd_db._get_conn function
    """
    with patch("salt.utils.etcd_util.get_conn", etcd_client_mock):
        conn = etcd_db._get_conn("random profile")

        # Checking for EtcdClient methods since we autospec'd
        assert hasattr(conn, "set")
        assert hasattr(conn, "get")
