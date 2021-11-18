import logging
import shutil
import socket
import time

import pytest
import salt.cache
from salt.exceptions import SaltCacheError
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string
from saltfactories.utils.ports import get_unused_localhost_port
from tests.support.mock import MagicMock, patch

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_if_binaries_missing("dockerd"),
]

# TODO: add out-of-band (i.e. not via the API) additions to the cache -W. Werner, 2021-09-28

# TODO: in PR request opinion: is it better to double serialize the data, e.g.
# store -> __context__['serial'].dumps({"timestamp": tstamp, "value": __context__['serial'].dumps(value)})
# or is the existing approach of storing timestamp as a secondary key a good one???
# ??? Is one slower than the other?


# TODO: Is there a better approach for waiting until the container is fully running? -W. Werner, 2021-07-27
class Timer:
    def __init__(self, timeout=20):
        self.start = time.time()
        self.timeout = timeout

    @property
    def expired(self):
        return time.time() - self.start > self.timeout


@pytest.fixture(scope="module")
def docker_client():
    try:
        client = docker.from_env()
    except docker.errors.DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = Container.client_connectable(client)
    if connectable is not True:  # pragma: nocover
        pytest.skip(connectable)
    return client


@pytest.fixture(scope="module")
def etcd_port():
    return get_unused_localhost_port()


@pytest.fixture(scope="module")
def redis_port():
    return get_unused_localhost_port()


@pytest.fixture(scope="module")
def consul_port():
    return get_unused_localhost_port()


@pytest.fixture(scope="module")
def mysql_port():
    return get_unused_localhost_port()


# TODO: We should probably be building our own etcd docker image - fine to base it off of this one (or... others) -W. Werner, 2021-07-27
@pytest.fixture(scope="module")
def etcd_apiv2_container(salt_factories, docker_client, etcd_port):
    container = salt_factories.get_container(
        random_string("etcd-server-"),
        image_name="elcolio/etcd",
        docker_client=docker_client,
        check_ports=[etcd_port],
        container_run_kwargs={
            "environment": {"ALLOW_NONE_AUTHENTICATION": "yes"},
            "ports": {"2379/tcp": etcd_port},
        },
    )
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def redis_container(salt_factories, docker_client, redis_port):
    container = salt_factories.get_container(
        random_string("redis-server-"),
        image_name="redis:alpine",
        docker_client=docker_client,
        check_ports=[redis_port],
        container_run_kwargs={"ports": {"6379/tcp": redis_port}},
    )
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def mysql_container(salt_factories, docker_client, mysql_port):
    # TODO: Gareth has some container stuff already for lots of mysql versions - see pytests/integration/modules/test_mysql.py -W. Werner, 2021-08-05
    container = salt_factories.get_container(
        random_string("mysql-server-"),
        image_name="mysql",
        docker_client=docker_client,
        check_ports=[mysql_port],
        container_run_kwargs={
            "environment": {"MYSQL_ALLOW_EMPTY_PASSWORD": "yes"},
            "ports": {"3306/tcp": mysql_port},
        },
    )
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def consul_container(salt_factories, docker_client, consul_port):
    container = salt_factories.get_container(
        random_string("consul-server-"),
        image_name="consul",
        docker_client=docker_client,
        check_ports=[consul_port],
        container_run_kwargs={"ports": {"8500/tcp": consul_port}},
    )
    with container.started() as factory:
        # TODO: May want to do the same thing for redis to ensure that service is up & running
        # TODO: THIS IS HORRIBLE. THERE ARE BETTER WAYS TO DETECT SERVICE IS UP -W. Werner, 2021-10-12

        timer = Timer(timeout=10)
        sleeptime = 0.1
        while not timer.expired:
            try:
                with socket.create_connection(
                    ("localhost", consul_port), timeout=1
                ) as cli:
                    cli.send(b"GET /v1/kv/fnord HTTP/1.1\n\n")
                    cli.recv(2048)
                    break
            except ConnectionResetError as e:
                if e.errno == 104:
                    time.sleep(sleeptime)
                    sleeptime += sleeptime
        else:
            assert False, "Timer expired before connecting to consul"
        yield factory


