"""
Unit tests for salt.cache.etcd3_cache.

These mock the underlying etcd3-py client (``etcd3_cache.client``) and
assert the module issues the right calls. The single-key storage model
(value and timestamp packed together as
``salt.payload.dumps({"d": data, "t": epoch})``) means a successful
``store`` is one ``client.put`` call, with an optional lease for
``expires=``. Listing uses keys-only range scans.

For end-to-end correctness against a real etcd, see the functional and
integration tests.
"""

import pytest

import salt.cache.etcd3_cache as etcd3_cache
import salt.payload
from salt.exceptions import SaltCacheError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skipif(
        not etcd3_cache.HAS_ETCD,
        reason="Install etcd3-py for this test",
    ),
]


class FakeKv:
    """
    Minimal stand-in for an etcd3 KeyValue. etcd returns keys and values
    as bytes; keys-only scans leave ``value`` empty.
    """

    def __init__(self, key=b"", value=None):
        self.key = key
        self.value = value


def _range(kvs):
    """A fake etcd3-py range response whose ``.kvs`` is ``kvs``."""
    return MagicMock(kvs=kvs)


@pytest.fixture
def configure_loader_modules():
    return {
        etcd3_cache: {
            "__opts__": {
                "etcd.host": "127.0.0.1",
                "etcd.port": 2379,
            }
        }
    }


@pytest.fixture
def client():
    """
    Patch in a mocked, already-initialized etcd3-py client so the cache
    functions skip ``_init_client()`` and operate against a known prefix.
    """
    fake = MagicMock()
    with patch.object(etcd3_cache, "client", fake), patch.object(
        etcd3_cache, "path_prefix", "/salt/cache"
    ):
        yield fake


# --- __virtual__ -------------------------------------------------------------


def test_virtual_returns_name_when_etcd_installed():
    with patch.object(etcd3_cache, "HAS_ETCD", True):
        assert etcd3_cache.__virtual__() == "etcd3"


def test_virtual_returns_false_tuple_when_etcd_missing():
    with patch.object(etcd3_cache, "HAS_ETCD", False):
        result = etcd3_cache.__virtual__()
    assert result[0] is False
    assert "etcd3-py" in result[1]


# --- init_kwargs -------------------------------------------------------------


def test_init_kwargs_is_noop():
    assert etcd3_cache.init_kwargs({"anything": 1}) == {}


# --- _init_client ------------------------------------------------------------


@pytest.mark.parametrize("bad_prefix", ["", "/", "//", "///", None])
def test_init_client_rejects_empty_or_root_path_prefix(bad_prefix):
    with patch.dict(
        etcd3_cache.__opts__, {"etcd.path_prefix": bad_prefix}, clear=True
    ), patch.object(etcd3_cache, "client", None), patch(
        "salt.utils.etcd_util.EtcdClientV3"
    ) as client_cls:
        with pytest.raises(SaltCacheError, match="path_prefix"):
            etcd3_cache._init_client()
    client_cls.assert_not_called()


def test_init_client_normalises_path_prefix_and_strips_outer_slashes():
    with patch.dict(
        etcd3_cache.__opts__, {"etcd.path_prefix": "/my/prefix/"}, clear=True
    ), patch.object(etcd3_cache, "client", None), patch.object(
        etcd3_cache, "path_prefix", None
    ), patch(
        "salt.utils.etcd_util._get_etcd_opts", return_value={}
    ), patch(
        "salt.utils.etcd_util.EtcdClientV3"
    ):
        etcd3_cache._init_client()
        assert etcd3_cache.path_prefix == "/my/prefix"


