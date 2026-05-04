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
