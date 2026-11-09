"""
Integration tests for ``salt.cache.etcd3_cache`` against a real etcd v3
server, covering behaviour the (mocked) unit tests cannot: real
prefix-range semantics, the trailing-slash bank boundary, the single-key
storage model, native lease expiry, and the bank/key patterns used by
in-tree cache callers (auth tokens, pillar, master keys, grains).

A throwaway etcd v3 container is started by the shared
``tests.support.pytest.etcd`` fixtures, so this runs in CI wherever
docker is available. Each test uses a unique ``etcd.path_prefix``.
"""

import time
import uuid

import pytest

import salt.cache.etcd3_cache as etcd3_cache
import salt.payload
from tests.support.pytest.etcd import *  # pylint: disable=wildcard-import,unused-wildcard-import

docker = pytest.importorskip("docker")

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
    pytest.mark.skipif(
        not etcd3_cache.HAS_ETCD,
        reason="etcd3-py is not installed",
    ),
]


@pytest.fixture(scope="module", params=(EtcdVersion.v3,), ids=etcd_version_ids)
def etcd_version(request):  # pylint: disable=function-redefined
    # The etcd3 cache only speaks the v3 API.
    if not HAS_ETCD_V3:
        pytest.skip("No etcd3 library installed")
    return request.param


@pytest.fixture
def opts(etcd_port):
    return {
        "etcd.host": "127.0.0.1",
        "etcd.port": etcd_port,
        "etcd.path_prefix": f"/salt_cache_test_{uuid.uuid4().hex}",
    }


@pytest.fixture
def cache(opts, monkeypatch):
    monkeypatch.setattr(etcd3_cache, "client", None)
    monkeypatch.setattr(etcd3_cache, "path_prefix", None)
    monkeypatch.setattr(etcd3_cache, "__opts__", opts, raising=False)
    # Eagerly initialize so tests that poke ``etcd3_cache.client`` directly
    # (rather than going through store/fetch first) do not depend on test
    # ordering -- isolated runs via ``pytest --lf`` would otherwise see
    # ``client is None``.
    etcd3_cache._init_client()
    yield etcd3_cache
    # Best-effort cleanup of this test's prefix.
    try:
        if etcd3_cache.client is not None and etcd3_cache.path_prefix:
            etcd3_cache.client.delete_range(etcd3_cache.path_prefix + "/", prefix=True)
    except Exception:  # pylint: disable=broad-except
        pass


# --- core round-trip ---------------------------------------------------------


def test_store_then_fetch_roundtrip(cache):
    data = {"minion_id": "minion-1", "grains": {"os": "Ubuntu", "n": 42}}
    cache.store("minions/minion-1", "data", data)
    assert cache.fetch("minions/minion-1", "data") == data


def test_store_overwrites_previous_value(cache):
    cache.store("b", "k", {"v": 1})
    cache.store("b", "k", {"v": 2})
    assert cache.fetch("b", "k") == {"v": 2}


def test_fetch_miss_returns_empty_dict(cache):
    assert cache.fetch("does/not", "exist") == {}


# ``bytes`` is deliberately excluded: ``salt.payload.loads`` calls
# ``decode_embedded_strs`` on the default code path, which converts every
# ``bytes`` value to ``str``. Every salt cache backend that goes through
# ``salt.payload`` (redis, mysql, localfs, ...) inherits this behavior, so
# real cache callers do not store raw bytes. Asserting bytes preservation
# here would be a stricter contract than the rest of ``salt.cache``.
@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "string",
        0,
        -1,
        1.5,
        True,
        False,
        [1, 2, 3],
        {"nested": {"deeply": {"yes": True}}},
        [{"a": 1}, {"b": 2}],
        {"unicode": "héllo wörld 🥗"},
    ],
    ids=lambda v: type(v).__name__ + "=" + repr(v)[:32],
)
def test_store_handles_serializable_types(cache, value):
    cache.store("types", "k", value)
    assert cache.fetch("types", "k") == value


# --- single-key storage model -----------------------------------------------


