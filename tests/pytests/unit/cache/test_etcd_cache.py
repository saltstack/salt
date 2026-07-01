"""
Unit tests for salt.cache.etcd_cache
"""

import base64

import pytest

import salt.cache.etcd_cache as etcd_cache
import salt.payload
from salt.exceptions import SaltCacheError
from tests.support.mock import MagicMock, patch

etcd = pytest.importorskip("etcd")

pytestmark = [
    pytest.mark.skipif(
        not etcd_cache.HAS_ETCD, reason="Install python-etcd for this test"
    ),
]


class FakeResult:
    """
    Minimal stand-in for etcd.EtcdResult.
    """

    def __init__(self, key=None, value=None, dir=False, children=None):
        self.key = key
        self.value = value
        self.dir = dir
        self._children = children if children is not None else []

    @property
    def children(self):
        return iter(self._children)


@pytest.fixture
def configure_loader_modules():
    return {
        etcd_cache: {
            "__opts__": {
                "etcd.host": "127.0.0.1",
                "etcd.port": 2379,
            }
        }
    }


@pytest.fixture
def client():
    """
    Patch in a mocked, already-initialized client so the cache functions skip
    _init_client() and operate against a known path_prefix.
    """
    fake = MagicMock()
    with patch.object(etcd_cache, "client", fake), patch.object(
        etcd_cache, "path_prefix", "/salt/cache"
    ), patch.object(etcd_cache, "_tstamp_suffix", ".tstamp"):
        yield fake


# --- __virtual__ -------------------------------------------------------------


def test_virtual_available():
    assert etcd_cache.__virtual__() == "etcd"


def test_virtual_missing_etcd():
    with patch.object(etcd_cache, "HAS_ETCD", False):
        ret = etcd_cache.__virtual__()
    assert ret[0] is False
    assert "python-etcd" in ret[1]


# --- _init_client ------------------------------------------------------------


def test_init_client_noop_when_already_initialized(client):
    with patch("etcd.Client") as etcd_client:
        etcd_cache._init_client()
    etcd_client.assert_not_called()


def test_init_client_initializes_when_unset():
    fake = MagicMock()
    with patch.object(etcd_cache, "client", None), patch.object(
        etcd_cache, "path_prefix", None
    ):
        with patch("etcd.Client", return_value=fake) as etcd_client:
            etcd_cache._init_client()
    etcd_client.assert_called_once()
    fake.read.assert_called_once()


def test_init_client_creates_missing_root_dir():
    fake = MagicMock()
    fake.read.side_effect = etcd.EtcdKeyNotFound
    with patch.object(etcd_cache, "client", None), patch.object(
        etcd_cache, "path_prefix", None
    ):
        with patch("etcd.Client", return_value=fake):
            etcd_cache._init_client()
    fake.write.assert_called_once()
    assert fake.write.call_args.kwargs.get("dir") is True


# --- store -------------------------------------------------------------------


def test_store(client):
    etcd_cache.store("bank", "key", {"a": 1})
    assert client.write.call_count == 2
    assert client.write.call_args_list[0].args[0] == "/salt/cache/bank/key"
    assert client.write.call_args_list[1].args[0] == "/salt/cache/bank/key.tstamp"


def test_store_roundtrip_encoding(client):
    etcd_cache.store("bank", "key", {"a": 1})
    stored = client.write.call_args_list[0].args[1]
    assert salt.payload.loads(base64.b64decode(stored)) == {"a": 1}


def test_store_error(client):
    client.write.side_effect = Exception("boom")
    with pytest.raises(SaltCacheError):
        etcd_cache.store("bank", "key", {"a": 1})


# --- fetch -------------------------------------------------------------------


def test_fetch(client):
    data = {"a": 1}
    encoded = base64.b64encode(salt.payload.dumps(data))
    client.read.return_value = FakeResult(value=encoded)
    assert etcd_cache.fetch("bank", "key") == data


def test_fetch_missing_returns_empty(client):
    client.read.side_effect = etcd.EtcdKeyNotFound
    assert etcd_cache.fetch("bank", "key") == {}


