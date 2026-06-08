"""
Unit tests for the redis_return returner.

These regression tests cover the bug where `redis.password` was
documented as a configuration option but never actually read from
config nor passed to either the single-server (`redis.StrictRedis`)
or cluster (`StrictRedisCluster`) clients. Operators who set
`redis.password` saw `NOAUTH Authentication required` and silently
lost all returner data.
"""

import pytest

import salt.returners.redis_return as redis_return
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        redis_return: {
            "__opts__": {},
            "__salt__": {},
        }
    }


@pytest.fixture(autouse=True)
def reset_redis_pool_singleton():
    """
    `_get_serv` caches the redis client in a module-global singleton.
    Patching the attribute resets it for the duration of every test
    and restores the original value on teardown -- ``patch.object`` is
    used here rather than direct attribute assignment to satisfy
    Salt's ``unmocked-patch`` lint rule on tests.
    """
    with patch.object(redis_return, "REDIS_POOL", None):
        yield


@pytest.fixture
def patched_redis():
    """
    Replace `redis.StrictRedis` and `StrictRedisCluster` with mocks so we
    can inspect the (host, port, db, password, ...) tuple that
    `_get_serv` constructs. ``create=True`` on the cluster patch covers
    environments where the optional ``rediscluster`` package is not
    installed and the symbol therefore never made it into the module.
    """
    fake_strict_redis = MagicMock(name="StrictRedis")
    fake_redis_cluster = MagicMock(name="StrictRedisCluster")
    fake_redis_module = MagicMock(name="redis_module", StrictRedis=fake_strict_redis)

    # ``create=True`` covers environments where the optional ``redis`` /
    # ``rediscluster`` packages are not installed and the symbols therefore
    # never made it into the module under test.
    with patch.object(
        redis_return, "redis", fake_redis_module, create=True
    ), patch.object(
        redis_return, "StrictRedisCluster", fake_redis_cluster, create=True
    ):
        yield fake_strict_redis, fake_redis_cluster


# ---------------------------------------------------------------------------
# _get_options: password is now read from config
# ---------------------------------------------------------------------------


def test_get_options_includes_password_in_attrs_mapping():
    """
    The ``attrs`` dict passed to ``salt.returners.get_returner_options``
    must contain a ``password`` entry, otherwise the helper has no way
    to surface the configured value to the rest of the module.
    """
    captured = {}

    def fake_get_returner_options(virtualname, ret, attrs, **kwargs):
        captured["attrs"] = attrs
        return {}

    with patch("salt.returners.get_returner_options", fake_get_returner_options), patch(
        "salt.utils.platform.is_proxy", return_value=False
    ):
        redis_return._get_options()

    assert "password" in captured["attrs"], (
        "_get_options never asks get_returner_options for redis.password; "
        "this is the bug"
    )


def test_get_options_proxy_mode_reads_password():
    """
    In proxy mode `_get_options` builds the dict by hand from
    ``__opts__``. The hand-built dict must include ``password`` --
    otherwise proxy minions running this returner never authenticate.
    """
    proxy_opts = {"redis.password": "proxy-secret"}

    with patch.dict(redis_return.__opts__, proxy_opts), patch(
        "salt.utils.platform.is_proxy", return_value=True
    ):
        result = redis_return._get_options()

    assert result.get("password") == "proxy-secret"


def test_get_options_proxy_mode_password_defaults_to_none():
    """
    In proxy mode without any configured password, the resulting dict
    still contains a ``password`` key set to ``None`` so downstream code
    in `_get_serv` does not need to handle a missing key.
    """
    with patch.dict(redis_return.__opts__, {}, clear=True), patch(
        "salt.utils.platform.is_proxy", return_value=True
    ):
        result = redis_return._get_options()

    assert "password" in result
    assert result["password"] is None


# ---------------------------------------------------------------------------
# _get_serv: password reaches the single-server client
# ---------------------------------------------------------------------------