def test_store_writes_exactly_one_etcd_key_per_entry(cache):
    """
    Confirms the single-key design: ``store`` writes one etcd key per
    cached entry, not a value + sibling-tstamp pair. Regression guard
    if anyone ever reintroduces a companion key.
    """
    cache.store("b", "k", {"v": 1})

    raw = etcd3_cache.client
    # Prefix-scan the bank; only the single value key should exist.
    bank_resp = raw.range(f"{etcd3_cache.path_prefix}/b/", prefix=True)
    assert bank_resp.kvs and len(bank_resp.kvs) == 1
    assert bank_resp.kvs[0].key.decode() == f"{etcd3_cache.path_prefix}/b/k"


def test_stored_value_is_msgpack_wrapped_not_base64(cache):
    """
    On the wire, the value is ``salt.payload.dumps({"d": ..., "t": ...})``
    -- raw bytes, no base64 (v3 takes binary natively).
    """
    cache.store("b", "k", {"v": 1})

    raw = etcd3_cache.client
    kv = raw.range(f"{etcd3_cache.path_prefix}/b/k").kvs[0]
    payload = salt.payload.loads(kv.value)
    assert payload["d"] == {"v": 1}
    assert isinstance(payload["t"], int)


def test_updated_matches_stored_timestamp(cache):
    """
    The timestamp returned by updated() is the same one embedded in the
    stored value -- there's no second source of truth.
    """
    cache.store("b", "k", {"v": 1})
    via_updated = cache.updated("b", "k")

    raw = etcd3_cache.client
    kv = raw.range(f"{etcd3_cache.path_prefix}/b/k").kvs[0]
    via_payload = salt.payload.loads(kv.value)["t"]
    assert via_updated == via_payload


# --- native expiry via etcd v3 leases ----------------------------------------


def test_store_with_expires_attaches_lease(cache):
    """
    ``store(..., expires=N)`` must attach an etcd v3 lease so the key
    is auto-deleted when the TTL elapses.
    """
    cache.store("tokens", "tok1", {"u": "alice"}, expires=3600)

    raw = etcd3_cache.client
    kv = raw.range(f"{etcd3_cache.path_prefix}/tokens/tok1").kvs[0]
    assert kv.lease != 0, "lease should be attached when expires> 0"


def test_store_without_expires_has_no_lease(cache):
    cache.store("bank", "k", "v")
    raw = etcd3_cache.client
    kv = raw.range(f"{etcd3_cache.path_prefix}/bank/k").kvs[0]
    assert kv.lease == 0, "no lease should be attached without expires="


def test_store_with_expires_actually_expires_the_key(cache):
    """
    End-to-end check: a key written with a short TTL is gone from etcd
    after the TTL elapses (no manual flush required).
    """
    import time as _time

    cache.store("ephemeral", "k", "v", expires=2)
    assert cache.fetch("ephemeral", "k") == "v"

    # etcd lease minimum is 1 second; give ourselves slack to avoid
    # flakiness on a loaded test machine.
    _time.sleep(4)

    assert cache.fetch("ephemeral", "k") == {}
    assert cache.contains("ephemeral", "k") is False


# --- listing and containment ------------------------------------------------


def test_ls_returns_direct_keys(cache):
    cache.store("bank1", "k1", "v1")
    cache.store("bank1", "k2", "v2")
    assert sorted(cache.ls("bank1")) == ["k1", "k2"]


def test_ls_returns_immediate_sub_bank_names(cache):
    """
    The reason for the localfs-style semantic: ``ls('minions')`` must
    return the minion IDs, which is what callers iterating
    ``minions/<id>``-style banks need. v2 etcd_cache returned the
    recursive leaves (``['data', 'data', ...]``) and redis_cache
    returned ``[]``; both are wrong for this use case.
    """
    cache.store("minions/m1", "data", {"a": 1})
    cache.store("minions/m2", "data", {"a": 2})
    cache.store("minions/m3", "data", {"a": 3})

    assert sorted(cache.ls("minions")) == ["m1", "m2", "m3"]
    # And the sub-banks themselves still report their direct keys.
    assert cache.ls("minions/m1") == ["data"]
    assert cache.ls("minions/m2") == ["data"]


def test_ls_returns_direct_keys_alongside_sub_banks(cache):
    cache.store("bank", "direct1", "v1")
    cache.store("bank", "direct2", "v2")
    cache.store("bank/sub", "nested", "v3")

    assert sorted(cache.ls("bank")) == ["direct1", "direct2", "sub"]
    assert cache.ls("bank/sub") == ["nested"]


