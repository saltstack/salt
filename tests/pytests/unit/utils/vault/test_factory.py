import copy

import pytest

import salt.exceptions
import salt.utils.vault as vault
import salt.utils.vault.cache as vcache
import salt.utils.vault.client as vclient
import salt.utils.vault.factory as factory
from tests.pytests.unit.utils.vault.conftest import _mock_json_response
from tests.support.mock import ANY, MagicMock, Mock, patch


class TestGetAuthdClient:
    @pytest.fixture
    def client_valid(self):
        client = Mock(spec=vclient.AuthenticatedVaultClient)
        client.token_valid.return_value = True
        return client

    @pytest.fixture
    def client_invalid(self):
        client = Mock(spec=vclient.AuthenticatedVaultClient)
        client.token_valid.return_value = False
        return client

    @pytest.fixture
    def client_renewable(self):
        client = Mock(spec=vclient.AuthenticatedVaultClient)
        client.auth.get_token.return_value.is_renewable.return_value = True
        client.auth.get_token.return_value.is_valid.return_value = False
        client.token_valid.return_value = True
        return client

    @pytest.fixture
    def client_unrenewable(self):
        client = Mock(spec=vclient.AuthenticatedVaultClient)
        client.auth.get_token.return_value.is_renewable.return_value = False
        client.auth.get_token.return_value.is_valid.return_value = False
        client.token_valid.side_effect = (False, True)
        return client

    @pytest.fixture
    def client_renewable_max_ttl(self):
        client = Mock(spec=vclient.AuthenticatedVaultClient)
        client.auth.get_token.return_value.is_renewable.return_value = True
        client.auth.get_token.return_value.is_valid.return_value = False
        client.token_valid.side_effect = (False, True)
        return client

    @pytest.fixture(
        params=[
            {"auth": {"token_lifecycle": {"minimum_ttl": 10, "renew_increment": False}}}
        ]
    )
    def build_succeeds(self, client_valid, request):
        with patch(
            "salt.utils.vault.factory._build_authd_client", autospec=True
        ) as build:
            build.return_value = (client_valid, request.param)
            yield build

    @pytest.fixture(
        params=["VaultAuthExpired", "VaultConfigExpired", "VaultPermissionDeniedError"]
    )
    def build_fails(self, request):
        exception = request.param
        with patch(
            "salt.utils.vault.factory._build_authd_client", autospec=True
        ) as build:
            build.side_effect = getattr(vault, exception)
            yield build

    @pytest.fixture(
        params=["VaultAuthExpired", "VaultConfigExpired", "VaultPermissionDeniedError"]
    )
    def build_exception_first(self, client_valid, request):
        exception = request.param
        with patch(
            "salt.utils.vault.factory._build_authd_client", autospec=True
        ) as build:
            build.side_effect = (
                getattr(vault, exception),
                (
                    client_valid,
                    {
                        "auth": {
                            "token_lifecycle": {
                                "minimum_ttl": 10,
                                "renew_increment": False,
                            }
                        }
                    },
                ),
            )
            yield build

    @pytest.fixture(
        params=[
            {"auth": {"token_lifecycle": {"minimum_ttl": 10, "renew_increment": False}}}
        ]
    )
    def build_invalid_first(self, client_valid, client_invalid, request):
        with patch(
            "salt.utils.vault.factory._build_authd_client", autospec=True
        ) as build:
            build.side_effect = (
                (client_invalid, request.param),
                (client_valid, request.param),
            )
            yield build

    @pytest.fixture(
        params=[
            {"auth": {"token_lifecycle": {"minimum_ttl": 10, "renew_increment": 60}}}
        ]
    )
    def build_renewable(self, client_renewable, request):
        with patch(
            "salt.utils.vault.factory._build_authd_client", autospec=True
        ) as build:
            build.return_value = (client_renewable, request.param)
            yield build

    @pytest.fixture(
        params=[
            {"auth": {"token_lifecycle": {"minimum_ttl": 10, "renew_increment": 60}}}
        ]
    )
    def build_unrenewable(self, client_unrenewable, request):
        with patch(
            "salt.utils.vault.factory._build_authd_client", autospec=True
        ) as build:
            build.return_value = (client_unrenewable, request.param)
            yield build

    @pytest.fixture(
        params=[
            {"auth": {"token_lifecycle": {"minimum_ttl": 10, "renew_increment": 60}}}
        ]
    )
    def build_renewable_max_ttl(self, client_renewable_max_ttl, request):
        with patch(
            "salt.utils.vault.factory._build_authd_client", autospec=True
        ) as build:
            build.return_value = (client_renewable_max_ttl, request.param)
            yield build

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        with patch("salt.utils.vault.factory.clear_cache", autospec=True) as clear:
            clear.return_value = True
            yield clear

    @pytest.mark.parametrize("get_config", [False, True])
    def test_get_authd_client_succeeds(self, build_succeeds, clear_cache, get_config):
        """
        Ensure a valid client is returned directly without clearing cache.
        """
        client = vault.get_authd_client({}, {}, get_config=get_config)
        if get_config:
            client, config = client
        client.token_valid.assert_called_with(10, remote=False)
        assert client.token_valid()
        clear_cache.assert_not_called()
        assert build_succeeds.call_count == 1
        if get_config:
            assert config == {
                "auth": {
                    "token_lifecycle": {"minimum_ttl": 10, "renew_increment": False}
                }
            }

    @pytest.mark.parametrize("get_config", [False, True])
    def test_get_authd_client_invalid(
        self, build_invalid_first, clear_cache, get_config, client_invalid
    ):
        """
        Ensure invalid clients are not returned but rebuilt after
        clearing cache.
        """
        client = vault.get_authd_client({}, {}, get_config=get_config)
        if get_config:
            client, config = client
        client_invalid.token_valid.assert_called_with(10, remote=False)
        assert client.token_valid()
        clear_cache.assert_called_once_with({}, ANY, force_local=False, session=True)
        assert build_invalid_first.call_count == 2
        if get_config:
            assert config == {
                "auth": {
                    "token_lifecycle": {"minimum_ttl": 10, "renew_increment": False}
                }
            }

    @pytest.mark.parametrize("get_config", [False, True])
    @pytest.mark.parametrize(
        "build_exception_first,session",
        (
            ("VaultAuthExpired", True),
            ("VaultConfigExpired", False),
            ("VaultPermissionDeniedError", False),
        ),
        indirect=["build_exception_first"],
    )
    def test_get_authd_client_exception(
        self, build_exception_first, session, clear_cache, get_config
    ):
        """
        Ensure relevant exceptions are caught, cache is cleared and
        new credentials are requested.
        """
        client = vault.get_authd_client({}, {}, get_config=get_config)
        if get_config:
            client, config = client
        client.token_valid.assert_called_with(10, remote=False)
        assert client.token_valid()
        if session:
            clear_cache.assert_called_once_with(
                {}, ANY, force_local=False, session=session
            )
        else:
            clear_cache.assert_called_once_with(
                {}, ANY, force_local=False, connection=True
            )
        assert build_exception_first.call_count == 2
        if get_config:
            assert config == {
                "auth": {
                    "token_lifecycle": {"minimum_ttl": 10, "renew_increment": False}
                }
            }

    def test_get_authd_client_unwrap_exception(self, events):
        """
        Ensure unwrap exceptions are re-raised, but an event is sent
        warning about the potential tampering
        """

        def raise_unwrap(*args, **kwargs):
            raise factory.VaultUnwrapException(
                "foo", "bar", "vaulturl", "namespace", "verify"
            )

        with patch(
            "salt.utils.vault.factory._get_event", autospec=True, return_value=events
        ):
            with patch(
                "salt.utils.vault.factory._build_authd_client", autospec=True
            ) as build:
                build.side_effect = raise_unwrap
                with pytest.raises(factory.VaultUnwrapException):
                    vault.get_authd_client({}, {})
            events.assert_called_once_with(
                data={
                    "expected": "foo",
                    "actual": "bar",
                    "url": "vaulturl",
                    "namespace": "namespace",
                    "verify": "verify",
                },
                tag="vault/security/unwrapping/error",
            )

    def test_get_authd_client_fails(self, build_fails, clear_cache):
        """
        Ensure exceptions are leaked after one retry.
        """
        with pytest.raises(build_fails.side_effect):
            vault.get_authd_client({}, {})
            clear_cache.assert_called_once()

    @pytest.mark.usefixtures("build_renewable")
    def test_get_authd_client_renews_token(self, clear_cache):
        """
        Ensure renewable tokens are renewed when necessary.
        """
        client = vault.get_authd_client({}, {}, get_config=False)
        client.token_renew.assert_called_once_with(increment=60)
        clear_cache.assert_not_called()

    @pytest.mark.usefixtures("build_unrenewable")
    def test_get_authd_client_unrenewable_new_token(self, clear_cache):
        """
        Ensure minimum_ttl is respected such that a new token is requested,
        even though the current one would still be valid for some time.
        """
        client = vault.get_authd_client({}, {}, get_config=False)
        client.token_renew.assert_not_called()
        clear_cache.assert_called_once()

    @pytest.mark.usefixtures("build_renewable_max_ttl")
    def test_get_authd_client_renewable_token_max_ttl_insufficient(
        self, build_renewable_max_ttl, clear_cache
    ):
        """
        Ensure minimum_ttl is respected when a token can be renewed, but the
        new ttl does not satisfy it.
        """
        client = vault.get_authd_client({}, {}, get_config=False)
        client.token_renew.assert_called_once_with(increment=60)
        clear_cache.assert_called_once()