def test_init_client_forces_require_v2_off_in_resolved_conf():
    """
    The cache is inherently v3; it must force ``etcd.require_v2`` off in
    the resolved conf so EtcdClientV3 constructs (it raises otherwise) and
    the user does not have to set a "require v2" option to use it.
    """
    with patch.dict(
        etcd3_cache.__opts__, {"etcd.path_prefix": "/test_cache"}, clear=True
    ), patch.object(etcd3_cache, "client", None), patch.object(
        etcd3_cache, "path_prefix", None
    ), patch(
        "salt.utils.etcd_util._get_etcd_opts", return_value={"etcd.host": "h"}
    ), patch(
        "salt.utils.etcd_util.EtcdClientV3"
    ) as client_cls:
        etcd3_cache._init_client()
        conf = client_cls.call_args.args[0]
        assert conf["etcd.require_v2"] is False
        assert client_cls.call_args.kwargs.get("has_etcd_opts") is True
        # The module operates on the raw etcd3-py client, not the wrapper.
        assert etcd3_cache.client is client_cls.return_value.client


def test_init_client_resolves_cache_profile():
    with patch.dict(
        etcd3_cache.__opts__,
        {"etcd.path_prefix": "/test_cache", "etcd.cache_profile": "my_profile"},
        clear=True,
    ), patch.object(etcd3_cache, "client", None), patch.object(
        etcd3_cache, "path_prefix", None
    ), patch(
        "salt.utils.etcd_util._get_etcd_opts", return_value={}
    ) as get_opts, patch(
        "salt.utils.etcd_util.EtcdClientV3"
    ):
        etcd3_cache._init_client()
    # Profile is passed through to the shared opts resolver.
    assert get_opts.call_args.args[1] == "my_profile"


def test_init_client_is_idempotent():
    sentinel = MagicMock()
    with patch.object(etcd3_cache, "client", sentinel):
        etcd3_cache._init_client()
        assert etcd3_cache.client is sentinel


# --- _pack / _unpack ---------------------------------------------------------


def test_pack_wraps_data_and_timestamp():
    obj = salt.payload.loads(etcd3_cache._pack({"a": 1}))
    assert obj["d"] == {"a": 1}
    assert isinstance(obj["t"], int)
    assert obj["t"] > 0


def test_unpack_returns_data_and_timestamp():
    data, ts = etcd3_cache._unpack(etcd3_cache._pack({"hello": "world"}))
    assert data == {"hello": "world"}
    assert isinstance(ts, int)


# --- store -------------------------------------------------------------------


def test_store_writes_single_packed_key(client):
    etcd3_cache.store("bank", "key", {"a": 1})

    client.put.assert_called_once()
    call = client.put.call_args
    assert call.args[0] == "/salt/cache/bank/key"
    payload = salt.payload.loads(call.args[1])
    assert payload["d"] == {"a": 1}
    assert isinstance(payload["t"], int)
    assert "lease" not in call.kwargs


def test_store_with_expires_attaches_lease(client):
    fake_lease = MagicMock()
    fake_lease.ID = 0xDEADBEEF
    client.Lease.return_value = fake_lease

    etcd3_cache.store("tokens", "abc", {"u": "alice"}, expires=3600)

    client.Lease.assert_called_once_with(ttl=3600)
    fake_lease.grant.assert_called_once()
    put_call = client.put.call_args
    assert put_call.args[0] == "/salt/cache/tokens/abc"
    assert put_call.kwargs.get("lease") == 0xDEADBEEF


@pytest.mark.parametrize("falsy_expires", [None, 0, False, -1])
def test_store_non_positive_expires_does_not_create_lease(client, falsy_expires):
    etcd3_cache.store("bank", "key", "v", expires=falsy_expires)
    client.Lease.assert_not_called()
    assert "lease" not in client.put.call_args.kwargs


def test_store_handles_complex_serializable_types(client):
    data = {"int": 42, "list": [1, 2, 3], "nested": {"a": "b"}, "bytes": b"\x00\xff"}
    etcd3_cache.store("bank", "key", data)
    payload = salt.payload.loads(client.put.call_args.args[1])
    assert payload["d"] == data


def test_store_nested_bank_path(client):
    etcd3_cache.store("minions/node-a", "data", {"x": 1})
    assert client.put.call_args.args[0] == "/salt/cache/minions/node-a/data"


