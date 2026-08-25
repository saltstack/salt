"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.redismod
"""

from datetime import datetime

import pytest

import salt.modules.redismod as redismod
from tests.support.mock import MagicMock, patch

# Capture the real ``_connect`` reference before the loader fixture replaces
# it with a MagicMock. The tests for ``_connect`` itself need the real
# implementation; everything else uses the mocked one.
_REAL_CONNECT = redismod._connect


class Mockredis:
    """
    Mock redis class
    """

    class ConnectionError(Exception):
        """
        Mock ConnectionError class
        """


class MockConnect:
    """
    Mock Connect class
    """

    counter = 0

    def __init__(self):
        self.name = None
        self.pattern = None
        self.value = None
        self.key = None
        self.seconds = None
        self.timestamp = None
        self.field = None
        self.start = None
        self.stop = None
        self.master_host = None
        self.master_port = None

    @staticmethod
    def bgrewriteaof():
        """
        Mock bgrewriteaof method
        """
        return "A"

    @staticmethod
    def bgsave():
        """
        Mock bgsave method
        """
        return "A"

    def config_get(self, pattern):
        """
        Mock config_get method
        """
        self.pattern = pattern
        return "A"

    def config_set(self, name, value):
        """
        Mock config_set method
        """
        self.name = name
        self.value = value
        return "A"

    @staticmethod
    def dbsize():
        """
        Mock dbsize method
        """
        return "A"

    @staticmethod
    def delete():
        """
        Mock delete method
        """
        return "A"

    def exists(self, key):
        """
        Mock exists method
        """
        self.key = key
        return "A"

    def expire(self, key, seconds):
        """
        Mock expire method
        """
        self.key = key
        self.seconds = seconds
        return "A"

    def expireat(self, key, timestamp):
        """
        Mock expireat method
        """
        self.key = key
        self.timestamp = timestamp
        return "A"

    @staticmethod
    def flushall():
        """
        Mock flushall method
        """
        return "A"

    @staticmethod
    def flushdb():
        """
        Mock flushdb method
        """
        return "A"

    def get(self, key):
        """
        Mock get method
        """
        self.key = key
        return "A"

    def hget(self, key, field):
        """
        Mock hget method
        """
        self.key = key
        self.field = field
        return "A"

    def hgetall(self, key):
        """
        Mock hgetall method
        """
        self.key = key
        return "A"

    @staticmethod
    def info():
        """
        Mock info method
        """
        return "A"

    def keys(self, pattern):
        """
        Mock keys method
        """
        self.pattern = pattern
        return "A"

    def type(self, key):
        """
        Mock type method
        """
        self.key = key
        return "A"

    @staticmethod
    def lastsave():
        """
        Mock lastsave method
        """
        return datetime.now()

    def llen(self, key):
        """
        Mock llen method
        """
        self.key = key
        return "A"

    def lrange(self, key, start, stop):
        """
        Mock lrange method
        """
        self.key = key
        self.start = start
        self.stop = stop
        return "A"

    @staticmethod
    def ping():
        """
        Mock ping method
        """
        MockConnect.counter = MockConnect.counter + 1
        if MockConnect.counter == 1:
            return "A"
        elif MockConnect.counter in (2, 3, 5):
            raise Mockredis.ConnectionError("foo")

    @staticmethod
    def save():
        """
        Mock save method
        """
        return "A"

    def set(self, key, value):
        """
        Mock set method
        """
        self.key = key
        self.value = value
        return "A"

    @staticmethod
    def shutdown():
        """
        Mock shutdown method
        """
        return "A"

    def slaveof(self, master_host, master_port):
        """
        Mock slaveof method
        """
        self.master_host = master_host
        self.master_port = master_port
        return "A"

    def smembers(self, key):
        """
        Mock smembers method
        """
        self.key = key
        return "A"

    @staticmethod
    def time():
        """
        Mock time method
        """
        return "A"

    def zcard(self, key):
        """
        Mock zcard method
        """
        self.key = key
        return "A"

    def zrange(self, key, start, stop):
        """
        Mock zrange method
        """
        self.key = key
        self.start = start
        self.stop = stop
        return "A"


@pytest.fixture
def configure_loader_modules():
    return {
        redismod: {
            "redis": Mockredis,
            "_connect": MagicMock(return_value=MockConnect()),
        }
    }


def test_bgrewriteaof():
    """
    Test to asynchronously rewrite the append-only file
    """
    assert redismod.bgrewriteaof() == "A"


def test_bgsave():
    """
    Test to asynchronously save the dataset to disk
    """
    assert redismod.bgsave() == "A"


def test_config_get():
    """
    Test to get redis server configuration values
    """
    assert redismod.config_get("*") == "A"


def test_config_set():
    """
    Test to set redis server configuration values
    """
    assert redismod.config_set("name", "value") == "A"


def test_dbsize():
    """
    Test to return the number of keys in the selected database
    """
    assert redismod.dbsize() == "A"


def test_delete():
    """
    Test to deletes the keys from redis, returns number of keys deleted
    """
    assert redismod.delete() == "A"


def test_exists():
    """
    Test to return true if the key exists in redis
    """
    assert redismod.exists("key") == "A"


def test_expire():
    """
    Test to set a keys time to live in seconds
    """
    assert redismod.expire("key", "seconds") == "A"


def test_expireat():
    """
    Test to set a keys expire at given UNIX time
    """
    assert redismod.expireat("key", "timestamp") == "A"


def test_flushall():
    """
    Test to remove all keys from all databases
    """
    assert redismod.flushall() == "A"


def test_flushdb():
    """
    Test to remove all keys from the selected database
    """
    assert redismod.flushdb() == "A"


def test_get_key():
    """
    Test to get redis key value
    """
    assert redismod.get_key("key") == "A"


def test_hget():
    """
    Test to get specific field value from a redis hash, returns dict
    """
    assert redismod.hget("key", "field") == "A"


def test_hgetall():
    """
    Test to get all fields and values from a redis hash, returns dict
    """
    assert redismod.hgetall("key") == "A"


def test_info():
    """
    Test to get information and statistics about the server
    """
    assert redismod.info() == "A"


def test_keys():
    """
    Test to get redis keys, supports glob style patterns
    """
    assert redismod.keys("pattern") == "A"


def test_key_type():
    """
    Test to get redis key type
    """
    assert redismod.key_type("key") == "A"


def test_lastsave():
    """
    Test to get the UNIX time in seconds of the last successful
    save to disk
    """
    assert redismod.lastsave()


def test_llen():
    """
    Test to get the length of a list in Redis
    """
    assert redismod.llen("key") == "A"


def test_lrange():
    """
    Test to get a range of values from a list in Redis
    """
    assert redismod.lrange("key", "start", "stop") == "A"


def test_ping():
    """
    Test to ping the server, returns False on connection errors
    """
    assert redismod.ping() == "A"

    assert not redismod.ping()


def test_save():
    """
    Test to synchronously save the dataset to disk
    """
    assert redismod.save() == "A"


def test_set_key():
    """
    Test to set redis key value
    """
    assert redismod.set_key("key", "value") == "A"


def test_shutdown():
    """
    Test to synchronously save the dataset to disk and then
    shut down the server
    """
    assert not redismod.shutdown()

    assert redismod.shutdown()

    assert not redismod.shutdown()


def test_slaveof():
    """
    Test to make the server a slave of another instance, or
    promote it as master
    """
    assert redismod.slaveof("master_host", "master_port") == "A"


def test_smembers():
    """
    Test to get members in a Redis set
    """
    assert redismod.smembers("key") == ["A"]


def test_time():
    """
    Test to return the current server UNIX time in seconds
    """
    assert redismod.time() == "A"


def test_zcard():
    """
    Test to get the length of a sorted set in Redis
    """
    assert redismod.zcard("key") == "A"


def test_zrange():
    """
    Test to get a range of values from a sorted set in Redis by index
    """
    assert redismod.zrange("key", "start", "stop") == "A"


# ---------------------------------------------------------------------------
# Regression tests for the get_master_ip positional-args bug.
#
# get_master_ip used to forward its arguments to _connect positionally:
#
#     server = _connect(host, port, password)
#
# but _connect's positional signature is (host, port, db, password). The
# password value therefore landed in the db slot, while the actual password
# parameter of _connect fell through to config.option("redis.password").
# The fix passes arguments by keyword.
# ---------------------------------------------------------------------------


def _fake_redis_server(master_host="10.0.0.5", master_port="6379"):
    """Build a MagicMock that quacks like the redis client _connect returns."""
    server = MagicMock()
    server.info.return_value = {
        "master_host": master_host,
        "master_port": master_port,
    }
    return server


def test_get_master_ip_passes_password_as_keyword():
    """
    get_master_ip must forward the password to _connect as a keyword
    argument, not as a positional argument that would land in _connect's
    `db` slot.
    """
    server = _fake_redis_server()
    with patch.object(redismod, "_connect", return_value=server) as mock_connect:
        result = redismod.get_master_ip(host="redis-1", port=6379, password="my-secret")

    mock_connect.assert_called_once_with(
        host="redis-1", port=6379, password="my-secret"
    )
    assert result == {"master_host": "10.0.0.5", "master_port": "6379"}


def test_get_master_ip_does_not_send_password_as_db():
    """
    Tight regression check: the password value must never appear in
    _connect's positional args nor in its `db` keyword slot.
    """
    server = _fake_redis_server(master_host="x", master_port="y")
    with patch.object(redismod, "_connect", return_value=server) as mock_connect:
        redismod.get_master_ip(host="h", port=1234, password="MY_SECRET")

    call = mock_connect.call_args
    assert "MY_SECRET" not in call.args, (
        "password leaked into _connect positional args; " "this is the original bug."
    )
    assert call.kwargs.get("db") != "MY_SECRET", (
        "password leaked into _connect's db keyword; " "this is the original bug."
    )
    assert call.kwargs.get("password") == "MY_SECRET"


def test_get_master_ip_no_args_passes_none_to_connect():
    """
    With no explicit arguments, _connect must receive None for each
    parameter so that _connect itself can resolve the values from
    config.option(...). The fix must not change this behaviour.
    """
    server = _fake_redis_server(master_host="", master_port="")
    with patch.object(redismod, "_connect", return_value=server) as mock_connect:
        result = redismod.get_master_ip()

    mock_connect.assert_called_once_with(host=None, port=None, password=None)
    assert result == {"master_host": "", "master_port": ""}


def test_get_master_ip_returns_dict_with_info_fields_missing():
    """
    If the Redis INFO response does not include master_host/master_port
    (e.g. when querying a master that has no master), the function still
    returns a dict with both keys present, defaulted to "". The fix to
    the positional-args bug must not regress this.
    """
    server = MagicMock()
    server.info.return_value = {}  # no master_host, no master_port
    with patch.object(redismod, "_connect", return_value=server):
        result = redismod.get_master_ip(host="h", port=1, password="p")

    assert result == {"master_host": "", "master_port": ""}


def test_get_master_ip_with_only_password_kwarg_routes_password_correctly():
    """
    The most common real-world failure pattern of the original bug:
    operator passes ``password=...`` and relies on host/port defaults
    coming from config. The password must still arrive at _connect via
    the password keyword, not via the db slot.
    """
    server = _fake_redis_server()
    with patch.object(redismod, "_connect", return_value=server) as mock_connect:
        redismod.get_master_ip(password="only-password")

    mock_connect.assert_called_once_with(host=None, port=None, password="only-password")


def test_get_master_ip_called_positionally_routes_password_correctly():
    """
    The public function signature accepts positional arguments. Even
    when callers use the positional style, password must end up in
    _connect's password keyword, not its db slot. This guards against
    a regression where someone might re-introduce positional forwarding
    to _connect ('it worked when called positionally so it must be
    fine').
    """
    server = _fake_redis_server()
    with patch.object(redismod, "_connect", return_value=server) as mock_connect:
        redismod.get_master_ip("redis-1", 6379, "my-secret")

    mock_connect.assert_called_once_with(
        host="redis-1", port=6379, password="my-secret"
    )


# ---------------------------------------------------------------------------
# Regression tests for the _connect "if not db" bug.
#
# _connect used the truthy check ``if not db`` to decide whether to fall
# back to ``config.option("redis.db")``. That predicate is also true for
# ``db=0`` -- the default Redis database index, and a perfectly valid
# explicit value. As a result, callers who explicitly targeted db 0 had
# their argument silently replaced by the configured value.
#
# The fix uses ``if db is None`` so that only the absent-argument case
# triggers the fall-back. The other arguments (host/port/password) keep
# their truthy-check semantics on purpose: empty string and 0 are not
# legitimate values for a hostname or port, and "" is not a meaningful
# password override.
# ---------------------------------------------------------------------------


def _connect_test_env(config_options):
    """
    Build the (config_option_mock, fake_strict_redis, fake_redis_module)
    triple used by every _connect test. Mocking redis.StrictRedis lets us
    assert exactly which (host, port, db, password) tuple _connect built;
    wrapping config.option in a MagicMock lets us assert which keys it
    queried (and which it skipped).
    """
    config_option_mock = MagicMock(
        side_effect=lambda key, *args, **kwargs: config_options.get(key)
    )
    fake_strict_redis = MagicMock(name="StrictRedis")
    fake_redis_module = MagicMock(name="redis_module", StrictRedis=fake_strict_redis)
    return config_option_mock, fake_strict_redis, fake_redis_module


def test_connect_passes_db_zero_through():
    """
    The headline regression test: when the caller explicitly passes
    ``db=0``, _connect must hand 0 to StrictRedis verbatim and must NOT
    consult ``config.option("redis.db")``.
    """
    config_option_mock, fake_strict_redis, fake_redis_module = _connect_test_env(
        {
            "redis.host": "config-host",
            "redis.port": 6380,
            "redis.db": "5",
            "redis.password": "config-pass",
        }
    )

    with patch.object(
        redismod, "__salt__", {"config.option": config_option_mock}, create=True
    ), patch.object(redismod, "redis", fake_redis_module):
        _REAL_CONNECT(host="h", port=6379, db=0, password="p")

    # StrictRedis is called positionally: (host, port, db, password).
    call = fake_strict_redis.call_args
    assert (
        call.args[2] == 0
    ), f"db=0 was replaced (got {call.args[2]!r}); this is the bug"

    queried_keys = [c.args[0] for c in config_option_mock.call_args_list]
    assert "redis.db" not in queried_keys, (
        "_connect queried config.option('redis.db') even though the caller "
        "supplied db=0; this is the bug"
    )


def test_connect_falls_back_to_config_when_db_is_none():
    """
    With db=None (the default), _connect must read redis.db from config
    and pass the resulting value to StrictRedis.
    """
    config_option_mock, fake_strict_redis, fake_redis_module = _connect_test_env(
        {
            "redis.host": "config-host",
            "redis.port": 6380,
            "redis.db": "7",
            "redis.password": "config-pass",
        }
    )

    with patch.object(
        redismod, "__salt__", {"config.option": config_option_mock}, create=True
    ), patch.object(redismod, "redis", fake_redis_module):
        _REAL_CONNECT()

    call = fake_strict_redis.call_args
    assert call.args == ("config-host", 6380, "7", "config-pass")

    queried_keys = [c.args[0] for c in config_option_mock.call_args_list]
    assert "redis.db" in queried_keys


def test_connect_passes_explicit_nonzero_db_through():
    """
    Sanity check: an explicit non-zero db value is honoured. This already
    worked before the fix (because the truthy check passed for non-zero),
    but the test pins the behaviour so future refactors do not regress it.
    """
    config_option_mock, fake_strict_redis, fake_redis_module = _connect_test_env(
        {"redis.db": "should-not-be-used"}
    )

    with patch.object(
        redismod, "__salt__", {"config.option": config_option_mock}, create=True
    ), patch.object(redismod, "redis", fake_redis_module):
        _REAL_CONNECT(host="h", port=6379, db=5, password="p")

    call = fake_strict_redis.call_args
    assert call.args[2] == 5

    queried_keys = [c.args[0] for c in config_option_mock.call_args_list]
    assert "redis.db" not in queried_keys


def test_connect_other_args_keep_truthy_fallback_semantics():
    """
    The fix narrows the fall-back predicate only for ``db``. The host,
    port and password arguments keep their existing truthy-check
    semantics on purpose -- empty string is not a legitimate hostname,
    0 is not a legitimate port, and "" is not a meaningful password
    override. This test pins that scope so the fix does not silently
    widen.
    """
    config_option_mock, fake_strict_redis, fake_redis_module = _connect_test_env(
        {
            "redis.host": "config-host",
            "redis.port": 6380,
            "redis.password": "config-pass",
        }
    )

    with patch.object(
        redismod, "__salt__", {"config.option": config_option_mock}, create=True
    ), patch.object(redismod, "redis", fake_redis_module):
        _REAL_CONNECT(host="", port=None, db=2, password=None)

    call = fake_strict_redis.call_args
    # host="" -> falls back; port=None -> falls back; db=2 -> kept;
    # password=None -> falls back.
    assert call.args == ("config-host", 6380, 2, "config-pass")