class TestBuildAuthdClient:
    @pytest.fixture(autouse=True)
    def cbank(self):
        with patch("salt.utils.vault.cache._get_cache_bank", autospec=True) as cbank:
            cbank.return_value = "vault"
            yield cbank

    @pytest.fixture(autouse=True)
    def conn_config(self):
        with patch(
            "salt.utils.vault.factory._get_connection_config", autospec=True
        ) as conn_config:
            yield conn_config

    @pytest.fixture(autouse=True)
    def fetch_secret_id(self, secret_id_response):
        with patch(
            "salt.utils.vault.factory._fetch_secret_id", autospec=True
        ) as fetch_secret_id:
            fetch_secret_id.return_value = vault.VaultSecretId(
                **secret_id_response["data"]
            )
            yield fetch_secret_id

    @pytest.fixture(autouse=True)
    def fetch_token(self, token_auth):
        with patch(
            "salt.utils.vault.factory._fetch_token", autospec=True
        ) as fetch_token:
            fetch_token.return_value = vault.VaultToken(**token_auth["auth"])
            yield fetch_token

    @pytest.fixture(params=["token", "secret_id", "both", "none"])
    def cached(self, token_auth, secret_id_response, request):
        cached_what = request.param
        # Save a reference to the original class since it will be
        # mocked when _cache is called
        vauth_cache = vcache.VaultAuthCache

        def _cache(context, cbank, ckey, *args, **kwargs):
            token = Mock(spec=vauth_cache)
            token.get.return_value = None
            approle = Mock(spec=vauth_cache)
            approle.get.return_value = None
            if cached_what in ["token", "both"]:
                token.get.return_value = vault.VaultToken(**token_auth["auth"])
            if cached_what in ["secret_id", "both"]:
                approle.get.return_value = vault.VaultSecretId(
                    **secret_id_response["data"]
                )
            return token if ckey == factory.TOKEN_CKEY else approle

        cache = MagicMock(spec=vcache.VaultAuthCache)
        cache.side_effect = _cache
        with patch("salt.utils.vault.cache.VaultAuthCache", cache):
            yield cache

    @pytest.mark.parametrize(
        "test_remote_config",
        ["token", "approle", "approle_no_secretid", "approle_wrapped_roleid"],
        indirect=True,
    )
    def test_build_authd_client(
        self, test_remote_config, conn_config, fetch_secret_id, cached
    ):
        """
        Ensure credentials are only requested if necessary.
        """
        conn_config.return_value = (test_remote_config, None, Mock())
        client, config = factory._build_authd_client({}, {})
        assert client.token_valid(remote=False)
        if test_remote_config["auth"]["method"] == "approle":
            if (
                not test_remote_config["auth"]["secret_id"]
                or cached(None, None, factory.TOKEN_CKEY).get()
                or cached(None, None, "secret_id").get()
            ):
                # In case a secret_id is not necessary or only a cached token is available,
                # make sure we do not request a new secret ID from the master
                fetch_secret_id.assert_not_called()
            else:
                fetch_secret_id.assert_called_once()


