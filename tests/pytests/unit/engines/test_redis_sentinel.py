"""
Unit tests for the redis_sentinel engine.

These regression tests cover two distinct bugs that together prevented
the engine from being usable on any modern Salt installation:

1. ``start()`` crashed on Python 3 with
   ``AttributeError: 'dict_values' object has no attribute 'pop'``
   because ``dict.values()`` no longer supports ``.pop()`` in Python 3.
2. ``Listener`` built the redis client without ever passing a password,
   so the engine could not authenticate to a Sentinel that required
   AUTH.
"""

import pytest

redis_sentinel = pytest.importorskip(
    "salt.engines.redis_sentinel",
    reason="salt.engines.redis_sentinel is not available in this build",
)
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {redis_sentinel: {"__opts__": {"sock_dir": "/tmp/sock"}}}


@pytest.fixture
def patched_listener_deps():
    """
    Mock everything ``Listener.__init__`` reaches outside its own
    module so that the constructor can be exercised in isolation.
    """
    fake_strict_redis = MagicMock(name="StrictRedis")
    fake_redis_module = MagicMock(name="redis_module", StrictRedis=fake_strict_redis)
    fake_event = MagicMock(name="get_master_event")

    with patch.object(redis_sentinel, "redis", fake_redis_module), patch(
        "salt.utils.event.get_master_event", fake_event
    ):
        yield fake_strict_redis


@pytest.fixture
def patched_localclient_and_listener():
    """
    Mock ``salt.client.LocalClient`` (returns a deterministic dict
    mapping minion -> [ip]) and ``Listener`` (so we can inspect what
    ``start()`` constructed without actually running the pubsub loop).
    """
    fake_local = MagicMock()
    fake_local.cmd.return_value = {
        "sentinel-1.example.com": ["10.0.0.5"],
        "sentinel-2.example.com": ["10.0.0.6"],
    }
    fake_listener_class = MagicMock(name="Listener")
    fake_listener_class.return_value = MagicMock(name="Listener instance")

    with patch("salt.client.LocalClient") as lc_mock, patch.object(
        redis_sentinel, "Listener", fake_listener_class
    ):
        lc_mock.return_value.__enter__.return_value = fake_local
        yield fake_local, fake_listener_class


# ---------------------------------------------------------------------------
# Listener: password propagation
# ---------------------------------------------------------------------------


def test_listener_passes_password_to_redis_client(patched_listener_deps):
    """
    When a password is supplied to Listener, it must be forwarded to
    redis.StrictRedis. Before the fix Listener had no ``password``
    parameter at all -- this test would raise TypeError.
    """
    fake_strict_redis = patched_listener_deps
    redis_sentinel.Listener(host="sentinel-1", port=26379, password="my-secret")
    fake_strict_redis.assert_called_once_with(
        host="sentinel-1", port=26379, password="my-secret", decode_responses=True
    )


def test_listener_default_password_is_none(patched_listener_deps):
    """
    With no password supplied, redis.StrictRedis must receive
    ``password=None``. Pins the backwards-compatible default: omitting
    the password keeps AUTH disabled, so the change is non-breaking
    for existing operators who never set one.
    """
    fake_strict_redis = patched_listener_deps
    redis_sentinel.Listener(host="sentinel-1", port=26379)
    call = fake_strict_redis.call_args
    assert call.kwargs.get("password") is None


# ---------------------------------------------------------------------------
# start(): dict_values.pop fix and password forwarding
# ---------------------------------------------------------------------------


def test_start_does_not_crash_on_dict_values_pop(patched_localclient_and_listener):
    """
    Headline regression: the original code called
    ``local.cmd(...).values().pop()`` where ``.values()`` returns a
    Python 3 ``dict_values`` view (no ``.pop`` method). The engine
    therefore raised ``AttributeError`` on its very first call and
    never actually ran. The fix wraps in ``list(...)``.
    """
    _fake_local, fake_listener_class = patched_localclient_and_listener
    redis_sentinel.start(
        hosts={"matching": "sentinel*", "port": 26379, "interface": "eth0"},
        channels=["+switch-master"],
    )
    # Listener must have been constructed (which is what would not happen
    # if .pop() raised) and its run loop must have been entered.
    assert fake_listener_class.call_count == 1
    fake_listener_class.return_value.run.assert_called_once()


def test_start_forwards_password_to_listener(patched_localclient_and_listener):
    """
    When the engine YAML supplies ``password: '...'`` (which Salt's
    engine loader hands to ``start()`` as a kwarg), the value must reach
    the Listener constructor.
    """
    _fake_local, fake_listener_class = patched_localclient_and_listener
    redis_sentinel.start(
        hosts={"matching": "sentinel*", "port": 26379, "interface": "eth0"},
        channels=["+switch-master"],
        password="my-secret",
    )
    call = fake_listener_class.call_args
    assert call.kwargs["password"] == "my-secret"


def test_start_default_password_is_none(patched_localclient_and_listener):
    """
    When the YAML does not specify a password, Listener must be
    constructed with ``password=None``. Pins backwards compatibility
    for existing engine configs that never set one.
    """
    _fake_local, fake_listener_class = patched_localclient_and_listener
    redis_sentinel.start(
        hosts={"matching": "sentinel*", "port": 26379, "interface": "eth0"},
        channels=["+switch-master"],
    )
    call = fake_listener_class.call_args
    assert call.kwargs.get("password") is None


def test_start_logs_and_returns_when_no_minions_match(caplog):
    """
    When the ``matching`` target hits zero minions, ``local.cmd`` returns
    an empty dict. The engine must log a clear error and return rather
    than dereferencing the empty result -- the previous code crashed with
    ``IndexError`` from ``.pop()``, which gave operators no hint that the
    real problem was a misconfigured target pattern.
    """
    fake_local = MagicMock()
    fake_local.cmd.return_value = {}
    fake_listener_class = MagicMock(name="Listener")

    with patch("salt.client.LocalClient") as lc_mock, patch.object(
        redis_sentinel, "Listener", fake_listener_class
    ):
        lc_mock.return_value.__enter__.return_value = fake_local
        with caplog.at_level("ERROR", logger="salt.engines.redis_sentinel"):
            redis_sentinel.start(
                hosts={
                    "matching": "no-such-minion-*",
                    "port": 26379,
                    "interface": "eth0",
                },
                channels=["+switch-master"],
            )

    fake_listener_class.assert_not_called()
    assert any(
        "no minions matched" in rec.message and "no-such-minion-*" in rec.message
        for rec in caplog.records
    ), "expected an ERROR log explaining the empty match; got: {}".format(
        [rec.message for rec in caplog.records]
    )
