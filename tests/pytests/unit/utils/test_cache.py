"""
    tests.unit.utils.cache_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt cache objects
"""

import time

import pytest
import salt.config
import salt.loader
import salt.payload
import salt.utils.cache as cache
import salt.utils.data
import salt.utils.files


def test_sanity():
    """
    Make sure you can instantiate etc.
    """
    cd = cache.CacheDict(5)
    assert isinstance(cd, cache.CacheDict)

    # do some tests to make sure it looks like a dict
    assert "foo" not in cd
    cd["foo"] = "bar"
    assert cd["foo"] == "bar"
    del cd["foo"]
    assert "foo" not in cd


def test_ttl():
    cd = cache.CacheDict(0.1)
    cd["foo"] = "bar"
    assert "foo" in cd
    assert cd["foo"] == "bar"
    time.sleep(0.2)
    assert "foo" not in cd

    # make sure that a get would get a regular old key error
    with pytest.raises(KeyError):
        cd["foo"]  # pylint: disable=pointless-statement


@pytest.fixture
def cache_dir(tmp_path):
    cachedir = tmp_path / "cachedir"
    cachedir.mkdir()
    return cachedir


@pytest.fixture
def minion_config(cache_dir):
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["cachedir"] = str(cache_dir)
    return opts


def test_smoke_context(minion_config):
    """
    Smoke test the context cache
    """
    context_cache = cache.ContextCache(minion_config, "cache_test")

    data = {"a": "b"}
    context_cache.cache_context(data.copy())

    ret = context_cache.get_cache_context()

    assert ret == data


@pytest.fixture
def cache_mod_name():
    return "cache_mod"


@pytest.fixture
def cache_mods_path(tmp_path, cache_mod_name):
    _cache_mods_path = tmp_path / "cache_mods"
    mod_contents = """
    import salt.utils.cache

    def __virtual__():
        return True

    @salt.utils.cache.context_cache
    def test_context_module():
        if "called" in __context__:
            __context__["called"] += 1
        else:
            __context__["called"] = 0
        return __context__.value()

    @salt.utils.cache.context_cache
    def test_compare_context():
        return __context__.value()
    """
    with pytest.helpers.temp_file(
        cache_mod_name + ".py", mod_contents, _cache_mods_path
    ):
        yield _cache_mods_path


def test_context_wrapper(minion_config, cache_mods_path):
    """
    Test to ensure that a module which decorates itself
    with a context cache can store and retrieve its contextual
    data
    """

    loader = salt.loader.LazyLoader(
        [str(cache_mods_path)],
        tag="rawmodule",
        virtual_enable=False,
        opts=minion_config,
    )

    cache_test_func = loader["cache_mod.test_context_module"]

    assert cache_test_func()["called"] == 0
    assert cache_test_func()["called"] == 1


def test_set_cache(minion_config, cache_mods_path, cache_mod_name, cache_dir):
    """
    Tests to ensure the cache is written correctly
    """

    context = {"c": "d"}
    loader = salt.loader.LazyLoader(
        [str(cache_mods_path)],
        tag="rawmodule",
        virtual_enable=False,
        opts=minion_config,
        pack={"__context__": context, "__opts__": minion_config},
    )

    cache_test_func = loader["cache_mod.test_context_module"]

    # Call the function to trigger the context cache
    assert cache_test_func()["called"] == 0
    assert cache_test_func()["called"] == 1
    assert cache_test_func()["called"] == 2

    cache_file_name = "salt.loaded.ext.rawmodule.{}.p".format(cache_mod_name)

    cached_file = cache_dir / "context" / cache_file_name
    assert cached_file.exists()

    # Test manual de-serialize
    target_cache_data = salt.utils.data.decode(
        salt.payload.loads(cached_file.read_bytes())
    )
    assert target_cache_data == dict(context, called=1)

    # Test cache de-serialize
    cc = cache.ContextCache(
        minion_config, "salt.loaded.ext.rawmodule.{}".format(cache_mod_name)
    )
    retrieved_cache = cc.get_cache_context()
    assert retrieved_cache == dict(context, called=1)


def test_refill_cache(minion_config, cache_mods_path):
    """
    Tests to ensure that the context cache can rehydrate a wrapped function
    """
    context = {"c": "d"}
    loader = salt.loader.LazyLoader(
        [str(cache_mods_path)],
        tag="rawmodule",
        virtual_enable=False,
        opts=minion_config,
        pack={"__context__": context, "__opts__": minion_config},
    )

    cache_test_func = loader["cache_mod.test_compare_context"]
    # First populate the cache
    ret = cache_test_func()
    assert ret == context

    # Then try to rehydrate a func
    context_copy = context.copy()
    context.clear()

    # Compare to the context before it was emptied
    ret = cache_test_func()
    assert ret == context_copy


def test_everything(tmp_path):
    """
    Make sure you can instantiate, add, update, remove, expire
    """
    path = str(tmp_path / "cachedir")

    # test instantiation
    cd = cache.CacheDisk(0.3, path)
    assert isinstance(cd, cache.CacheDisk)

    # test to make sure it looks like a dict
    assert "foo" not in cd
    cd["foo"] = "bar"
    assert "foo" in cd
    assert cd["foo"] == "bar"
    del cd["foo"]
    assert "foo" not in cd

    # test persistence
    cd["foo"] = "bar"
    cd2 = cache.CacheDisk(0.3, path)
    assert "foo" in cd2
    assert cd2["foo"] == "bar"

    # test ttl
    time.sleep(0.5)
    assert "foo" not in cd
    assert "foo" not in cd2
