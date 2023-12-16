import copy
import time

import pytest

import salt.cache
import salt.utils.vault as vault
import salt.utils.vault.cache as vcache
from tests.support.mock import ANY, Mock, patch


@pytest.fixture
def cbank():
    return "vault/connection"


@pytest.fixture
def ckey():
    return "test"


@pytest.fixture
def data():
    return {"foo": "bar"}


@pytest.fixture
def context(cbank, ckey, data):
    return {cbank: {ckey: data}}


@pytest.fixture
def cached(cache_factory, data):
    cache = Mock(spec=salt.cache.Cache)
    cache.contains.return_value = True
    cache.fetch.return_value = data
    cache.updated.return_value = time.time()
    cache_factory.return_value = cache
    return cache


@pytest.fixture
def cached_outdated(cache_factory, data):
    cache = Mock(spec=salt.cache.Cache)
    cache.contains.return_value = True
    cache.fetch.return_value = data
    cache.updated.return_value = time.time() - 9999999
    cache_factory.return_value = cache
    return cache


@pytest.fixture
def uncached(cache_factory):
    cache = Mock(spec=salt.cache.Cache)
    cache.contains.return_value = False
    cache.fetch.return_value = None
    cache.updated.return_value = None
    cache_factory.return_value = cache
    return cache


@pytest.fixture(autouse=True, params=[0])
def time_stopped(request):
    with patch(
        "salt.utils.vault.cache.time.time", autospec=True, return_value=request.param
    ):
        yield


@pytest.mark.parametrize("connection", [True, False])
@pytest.mark.parametrize(
    "salt_runtype,force_local,expected",
    [
        ("MASTER", False, "vault"),
        ("MASTER_IMPERSONATING", False, "minions/test-minion/vault"),
        ("MASTER_IMPERSONATING", True, "vault"),
        ("MINION_LOCAL", False, "vault"),
        ("MINION_REMOTE", False, "vault"),
    ],
    indirect=["salt_runtype"],
)
def test_get_cache_bank(connection, salt_runtype, force_local, expected):
    """
    Ensure the cache banks are mapped as expected, depending on run type
    """
    opts = {"grains": {"id": "test-minion"}}
    cbank = vcache._get_cache_bank(opts, force_local=force_local, connection=connection)
    if connection:
        expected += "/connection"
    assert cbank == expected


class TestVaultCache:
    @pytest.mark.parametrize("config", ["session", "other"])
    def test_get_uncached(self, config, uncached, cbank, ckey):
        """
        Ensure that unavailable cached data is reported as None.
        """
        cache = vcache.VaultCache(
            {}, cbank, ckey, cache_backend=uncached if config != "session" else None
        )
        res = cache.get()
        assert res is None
        if config != "session":
            uncached.contains.assert_called_once_with(cbank, ckey)

    def test_get_cached_from_context(self, context, cached, cbank, ckey, data):
        """
        Ensure that cached data in __context__ is respected, regardless
        of cache backend.
        """
        cache = vcache.VaultCache(context, cbank, ckey, cache_backend=cached)
        res = cache.get()
        assert res == data
        cached.updated.assert_not_called()
        cached.fetch.assert_not_called()

    def test_get_cached_not_outdated(self, cached, cbank, ckey, data):
        """
        Ensure that cached data that is still valid is returned.
        """
        cache = vcache.VaultCache({}, cbank, ckey, cache_backend=cached, ttl=3600)
        res = cache.get()
        assert res == data
        cached.updated.assert_called_once_with(cbank, ckey)
        cached.fetch.assert_called_once_with(cbank, ckey)

    def test_get_cached_outdated(self, cached_outdated, cbank, ckey):
        """
        Ensure that cached data that is not valid anymore is flushed
        and None is returned by default.
        """
        cache = vcache.VaultCache({}, cbank, ckey, cache_backend=cached_outdated, ttl=1)
        res = cache.get()
        assert res is None
        cached_outdated.updated.assert_called_once_with(cbank, ckey)
        cached_outdated.flush.assert_called_once_with(cbank, ckey)
        cached_outdated.fetch.assert_not_called()

    @pytest.mark.parametrize("config", ["session", "other"])
    def test_flush(self, config, context, cached, cbank, ckey):
        """
        Ensure that flushing clears the context key only and, if
        a cache backend is in use, it is also cleared.
        """
        cache = vcache.VaultCache(
            context, cbank, ckey, cache_backend=cached if config != "session" else None
        )
        cache.flush()
        assert context == {cbank: {}}
        if config != "session":
            cached.flush.assert_called_once_with(cbank, ckey)

    @pytest.mark.parametrize("config", ["session", "other"])
    def test_flush_cbank(self, config, context, cached, cbank, ckey):
        """
        Ensure that flushing with cbank=True clears the context bank and, if
        a cache backend is in use, it is also cleared.
        """
        cache = vcache.VaultCache(
            context, cbank, ckey, cache_backend=cached if config != "session" else None
        )
        cache.flush(cbank=True)
        assert context == {}
        if config != "session":
            cached.flush.assert_called_once_with(cbank, None)

    @pytest.mark.parametrize("context", [{}, {"vault/connection": {}}])
    @pytest.mark.parametrize("config", ["session", "other"])
    def test_store(self, config, context, uncached, cbank, ckey, data):
        """
        Ensure that storing data in cache always updates the context
        and, if a cache backend is in use, it is also stored there.
        """
        cache = vcache.VaultCache(
            context,
            cbank,
            ckey,
            cache_backend=uncached if config != "session" else None,
        )
        cache.store(data)
        assert context == {cbank: {ckey: data}}
        if config != "session":
            uncached.store.assert_called_once_with(cbank, ckey, data)


