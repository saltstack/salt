"""
Test cases for salt.returners.etcd_return
"""

import pytest

import salt.returners.etcd_return as etcd_return
import salt.utils.etcd_util
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def configure_loader_modules():
    return {
        etcd_return: {
            "__opts__": {
                "etcd.returner": "default_profile",
                "etcd.returner_root": "/salt/return/",
                "etcd.ttl": 30,
                "write_profile": {"etcd.ttl": 5},
            }
        }
    }


@pytest.fixture
def client():
    client = MagicMock(encode_values=True)
    client.get.return_value = None
    with patch("salt.utils.etcd_util.get_conn", return_value=client) as get_conn:
        client.get_conn = get_conn
        yield client


def test_virtual():
    with patch.object(salt.utils.etcd_util, "HAS_ETCD_V3", True):
        assert etcd_return.__virtual__() == "etcd"
    with patch.object(salt.utils.etcd_util, "HAS_ETCD_V3", False):
        assert etcd_return.__virtual__()[0] is False


def test_returner_writes_one_key_per_return(client):
    etcd_return.returner(
        {"id": "minion1", "jid": "123", "fun": "test.ping", "return": True, "x": 1}
    )
    client.get_conn.assert_called_with(etcd_return.__opts__, "default_profile")
    assert client.set.call_args_list == [
        call("/salt/return/minions/minion1", "123", ttl=30),
        call(
            "/salt/return/jobs/123/minion1",
            {"fun": "test.ping", "return": True},
            ttl=30,
        ),
    ]


def test_write_profile_ttl(client):
    with patch.dict(
        etcd_return.__opts__, {"etcd.returner_write_profile": "write_profile"}
    ):
        etcd_return.returner({"id": "minion1", "jid": "123", "return": True})
    client.get_conn.assert_called_with(etcd_return.__opts__, "write_profile")
    assert all(c.kwargs["ttl"] == 5 for c in client.set.call_args_list)


def test_read_profile(client):
    with patch.dict(
        etcd_return.__opts__, {"etcd.returner_read_profile": "read_profile"}
    ):
        assert etcd_return.get_load("123") == {}
    client.get_conn.assert_called_with(etcd_return.__opts__, "read_profile")


def test_plain_values_are_json(client):
    client.encode_values = False
    etcd_return.returner({"id": "minion1", "jid": "123", "return": {"a": 1}})
    assert client.set.call_args_list[1] == call(
        "/salt/return/jobs/123/minion1", '{"return": {"a": 1}}', ttl=30
    )


def test_prep_jid_keeps_passed_jid(client):
    assert etcd_return.prep_jid(passed_jid="20261103120000123456") == (
        "20261103120000123456"
    )
    client.set.assert_not_called()
