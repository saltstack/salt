import logging
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

# PLAN: currently the salt/cache/*.py caches do not have a consistent API. In
# fact update is completely missing from at least one of them. This is not
# ideal. We would like instead to have a consistent API across our caches. The
# one problem with that is that in order to have a consistent API our existing
# API must become a legacy API. Short term what that means is that the default
# approach will be to use the legacy API which should produce deprecation
# warnings. Then after a certain time we should drop the legacy cache api in
# each of these backends. I need to add documentation to the cache files to
# describe what needs to be removed when the deprecations hit removal so that
# whoever is responsible for that is not a homicidal psychopath who wants to
# know where I live. Also we'll need a flag in the config that starts with use
# legacy. Maybe we want a shift from use legacy to have one release with that
# toggled to false? Anyway. The approach that I'm taking here is to assume the
# (default) localfs cache has the most correct API. I'm just going through and
# building up the alternative cache backends to match the localfs cache API.

# Thursday: start making etcd tests work

# TODO: Ensure that timestamps are flushed from the cache(s) as well -W. Werner, 2021-10-12
# TODO: add out-of-band (i.e. not via the API) additions to the cache -W. Werner, 2021-09-28


# - [✓] - redis_cache
# - [✓] - etcd_cache - mostly complete - tried PR 56001, many more errors happened
# - [✓] - consul_cache
# - [✓✓] - mysql_cache


# WOOHOO! Tests are all passing for all of the cache modules. They are in sync,
# behavior-wise, with localfs cache. However! They're not quite perfect.
# Currently the mysql_cache won't update an existing cache table - it should
# ALTER TABLE if the table exists. It's also looking horrible from a SQL
# injection perspective, that should 100% be addressed. etcd/consul/redis
# caches also need to appropritately clean up the timestamp entries. As
# mentioned, we also need to add some out-of-band tests.

# TODO
# - [✓] - mysql, check to see if the timestamp exists on the table, if not, alter table, otherwise create
# - [✓] - as much as possible fix sql injection potential
# - [✓] - consul - check that we're purging the timetstamps when keys/banks are flushed
# - [✓] - etcd - check that we're purging timestamps when keys/banks are flushed
# - [✓] - redis - re-unify things to use original approach + ensure timestamps are flushed
# - [ ] - MemCache - add some tests for MemCache

# TODO: in PR request opinion: is it better to double serialize the data, e.g.
# store -> __context__['serial'].dumps({"timestamp": tstamp, "value": __context__['serial'].dumps(value)})
# or is the existing approach of storing timestamp as a secondary key a good one???
# ??? Is one slower than the other?


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
        import socket, time  # pylint: disable=multiple-imports,multiple-imports-on-one-line

        sleeptime = 0.1
        up_yet = False
        while not up_yet:
            try:
                with socket.create_connection(
                    ("localhost", consul_port), timeout=1
                ) as cli:
                    cli.send(b"GET /v1/kv/fnord HTTP/1.1\n\n")
                    cli.recv(2048)
                    up_yet = True
            except ConnectionResetError as e:
                if e.errno == 104:
                    time.sleep(sleeptime)
                    sleeptime += sleeptime
        yield factory


@pytest.fixture
def redis_cache(minion_opts, redis_port, redis_container):
    opts = minion_opts.copy()
    opts["cache"] = "redis"
    opts["cache.redis.host"] = "127.0.0.1"
    opts["cache.redis.port"] = redis_port
    opts["cache.redis.bank_prefix"] = "#BANKY_BANK"
    opts["cache.redis.bank_keys_prefix"] = "#WHO_HAS_MY_KEYS"
    opts["cache.redis.key_prefix"] = "#LPL"
    opts["cache.redis.timestamp_prefix"] = "%TICK_TOCK"
    opts["cache.redis.separator"] = "\N{SNAKE}"
    cache = salt.cache.factory(opts)
    yield cache


@pytest.fixture(scope="module", autouse="true")
def ensure_deps(states):
    ret = states.pip.installed(name="python-etcd")
    assert ret.result is True, "unable to pip install python-etcd"


@pytest.fixture
def etcd_cache(minion_opts, etcd_port, etcd_apiv2_container):
    opts = minion_opts.copy()
    opts["cache"] = "etcd"
    opts["etcd.host"] = "127.0.0.1"
    opts["etcd.port"] = etcd_port
    opts["etcd.protocol"] = "http"
    opts["etcd.timestamp_suffix"] = ".frobnosticate"
    cache = salt.cache.factory(opts)
    yield cache


@pytest.fixture
def localfs_cache(minion_opts):
    opts = minion_opts.copy()
    opts["cache"] = "localfs"
    cache = salt.cache.factory(opts)
    yield cache


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
    # TODO: Is there a better way to wait until the container is fully running? -W. Werner, 2021-07-27
    class Timer:
        def __init__(self, timeout=20):
            self.start = time.time()
            self.timeout = timeout

        @property
        def expired(self):
            return time.time() - self.start > self.timeout

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
        except Exception as e:  # pylint: disable=broad-except
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
        run_query.func.__globals__["client"],
        "ALTER TABLE salt_cache.cache DROP COLUMN last_update",
    )[0].fetchone()
    run_query.func.__globals__["client"] = None

    yield cache


@pytest.fixture(
    params=[
        "localfs_cache",
        "redis_cache",
        "etcd_cache",
        "consul_cache",
        "mysql_cache",
    ]
)
def cache(request):
    # This is not an ideal way to get the particular cache type but
    # it's currently what we have available.
    yield request.param.replace("_cache", ""), request.getfixturevalue(request.param)


def test_caching(subtests, cache):
    cachename, cache = cache
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
            {"{}.updated".format(cachename): MagicMock(side_effect=SaltCacheError)},
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
        "salt.cache.Cache.updated", return_value=42, autospec=True,
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
        "salt.cache.Cache.updated", return_value=time.time() * 2, autospec=True,
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
