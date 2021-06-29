import time

import pytest
import salt.cache
from salt.exceptions import SaltCacheError
from tests.support.mock import MagicMock, patch


def etcd_setup(salt_minion, salt_cli, tmp):
    tmp_path = tmp / "etcd_v3.5.0-linux-amd64.tar.gz"
    ret = salt_cli.run(
        "file.manage_file",
        tmp_path,
        "source=https://github.com/etcd-io/etcd/releases/download/v3.5.0/etcd-v3.5.0-linux-amd64.tar.gz",
        "source_sum=sha256:864baa0437f8368e0713d44b83afe21dce1fb4ee7dae4ca0f9dd5f0df22d01c4",
        "makedirs=True",
        minion_tgt=salt_minion.id,
    )
    assert ret.exitcode == 0, "Unable to download etcd"
    opts = salt_minion.config["cache"].copy()
    opts["cache"] = "etcd"
    cache = salt.cache.factory(opts)
    return cache


@pytest.fixture(params=["etcd"])
def cache(request, tmp_path, salt_minion, salt_cli):
    driver = request.param
    if driver == "localfs":
        cache = salt.cache.factory(salt_minion.config)
    elif driver == "etcd":
        cache = etcd_setup(salt_minion=salt_minion, salt_cli=salt_cli, tmp=tmp_path)
    yield cache


def test_blerp(subtests, cache):
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

    # TODO: test other backends - redis, consul, etcd, mysql -W. Werner, 2021-06-29
    # TODO: document how to test custom backends - maybe os.environ flags? Or... something? -W. Werner, 2021-06-29
    # TODO: test memcache cache, not to be confused with memcached. memcache cache also appears to use these backends as well, so... test those. -W. Werner, 2021-06-29