class TestGetConnectionConfig:
    @pytest.fixture
    def cached(self, test_remote_config):
        cache = Mock(spec=vcache.VaultConfigCache)
        # cached config does not include tokens
        test_remote_config["auth"].pop("token", None)
        cache.get.return_value = test_remote_config
        with patch(
            "salt.utils.vault.cache._get_config_cache", autospec=True
        ) as cfactory:
            cfactory.return_value = cache
            yield cache

    @pytest.fixture
    def uncached(self):
        cache = Mock(spec=vcache.VaultConfigCache)
        cache.get.return_value = None
        with patch(
            "salt.utils.vault.cache._get_config_cache", autospec=True
        ) as cfactory:
            cfactory.return_value = cache
            yield cache

    @pytest.fixture
    def local(self):
        with patch(
            "salt.utils.vault.factory._use_local_config", autospec=True
        ) as local:
            yield local

    @pytest.fixture
    def remote(self, test_remote_config, unauthd_client_mock):
        with patch("salt.utils.vault.factory._query_master") as query:
            query.return_value = (test_remote_config, unauthd_client_mock)
            yield query

    @pytest.mark.parametrize(
        "salt_runtype,force_local",
        [
            ("MASTER", False),
            ("MASTER_IMPERSONATING", True),
            ("MINION_LOCAL", False),
        ],
        indirect=["salt_runtype"],
    )
    def test_get_connection_config_local(self, salt_runtype, force_local, local):
        """
        Ensure the local configuration is used when
        a) running on master
        b) running on master impersonating a minion when called from runner
        c) running on minion in local mode
        """
        factory._get_connection_config("vault", {}, {}, force_local=force_local)
        local.assert_called_once()

    def test_get_connection_config_cached(self, cached, remote, test_remote_config):
        """
        Ensure cache is respected
        """
        res, embedded_token, _ = factory._get_connection_config("vault", {}, {})
        assert res == test_remote_config
        assert embedded_token is None
        cached.store.assert_not_called()
        remote.assert_not_called()

    def test_get_connection_config_uncached(self, uncached, remote):
        """
        Ensure uncached configuration is treated as expected, especially
        that the embedded token is removed and returned separately.
        """
        res, embedded_token, _ = factory._get_connection_config("vault", {}, {})
        uncached.store.assert_called_once()
        remote.assert_called_once()
        data, _ = remote()
        token = data["auth"].pop("token", None)
        assert res == data
        assert embedded_token == token

    @pytest.mark.usefixtures("uncached", "local")
    @pytest.mark.parametrize("test_remote_config", ["token"], indirect=True)
    @pytest.mark.parametrize(
        "conf_location,called",
        [("local", False), ("master", True), (None, False), ("doesnotexist", False)],
    )
    def test_get_connection_config_location(self, conf_location, called, remote):
        """
        test the _get_connection_config function when
        config_location is set in opts
        """
        opts = {"vault": {"config_location": conf_location}, "file_client": "local"}
        if conf_location == "doesnotexist":
            with pytest.raises(
                salt.exceptions.InvalidConfigError,
                match=".*config_location must be either local or master.*",
            ):
                factory._get_connection_config("vault", opts, {})
        else:
            factory._get_connection_config("vault", opts, {})
            if called:
                remote.assert_called()
            else:
                remote.assert_not_called()

    def test_get_connection_config_update(self, cached, remote, test_remote_config):
        """
        Ensure updating connection config works without clearing the session
        """
        updated_remote_config = copy.deepcopy(test_remote_config)
        updated_remote_config["cache"]["clear_on_unauthorized"] = False
        remote.return_value = (updated_remote_config, remote.return_value[1])
        res, embedded_token, _ = factory._get_connection_config(
            "vault", {}, {}, update=True
        )
        assert res == updated_remote_config
        assert embedded_token is None
        remote.assert_called_once_with(
            "get_config", {}, issue_params=None, config_only=True
        )
        cached.flush.assert_called_once_with(cbank=False)
        cached.store.assert_called_once_with(updated_remote_config)

    @pytest.mark.parametrize("test_remote_config", ["token"], indirect=True)
    def test_get_connection_config_update_server(
        self, cached, remote, test_remote_config
    ):
        """
        Ensure updating connection config does not work without clearing
        the session if fundamental details have changed
        """
        updated_remote_config = copy.deepcopy(test_remote_config)
        updated_remote_config["server"]["url"] = "https://vault.new-url.com"
        remote.return_value = (updated_remote_config, remote.return_value[1])
        with pytest.raises(vault.VaultConfigExpired):
            res, embedded_token, _ = factory._get_connection_config(
                "vault", {}, {}, update=True
            )
        self._assert_not_updated(remote, cached)

    @pytest.mark.parametrize("test_remote_config", ["token"], indirect=True)
    def test_get_connection_config_update_auth_method(
        self, cached, remote, test_remote_config
    ):
        """
        Ensure updating connection config does not work without clearing
        the session if fundamental details have changed
        """
        updated_remote_config = copy.deepcopy(test_remote_config)
        updated_remote_config["auth"]["method"] = "approle"
        updated_remote_config["auth"]["role_id"] = "test-role-id"
        remote.return_value = (updated_remote_config, remote.return_value[1])
        with pytest.raises(vault.VaultConfigExpired):
            res, embedded_token, _ = factory._get_connection_config(
                "vault", {}, {}, update=True
            )
        self._assert_not_updated(remote, cached)

    @pytest.mark.parametrize("test_remote_config", ["token"], indirect=True)
    def test_get_connection_config_update_cache_backend(
        self, cached, remote, test_remote_config
    ):
        """
        Ensure updating connection config does not work without clearing
        the session if fundamental details have changed
        """
        updated_remote_config = copy.deepcopy(test_remote_config)
        updated_remote_config["cache"]["backend"] = "disk"
        remote.return_value = (updated_remote_config, remote.return_value[1])
        with pytest.raises(vault.VaultConfigExpired):
            res, embedded_token, _ = factory._get_connection_config(
                "vault", {}, {}, update=True
            )
        self._assert_not_updated(remote, cached)

    @pytest.mark.parametrize("test_remote_config", ["approle"], indirect=True)
    def test_get_connection_config_update_role_id(
        self, cached, remote, test_remote_config
    ):
        """
        Ensure updating connection config does not work without clearing
        the session if fundamental details have changed
        """
        updated_remote_config = copy.deepcopy(test_remote_config)
        updated_remote_config["auth"]["role_id"] = "new_role"
        remote.return_value = (updated_remote_config, remote.return_value[1])
        with pytest.raises(vault.VaultConfigExpired):
            res, embedded_token, _ = factory._get_connection_config(
                "vault", {}, {}, update=True
            )
        self._assert_not_updated(remote, cached)

    @pytest.mark.parametrize("test_remote_config", ["approle"], indirect=True)
    def test_get_connection_config_update_bind_secret_id(
        self, cached, remote, test_remote_config
    ):
        """
        Ensure updating connection config does not work without clearing
        the session if fundamental details have changed
        """
        test_remote_config["auth"]["secret_id"] = True
        updated_remote_config = copy.deepcopy(test_remote_config)
        updated_remote_config["auth"]["secret_id"] = False
        remote.return_value = (updated_remote_config, remote.return_value[1])
        with pytest.raises(vault.VaultConfigExpired):
            res, embedded_token, _ = factory._get_connection_config(
                "vault", {}, {}, update=True
            )
        self._assert_not_updated(remote, cached)

    def _assert_not_updated(self, remote, cached):
        remote.assert_called_once_with(
            "get_config", {}, issue_params=None, config_only=True
        )
        cached.flush.assert_not_called()
        cached.store.assert_not_called()