def test_get_serv_passes_password_to_strict_redis(patched_redis):
    """
    Headline regression: when the resolved options dict contains a
    password, `_get_serv` must forward it to `redis.StrictRedis`.
    Before the fix, ``password=`` was simply absent from the
    constructor call.
    """
    fake_strict_redis, _ = patched_redis
    options = {
        "host": "redis.example.com",
        "port": 6379,
        "db": "0",
        "password": "my-secret",
        "unix_socket_path": None,
        "cluster_mode": False,
    }
    with patch.object(redis_return, "_get_options", return_value=options):
        redis_return._get_serv()

    fake_strict_redis.assert_called_once()
    assert fake_strict_redis.call_args.kwargs.get("password") == "my-secret"


def test_get_serv_password_none_keeps_unauthenticated_path(patched_redis):
    """
    With no password configured, `_get_serv` must still pass
    ``password=None`` to StrictRedis. Pins the backwards-compatible
    default so existing unauthenticated deployments keep working.
    """
    fake_strict_redis, _ = patched_redis
    options = {
        "host": "redis.example.com",
        "port": 6379,
        "db": "0",
        "password": None,
        "unix_socket_path": None,
        "cluster_mode": False,
    }
    with patch.object(redis_return, "_get_options", return_value=options):
        redis_return._get_serv()

    fake_strict_redis.assert_called_once()
    assert fake_strict_redis.call_args.kwargs.get("password") is None


# ---------------------------------------------------------------------------
# _get_serv: password reaches the cluster client
# ---------------------------------------------------------------------------


def test_get_serv_passes_password_to_strict_redis_cluster(patched_redis):
    """
    The cluster path also forwards the password. Before the fix, the
    ``StrictRedisCluster`` constructor was called without ``password=``
    too, so cluster-mode operators were equally locked out of any
    auth-protected Redis cluster.
    """
    _, fake_redis_cluster = patched_redis
    options = {
        "cluster_mode": True,
        "startup_nodes": [{"host": "n1", "port": 6379}],
        "skip_full_coverage_check": True,
        "password": "cluster-secret",
    }
    with patch.object(redis_return, "_get_options", return_value=options):
        redis_return._get_serv()

    fake_redis_cluster.assert_called_once()
    assert fake_redis_cluster.call_args.kwargs.get("password") == "cluster-secret"


def test_get_serv_cluster_mode_password_none_keeps_unauthenticated_path(
    patched_redis,
):
    """
    Cluster mode without a configured password must still pass
    ``password=None`` to ``StrictRedisCluster``. Pins backwards
    compatibility for existing unauthenticated cluster deployments.
    """
    _, fake_redis_cluster = patched_redis
    options = {
        "cluster_mode": True,
        "startup_nodes": [{"host": "n1", "port": 6379}],
        "skip_full_coverage_check": True,
        "password": None,
    }
    with patch.object(redis_return, "_get_options", return_value=options):
        redis_return._get_serv()

    fake_redis_cluster.assert_called_once()
    assert fake_redis_cluster.call_args.kwargs.get("password") is None


# ---------------------------------------------------------------------------
# get_jids / clean_old_jobs: SCAN replaces blocking KEYS
# ---------------------------------------------------------------------------


def _serv_with_scan(scan_data, mget_data=None):
    """
    Build a ``serv`` mock whose ``scan_iter(match=...)`` returns the
    keys for a given pattern, plus a ``keys(...)`` that raises -- so
    the test fails loudly if the production code falls back to ``KEYS``.
    """
    serv = MagicMock(name="redis_serv")

    def fake_scan_iter(match=None, **kwargs):
        return iter(scan_data.get(match, []))

    def fake_keys(*args, **kwargs):
        raise AssertionError(
            "production code called serv.keys(...); it must use "
            "scan_iter() instead to avoid blocking the Redis server"
        )

    serv.scan_iter.side_effect = fake_scan_iter
    serv.keys.side_effect = fake_keys
    if mget_data is not None:
        serv.mget.return_value = mget_data
    return serv


def test_get_jids_uses_scan_iter_not_keys():
    """
    Headline regression: ``get_jids`` must walk the keyspace with
    ``SCAN``, not the blocking ``KEYS load:*``.
    """
    serv = _serv_with_scan(
        scan_data={"load:*": ["load:20240101", "load:20240102"]},
        mget_data=[None, None],  # contents don't matter for this test
    )
    with patch.object(redis_return, "_get_serv", return_value=serv):
        redis_return.get_jids()

    # scan_iter was called with the right pattern at least once.
    matches = [call.kwargs.get("match") for call in serv.scan_iter.call_args_list]
    assert "load:*" in matches