def test_ls_empty_bank_returns_empty_list(cache):
    assert cache.ls("never_stored") == []


def test_ls_trailing_slash_boundary(cache):
    """
    The single most important correctness test for a flat-keyspace port:
    bank "foo" must not pick up data from bank "foobar".
    """
    cache.store("foo", "k", "in_foo")
    cache.store("foobar", "k", "in_foobar")

    assert cache.ls("foo") == ["k"]
    assert cache.ls("foobar") == ["k"]
    assert cache.fetch("foo", "k") == "in_foo"
    assert cache.fetch("foobar", "k") == "in_foobar"


def test_ls_empty_bank_returns_top_level_banks(cache):
    """
    ``cache.list("")`` must enumerate top-level banks. This is the
    semantic that ``salt.runners.cache.migrate`` relies on; if it
    returns ``[]`` the migration silently does nothing.
    """
    cache.store("grains", "minion-1", {"os": "Linux"})
    cache.store("grains", "minion-2", {"os": "Linux"})
    cache.store("mine", "minion-1", {})
    cache.store("tokens", "abcdef", {})

    assert sorted(cache.ls("")) == ["grains", "mine", "tokens"]


def test_contains_specific_key(cache):
    cache.store("bank1", "key1", {"x": 1})
    assert cache.contains("bank1", "key1") is True
    assert cache.contains("bank1", "missing") is False
    assert cache.contains("nonexistent_bank", "key1") is False


def test_contains_bank_with_direct_key(cache):
    cache.store("bank1", "key1", {"x": 1})
    assert cache.contains("bank1", None) is True
    assert cache.contains("nonexistent_bank", None) is False


def test_contains_bank_with_only_sub_banks(cache):
    # localfs-style: a bank that exists only as a parent of sub-banks
    # still counts as "containing" something for the existence check.
    cache.store("minions/m1", "data", {"a": 1})
    assert cache.contains("minions", None) is True
    assert cache.contains("minions/m1", None) is True


def test_contains_bank_boundary(cache):
    cache.store("foobar", "k", "v")
    assert cache.contains("foo", None) is False
    assert cache.contains("foobar", None) is True


# --- timestamps --------------------------------------------------------------


def test_updated_returns_recent_timestamp(cache):
    before = int(time.time())
    cache.store("b", "k", {"d": 1})
    after = int(time.time())

    ts = cache.updated("b", "k")
    assert ts is not None
    assert before <= ts <= after


def test_updated_returns_none_when_absent(cache):
    assert cache.updated("b", "never_stored") is None


def test_overwrite_updates_timestamp(cache):
    cache.store("b", "k", "v1")
    first_ts = cache.updated("b", "k")

    time.sleep(1.1)

    cache.store("b", "k", "v2")
    second_ts = cache.updated("b", "k")

    assert second_ts > first_ts
    assert cache.fetch("b", "k") == "v2"


# --- flushing ----------------------------------------------------------------


def test_flush_key_removes_entry(cache):
    cache.store("b", "k", {"d": 1})
    assert cache.fetch("b", "k") == {"d": 1}
    assert cache.updated("b", "k") is not None

    assert cache.flush("b", "k") is True
    assert cache.fetch("b", "k") == {}
    assert cache.updated("b", "k") is None


def test_flush_bank_removes_all_entries(cache):
    cache.store("b", "k1", "v1")
    cache.store("b", "k2", "v2")
    assert sorted(cache.ls("b")) == ["k1", "k2"]

    assert cache.flush("b") is True
    assert cache.ls("b") == []
    assert cache.contains("b", None) is False


def test_flush_bank_does_not_affect_sibling_banks(cache):
    cache.store("foo", "k", "in_foo")
    cache.store("foobar", "k", "in_foobar")

    cache.flush("foo")

    assert cache.fetch("foo", "k") == {}
    assert cache.fetch("foobar", "k") == "in_foobar"


def test_flush_nonexistent_bank_returns_true(cache):
    # A flush of a bank that never existed is a successful no-op.
    # We return True to match redis_cache/localfs so callers like
    # salt.auth.del_token surface a consistent value regardless of
    # whether the entry was actually present.
    assert cache.flush("never_existed") is True


def test_flush_nonexistent_key_returns_true(cache):
    assert cache.flush("never_existed", "k") is True