class TestFetchSecretId:
    @pytest.fixture
    def cached(self, secret_id_response):
        cache = Mock(spec=vcache.VaultAuthCache)
        cache.get.return_value = vault.VaultSecretId(**secret_id_response["data"])
        return cache

    @pytest.fixture
    def uncached(self):
        cache = Mock(spec=vcache.VaultConfigCache)
        cache.get.return_value = None
        return cache

    @pytest.fixture
    def remote(self, secret_id_response, server_config, unauthd_client_mock):
        with patch("salt.utils.vault.factory._query_master") as query:
            query.return_value = (
                {"data": secret_id_response["data"], "server": server_config},
                unauthd_client_mock,
            )
            yield query

    @pytest.fixture
    def local(self):
        with patch(
            "salt.utils.vault.factory._use_local_config", autospec=True
        ) as local:
            yield local

    @pytest.fixture(params=["plain", "wrapped", "dict"])
    def secret_id(self, secret_id_response, wrapped_secret_id_response, request):
        ret = {
            "plain": "test-secret-id",
            "wrapped": {"wrap_info": wrapped_secret_id_response["wrap_info"]},
            "dict": secret_id_response["data"],
        }
        return ret[request.param]

    @pytest.mark.parametrize("test_remote_config", ["approle"], indirect=True)
    @pytest.mark.parametrize(
        "salt_runtype,force_local",
        [
            ("MASTER", False),
            ("MASTER_IMPERSONATING", True),
            ("MINION_LOCAL", False),
        ],
        indirect=["salt_runtype"],
    )
    def test_fetch_secret_id_local(
        self,
        salt_runtype,
        force_local,
        uncached,
        test_remote_config,
        secret_id,
        secret_id_response,
        unauthd_client_mock,
    ):
        """
        Ensure the local configuration is used when
        a) running on master
        b) running on master impersonating a minion when called from runner
        c) running on minion in local mode
        Also ensure serialized or wrapped secret ids are resolved.
        """
        test_remote_config["auth"]["secret_id"] = secret_id
        unauthd_client_mock.unwrap.return_value = secret_id_response
        res = factory._fetch_secret_id(
            test_remote_config,
            {},
            uncached,
            unauthd_client_mock,
            force_local=force_local,
        )
        if not isinstance(secret_id, str):
            if "wrap_info" not in secret_id:
                unauthd_client_mock.unwrap.assert_not_called()
            else:
                secret_id = secret_id_response["data"]
            assert res == vault.VaultSecretId(**secret_id)
        else:
            assert res == vault.VaultSecretId(
                secret_id=secret_id,
                secret_id_ttl=0,
                secret_id_num_uses=0,
            )
        uncached.get.assert_not_called()
        uncached.store.assert_not_called()

    @pytest.mark.parametrize("test_remote_config", ["approle"], indirect=True)
    def test_fetch_secret_id_cached(
        self, test_remote_config, cached, remote, unauthd_client_mock
    ):
        """
        Ensure cache is respected
        """
        res = factory._fetch_secret_id(
            test_remote_config, {}, cached, unauthd_client_mock
        )
        assert res == cached.get()
        cached.store.assert_not_called()
        remote.assert_not_called()

    @pytest.mark.parametrize("test_remote_config", ["approle"], indirect=True)
    def test_fetch_secret_id_uncached(
        self, test_remote_config, uncached, remote, unauthd_client_mock
    ):
        """
        Ensure requested credentials are cached and returned as data objects
        """
        res = factory._fetch_secret_id(
            test_remote_config, {}, uncached, unauthd_client_mock
        )
        uncached.store.assert_called_once()
        remote.assert_called_once()
        data, _ = remote()
        assert res == vault.VaultSecretId(**data["data"])

    @pytest.mark.parametrize("test_remote_config", ["approle"], indirect=True)
    def test_fetch_secret_id_uncached_single_use(
        self,
        test_remote_config,
        uncached,
        remote,
        secret_id_response,
        server_config,
        unauthd_client_mock,
    ):
        """
        Check that single-use secret ids are not cached
        """
        secret_id_response["data"]["secret_id_num_uses"] = 1
        remote.return_value = (
            {
                "data": secret_id_response["data"],
                "server": server_config,
            },
            unauthd_client_mock,
        )
        res = factory._fetch_secret_id(
            test_remote_config, {}, uncached, unauthd_client_mock
        )
        uncached.store.assert_not_called()
        remote.assert_called_once()
        data, _ = remote()
        assert res == vault.VaultSecretId(**data["data"])

    @pytest.mark.usefixtures("local")
    @pytest.mark.parametrize("test_remote_config", ["approle"], indirect=True)
    @pytest.mark.parametrize(
        "conf_location,called",
        [("local", False), ("master", True), (None, False), ("doesnotexist", False)],
    )
    def test_fetch_secret_id_config_location(
        self,
        conf_location,
        called,
        remote,
        uncached,
        test_remote_config,
        unauthd_client_mock,
    ):
        """
        Ensure config_location is respected.
        """
        test_remote_config["config_location"] = conf_location
        opts = {"vault": test_remote_config, "file_client": "local"}
        if conf_location == "doesnotexist":
            with pytest.raises(
                salt.exceptions.InvalidConfigError,
                match=".*config_location must be either local or master.*",
            ):
                factory._fetch_secret_id(
                    test_remote_config, opts, uncached, unauthd_client_mock
                )
        else:
            factory._fetch_secret_id(
                test_remote_config, opts, uncached, unauthd_client_mock
            )
            if called:
                remote.assert_called()
            else:
                remote.assert_not_called()