class TestVaultConfigCache:
    @pytest.fixture(params=["session", "other", None])
    def config(self, request):
        if request.param is None:
            return None
        return {
            "cache": {
                "backend": request.param,
                "config": 3600,
                "secret": "ttl",
            }
        }

    @pytest.fixture
    def data(self, config):
        return {
            "cache": {
                "backend": "new",
                "config": 1337,
                "secret": "ttl",
            }
        }

    @pytest.mark.usefixtures("uncached")
    def test_get_config_cache_uncached(self, cbank, ckey):
        """
        Ensure an uninitialized instance is returned when there is no cache
        """
        res = vault.cache._get_config_cache({}, {}, cbank, ckey)
        assert res.config is None

    def test_get_config_context_cached(self, uncached, cbank, ckey, context):
        """
        Ensure cached data in context wins
        """
        res = vault.cache._get_config_cache({}, context, cbank, ckey)
        assert res.config == context[cbank][ckey]
        uncached.contains.assert_not_called()

    def test_get_config_other_cached(self, cached, cbank, ckey, data):
        """
        Ensure cached data from other sources is respected
        """
        res = vault.cache._get_config_cache({}, {}, cbank, ckey)
        assert res.config == data
        cached.contains.assert_called_once_with(cbank, ckey)
        cached.fetch.assert_called_once_with(cbank, ckey)

    def test_reload(self, config, data, cbank, ckey):
        """
        Ensure that a changed configuration is reloaded correctly and
        during instantiation. When the config backend changes and the
        previous was not session only, it should be flushed.
        """
        with patch("salt.utils.vault.cache.VaultConfigCache.flush") as flush:
            cache = vcache.VaultConfigCache({}, cbank, ckey, {}, init_config=config)
            assert cache.config == config
            if config is not None:
                assert cache.ttl == config["cache"]["config"]
                if config["cache"]["backend"] != "session":
                    assert cache.cache is not None
            else:
                assert cache.ttl is None
                assert cache.cache is None
            cache._load(data)
            assert cache.ttl == data["cache"]["config"]
            assert cache.cache is not None
            if config is not None and config["cache"]["backend"] != "session":
                flush.assert_called_once()

    @pytest.mark.usefixtures("cached")
    def test_exists(self, config, context, cbank, ckey):
        """
        Ensure exists always evaluates to false when uninitialized
        """
        cache = vcache.VaultConfigCache(context, cbank, ckey, {}, init_config=config)
        res = cache.exists()
        assert res is bool(config)

    def test_get(self, config, cached, context, cbank, ckey, data):
        """
        Ensure cached data is returned and backend settings honored,
        unless the instance has not been initialized yet
        """
        if config is not None and config["cache"]["backend"] != "session":
            context = {}
        cache = vcache.VaultConfigCache(context, cbank, ckey, {}, init_config=config)
        res = cache.get()
        if config is not None:
            assert res == data
            if config["cache"]["backend"] != "session":
                cached.fetch.assert_called_once_with(cbank, ckey)
            else:
                cached.contains.assert_not_called()
                cached.fetch.assert_not_called()
        else:
            # uninitialized should always return None
            # initialization when first stored or constructed with init_config
            cached.contains.assert_not_called()
            assert res is None

    def test_flush(self, config, context, cached, cbank, ckey):
        """
        Ensure flushing deletes the whole cache bank (=connection scope),
        unless the configuration has not been initialized.
        Also, it should uninitialize the instance.
        """
        if config is None:
            context_old = copy.deepcopy(context)
        cache = vcache.VaultConfigCache(context, cbank, ckey, {}, init_config=config)
        cache.flush()
        if config is None:
            assert context == context_old
            cached.flush.assert_not_called()
        else:
            if config["cache"]["backend"] == "session":
                assert context == {}
            else:
                cached.flush.assert_called_once_with(cbank, None)
            assert cache.ttl is None
            assert cache.cache is None
            assert cache.config is None

    @pytest.mark.usefixtures("uncached")
    def test_store(self, data, cbank, ckey):
        """
        Ensure storing config in cache also reloads the instance
        """
        cache = vcache.VaultConfigCache({}, {}, cbank, ckey)
        assert cache.config is None
        with patch("salt.utils.vault.cache.VaultConfigCache._load") as rld:
            with patch("salt.utils.vault.cache.VaultCache.store") as store:
                cache.store(data)
                rld.assert_called_once_with(data)
                store.assert_called_once()

    @pytest.mark.parametrize("config", ["other"], indirect=True)
    def test_flush_exceptions_with_flush(self, config, cached, cbank, ckey):
        """
        Ensure internal flushing is disabled when the object is initialized
        with a reference to an exception class.
        """
        cache = vcache.VaultConfigCache(
            {},
            cbank,
            ckey,
            {},
            cache_backend_factory=lambda *args: cached,
            flush_exception=vault.VaultConfigExpired,
            init_config=config,
        )
        with pytest.raises(vault.VaultConfigExpired):
            cache.flush()

    @pytest.mark.parametrize("config", ["other"], indirect=True)
    def test_flush_exceptions_with_get(self, config, cached_outdated, cbank, ckey):
        """
        Ensure internal flushing is disabled when the object is initialized
        with a reference to an exception class.
        """
        cache = vcache.VaultConfigCache(
            {},
            cbank,
            ckey,
            {},
            cache_backend_factory=lambda *args: cached_outdated,
            flush_exception=vault.VaultConfigExpired,
            init_config=config,
        )
        with pytest.raises(vault.VaultConfigExpired):
            cache.get()