def test_store_error_wraps_as_saltcacheerror(client):
    client.put.side_effect = Exception("boom")
    with pytest.raises(SaltCacheError, match="error writing key"):
        etcd3_cache.store("bank", "key", "v")


# --- fetch -------------------------------------------------------------------


def test_fetch_returns_unwrapped_data(client):
    payload = etcd3_cache._pack({"a": 1, "b": [1, 2]})
    client.range.return_value = _range([FakeKv(value=payload)])
    assert etcd3_cache.fetch("bank", "key") == {"a": 1, "b": [1, 2]}


def test_fetch_uses_value_key_path(client):
    client.range.return_value = _range(None)
    etcd3_cache.fetch("bank", "key")
    assert client.range.call_args.args[0] == "/salt/cache/bank/key"


def test_fetch_miss_returns_empty_dict(client):
    client.range.return_value = _range(None)
    assert etcd3_cache.fetch("bank", "key") == {}


def test_fetch_error_wraps_as_saltcacheerror(client):
    client.range.side_effect = Exception("boom")
    with pytest.raises(SaltCacheError, match="error reading key"):
        etcd3_cache.fetch("bank", "key")


# --- flush -------------------------------------------------------------------


def test_flush_key_deletes_single_key(client):
    assert etcd3_cache.flush("bank", "key") is True
    client.delete_range.assert_called_once_with("/salt/cache/bank/key")


def test_flush_bank_uses_prefix_range_delete(client):
    assert etcd3_cache.flush("bank", None) is True
    client.delete_range.assert_called_once_with("/salt/cache/bank/", prefix=True)


def test_flush_bank_defaults_to_full_bank(client):
    assert etcd3_cache.flush("bank") is True
    client.delete_range.assert_called_once_with("/salt/cache/bank/", prefix=True)


def test_flush_returns_true_even_when_nothing_existed(client):
    assert etcd3_cache.flush("nonexistent", "key") is True
    assert etcd3_cache.flush("nonexistent", None) is True


def test_flush_error_wraps_as_saltcacheerror(client):
    client.delete_range.side_effect = Exception("boom")
    with pytest.raises(SaltCacheError, match="error flushing"):
        etcd3_cache.flush("bank", "key")


# --- ls ----------------------------------------------------------------------


def test_ls_returns_direct_keys(client):
    client.range.return_value = _range(
        [
            FakeKv(key=b"/salt/cache/bank/minion1"),
            FakeKv(key=b"/salt/cache/bank/minion2"),
        ]
    )
    assert sorted(etcd3_cache.ls("bank")) == ["minion1", "minion2"]


def test_ls_returns_immediate_sub_bank_names(client):
    """
    bank="minions" with data at minions/m1/data and minions/m2/data should
    yield the minion IDs -- what salt.utils.master._get_cached_minion_data
    and similar callers expect.
    """
    client.range.return_value = _range(
        [
            FakeKv(key=b"/salt/cache/minions/m1/data"),
            FakeKv(key=b"/salt/cache/minions/m2/data"),
        ]
    )
    assert sorted(etcd3_cache.ls("minions")) == ["m1", "m2"]


def test_ls_dedupes_sub_bank_names_across_descendants(client):
    client.range.return_value = _range(
        [
            FakeKv(key=b"/salt/cache/bank/sub/k1"),
            FakeKv(key=b"/salt/cache/bank/sub/k2"),
            FakeKv(key=b"/salt/cache/bank/sub/deeper/k3"),
        ]
    )
    assert etcd3_cache.ls("bank") == ["sub"]


def test_ls_returns_direct_keys_alongside_sub_banks(client):
    client.range.return_value = _range(
        [
            FakeKv(key=b"/salt/cache/bank/direct1"),
            FakeKv(key=b"/salt/cache/bank/direct2"),
            FakeKv(key=b"/salt/cache/bank/sub/nested"),
        ]
    )
    assert sorted(etcd3_cache.ls("bank")) == ["direct1", "direct2", "sub"]