class TestFetchToken:
    @pytest.fixture
    def cached(self, token_auth):
        cache = Mock(spec=vcache.VaultAuthCache)
        cache.get.return_value = vault.VaultToken(**token_auth["auth"])
        return cache

    @pytest.fixture
    def uncached(self):
        cache = Mock(spec=vcache.VaultConfigCache)
        cache.get.return_value = None
        return cache

    @pytest.fixture
    def remote(self, token_auth, server_config, unauthd_client_mock):
        with patch("salt.utils.vault.factory._query_master", autospec=True) as query:
            query.return_value = (
                {"auth": token_auth["auth"], "server": server_config},
                unauthd_client_mock,
            )
            yield query

    @pytest.fixture
    def local(self):
        with patch(
            "salt.utils.vault.factory._use_local_config", autospec=True
        ) as local:
            yield local

    @pytest.fixture(params=["plain", "wrapped", "dict"])
    def token(self, token_auth, wrapped_token_auth_response, request):
        ret = {
            "plain": token_auth["auth"]["client_token"],
            "wrapped": {"wrap_info": wrapped_token_auth_response["wrap_info"]},
            "dict": token_auth["auth"],
        }
        return ret[request.param]

    @pytest.mark.parametrize(
        "test_remote_config", ["token", "wrapped_token"], indirect=True
    )
    @pytest.mark.parametrize(
        "salt_runtype,force_local",
        [
            ("MASTER", False),
            ("MASTER_IMPERSONATING", True),
            ("MINION_LOCAL", False),
        ],
        indirect=["salt_runtype"],
    )
    def test_fetch_token_local(
        self,
        salt_runtype,
        force_local,
        uncached,
        test_remote_config,
        unauthd_client_mock,
        token,
        token_auth,
        token_lookup_self_response,
    ):
        """
        Ensure the local configuration is used when
        a) running on master
        b) running on master impersonating a minion when called from runner
        c) running on minion in local mode
        Also ensure serialized or wrapped tokens are resolved and plain tokens
        are looked up.
        Also ensure only plain token metadata is cached.
        """
        test_remote_config["auth"].pop("token", None)
        unauthd_client_mock.unwrap.return_value = token_auth
        unauthd_client_mock.token_lookup.return_value = _mock_json_response(
            token_lookup_self_response, status_code=200
        )
        res = factory._fetch_token(
            test_remote_config,
            {},
            uncached,
            unauthd_client_mock,
            force_local=force_local,
            embedded_token=token,
        )
        if not isinstance(token, str):
            unauthd_client_mock.token_lookup.assert_not_called()
            if "wrap_info" not in token:
                unauthd_client_mock.unwrap.assert_not_called()
            else:
                token = token_auth["auth"]
            assert res == vault.VaultToken(**token)
        elif test_remote_config["auth"]["method"] == "wrapped_token":
            unauthd_client_mock.unwrap.assert_called_once()
            unauthd_client_mock.token_lookup.assert_not_called()
            token = token_auth["auth"]
            assert res == vault.VaultToken(**token)
        else:
            unauthd_client_mock.unwrap.assert_not_called()
            unauthd_client_mock.token_lookup.assert_called_once()
            assert res == vault.VaultToken(
                client_token=token,
                lease_duration=token_lookup_self_response["data"]["ttl"],
                **token_lookup_self_response["data"],
            )
        if not isinstance(token, str):
            uncached.get.assert_not_called()
            uncached.store.assert_not_called()
        else:
            uncached.get.assert_called_once()
            uncached.store.assert_called_once()

    @pytest.mark.parametrize(
        "test_remote_config", ["token", "token_changed"], indirect=True
    )
    @pytest.mark.parametrize(
        "salt_runtype,force_local",
        [
            ("MASTER", False),
            ("MASTER_IMPERSONATING", True),
            ("MINION_LOCAL", False),
        ],
        indirect=["salt_runtype"],
    )
    def test_fetch_token_local_cached_changed(
        self,
        salt_runtype,
        force_local,
        cached,
        test_remote_config,
        token_lookup_self_response,
        unauthd_client_mock,
    ):
        """
        Test that only when the embedded plain token changed, the token metadata
        cache is written/refreshed.
        """
        embedded_token = test_remote_config["auth"].pop("token")
        # with patch("salt.utils.vault.VaultClient.token_lookup") as token_lookup:
        unauthd_client_mock.token_lookup.return_value = _mock_json_response(
            token_lookup_self_response, status_code=200
        )
        res = factory._fetch_token(
            test_remote_config,
            {},
            cached,
            unauthd_client_mock,
            force_local=force_local,
            embedded_token=embedded_token,
        )
        if embedded_token == "test-token":
            unauthd_client_mock.token_lookup.assert_not_called()
            assert res == cached.get()
        elif embedded_token == "test-token-changed":
            unauthd_client_mock.token_lookup.assert_called_once()
            assert res == vault.VaultToken(
                lease_id=embedded_token,
                lease_duration=token_lookup_self_response["data"]["ttl"],
                **token_lookup_self_response["data"],
            )

    @pytest.mark.parametrize(
        "test_remote_config", ["token", "wrapped_token"], indirect=True
    )
    def test_fetch_token_cached(
        self, test_remote_config, cached, remote, unauthd_client_mock
    ):
        """
        Ensure that cache is respected
        """
        res = factory._fetch_token(test_remote_config, {}, cached, unauthd_client_mock)
        assert res == cached.get()
        cached.store.assert_not_called()
        remote.assert_not_called()

    @pytest.mark.parametrize("test_remote_config", ["token"], indirect=True)
    def test_fetch_token_uncached_embedded(
        self, test_remote_config, uncached, remote, token_auth, unauthd_client_mock
    ):
        """
        Test that tokens that were sent with the connection configuration
        are used when no cached token is available
        """
        test_remote_config["auth"].pop("token", None)
        res = factory._fetch_token(
            test_remote_config,
            {},
            uncached,
            unauthd_client_mock,
            embedded_token=token_auth["auth"],
        )
        uncached.store.assert_called_once()
        remote.assert_not_called()
        assert res == vault.VaultToken(**token_auth["auth"])

    @pytest.mark.parametrize("test_remote_config", ["token"], indirect=True)
    def test_fetch_token_uncached(
        self, test_remote_config, uncached, remote, unauthd_client_mock
    ):
        """
        Test that tokens that were sent with the connection configuration
        are used when no cached token is available
        """
        test_remote_config["auth"].pop("token", None)
        res = factory._fetch_token(
            test_remote_config, {}, uncached, unauthd_client_mock
        )
        uncached.store.assert_called_once()
        remote.assert_called_once()
        assert res == vault.VaultToken(**remote.return_value[0]["auth"])

    @pytest.mark.parametrize("test_remote_config", ["token"], indirect=True)
    def test_fetch_token_uncached_single_use(
        self,
        test_remote_config,
        uncached,
        remote,
        token_auth,
        server_config,
        unauthd_client_mock,
    ):
        """
        Check that single-use tokens are not cached
        """
        token_auth["auth"]["num_uses"] = 1
        remote.return_value = (
            {"auth": token_auth["auth"], "server": server_config},
            unauthd_client_mock,
        )
        res = factory._fetch_token(
            test_remote_config, {}, uncached, unauthd_client_mock
        )
        uncached.store.assert_not_called()
        remote.assert_called_once()
        assert res == vault.VaultToken(**remote.return_value[0]["auth"])

    @pytest.mark.usefixtures("local")
    @pytest.mark.parametrize("test_remote_config", ["token"], indirect=True)
    @pytest.mark.parametrize(
        "conf_location,called",
        [("local", False), ("master", True), (None, False), ("doesnotexist", False)],
    )
    def test_fetch_token_config_location(
        self,
        conf_location,
        called,
        remote,
        uncached,
        test_remote_config,
        token_auth,
        unauthd_client_mock,
    ):
        """
        Ensure config_location is respected.
        """
        test_remote_config["config_location"] = conf_location
        opts = {"vault": test_remote_config, "file_client": "local"}
        embedded_token = token_auth["auth"] if not called else None
        if conf_location == "doesnotexist":
            with pytest.raises(
                salt.exceptions.InvalidConfigError,
                match=".*config_location must be either local or master.*",
            ):
                factory._fetch_token(
                    test_remote_config,
                    opts,
                    uncached,
                    unauthd_client_mock,
                    embedded_token=embedded_token,
                )
        else:
            factory._fetch_token(
                test_remote_config,
                opts,
                uncached,
                unauthd_client_mock,
                embedded_token=embedded_token,
            )
            if called:
                remote.assert_called()
            else:
                remote.assert_not_called()