# --- realistic Salt usage ----------------------------------------------------


def test_minion_data_pattern(cache):
    """
    Mirrors how ``salt.utils.minions`` uses the cache:
    cbank=``minions/<id>``, ckey=``data``. The key correctness check
    here is ``ls('minions')`` returning the minion IDs -- this is what
    callers iterating cached minions need, and what v2 etcd_cache fails
    to deliver.
    """
    minion_ids = [f"minion-{i}" for i in range(5)]

    for mid in minion_ids:
        cache.store(
            f"minions/{mid}",
            "data",
            {"grains": {"id": mid, "os": "Linux"}},
        )

    # ls('minions') must return the minion IDs (immediate sub-banks).
    assert sorted(cache.ls("minions")) == sorted(minion_ids)

    for mid in minion_ids:
        got = cache.fetch(f"minions/{mid}", "data")
        assert got["grains"]["id"] == mid

    for mid in minion_ids:
        assert cache.contains(f"minions/{mid}", None) is True
    # The parent bank exists as long as any sub-bank does.
    assert cache.contains("minions", None) is True

    cache.flush(f"minions/{minion_ids[0]}")
    assert cache.fetch(f"minions/{minion_ids[0]}", "data") == {}
    # The flushed minion drops out of the listing.
    assert sorted(cache.ls("minions")) == sorted(minion_ids[1:])
    for mid in minion_ids[1:]:
        assert cache.fetch(f"minions/{mid}", "data")["grains"]["id"] == mid


# --- shared-cluster co-tenancy -----------------------------------------------


def test_flush_does_not_touch_keys_outside_path_prefix(cache):
    """
    Real-world deployment safety check: this cache is expected to be
    pointed at etcd clusters shared with Patroni, Kubernetes, etc.
    A flush() call must never delete keys outside the configured
    ``etcd.path_prefix``, no matter what bank name is passed.
    """
    # Plant some "foreign tenant" data alongside ours, simulating
    # Patroni-style keys under a sibling prefix.
    raw = etcd3_cache.client
    foreign_prefix = "/service/test-patroni"
    foreign_keys = [
        f"{foreign_prefix}/leader",
        f"{foreign_prefix}/members/node-1",
        f"{foreign_prefix}/config",
    ]
    try:
        for k in foreign_keys:
            raw.put(k, b"foreign-data")

        # Sanity: foreign keys are there.
        for k in foreign_keys:
            assert raw.range(k).kvs, f"foreign key {k} did not land"

        # Store something in our cache and then flush aggressively.
        cache.store("bank1", "k1", "v1")
        cache.store("bank2", "k2", "v2")

        cache.flush("bank1")
        cache.flush("bank2")
        # Even a flush with a bank name that overlaps the foreign
        # tenant's path component must not reach the foreign tenant.
        cache.flush("service")  # not a real bank; would only hit our prefix
        cache.flush("service/test-patroni")

        # Foreign keys must still be intact.
        for k in foreign_keys:
            resp = raw.range(k)
            assert resp.kvs, f"flush() reached foreign key {k}"
            assert resp.kvs[0].value == b"foreign-data"
    finally:
        # Clean up the foreign keys regardless of test outcome.
        try:
            raw.delete_range(foreign_prefix + "/", prefix=True)
        except Exception:  # pylint: disable=broad-except
            pass


# --- direct cache users (auth, pillar, channel, key, etc.) -------------------
#
# These tests exercise the actual bank/key patterns used by in-tree
# modules that call salt.cache.Cache directly, not via the minion data
# cache contract. The goal is to confirm the driver supports these
# patterns naturally, without ``etcd``-specific contortions.


def test_auth_token_pattern(cache):
    """
    ``salt.auth`` stores tokens at ``tokens/<token>``. The ``Cache``
    wrapper handles ``expires=`` automatically for drivers that don't
    accept it natively, so we don't need to test that here; we only
    confirm the bank/key shape works.
    """
    cache.store("tokens", "deadbeef" * 8, {"name": "alice", "perms": ["*"]})
    cache.store("tokens", "cafebabe" * 8, {"name": "bob", "perms": ["test.*"]})

    assert sorted(cache.ls("tokens")) == sorted(["deadbeef" * 8, "cafebabe" * 8])
    assert cache.fetch("tokens", "deadbeef" * 8)["name"] == "alice"
    assert cache.contains("tokens", "cafebabe" * 8) is True