class TestVaultAuthCache:
    @pytest.fixture
    def uncached(self):
        with patch(
            "salt.utils.vault.cache.CommonCache._ckey_exists",
            return_value=False,
            autospec=True,
        ):
            with patch(
                "salt.utils.vault.cache.CommonCache._get_ckey",
                return_value=None,
                autospec=True,
            ) as get:
                yield get

    @pytest.fixture
    def cached(self, token_auth):
        with patch(
            "salt.utils.vault.cache.CommonCache._ckey_exists",
            return_value=True,
            autospec=True,
        ):
            with patch(
                "salt.utils.vault.cache.CommonCache._get_ckey",
                return_value=token_auth["auth"],
                autospec=True,
            ) as get:
                yield get

    @pytest.fixture
    def cached_outdated(self, token_auth):
        with patch(
            "salt.utils.vault.cache.CommonCache._ckey_exists",
            return_value=True,
            autospec=True,
        ):
            token_auth["auth"]["creation_time"] = 0
            token_auth["auth"]["lease_duration"] = 1
            with patch(
                "salt.utils.vault.cache.CommonCache._get_ckey",
                return_value=token_auth["auth"],
                autospec=True,
            ) as get:
                yield get

    @pytest.fixture
    def cached_invalid_flush(self, token_auth, cached):
        with patch("salt.utils.vault.cache.CommonCache._flush", autospec=True) as flush:
            token_auth["auth"]["num_uses"] = 1
            token_auth["auth"]["use_count"] = 1
            cached.return_value = token_auth["auth"]
            yield flush

    @pytest.mark.usefixtures("uncached")
    def test_get_uncached(self):
        """
        Ensure that unavailable cached data is reported as None.
        """
        cache = vcache.VaultAuthCache({}, "cbank", "ckey", vault.VaultToken)
        res = cache.get()
        assert res is None

    @pytest.mark.usefixtures("cached")
    def test_get_cached(self, token_auth):
        """
        Ensure that cached data that is still valid is returned.
        """
        cache = vcache.VaultAuthCache({}, "cbank", "ckey", vault.VaultToken)
        res = cache.get()
        assert res is not None
        assert res == vault.VaultToken(**token_auth["auth"])

    def test_get_cached_invalid(self, cached_invalid_flush):
        """
        Ensure that cached data that is not valid anymore is flushed
        and None is returned.
        """
        cache = vcache.VaultAuthCache({}, "cbank", "ckey", vault.VaultToken)
        res = cache.get()
        assert res is None
        cached_invalid_flush.assert_called_once()

    def test_store(self, token_auth):
        """
        Ensure that storing authentication data sends a dictionary
        representation to the store implementation of the parent class.
        """
        token = vault.VaultToken(**token_auth["auth"])
        cache = vcache.VaultAuthCache({}, "cbank", "ckey", vault.VaultToken)
        with patch("salt.utils.vault.cache.CommonCache._store_ckey") as store:
            cache.store(token)
            store.assert_called_once_with("ckey", token.to_dict())

    def test_flush_exceptions_with_flush(self, cached, cbank, ckey):
        """
        Ensure internal flushing is disabled when the object is initialized
        with a reference to an exception class.
        """
        cache = vcache.VaultAuthCache(
            {},
            cbank,
            ckey,
            vault.VaultToken,
            cache_backend=cached,
            flush_exception=vault.VaultAuthExpired,
        )
        with pytest.raises(vault.VaultAuthExpired):
            cache.flush()

    def test_flush_exceptions_with_get(self, cached_outdated, cbank, ckey):
        """
        Ensure internal flushing is disabled when the object is initialized
        with a reference to an exception class.
        """
        cache = vcache.VaultAuthCache(
            {}, cbank, ckey, vault.VaultToken, flush_exception=vault.VaultAuthExpired
        )
        with pytest.raises(vault.VaultAuthExpired):
            cache.get(10)