def test_get_jids_handles_no_jobs():
    """
    With no ``load:*`` keys in Redis, ``get_jids`` must return an empty
    dict (and must not call ``mget`` with an empty list, which some
    Redis clients reject). Pins the behaviour after the SCAN switch.
    """
    serv = _serv_with_scan(scan_data={"load:*": []})
    with patch.object(redis_return, "_get_serv", return_value=serv):
        result = redis_return.get_jids()

    assert result == {}
    serv.mget.assert_not_called()


def test_clean_old_jobs_uses_scan_iter_not_keys():
    """
    Headline regression: ``clean_old_jobs`` must enumerate both
    ``ret:*`` and ``load:*`` via ``SCAN``. Both calls were blocking
    ``KEYS`` before the fix.
    """
    serv = _serv_with_scan(
        scan_data={
            "ret:*": ["ret:20240101", "ret:20240102"],
            "load:*": ["load:20240102"],  # 20240101 is orphan
        }
    )
    with patch.object(redis_return, "_get_serv", return_value=serv):
        redis_return.clean_old_jobs()

    matches = [call.kwargs.get("match") for call in serv.scan_iter.call_args_list]
    assert "ret:*" in matches
    assert "load:*" in matches


def test_clean_old_jobs_removes_only_orphan_ret_keys():
    """
    End-to-end behaviour after the SCAN switch: ``ret:<jid>`` keys
    whose ``load:<jid>`` counterpart no longer exists must be deleted.
    Active jobs (``ret`` with a matching ``load``) must be left alone.
    """
    serv = _serv_with_scan(
        scan_data={
            "ret:*": ["ret:dead-jid", "ret:alive-jid"],
            "load:*": ["load:alive-jid"],
        }
    )
    with patch.object(redis_return, "_get_serv", return_value=serv):
        redis_return.clean_old_jobs()

    serv.delete.assert_called_once()
    deleted = set(serv.delete.call_args.args)
    assert deleted == {"ret:dead-jid"}


def test_clean_old_jobs_no_orphans_no_delete():
    """No orphan keys -> no delete call. Pins backward compatibility."""
    serv = _serv_with_scan(
        scan_data={
            "ret:*": ["ret:alive"],
            "load:*": ["load:alive"],
        }
    )
    with patch.object(redis_return, "_get_serv", return_value=serv):
        redis_return.clean_old_jobs()

    serv.delete.assert_not_called()


# ---------------------------------------------------------------------------
# returner(): TTL on the {minion}:{fun} last-jid pointer
# ---------------------------------------------------------------------------


def _returner_pipeline_mock(ttl=3600):
    """
    Mock the ``serv.pipeline()`` returned by the returner so each
    call recorded on the pipeline is observable. ``_get_ttl()`` is
    patched to return a deterministic value so the test can match it
    exactly.
    """
    pipeline = MagicMock(name="pipeline")
    serv = MagicMock(name="redis_serv")
    serv.pipeline.return_value = pipeline
    return serv, pipeline


def test_returner_sets_ttl_on_minion_fun_pointer():
    """
    Headline regression: ``<minion>:<fun>`` key must be written with
    ``ex=_get_ttl()`` so it expires on the same schedule as the rest
    of the returner data. Before the fix it was written with no TTL
    and accumulated forever.
    """
    serv, pipeline = _returner_pipeline_mock()
    ret = {"id": "minion-1", "jid": "20240101", "fun": "test.ping"}

    with patch.object(redis_return, "_get_serv", return_value=serv), patch.object(
        redis_return, "_get_ttl", return_value=3600
    ):
        redis_return.returner(ret)

    # Find the set() call that targets the <minion>:<fun> pointer.
    set_calls = [
        call
        for call in pipeline.set.call_args_list
        if call.args and call.args[0] == "minion-1:test.ping"
    ]
    assert len(set_calls) == 1, (
        f"expected exactly one set('minion-1:test.ping', ...); "
        f"got {pipeline.set.call_args_list}"
    )
    set_call = set_calls[0]
    assert set_call.kwargs.get("ex") == 3600, (
        f"<minion>:<fun> pointer must be set with ex=_get_ttl(); "
        f"got kwargs={set_call.kwargs!r}"
    )