@pytest.fixture
def redis_cache(minion_opts, redis_port, redis_container):
    opts = minion_opts.copy()
    opts["cache"] = "redis"
    opts["cache.redis.host"] = "127.0.0.1"
    opts["cache.redis.port"] = redis_port
    # NOTE: If you would like to ensure that alternate prefixes are properly
    # tested, simply change these values and re-run the tests.
    opts["cache.redis.bank_prefix"] = "#BANKY_BANK"
    opts["cache.redis.bank_keys_prefix"] = "#WHO_HAS_MY_KEYS"
    opts["cache.redis.key_prefix"] = "#LPL"
    opts["cache.redis.timestamp_prefix"] = "%TICK_TOCK"
    opts["cache.redis.separator"] = "\N{SNAKE}"
    cache = salt.cache.factory(opts)
    yield cache


@pytest.fixture(scope="module", autouse="true")
def ensure_deps(states):
    installation_result = states.pip.installed(
        name="fnord",
        pkgs=["python-etcd", "redis", "redis-py-cluster", "python-consul", "pymysql"],
    )
    assert (
        installation_result.result is True
    ), f"unable to pip install requirements {installation_result.comment}"


@pytest.fixture
def etcd_cache(minion_opts, etcd_port, etcd_apiv2_container):
    opts = minion_opts.copy()
    opts["cache"] = "etcd"
    opts["etcd.host"] = "127.0.0.1"
    opts["etcd.port"] = etcd_port
    opts["etcd.protocol"] = "http"
    # NOTE: If you would like to ensure that alternate suffixes are properly
    # tested, simply change this value and re-run the tests.
    opts["etcd.timestamp_suffix"] = ".frobnosticate"
    cache = salt.cache.factory(opts)
    yield cache


@pytest.fixture
def localfs_cache(minion_opts):
    opts = minion_opts.copy()
    opts["cache"] = "localfs"
    cache = salt.cache.factory(opts)
    yield cache
    try:
        shutil.rmtree(opts["cachedir"])
    except Exception:  # pylint: disable=broad-except
        # Not my circus, not my monkey
        pass


@pytest.fixture
def consul_cache(minion_opts, consul_port, consul_container):
    opts = minion_opts.copy()
    opts["cache"] = "consul"
    opts["consul.host"] = "127.0.0.1"
    opts["consul.port"] = consul_port
    # NOTE: If you would like to ensure that alternate suffixes are properly
    # tested, simply change this value and re-run the tests.
    opts["consul.timestamp_suffix"] = ".frobnosticate"
    cache = salt.cache.factory(opts)
    yield cache


@pytest.fixture
def mysql_cache(minion_opts, mysql_port, mysql_container):
    # We're doing a late import because we need access to the exception
    import salt.cache.mysql_cache

    # The container can be available before mysql actually is
    mysql_container.container.exec_run(
        ["/bin/sh", "-c", 'while ! mysql -e "SELECT 1;" >/dev/null; do sleep 1; done'],
    )

    # Gotta make the db we're going to use
    res = mysql_container.container.exec_run(
        ["/bin/sh", "-c", 'echo "create database salt_cache;" | mysql'],
    )

    opts = minion_opts.copy()
    opts["cache"] = "mysql"
    opts["mysql.host"] = "127.0.0.1"
    opts["mysql.port"] = mysql_port
    opts["mysql.user"] = "root"
    opts["mysql.database"] = "salt_cache"
    opts["mysql.table_name"] = "cache"
    cache = salt.cache.factory(opts)

    # For some reason even though mysql is available in the container, we
    # can't reliably connect outside the container. Wait for access
    timer = Timer(timeout=10)
    while not timer.expired:
        try:
            # Doesn't matter what. We just have to execute so that we spin
            # here until we can actually connect to the db instance.
            cache.modules["mysql.list"]("fnord")
        except salt.cache.mysql_cache.MySQLdb.DatabaseError:
            # We don't really care what MySQL error is happening -
            pass
        else:
            break
    else:
        assert False, 'Timer expired before "select 1;" worked'

    # This ensures that we will correctly alter any existing mysql tables for
    # current mysql cache users. Without completely altering the mysql_cache
    # implementation there's no real other reasonable way to reset the client
    # and force the alter_table to be called. Resetting the client to `None` is
    # what triggers the implementation to allow the ALTER TABLE to add the
    # last_update column
    run_query = cache.modules["mysql.run_query"]
    run_query(
        conn=None,
        query="ALTER TABLE salt_cache.cache DROP COLUMN last_update",
    )[0].fetchone()

    cache.modules["mysql.force_reconnect"]()
    yield cache


# TODO: Figure out how to parametrize this in combo with the getfixturevalue process -W. Werner, 2021-10-28
@pytest.fixture
def memcache_cache(minion_opts):
    opts = minion_opts.copy()
    opts["memcache_expire_seconds"] = 42
    cache = salt.cache.factory(opts)
    yield cache