def test_fetch_error(client):
    client.read.side_effect = Exception("boom")
    with pytest.raises(SaltCacheError):
        etcd_cache.fetch("bank", "key")


# --- flush -------------------------------------------------------------------


def test_flush_key(client):
    etcd_cache.flush("bank", "key")
    client.delete.assert_any_call("/salt/cache/bank/key.tstamp")
    client.delete.assert_any_call("/salt/cache/bank/key", recursive=True)


def test_flush_bank(client):
    etcd_cache.flush("bank")
    client.delete.assert_called_once_with("/salt/cache/bank", recursive=True)


def test_flush_missing_is_noop(client):
    client.read.side_effect = etcd.EtcdKeyNotFound
    etcd_cache.flush("bank", "key")
    client.delete.assert_not_called()


def test_flush_error(client):
    client.delete.side_effect = Exception("boom")
    with pytest.raises(SaltCacheError):
        etcd_cache.flush("bank", "key")


# --- _walk -------------------------------------------------------------------


def test_walk_leaf_key(client):
    leaf = FakeResult(key="/salt/cache/bank/minion", dir=False)
    assert etcd_cache._walk(leaf) == ["minion"]


def test_walk_skips_timestamp_keys(client):
    leaf = FakeResult(key="/salt/cache/bank/minion.tstamp", dir=False)
    assert etcd_cache._walk(leaf) == []


def test_walk_directory(client):
    minion = FakeResult(key="/salt/cache/bank/minion", dir=False)
    tstamp = FakeResult(key="/salt/cache/bank/minion.tstamp", dir=False)
    client.read.return_value = FakeResult(
        key="/salt/cache/bank", dir=True, children=[minion, tstamp]
    )
    bank = FakeResult(key="/salt/cache/bank", dir=True)
    assert etcd_cache._walk(bank) == ["minion"]


def test_walk_empty_folder_does_not_recurse(client):
    """
    Regression test for #57377: an empty etcd folder lists itself as its only
    child, which previously caused _walk to recurse until it hit the recursion
    limit and raised a SaltCacheError.
    """
    self_ref = FakeResult(key="/salt/cache/bank", dir=True)
    client.read.return_value = FakeResult(
        key="/salt/cache/bank", dir=True, children=[self_ref]
    )
    bank = FakeResult(key="/salt/cache/bank", dir=True)
    assert etcd_cache._walk(bank) == []


# --- ls ----------------------------------------------------------------------


def test_ls(client):
    minion = FakeResult(key="/salt/cache/bank/minion", dir=False)
    client.read.return_value = FakeResult(
        key="/salt/cache/bank", dir=True, children=[minion]
    )
    assert etcd_cache.ls("bank") == ["minion"]


def test_ls_missing_returns_empty(client):
    client.read.side_effect = etcd.EtcdKeyNotFound
    assert etcd_cache.ls("bank") == []


def test_ls_error(client):
    client.read.side_effect = Exception("boom")
    with pytest.raises(SaltCacheError):
        etcd_cache.ls("bank")


# --- contains ----------------------------------------------------------------


def test_contains_existing_key(client):
    client.read.return_value = FakeResult(dir=False)
    assert etcd_cache.contains("bank", "key") is True


def test_contains_key_that_is_a_dir(client):
    client.read.return_value = FakeResult(dir=True)
    assert etcd_cache.contains("bank", "key") is False


def test_contains_bank(client):
    client.read.return_value = FakeResult(dir=True)
    assert etcd_cache.contains("bank", None) is True


def test_contains_missing(client):
    client.read.side_effect = etcd.EtcdKeyNotFound
    assert etcd_cache.contains("bank", "key") is False


# --- updated -----------------------------------------------------------------


def test_updated(client):
    client.read.return_value = FakeResult(value="1700000000")
    assert etcd_cache.updated("bank", "key") == 1700000000


def test_updated_missing(client):
    client.read.side_effect = etcd.EtcdKeyNotFound
    assert etcd_cache.updated("bank", "key") is None


def test_updated_error(client):
    client.read.side_effect = Exception("boom")
    with pytest.raises(SaltCacheError):
        etcd_cache.updated("bank", "key")