def test_pillar_pattern(cache):
    """
    ``salt.pillar`` stores at ``pillar/<pillar_key>``. Pillar data can
    be large; this test uses a modest payload but exercises the shape.
    """
    pillar_data = {
        "users": {f"user{i}": {"uid": 1000 + i} for i in range(50)},
        "services": ["nginx", "postgres", "redis"],
    }
    cache.store("pillar", "minion-1:base", pillar_data)
    assert cache.fetch("pillar", "minion-1:base") == pillar_data

    cache.flush("pillar", "minion-1:base")
    assert cache.fetch("pillar", "minion-1:base") == {}


def test_master_keys_pattern(cache):
    """
    ``salt.crypt`` and ``salt.key`` store cluster master keys under
    ``master_keys/<filename>``, where filenames can contain dots
    (e.g. ``master.pem``, ``master.pub``, ``<id>.pem``).
    """
    cache.store("master_keys", "master.pem", b"-----BEGIN PRIVATE KEY-----")
    cache.store("master_keys", "master.pub", b"-----BEGIN PUBLIC KEY-----")
    cache.store("master_keys", "peer-id.pub", b"-----BEGIN PUBLIC KEY-----")

    assert cache.contains("master_keys", "master.pem") is True
    assert sorted(cache.ls("master_keys")) == sorted(
        ["master.pem", "master.pub", "peer-id.pub"]
    )


def test_grains_iteration_pattern(cache):
    """
    ``salt.utils.minions`` and ``salt.utils.master`` enumerate cached
    minions via ``cache.list("grains")`` and then ``cache.fetch("grains",
    minion_id)``. This is the dominant in-tree pattern -- flat keys
    under a bank, not nested sub-banks.
    """
    minion_ids = [f"node-{i}.example.com" for i in range(5)]
    for mid in minion_ids:
        cache.store("grains", mid, {"id": mid, "os": "Debian"})

    listed = cache.ls("grains")
    assert sorted(listed) == sorted(minion_ids)
    for mid in listed:
        grains = cache.fetch("grains", mid)
        assert grains["id"] == mid


def test_spm_dot_bank_pattern(cache):
    """
    ``salt.spm`` uses ``cache.store(".", repo, metadata)``. The bank
    being a single ``.`` is unusual but legitimate; the driver must
    treat it as an opaque path component.
    """
    cache.store(".", "myrepo", {"packages": ["pkg1", "pkg2"]})
    cache.store(".", "otherrepo", {"packages": ["pkg3"]})

    assert sorted(cache.ls(".")) == ["myrepo", "otherrepo"]
    assert cache.fetch(".", "myrepo")["packages"] == ["pkg1", "pkg2"]
    assert cache.updated(".", "myrepo") is not None


def test_migration_runner_walk_pattern(cache):
    """
    ``salt.runners.cache.migrate`` walks the cache via:

        for bank in cache.list(""):
            for name in cache.list(bank):
                if cache.contains(bank, name):
                    # name is a value key -- fetch and copy
                else:
                    # name is a sub-bank -- recurse

    Confirm the discriminator works on our driver: ``contains(bank,
    name)`` is True for direct value keys and False for sub-bank names.
    """
    # Mix of flat-bank and nested-bank patterns, like a real master.
    cache.store("grains", "node-a", {"os": "Linux"})
    cache.store("grains", "node-b", {"os": "Linux"})
    cache.store("tokens", "tok1", {"u": "alice"})
    cache.store("minions/node-a", "data", {"mine": {}})

    top_level = sorted(cache.ls(""))
    assert top_level == ["grains", "minions", "tokens"]

    # Under "grains", every listed name is a value key.
    for name in cache.ls("grains"):
        assert (
            cache.contains("grains", name) is True
        ), f"grains/{name} should be a value key"

    # Under "minions", the listed name ("node-a") is a sub-bank, not
    # a value key. The migrator relies on this distinction to recurse.
    for name in cache.ls("minions"):
        assert (
            cache.contains("minions", name) is False
        ), f"minions/{name} should be a sub-bank, not a value key"
        # The sub-bank itself has the value key.
        sub = f"minions/{name}"
        assert cache.contains(sub, "data") is True
