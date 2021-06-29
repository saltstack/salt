import logging
import time

import pytest
import salt.cache
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string
from saltfactories.utils.ports import get_unused_localhost_port

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_if_binaries_missing("dockerd"),
]


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
def etcd_container(salt_factories, docker_client, etcd_port):
    container = salt_factories.get_container(
        random_string("etcd-server-"),
        image_name="elcolio/etcd",
        docker_client=docker_client,
        check_ports=[etcd_port],
        # container_run_kwargs={"ports": {"2181/tcp": zookeeper_port}},
        container_run_kwargs={
            "environment": {"ALLOW_NONE_AUTHENTICATION": "yes"},
            "ports": {"2379/tcp": etcd_port},
        },
    )
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module", autouse="true")
def ensure_deps(states):
    ret = states.pip.installed(name="python-etcd")
    assert ret.result is True, "unable to pip install python-etcd"


@pytest.fixture
def etcd_cache(minion_opts, etcd_port):
    opts = minion_opts.copy()
    opts["cache"] = "etcd"
    opts["etcd.host"] = "127.0.0.1"
    opts["etcd.port"] = etcd_port
    opts["etcd.protocol"] = "http"
    cache = salt.cache.factory(opts)
    yield cache


@pytest.mark.skip
def test_some_blarp(etcd_container):
    etcd_container.container.exec_run(
        ["etcdctl", "set", "/the/lotion", "in the basket"]
    )

    res = etcd_container.container.exec_run(["etcdctl", "get", "/the/lotion"])

    assert res.output.decode() == "/the/lotion\nin the basket\n"


def test_another(etcd_container, etcd_cache):
    etcd_cache.store(bank="blarp", key="cool", data="whatever this data is")
    data = etcd_cache.fetch(bank="blarp", key="cool")
    assert data == "whatever this data is"


def test_blerp(subtests, etcd_cache):
    cache = etcd_cache
    bank = "fnord"
    good_key = "roscivs"
    bad_key = "monkey"

    with subtests.test("non-existent bank should be empty on cache start"):
        # TODO: this might need to be list(cache.list(bank)) -W. Werner, 2021-06-29
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
        cache.flush(bank=bank, key=good_key)
        assert cache.contains(bank=bank)
        assert cache.list(bank=bank) == []

    with subtests.test("flushing bank with None as key should remove bank"):
        cache.flush(bank=bank, key=None)
        assert not cache.contains(bank=bank)

    with subtests.test("Exception should happen when flushing None bank"):
        # This bit is maybe an accidental API, but currently there is no
        # protection at least with the localfs cache when bank is None. If
        # bank is None we try to `os.path.normpath` the bank, which explodes
        # and is at least the current behavior. If we want to change that
        # this test should change. Or be removed altogether.
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
            cache.modules, {"localfs.updated": MagicMock(side_effect=SaltCacheError)}
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

        assert cache_result == fetch_result == expected_result


# SUPER AWESOME WHERE WE ARE \0/
# basically: what we need now is to add stuff to configure the minion (also we want a minion in here that we can call)
# but the minion should be able to talk to the etcd docker container backend. That may mean that etcd stuff needs to be "installed" as part of the test. Oh that's what I was doing before in the test setup. May need to look into that closer? There is probably things to look at there...

# What do we need to do to make the minion (caching bit) talk to etcd?

# This seems like a good place to be. Once we can start caching in etcd we may also want to peep in etcd for things that were cached along with caching out-of-band (basically pretending that we were a different client or something)