class TestVaultLeaseCache:
    @pytest.fixture
    def uncached(self):
        with patch(
            "salt.utils.vault.cache.CommonCache._ckey_exists",
            return_value=False,
            autospec=True,
        ):
            with patch(
                "salt.utils.vault.cache.CommonCache._get_ckey",
                return_value=None,
                autospec=True,
            ) as get:
                yield get

    @pytest.fixture
    def cached(self, lease):
        with patch(
            "salt.utils.vault.cache.CommonCache._ckey_exists",
            return_value=True,
            autospec=True,
        ):
            with patch(
                "salt.utils.vault.cache.CommonCache._get_ckey",
                return_value=lease,
                autospec=True,
            ) as get:
                yield get

    @pytest.fixture
    def cached_outdated(self, lease):
        with patch(
            "salt.utils.vault.cache.CommonCache._ckey_exists",
            return_value=True,
            autospec=True,
        ):
            lease["duration"] = 6
            lease["expire_time"] = 6
            with patch(
                "salt.utils.vault.cache.CommonCache._get_ckey",
                return_value=lease,
                autospec=True,
            ) as get:
                yield get

    @pytest.mark.usefixtures("uncached")
    def test_get_uncached(self):
        """
        Ensure that unavailable cached data is reported as None.
        """
        cache = vcache.VaultLeaseCache({}, "cbank")
        res = cache.get("testlease")
        assert res is None

    @pytest.mark.usefixtures("cached")
    def test_get_cached(self, lease):
        """
        Ensure that cached data that is still valid is returned.
        """
        cache = vcache.VaultLeaseCache({}, "cbank")
        res = cache.get("testlease")
        assert res is not None
        assert res == vault.VaultLease(**lease)

    @pytest.mark.usefixtures("cached", "time_stopped")
    @pytest.mark.parametrize("valid_for,expected", ((1, True), (99999999, False)))
    def test_get_cached_valid_for(self, valid_for, expected, lease):
        """
        Ensure that requesting leases with a validity works as expected.
        The lease should be returned if it is valid, otherwise only
        the invalid ckey should be flushed and None returned.
        """
        cache = vcache.VaultLeaseCache({}, "cbank")
        with patch(
            "salt.utils.vault.cache.CommonCache._flush",
            autospec=True,
        ) as flush:
            res = cache.get("testlease", valid_for=valid_for, flush=True)
            if expected:
                flush.assert_not_called()
                assert res is not None
                assert res == vault.VaultLease(**lease)
            else:
                flush.assert_called_once_with(ANY, "testlease")
                assert res is None

    def test_store(self, lease):
        """
        Ensure that storing authentication data sends a dictionary
        representation to the store implementation of the parent class.
        """
        lease_ = vault.VaultLease(**lease)
        cache = vcache.VaultLeaseCache({}, "cbank")
        with patch("salt.utils.vault.cache.CommonCache._store_ckey") as store:
            cache.store("ckey", lease_)
            store.assert_called_once_with("ckey", lease_.to_dict())

    def test_expire_events_with_get(self, events, cached_outdated, cbank, ckey, lease):
        """
        Ensure internal flushing is disabled when the object is initialized
        with a reference to an exception class.
        """
        cache = vcache.VaultLeaseCache({}, "cbank", expire_events=events)
        ret = cache.get("ckey", 10)
        assert ret is None
        events.assert_called_once_with(
            tag="vault/lease/ckey/expire", data={"valid_for_less": 10}
        )