def test_returner_still_writes_all_four_keys():
    """
    Sanity: the TTL fix must not change which keys the returner
    writes. The four canonical operations (hset, expire, set, sadd)
    must all still appear on the pipeline.
    """
    serv, pipeline = _returner_pipeline_mock()
    ret = {"id": "minion-1", "jid": "20240101", "fun": "test.ping"}

    with patch.object(redis_return, "_get_serv", return_value=serv), patch.object(
        redis_return, "_get_ttl", return_value=3600
    ):
        redis_return.returner(ret)

    pipeline.hset.assert_called_once()
    pipeline.expire.assert_called_once()
    pipeline.set.assert_called_once()
    pipeline.sadd.assert_called_once_with("minions", "minion-1")
    pipeline.execute.assert_called_once()


# ---------------------------------------------------------------------------
# get_fun: reads from ret:<jid> hash, not from non-existent <minion>:<jid>
# ---------------------------------------------------------------------------


def test_get_fun_reads_data_from_ret_hash():
    """
    Headline regression: ``get_fun`` must read the per-minion return
    payload from ``HGET ret:<jid> <minion>``. Before the fix it did
    ``GET <minion>:<jid>`` -- a key the module never writes -- and
    therefore always returned ``{}``.
    """
    serv = MagicMock(name="redis_serv")
    serv.smembers.return_value = ["minion-1", "minion-2"]
    # <minion>:<fun> pointers exist for both minions.
    pointer_table = {
        "minion-1:test.ping": "20240101",
        "minion-2:test.ping": "20240102",
    }
    serv.get.side_effect = pointer_table.get
    # ret:<jid> hash holds the per-minion JSON-encoded return data.
    return_table = {
        ("ret:20240101", "minion-1"): '{"jid": "20240101", "return": "ok-1"}',
        ("ret:20240102", "minion-2"): '{"jid": "20240102", "return": "ok-2"}',
    }
    serv.hget.side_effect = lambda hashkey, field: return_table.get((hashkey, field))

    with patch.object(redis_return, "_get_serv", return_value=serv):
        result = redis_return.get_fun("test.ping")

    assert result == {
        "minion-1": {"jid": "20240101", "return": "ok-1"},
        "minion-2": {"jid": "20240102", "return": "ok-2"},
    }
    # And the production code must NOT have called the broken
    # ``serv.get("<minion>:<jid>")`` form for either minion.
    assert all(
        call.args[0] not in {"minion-1:20240101", "minion-2:20240102"}
        for call in serv.get.call_args_list
    ), "get_fun queried the non-existent <minion>:<jid> key; this is the bug"


def test_get_fun_skips_minions_with_no_recent_jid():
    """
    Minion is in the ``minions`` set but has never run the requested
    fun -> ``<minion>:<fun>`` returns None. Skip without consulting
    ``ret:<jid>`` and without raising.
    """
    serv = MagicMock(name="redis_serv")
    serv.smembers.return_value = ["minion-1"]
    serv.get.return_value = None  # no pointer for this (minion, fun)

    with patch.object(redis_return, "_get_serv", return_value=serv):
        result = redis_return.get_fun("test.ping")

    assert result == {}
    serv.hget.assert_not_called()


def test_get_fun_handles_missing_hash_field():
    """
    The pointer says the latest jid is X, but the ``ret:X`` hash no
    longer holds a field for this minion (e.g. it expired). Skip
    cleanly.
    """
    serv = MagicMock(name="redis_serv")
    serv.smembers.return_value = ["minion-1"]
    serv.get.return_value = "20240101"
    serv.hget.return_value = None  # field absent

    with patch.object(redis_return, "_get_serv", return_value=serv):
        result = redis_return.get_fun("test.ping")

    assert result == {}


def test_get_fun_no_minions_returns_empty():
    """
    No minions in the ``minions`` set -> empty dict. Pins backwards
    compatibility for fresh installs.
    """
    serv = MagicMock(name="redis_serv")
    serv.smembers.return_value = []

    with patch.object(redis_return, "_get_serv", return_value=serv):
        result = redis_return.get_fun("test.ping")

    assert result == {}
    serv.get.assert_not_called()
    serv.hget.assert_not_called()