class TestQueryMaster:
    @pytest.fixture(autouse=True)
    def publish_runner(self):
        with patch("salt.modules.publish.runner", autospec=True) as runner:
            runner.return_value = {"success": True}
            with patch("salt.utils.context.func_globals_inject"):
                yield runner

    @pytest.fixture(autouse=True)
    def saltutil_runner(self):
        with patch("salt.modules.saltutil.runner", autospec=True) as runner:
            runner.return_value = {"success": True}
            with patch("salt.utils.context.func_globals_inject"):
                yield runner

    @pytest.fixture(autouse=True, scope="class")
    def b64encode_sig(self):
        with patch("base64.b64encode", Mock(return_value="signature")):
            yield

    @pytest.fixture(autouse=True, scope="class")
    def salt_crypt(self):
        with patch("salt.crypt.sign_message", Mock(return_value="signature")):
            yield

    @pytest.fixture(params=["minion"])
    def opts(self, request):
        if request.param == "no_role":
            return {
                "grains": {"id": "test-minion"},
                "pki_dir": "/var/cache/salt/minion",
            }
        return {
            "__role": request.param,
            "grains": {"id": "test-minion"},
            "pki_dir": f"/var/cache/salt/{request.param}",
        }

    @pytest.fixture(params=["data"])
    def unwrap_client(self, server_config, request, unauthd_client_mock):
        # We're requesting unauthd_client_mock here because if it's not requested
        # first, its spec will be sourced from a MagicMock (and fail in Python >=3.11)
        with patch(
            "salt.utils.vault.client.VaultClient", autospec=True
        ) as unwrap_client:
            unwrap_client.return_value.get_config.return_value = server_config
            unwrap_client.return_value.unwrap.return_value = {
                request.param: {"bar": "baz"}
            }
            yield unwrap_client

    @pytest.mark.parametrize(
        "opts,expected",
        [
            ("master", "saltutil"),
            ("minion", "publish"),
            ("no_role", "publish"),
        ],
        indirect=["opts"],
    )
    def test_query_master_uses_correct_module(
        self, opts, expected, publish_runner, saltutil_runner
    ):
        """
        Ensure that the correct module to call the vault runner is used:
        minion - publish.runner
        master impersonating - saltutil.runner
        """
        out, _ = factory._query_master("func", opts)
        assert out == {"success": True}
        if expected == "saltutil":
            publish_runner.assert_not_called()
            saltutil_runner.assert_called_once()
        else:
            publish_runner.assert_called_once()
            saltutil_runner.assert_not_called()

    @pytest.mark.parametrize("response", [None, False, {}, "f", {"error": "error"}])
    def test_query_master_validates_response(
        self, opts, response, publish_runner, saltutil_runner
    ):
        """
        Ensure that falsey return values invalidate config (auth method change)
        or reported errors by the master are recognized and raised
        """
        publish_runner.return_value = saltutil_runner.return_value = response
        if not response:
            with pytest.raises(vault.VaultConfigExpired):
                factory._query_master("func", opts)
        else:
            with pytest.raises(salt.exceptions.CommandExecutionError):
                factory._query_master("func", opts)

    @pytest.mark.parametrize(
        "response", [{"expire_cache": True}, {"error": {"error"}, "expire_cache": True}]
    )
    def test_query_master_invalidates_cache_when_requested_by_master(
        self, opts, response, publish_runner, saltutil_runner
    ):
        """
        Ensure that "expire_cache" set to True invalidates cache
        """
        publish_runner.return_value = saltutil_runner.return_value = response
        with pytest.raises(vault.VaultConfigExpired):
            factory._query_master("func", opts)

    @pytest.mark.parametrize(
        "url,verify,namespace",
        [
            ("new-url", None, None),
            ("http://127.0.0.1:8200", "/etc/ssl/certs.pem", None),
            ("http://127.0.0.1:8200", None, "test-namespace"),
        ],
    )
    def test_query_master_invalidates_cache_when_expected_server_differs(
        self,
        opts,
        url,
        verify,
        namespace,
        server_config,
        wrapped_role_id_response,
        unauthd_client_mock,
        unwrap_client,
        publish_runner,
        saltutil_runner,
        caplog,
    ):
        """
        Ensure that VaultConfigExpired is raised when a passed unwrap client has a different
        server configuration than the master reports. Also ensure that the unwrapping
        still takes place (for security reasons) and with the correct server configuration.
        """
        ret = {
            "server": {"url": url, "verify": verify, "namespace": namespace},
            "wrap_info": wrapped_role_id_response["wrap_info"],
        }
        publish_runner.return_value = saltutil_runner.return_value = ret
        with pytest.raises(vault.VaultConfigExpired):
            factory._query_master("func", opts, unwrap_client=unauthd_client_mock)
            assert "Mismatch of cached and reported server data detected" in caplog.text
            # this one gets discarded because it's outdated
            unauthd_client_mock.unwrap.assert_not_called()
            # this one contains the reported server config
            unwrap_client.assert_called_once_with(ret)
            # ensure the issued secret is not left for anyone to take
            unwrap_client.unwrap.assert_called_once()

    def test_query_master_local_verify_does_not_interfere_with_expected_server(
        self,
        opts,
        publish_runner,
        saltutil_runner,
        wrapped_role_id_response,
        role_id_response,
        unwrap_client,
        unauthd_client_mock,
        caplog,
    ):
        """
        Ensure that a locally configured verify parameter is inserted before
        checking if there is a config mismatch.
        """
        publish_runner.return_value = saltutil_runner.return_value = {
            "server": {
                "url": "http://127.0.0.1:8200",
                "verify": None,
                "namespace": None,
            },
            "wrap_info": wrapped_role_id_response["wrap_info"],
        }
        expected_server = {
            "url": "http://127.0.0.1:8200",
            "verify": "/etc/ssl/certs.pem",
            "namespace": None,
        }
        opts["vault"] = {"server": {"verify": "/etc/ssl/certs.pem"}}

        unauthd_client_mock.get_config.return_value = expected_server
        unauthd_client_mock.unwrap.return_value = role_id_response
        ret, _ = factory._query_master("func", opts, unwrap_client=unauthd_client_mock)
        assert "Mismatch of cached and reported server data detected" not in caplog.text
        # ensure the client was not replaced
        unwrap_client.assert_not_called()
        unauthd_client_mock.unwrap.assert_called_once()
        assert ret == {
            "data": role_id_response["data"],
            "server": expected_server,
        }

    @pytest.mark.parametrize(
        "unauthd_client_mock,key",
        [
            ("data", "data"),
            ("auth", "auth"),
        ],
        indirect=["unauthd_client_mock"],
    )
    def test_query_master_merges_unwrapped_result(
        self,
        opts,
        publish_runner,
        saltutil_runner,
        wrapped_role_id_response,
        unauthd_client_mock,
        key,
        server_config,
    ):
        """
        Ensure that "data"/"auth" keys from unwrapped result are correctly merged
        """
        publish_runner.return_value = saltutil_runner.return_value = {
            "server": server_config,
            "wrap_info": wrapped_role_id_response["wrap_info"],
        }
        out, _ = factory._query_master("func", opts, unwrap_client=unauthd_client_mock)
        assert "wrap_info" not in out
        assert key in out
        assert out[key] == {"bar": "baz"}

    @pytest.mark.parametrize("unauthd_client_mock", ["data", "auth"], indirect=True)
    def test_query_master_merges_nested_unwrapped_result(
        self,
        opts,
        publish_runner,
        saltutil_runner,
        wrapped_role_id_response,
        unauthd_client_mock,
        server_config,
    ):
        """
        Ensure that "data"/"auth" keys from unwrapped results of nested
        wrapped responses are correctly merged
        """
        publish_runner.return_value = saltutil_runner.return_value = {
            "server": server_config,
            "wrap_info_nested": ["auth:role_id"],
            "auth": {"role_id": {"wrap_info": wrapped_role_id_response["wrap_info"]}},
        }
        out, _ = factory._query_master("func", opts, unwrap_client=unauthd_client_mock)
        assert "wrap_info_nested" not in out
        assert "wrap_info" not in out["auth"]["role_id"]
        assert out["auth"]["role_id"] == {"bar": "baz"}

    @pytest.mark.parametrize("misc_data", ["secret_id_num_uses", "secret_id_ttl"])
    @pytest.mark.parametrize("key", ["auth", "data"])
    def test_query_master_merges_misc_data(
        self, opts, publish_runner, saltutil_runner, secret_id_response, misc_data, key
    ):
        """
        Ensure that "misc_data" is merged into "data"/"auth" only if the key is not
        set there.
        This is used to provide miscellaneous information that might only be
        easily available to the master (such as secret_id_num_uses, which is
        not reported in the secret ID generation response currently and would
        consume a token use for the minion to look up).
        """
        response = {
            key: secret_id_response["data"],
            "misc_data": {misc_data: "merged"},
        }
        publish_runner.return_value = saltutil_runner.return_value = copy.deepcopy(
            response
        )
        out, _ = factory._query_master("func", opts)
        assert misc_data in out[key]
        assert "misc_data" not in out
        if misc_data in secret_id_response["data"]:
            assert out[key][misc_data] == secret_id_response["data"][misc_data]
        else:
            assert out[key][misc_data] == "merged"

    @pytest.mark.parametrize("misc_data", ["nested:value", "nested:num_uses"])
    @pytest.mark.parametrize("key", ["auth", "data"])
    def test_query_master_merges_misc_data_recursively(
        self, opts, publish_runner, saltutil_runner, misc_data, key
    ):
        """
        Ensure that "misc_data" is merged recursively into "data"/"auth" only if
        the key is not set there.
        This is used to provide miscellaneous information that might only be
        easily available to the master (such as num_uses for old vault versions,
        which is not reported in the token generation response there and would
        consume a token use for the minion to look up).
        """
        response = {
            key: {"nested": {"value": "existing"}},
            "misc_data": {misc_data: "merged"},
        }
        publish_runner.return_value = saltutil_runner.return_value = copy.deepcopy(
            response
        )
        out, _ = factory._query_master("func", opts)
        nested_key = misc_data.split(":")[1]
        assert nested_key in out[key]["nested"]
        assert "misc_data" not in out
        if nested_key in response[key]["nested"]:
            assert out[key]["nested"][nested_key] == "existing"
        else:
            assert out[key]["nested"][nested_key] == "merged"