@pytest.fixture(
    params=[
        "localfs_cache",
        "redis_cache",
        "etcd_cache",
        "consul_cache",
        "mysql_cache",
        "memcache_cache",  # Memcache actually delegates some behavior to the backing cache which alters the API somewhat.
    ]
)
def cache(request):
    # This is not an ideal way to get the particular cache type but
    # it's currently what we have available. It behaves *very* badly when
    # attempting to parametrize these fixtures. Don't ask me how I known.
    yield request.getfixturevalue(request.param)


def test_caching(subtests, cache):
    bank = "fnord/kevin/stuart"
    # ^^^^ This bank can be just fnord, or fnord/foo, or any mildly reasonable
    # or possibly unreasonably nested names.
    #
    # No. Seriously. Try import string; bank = '/'.join(string.ascii_letters)
    # - it works!
    # import string; bank = "/".join(string.ascii_letters)
    good_key = "roscivs"
    bad_key = "monkey"

    with subtests.test("non-existent bank should be empty on cache start"):
        assert not cache.contains(bank=bank)
        assert cache.list(bank=bank) == []

    with subtests.test("after storing key in bank it should be in cache list"):
        cache.store(bank=bank, key=good_key, data="fnordy data")
        assert cache.list(bank) == [good_key]

    with subtests.test("after storing value, it should be fetchable"):
        expected_data = "trombone pleasantry"
        cache.store(bank=bank, key=good_key, data=expected_data)
        assert cache.fetch(bank=bank, key=good_key) == expected_data

    with subtests.test("bad key should still be absent from cache"):
        assert cache.fetch(bank=bank, key=bad_key) == {}

    with subtests.test("storing new value should update it"):
        # Double check that the data was still the old stuff
        old_data = expected_data
        assert cache.fetch(bank=bank, key=good_key) == old_data
        new_data = "stromboli"
        cache.store(bank=bank, key=good_key, data=new_data)
        assert cache.fetch(bank=bank, key=good_key) == new_data

    with subtests.test("storing complex object works"):
        new_thing = {
            "some": "data",
            42: "wheee",
            "some other": {"sub": {"objects": "here"}},
        }

        cache.store(bank=bank, key=good_key, data=new_thing)
        actual_thing = cache.fetch(bank=bank, key=good_key)
        if isinstance(cache, salt.cache.MemCache):
            # MemCache should actually store the object - everything else
            # should create a copy of it.
            assert actual_thing is new_thing
        else:
            assert actual_thing is not new_thing
        assert actual_thing == new_thing

    with subtests.test("contains returns true if key in bank"):
        assert cache.contains(bank=bank, key=good_key)

    with subtests.test("contains returns true if bank exists and key is None"):
        assert cache.contains(bank=bank, key=None)

    with subtests.test(
        "contains returns False when bank not in cache and/or key not in bank"
    ):
        assert not cache.contains(bank=bank, key=bad_key)
        assert not cache.contains(bank="nonexistent", key=good_key)
        assert not cache.contains(bank="nonexistent", key=bad_key)
        assert not cache.contains(bank="nonexistent", key=None)

    with subtests.test("flushing nonexistent key should not remove other keys"):
        cache.flush(bank=bank, key=bad_key)
        assert cache.contains(bank=bank, key=good_key)

    with subtests.test(
        "flushing existing key should not remove bank if no more keys exist"
    ):
        pytest.skip(
            "This is impossible with redis. Should we make localfs behave the same way?"
        )
        cache.flush(bank=bank, key=good_key)
        assert cache.contains(bank=bank)
        assert cache.list(bank=bank) == []

    with subtests.test(
        "after existing key is flushed updated should not return a timestamp for that key"
    ):
        cache.store(bank=bank, key=good_key, data="fnord")
        cache.flush(bank=bank, key=good_key)
        timestamp = cache.updated(bank=bank, key=good_key)
        assert timestamp is None

    with subtests.test(
        "after flushing bank containing a good key, updated should not return a timestamp for that key"
    ):
        cache.store(bank=bank, key=good_key, data="fnord")
        cache.flush(bank=bank, key=None)
        timestamp = cache.updated(bank=bank, key=good_key)
        assert timestamp is None

    with subtests.test("flushing bank with None as key should remove bank"):
        cache.flush(bank=bank, key=None)
        assert not cache.contains(bank=bank)

    with subtests.test("Exception should happen when flushing None bank"):
        # This bit is maybe an accidental API, but currently there is no
        # protection at least with the localfs cache when bank is None. If
        # bank is None we try to `os.path.normpath` the bank, which explodes
        # and is at least the current behavior. If we want to change that
        # this test should change. Or be removed altogether.
        # TODO: this should actually not raise. Not sure if there's a test that we can do here... or just call the code which will fail if there's actually an exception. -W. Werner, 2021-09-28
        pytest.skip(
            "Skipping for now - etcd, redis, and mysql do not raise. Should ensure all backends behave consistently"
        )
        with pytest.raises(Exception):
            cache.flush(bank=None, key=None)

    with subtests.test("Updated for non-existent key should return None"):
        timestamp = cache.updated(bank="nonexistent", key="whatever")
        assert timestamp is None

    with subtests.test("Updated for key should return a reasonable time"):
        before_storage = int(time.time())
        cache.store(bank="fnord", key="updated test part 2", data="fnord")
        after_storage = int(time.time())

        timestamp = cache.updated(bank="fnord", key="updated test part 2")

        assert before_storage <= timestamp <= after_storage

    with subtests.test(
        "If the module raises SaltCacheError then it should make it out of updated"
    ):
        with patch.dict(
            cache.modules,
            {"{}.updated".format(cache.driver): MagicMock(side_effect=SaltCacheError)},
        ), pytest.raises(SaltCacheError):
            cache.updated(bank="kaboom", key="oops")

    with subtests.test(
        "cache.cache right after a value is cached should not update the cache"
    ):
        expected_value = "some cool value yo"
        cache.store(bank=bank, key=good_key, data=expected_value)
        result = cache.cache(
            bank=bank,
            key=good_key,
            fun=lambda **kwargs: "bad bad value no good",
            value="some other value?",
            loop_fun=lambda x: "super very no good bad",
        )
        fetch_result = cache.fetch(bank=bank, key=good_key)

        assert result == fetch_result == expected_value

    with subtests.test(
        "cache.cache should update the value with the result of fun when value was updated longer than expiration",
    ), patch(
        "salt.cache.Cache.updated",
        return_value=42,  # Dec 31, 1969... time to update the cache!
        autospec=True,
    ):
        expected_value = "this is the return value woo woo woo"
        cache.store(bank=bank, key=good_key, data="not this value")
        cache_result = cache.cache(
            bank=bank, key=good_key, fun=lambda *args, **kwargs: expected_value
        )
        fetch_result = cache.fetch(bank=bank, key=good_key)

        assert cache_result == fetch_result == expected_value

    with subtests.test(
        "cache.cache should update the value with all of the outputs from loop_fun if loop_fun was provided",
    ), patch(
        "salt.cache.Cache.updated",
        return_value=42,
        autospec=True,
    ):
        expected_value = "SOME HUGE STRING OKAY?"

        cache.store(bank=bank, key=good_key, data="nope, not me")
        cache_result = cache.cache(
            bank=bank,
            key=good_key,
            fun=lambda **kwargs: "some huge string okay?",
            loop_fun=str.upper,
        )
        fetch_result = cache.fetch(bank=bank, key=good_key)

        assert cache_result == fetch_result
        assert "".join(fetch_result) == expected_value

    with subtests.test(
        "cache.cache should update the value if the stored value is empty but present and expiry is way in the future"
    ), patch(
        "salt.cache.Cache.updated",
        return_value=time.time() * 2,
        autospec=True,
    ):
        # Unclear if this was intended behavior: currently any falsey data will
        # be updated by cache.cache. If this is incorrect, this test should
        # be updated or removed.
        expected_data = "some random string whatever"
        for empty in ("", (), [], {}, 0, 0.0, False, None):
            with subtests.test(empty=empty):
                cache.store(
                    bank=bank, key=good_key, data=empty
                )  # empty chairs and empty data
                cache_result = cache.cache(
                    bank=bank, key=good_key, fun=lambda **kwargs: expected_data
                )
                fetch_result = cache.fetch(bank=bank, key=good_key)

                assert cache_result == fetch_result == expected_data

    with subtests.test("cache.cache should store a value if it does not exist"):
        expected_result = "some result plz"
        cache.flush(bank=bank, key=None)
        assert cache.fetch(bank=bank, key=good_key) == {}
        cache_result = cache.cache(
            bank=bank, key=good_key, fun=lambda **kwargs: expected_result
        )
        fetch_result = cache.fetch(bank=bank, key=good_key)

        assert cache_result == fetch_result
        assert fetch_result == expected_result
        assert cache_result == fetch_result == expected_result