def test_ls_uses_keys_only_prefix_scan_with_trailing_slash(client):
    client.range.return_value = _range(None)
    etcd3_cache.ls("bank")
    call = client.range.call_args
    assert call.args[0] == "/salt/cache/bank/"
    assert call.kwargs.get("prefix") is True
    assert call.kwargs.get("keys_only") is True


def test_ls_empty_bank_returns_top_level_banks(client):
    """
    ``cache.list("")`` enumerates top-level banks (salt.runners.cache.migrate).
    """
    client.range.return_value = _range(
        [
            FakeKv(key=b"/salt/cache/grains/minion-1"),
            FakeKv(key=b"/salt/cache/grains/minion-2"),
            FakeKv(key=b"/salt/cache/mine/minion-1"),
            FakeKv(key=b"/salt/cache/tokens/abcdef"),
        ]
    )
    assert sorted(etcd3_cache.ls("")) == ["grains", "mine", "tokens"]


def test_ls_empty_bank_scans_root_prefix_without_double_slash(client):
    client.range.return_value = _range(None)
    etcd3_cache.ls("")
    assert client.range.call_args.args[0] == "/salt/cache/"


def test_ls_missing_returns_empty(client):
    client.range.return_value = _range(None)
    assert etcd3_cache.ls("bank") == []


def test_ls_error_wraps_as_saltcacheerror(client):
    client.range.side_effect = Exception("boom")
    with pytest.raises(SaltCacheError, match="error listing"):
        etcd3_cache.ls("bank")


# --- contains ----------------------------------------------------------------


def test_contains_existing_key(client):
    client.range.return_value = _range([FakeKv(key=b"/salt/cache/bank/key")])
    assert etcd3_cache.contains("bank", "key") is True


def test_contains_missing_key(client):
    client.range.return_value = _range(None)
    assert etcd3_cache.contains("bank", "key") is False


def test_contains_key_uses_exact_keys_only_limited_read(client):
    client.range.return_value = _range(None)
    etcd3_cache.contains("bank", "key")
    call = client.range.call_args
    assert call.args[0] == "/salt/cache/bank/key"
    assert call.kwargs.get("prefix") in (None, False)
    assert call.kwargs.get("keys_only") is True
    assert call.kwargs.get("limit") == 1


def test_contains_bank_with_only_sub_bank_entries(client):
    client.range.return_value = _range([FakeKv(key=b"/salt/cache/bank/sub/nested")])
    assert etcd3_cache.contains("bank", None) is True


def test_contains_missing_bank(client):
    client.range.return_value = _range(None)
    assert etcd3_cache.contains("bank", None) is False


def test_contains_bank_uses_keys_only_limited_prefix_scan(client):
    client.range.return_value = _range(None)
    etcd3_cache.contains("bank", None)
    call = client.range.call_args
    assert call.args[0] == "/salt/cache/bank/"
    assert call.kwargs.get("prefix") is True
    assert call.kwargs.get("keys_only") is True
    assert call.kwargs.get("limit") == 1


def test_contains_error_wraps_as_saltcacheerror(client):
    client.range.side_effect = Exception("boom")
    with pytest.raises(SaltCacheError, match="error checking"):
        etcd3_cache.contains("bank", "key")


# --- updated -----------------------------------------------------------------


def test_updated_returns_packed_timestamp(client):
    payload = etcd3_cache._pack({"some": "data"})
    client.range.return_value = _range([FakeKv(value=payload)])
    ts = etcd3_cache.updated("bank", "key")
    assert isinstance(ts, int)
    assert ts > 0


def test_updated_reads_value_key_not_sibling(client):
    client.range.return_value = _range(None)
    etcd3_cache.updated("bank", "key")
    assert client.range.call_args.args[0] == "/salt/cache/bank/key"


def test_updated_returns_none_when_absent(client):
    client.range.return_value = _range(None)
    assert etcd3_cache.updated("bank", "key") is None


def test_updated_error_wraps_as_saltcacheerror(client):
    client.range.side_effect = Exception("boom")
    with pytest.raises(SaltCacheError, match="error reading timestamp"):
        etcd3_cache.updated("bank", "key")