class TestBuildRevocationClient:
    @pytest.fixture(params=[False, True], autouse=True)
    def config(self, test_remote_config, request):
        cache = Mock(spec=vcache.VaultConfigCache)
        if request.param:
            cache.get.return_value = test_remote_config
        else:
            cache.get.return_value = None
        with patch(
            "salt.utils.vault.cache._get_config_cache", autospec=True
        ) as cfactory:
            cfactory.return_value = cache
            yield cache

    @pytest.fixture(params=[False, None, True])
    def token(self, token_auth, request):
        with patch("salt.utils.vault.cache.VaultAuthCache", autospec=True) as cache:
            if request.param:
                cache.return_value.get.return_value = vault.VaultToken(
                    **token_auth["auth"]
                )
            else:
                cache.return_value.get.return_value = None
            yield cache

    def test_build_revocation_client_never_calls_master_for_config(self):
        with patch("salt.utils.vault.factory._query_master") as query:
            factory._build_revocation_client({}, {})
            query.assert_not_called()

    @pytest.mark.parametrize("config", [True], indirect=True)
    def test_build_revocation_client_never_calls_master_for_token(
        self, token, test_remote_config
    ):
        with patch("salt.utils.vault.factory._query_master") as query:
            res = factory._build_revocation_client({}, {})
            query.assert_not_called()
            if token.return_value.get.return_value is not None:
                assert isinstance(res[0], vclient.AuthenticatedVaultClient)
                assert res[1] == test_remote_config
            else:
                assert res == (None, None)


@pytest.mark.parametrize("ckey", ["token", None])
@pytest.mark.parametrize("connection", [True, False])
@pytest.mark.parametrize("session", [True, False])
def test_clear_cache(ckey, connection, session, cache_factory):
    """
    Make sure clearing cache works as expected, allowing for
    connection-scoped cache and global cache that survives
    a configuration refresh
    """
    cbank = "vault"
    if connection or session:
        cbank += "/connection"
    if session:
        cbank += "/session"
    context = {cbank: {"token": "fake_token"}}
    with patch(
        "salt.utils.vault.factory._build_revocation_client", autospec=True
    ) as revoc:
        revoc.return_value = (None, None)
        vault.clear_cache(
            {}, context, ckey=ckey, connection=connection, session=session
        )
    cache_factory.return_value.flush.assert_called_once_with(cbank, ckey)
    if ckey:
        assert ckey not in context[cbank]
    else:
        assert cbank not in context


@pytest.mark.parametrize("ckey", ["token", None])
@pytest.mark.parametrize("connection", [True, False])
@pytest.mark.parametrize("session", [True, False])
def test_clear_cache_clears_client_from_context(
    ckey, connection, session, cache_factory
):
    """
    Ensure the cached client is removed when the connection cache is altered only
    """
    cbank = "vault/connection"
    context = {cbank: {factory.CLIENT_CKEY: "foo"}}
    with patch(
        "salt.utils.vault.factory._build_revocation_client", autospec=True
    ) as revoc:
        revoc.return_value = (None, None)
        vault.clear_cache(
            {}, context, ckey=ckey, connection=connection, session=session
        )
    if session or (not connection and ckey):
        assert factory.CLIENT_CKEY in context.get(cbank, {})
    else:
        assert factory.CLIENT_CKEY not in context.get(cbank, {})


@pytest.mark.parametrize(
    "test_config,expected_config,expected_token",
    [
        (
            "token",
            {
                "auth": {
                    "approle_mount": "approle",
                    "approle_name": "salt-master",
                    "method": "token",
                    "secret_id": None,
                    "token_lifecycle": {
                        "minimum_ttl": 10,
                        "renew_increment": None,
                    },
                },
                "cache": {
                    "backend": "session",
                    "clear_attempt_revocation": 60,
                    "clear_on_unauthorized": True,
                    "config": 3600,
                    "expire_events": False,
                    "secret": "ttl",
                },
                "server": {
                    "url": "http://127.0.0.1:8200",
                    "namespace": None,
                    "verify": None,
                },
            },
            "test-token",
        ),
        (
            "approle",
            {
                "auth": {
                    "approle_mount": "approle",
                    "approle_name": "salt-master",
                    "method": "approle",
                    "role_id": "test-role-id",
                    "secret_id": "test-secret-id",
                    "token_lifecycle": {
                        "minimum_ttl": 10,
                        "renew_increment": None,
                    },
                },
                "cache": {
                    "backend": "session",
                    "clear_attempt_revocation": 60,
                    "clear_on_unauthorized": True,
                    "config": 3600,
                    "expire_events": False,
                    "secret": "ttl",
                },
                "server": {
                    "url": "http://127.0.0.1:8200",
                    "namespace": None,
                    "verify": None,
                },
            },
            None,
        ),
    ],
    indirect=["test_config"],
)
def test_use_local_config(test_config, expected_config, expected_token):
    """
    Ensure that _use_local_config only returns auth, cache, server scopes
    and pops an embedded token, if present
    """
    with patch("salt.utils.vault.factory.parse_config", Mock(return_value=test_config)):
        output, token, _ = factory._use_local_config({})
        assert output == expected_config
        assert token == expected_token


@pytest.mark.parametrize(
    "config,expected",
    [
        ({"auth": {"method": "token", "token": "test-token"}}, "server:url"),
        ({"auth": {"method": "token"}, "server": {"url": "test-url"}}, "auth:token"),
        (
            {"auth": {"method": "approle"}, "server": {"url": "test-url"}},
            "auth:role_id",
        ),
        (
            {"auth": {"method": "foo"}, "server": {"url": "test-url"}},
            "not a valid auth method",
        ),
    ],
)
def test_parse_config_ensures_necessary_values(config, expected):
    """
    Ensure that parse_config validates the configuration
    """
    with pytest.raises(salt.exceptions.InvalidConfigError, match=f".*{expected}.*"):
        factory.parse_config(config)


@pytest.mark.parametrize(
    "opts",
    [
        {"vault": {"server": {"verify": "/etc/ssl/certs/ca-certificates.crt"}}},
        {"vault": {"verify": "/etc/ssl/certs/ca-certificates.crt"}},
    ],
)
def test_parse_config_respects_local_verify(opts):
    """
    Ensure locally configured verify values are respected.
    """
    testval = "/etc/ssl/certs/ca-certificates.crt"
    ret = factory.parse_config(
        {"server": {"verify": "default"}}, validate=False, opts=opts
    )
    assert ret["server"]["verify"] == testval


############################################
# Deprecation tests
############################################


@pytest.mark.parametrize(
    "old,new",
    [
        ("policies", "policies:assign"),
        ("auth:ttl", "issue:token:params:explicit_max_ttl"),
        ("auth:uses", "issue:token:params:num_uses"),
        ("url", "server:url"),
        ("namespace", "server:namespace"),
        ("verify", "server:verify"),
        ("role_name", "issue:token:role_name"),
        ("auth:token_backend", "cache:backend"),
        ("auth:allow_minion_override", "issue:allow_minion_override_params"),
    ],
)
def test_get_config_recognizes_old_config(old, new):
    """
    Ensure that parse_config recognizes the old configuration format
    and translates it to new equivalents correctly.
    """

    def rec(config, path, val=None):
        ptr = config
        parts = path.split(":")
        while parts:
            cur = parts.pop(0)
            if val:
                if parts and not isinstance(ptr.get(cur), dict):
                    ptr[cur] = {}
                elif not parts:
                    ptr[cur] = val
                    return
            ptr = ptr[cur]
        return ptr

    config = {
        "auth": {
            "token": "test-token",
        },
        "server": {
            "url": "test-url",
        },
    }

    oldval = "oldval" if old != "policies" else ["oldval"]
    rec(config, old, oldval)
    parsed = factory.parse_config(config)
    assert rec(parsed, new) == oldval
