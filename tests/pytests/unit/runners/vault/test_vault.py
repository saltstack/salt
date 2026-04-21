import pytest

import salt.exceptions
import salt.runners.vault as vault
import salt.utils.vault as vaultutil
import salt.utils.vault.api as vapi
import salt.utils.vault.client as vclient
from tests.support.mock import ANY, MagicMock, Mock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        vault: {
            "__grains__": {"id": "test-master"},
        }
    }


@pytest.fixture
def default_config():
    return {
        "auth": {
            "approle_mount": "approle",
            "approle_name": "salt-master",
            "method": "token",
            "token": "test-token",
            "role_id": "test-role-id",
            "secret_id": None,
            "token_lifecycle": {
                "minimum_ttl": 10,
                "renew_increment": None,
            },
        },
        "cache": {
            "backend": "session",
            "config": 3600,
            "kv_metadata": "connection",
            "secret": "ttl",
        },
        "issue": {
            "allow_minion_override_params": False,
            "type": "token",
            "approle": {
                "mount": "salt-minions",
                "params": {
                    "bind_secret_id": True,
                    "secret_id_num_uses": 1,
                    "secret_id_ttl": 60,
                    "token_explicit_max_ttl": 9999999999,
                    "token_num_uses": 1,
                },
            },
            "token": {
                "role_name": None,
                "params": {
                    "explicit_max_ttl": 9999999999,
                    "num_uses": 1,
                },
            },
            "wrap": "30s",
        },
        "issue_params": {},
        "metadata": {
            "entity": {
                "minion-id": "{minion}",
            },
            "secret": {
                "saltstack-jid": "{jid}",
                "saltstack-minion": "{minion}",
                "saltstack-user": "{user}",
            },
        },
        "policies": {
            "assign": [
                "saltstack/minions",
                "saltstack/{minion}",
            ],
            "cache_time": 60,
            "refresh_pillar": None,
        },
        "server": {
            "url": "http://test-vault:8200",
            "namespace": None,
            "verify": None,
        },
    }


@pytest.fixture
def token_response():
    return {
        "request_id": "0e8c388e-2cb6-bcb2-83b7-625127d568bb",
        "lease_id": "",
        "lease_duration": 0,
        "renewable": False,
        "auth": {
            "client_token": "test-token",
            "renewable": True,
            "lease_duration": 9999999999,
            "num_uses": 1,
            "creation_time": 1661188581,
            # "expire_time": 11661188580,
        },
    }


@pytest.fixture
def secret_id_response():
    return {
        "request_id": "0e8c388e-2cb6-bcb2-83b7-625127d568bb",
        "lease_id": "",
        "lease_duration": 0,
        "renewable": False,
        "data": {
            "secret_id_accessor": "84896a0c-1347-aa90-a4f6-aca8b7558780",
            "secret_id": "841771dc-11c9-bbc7-bcac-6a3945a69cd9",
            "secret_id_ttl": 60,
        },
    }


@pytest.fixture
def wrapped_response():
    return {
        "request_id": "",
        "lease_id": "",
        "lease_duration": 0,
        "renewable": False,
        "data": None,
        "warnings": None,
        "wrap_info": {
            "token": "test-wrapping-token",
            "accessor": "test-wrapping-token-accessor",
            "ttl": 180,
            "creation_time": "2022-09-10T13:37:12.123456789+00:00",
            "creation_path": "whatever/not/checked/here",
            "wrapped_accessor": "84896a0c-1347-aa90-a4f6-aca8b7558780",
        },
    }


@pytest.fixture
def token_serialized(token_response):
    return {
        "client_token": token_response["auth"]["client_token"],
        "renewable": token_response["auth"]["renewable"],
        "lease_duration": token_response["auth"]["lease_duration"],
        "num_uses": token_response["auth"]["num_uses"],
        "creation_time": token_response["auth"]["creation_time"],
        # "expire_time": token_response["auth"]["expire_time"],
    }


@pytest.fixture
def secret_id_serialized(secret_id_response):
    return {
        "secret_id": secret_id_response["data"]["secret_id"],
        "secret_id_ttl": secret_id_response["data"]["secret_id_ttl"],
        "secret_id_num_uses": 1,
        # + creation_time
        # + expire_time
    }


@pytest.fixture
def wrapped_serialized(wrapped_response):
    return {
        "wrap_info": {
            "token": wrapped_response["wrap_info"]["token"],
            "ttl": wrapped_response["wrap_info"]["ttl"],
            "creation_time": 1662817032,
            "creation_path": wrapped_response["wrap_info"]["creation_path"],
        },
    }


@pytest.fixture
def approle_meta(token_serialized, secret_id_serialized):
    return {
        "bind_secret_id": True,
        "local_secret_ids": False,
        "secret_id_bound_cidrs": [],
        "secret_id_num_uses": secret_id_serialized["secret_id_num_uses"],
        "secret_id_ttl": secret_id_serialized["secret_id_ttl"],
        "token_bound_cidrs": [],
        "token_explicit_max_ttl": token_serialized["lease_duration"],
        "token_max_ttl": 0,
        "token_no_default_policy": False,
        "token_num_uses": token_serialized["num_uses"],
        "token_period": 0,
        "token_policies": ["default"],
        "token_ttl": 0,
        "token_type": "default",
    }


@pytest.fixture
def policies_default():
    return ["saltstack/minions", "saltstack/minion/test-minion"]


@pytest.fixture
def metadata_secret_default():
    return {
        "saltstack-jid": "<no jid set>",
        "saltstack-minion": "test-minion",
        "saltstack-user": "<no user set>",
    }


@pytest.fixture
def metadata_entity_default():
    return {"minion-id": "test-minion"}


@pytest.fixture
def grains():
    return {
        "id": "test-minion",
        "roles": ["web", "database"],
        "aux": ["foo", "bar"],
        "deep": {"foo": {"bar": {"baz": ["hello", "world"]}}},
        "mixedcase": "UP-low-UP",
    }


@pytest.fixture
def pillar():
    return {
        "mixedcase": "UP-low-UP",
        "role": "test",
    }


@pytest.fixture
def client():
    with patch("salt.runners.vault._get_master_client", autospec=True) as get_client:
        client = Mock(spec=vclient.AuthenticatedVaultClient)
        get_client.return_value = client
        yield client


@pytest.fixture
def approle_api():
    with patch("salt.runners.vault._get_approle_api", autospec=True) as get_api:
        api = Mock(spec=vapi.AppRoleApi)
        get_api.return_value = api
        yield api


@pytest.fixture
def identity_api():
    with patch("salt.runners.vault._get_identity_api", autospec=True) as get_api:
        api = Mock(spec=vapi.IdentityApi)
        get_api.return_value = api
        yield api


@pytest.fixture
def client_token(client, token_response, wrapped_response):
    def res_or_wrap(*args, **kwargs):
        if kwargs.get("wrap"):
            return vaultutil.VaultWrappedResponse(**wrapped_response["wrap_info"])
        return token_response

    client.post.side_effect = res_or_wrap
    yield client


@pytest.fixture
def config(request, default_config):
    def rec(config, path, val=None, default=vaultutil.VaultException):
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
            if cur not in ptr:
                if isinstance(default, Exception):
                    raise default()
                return default
            ptr = ptr[cur]
        return ptr

    def get_config(key=None, default=vaultutil.VaultException):
        overrides = getattr(request, "param", {})
        if key is None:
            for ovar, oval in overrides.items():
                rec(default_config, ovar, oval)
            return default_config
        if key in overrides:
            return overrides[key]
        return rec(default_config, key, default=default)

    with patch("salt.runners.vault._config", autospec=True) as config:
        config.side_effect = get_config
        yield config


@pytest.fixture
def policies(request, policies_default):
    policies_list = getattr(request, "param", policies_default)
    with patch(
        "salt.runners.vault._get_policies_cached", autospec=True
    ) as get_policies_cached:
        get_policies_cached.return_value = policies_list
        with patch("salt.runners.vault._get_policies", autospec=True) as get_policies:
            get_policies.return_value = policies_list
            yield


@pytest.fixture
def metadata(request, metadata_entity_default, metadata_secret_default):
    def _get_metadata(minion_id, metadata_patterns, *args, **kwargs):
        if getattr(request, "param", None) is not None:
            return request.param
        if "saltstack-jid" not in metadata_patterns:
            return metadata_entity_default
        return metadata_secret_default

    with patch("salt.runners.vault._get_metadata", autospec=True) as get_metadata:
        get_metadata.side_effect = _get_metadata
        yield get_metadata


@pytest.fixture
def validate_signature():
    with patch(
        "salt.runners.vault._validate_signature", autospec=True, return_value=None
    ) as validate:
        yield validate


@pytest.mark.usefixtures("policies", "metadata")
@pytest.mark.parametrize(
    "config",
    [{}, {"issue:token:role_name": "test-role"}, {"issue:wrap": False}],
    indirect=True,
)
def test_generate_token(
    client_token,
    config,
    policies_default,
    token_serialized,
    wrapped_serialized,
    metadata_secret_default,
):
    """
    Ensure _generate_token calls the API as expected
    """
    wrap = config("issue:wrap")
    res_token, res_num_uses = vault._generate_token(
        "test-minion", issue_params=None, wrap=wrap
    )
    endpoint = "auth/token/create"
    role_name = config("issue:token:role_name")
    payload = {}
    if config("issue:token:params:explicit_max_ttl"):
        payload["explicit_max_ttl"] = config("issue:token:params:explicit_max_ttl")
    if config("issue:token:params:num_uses"):
        payload["num_uses"] = config("issue:token:params:num_uses")
    payload["meta"] = metadata_secret_default
    payload["policies"] = policies_default
    if role_name:
        endpoint += f"/{role_name}"
    if config("issue:wrap"):
        assert res_token == wrapped_serialized
        client_token.post.assert_called_once_with(
            endpoint, payload=payload, wrap=config("issue:wrap")
        )
    else:
        res_token.pop("expire_time")
        assert res_token == token_serialized
    assert res_num_uses == 1


@pytest.mark.usefixtures("config")
@pytest.mark.parametrize("policies", [[]], indirect=True)
def test_generate_token_no_policies_denied(policies):
    """
    Ensure generated tokens need at least one attached policy
    """
    with pytest.raises(
        salt.exceptions.SaltRunnerError, match=".*No policies matched minion.*"
    ):
        vault._generate_token("test-minion", issue_params=None, wrap=False)


@pytest.mark.parametrize("ttl", [None, 1337])
@pytest.mark.parametrize("uses", [None, 1, 30])
@pytest.mark.parametrize("config", [{}, {"issue:type": "approle"}], indirect=True)
def test_generate_token_deprecated(
    ttl, uses, token_serialized, config, validate_signature, caplog
):
    """
    Ensure the deprecated generate_token function returns data in the old format
    """
    issue_params = {}
    if ttl is not None:
        token_serialized["lease_duration"] = ttl
        issue_params["explicit_max_ttl"] = ttl
    if uses is not None:
        token_serialized["num_uses"] = uses
        issue_params["num_uses"] = uses
    expected = {
        "token": token_serialized["client_token"],
        "lease_duration": token_serialized["lease_duration"],
        "renewable": token_serialized["renewable"],
        "issued": token_serialized["creation_time"],
        "url": config("server:url"),
        "verify": config("server:verify"),
        "token_backend": config("cache:backend"),
        "namespace": config("server:namespace"),
        "uses": token_serialized["num_uses"],
    }
    with patch("salt.runners.vault._generate_token", autospec=True) as gen:
        gen.return_value = (token_serialized, token_serialized["num_uses"])
        res = vault.generate_token("test-minion", "sig", ttl=ttl, uses=uses)
        validate_signature.assert_called_once_with("test-minion", "sig", False)
        assert res == expected
        gen.assert_called_once_with(
            "test-minion", issue_params=issue_params or None, wrap=False
        )
        if config("issue:type") != "token":
            assert "Master is not configured to issue tokens" in caplog.text


@pytest.mark.parametrize("config", [{}, {"issue:wrap": False}], indirect=True)
@pytest.mark.parametrize(
    "issue_params", [None, {"explicit_max_ttl": 120, "num_uses": 3}]
)
def test_generate_new_token(
    issue_params, config, validate_signature, token_serialized, wrapped_serialized
):
    """
    Ensure generate_new_token returns data as expected
    """
    if issue_params is not None:
        if issue_params.get("explicit_max_ttl") is not None:
            token_serialized["lease_duration"] = issue_params["explicit_max_ttl"]
        if issue_params.get("num_uses") is not None:
            token_serialized["num_uses"] = issue_params["num_uses"]
    expected = {"server": config("server"), "auth": {}}
    if config("issue:wrap"):
        expected.update(wrapped_serialized)
        expected.update({"misc_data": {"num_uses": token_serialized["num_uses"]}})
    else:
        expected["auth"] = token_serialized

    with patch("salt.runners.vault._generate_token", autospec=True) as gen:

        def res_or_wrap(*args, **kwargs):
            if kwargs.get("wrap"):
                return wrapped_serialized, token_serialized["num_uses"]
            return token_serialized, token_serialized["num_uses"]

        gen.side_effect = res_or_wrap
        res = vault.generate_new_token("test-minion", "sig", issue_params=issue_params)
        validate_signature.assert_called_once_with("test-minion", "sig", False)
        assert res == expected
        gen.assert_called_once_with(
            "test-minion", issue_params=issue_params or None, wrap=config("issue:wrap")
        )


@pytest.mark.usefixtures("validate_signature")
@pytest.mark.parametrize("config", [{"issue:type": "approle"}], indirect=True)
def test_generate_new_token_refuses_if_not_configured(config):
    """
    Ensure generate_new_token only issues tokens if configured to issue them
    """
    res = vault.generate_new_token("test-minion", "sig")
    assert "error" in res
    assert "Master does not issue tokens" in res["error"]


@pytest.mark.parametrize("config", [{}, {"issue:wrap": False}], indirect=True)
@pytest.mark.parametrize(
    "issue_params", [None, {"explicit_max_ttl": 120, "num_uses": 3}]
)
def test_get_config_token(
    config, validate_signature, token_serialized, wrapped_serialized, issue_params
):
    """
    Ensure get_config returns data in the expected format when configured for token auth
    """
    expected = {
        "auth": {
            "method": "token",
            "token_lifecycle": {
                "minimum_ttl": 10,
                "renew_increment": None,
            },
        },
        "cache": config("cache"),
        "server": config("server"),
        "wrap_info_nested": [],
    }

    if issue_params is not None:
        if issue_params.get("explicit_max_ttl") is not None:
            token_serialized["lease_duration"] = issue_params["explicit_max_ttl"]
        if issue_params.get("num_uses") is not None:
            token_serialized["num_uses"] = issue_params["num_uses"]
    if config("issue:wrap"):
        expected["auth"].update({"token": wrapped_serialized})
        expected.update(
            {
                "wrap_info_nested": ["auth:token"],
                "misc_data": {"token:num_uses": token_serialized["num_uses"]},
            }
        )
    else:
        expected["auth"].update({"token": token_serialized})

    with patch("salt.runners.vault._generate_token", autospec=True) as gen:

        def res_or_wrap(*args, **kwargs):
            if kwargs.get("wrap"):
                return wrapped_serialized, token_serialized["num_uses"]
            return token_serialized, token_serialized["num_uses"]

        gen.side_effect = res_or_wrap
        res = vault.get_config("test-minion", "sig", issue_params=issue_params)
        validate_signature.assert_called_once_with("test-minion", "sig", False)
        assert res == expected
        gen.assert_called_once_with(
            "test-minion", issue_params=issue_params or None, wrap=config("issue:wrap")
        )


@pytest.mark.parametrize(
    "config",
    [
        {"issue:type": "approle"},
        {
            "issue:type": "approle",
            "issue:wrap": False,
            "issue:approle:mount": "test-mount",
        },
        {"issue:type": "approle", "issue:approle:params:bind_secret_id": False},
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "issue_params",
    [
        None,
        {"token_explicit_max_ttl": 120, "token_num_uses": 3},
        {"secret_id_num_uses": 2, "secret_id_ttl": 120},
    ],
)
def test_get_config_approle(
    config, validate_signature, wrapped_serialized, issue_params
):
    """
    Ensure get_config returns data in the expected format when configured for AppRole auth
    """
    expected = {
        "auth": {
            "approle_mount": config("issue:approle:mount"),
            "approle_name": "test-minion",
            "method": "approle",
            "secret_id": config("issue:approle:params:bind_secret_id"),
            "token_lifecycle": {
                "minimum_ttl": 10,
                "renew_increment": None,
            },
        },
        "cache": config("cache"),
        "server": config("server"),
        "wrap_info_nested": [],
    }

    if config("issue:wrap"):
        expected["auth"].update({"role_id": wrapped_serialized})
        expected.update({"wrap_info_nested": ["auth:role_id"]})
    else:
        expected["auth"].update({"role_id": "test-role-id"})

    with patch("salt.runners.vault._get_role_id", autospec=True) as gen:

        def res_or_wrap(*args, **kwargs):
            if kwargs.get("wrap"):
                return wrapped_serialized
            return "test-role-id"

        gen.side_effect = res_or_wrap
        res = vault.get_config("test-minion", "sig", issue_params=issue_params)
        validate_signature.assert_called_once_with("test-minion", "sig", False)
        assert res == expected
        gen.assert_called_once_with(
            "test-minion", issue_params=issue_params or None, wrap=config("issue:wrap")
        )


@pytest.mark.parametrize(
    "config",
    [{"issue:type": "approle"}, {"issue:type": "approle", "issue:wrap": False}],
    indirect=True,
)
@pytest.mark.parametrize(
    "issue_params",
    [
        None,
        {"token_explicit_max_ttl": 120, "token_num_uses": 3},
        {"secret_id_num_uses": 2, "secret_id_ttl": 120},
    ],
)
def test_get_role_id(config, validate_signature, wrapped_serialized, issue_params):
    """
    Ensure get_role_id returns data in the expected format
    """
    expected = {"server": config("server"), "data": {}}
    if config("issue:wrap"):
        expected.update(wrapped_serialized)
    else:
        expected["data"].update({"role_id": "test-role-id"})
    with patch("salt.runners.vault._get_role_id", autospec=True) as gen:

        def res_or_wrap(*args, **kwargs):
            if kwargs.get("wrap"):
                return wrapped_serialized
            return "test-role-id"

        gen.side_effect = res_or_wrap
        res = vault.get_role_id("test-minion", "sig", issue_params=issue_params)
        validate_signature.assert_called_once_with("test-minion", "sig", False)
        assert res == expected
        gen.assert_called_once_with(
            "test-minion", issue_params=issue_params or None, wrap=config("issue:wrap")
        )


@pytest.mark.usefixtures("validate_signature")
@pytest.mark.parametrize("config", [{"issue:type": "token"}], indirect=True)
def test_get_role_id_refuses_if_not_configured(config):
    """
    Ensure get_role_id returns an error if not configured to issue AppRoles
    """
    res = vault.get_role_id("test-minion", "sig")
    assert "error" in res
    assert "Master does not issue AppRoles" in res["error"]


class TestGetRoleId:
    @pytest.fixture(autouse=True)
    def lookup_approle(self, approle_meta):
        with patch(
            "salt.runners.vault._lookup_approle_cached", autospec=True
        ) as lookup_approle:
            lookup_approle.return_value = approle_meta
            yield lookup_approle

    @pytest.fixture(autouse=True)
    def lookup_roleid(self, wrapped_serialized):
        role_id = MagicMock(return_value="test-role-id")
        role_id.serialize_for_minion.return_value = wrapped_serialized
        with patch(
            "salt.runners.vault._lookup_role_id", autospec=True
        ) as lookup_roleid:
            lookup_roleid.return_value = role_id
            yield lookup_roleid

    @pytest.fixture(autouse=True)
    def manage_approle(self):
        with patch(
            "salt.runners.vault._manage_approle", autospec=True
        ) as manage_approle:
            yield manage_approle

    @pytest.fixture(autouse=True)
    def manage_entity(self):
        with patch("salt.runners.vault._manage_entity", autospec=True) as manage_entity:
            yield manage_entity

    @pytest.fixture(autouse=True)
    def manage_entity_alias(self):
        with patch(
            "salt.runners.vault._manage_entity_alias", autospec=True
        ) as manage_entity_alias:
            yield manage_entity_alias

    @pytest.mark.parametrize(
        "config",
        [{"issue:type": "approle"}, {"issue:type": "approle", "issue:wrap": False}],
        indirect=True,
    )
    def test_get_role_id(
        self,
        config,
        lookup_approle,
        lookup_roleid,
        manage_approle,
        manage_entity,
        manage_entity_alias,
        wrapped_serialized,
    ):
        """
        Ensure _get_role_id returns data in the expected format and does not
        try to generate a new AppRole if it exists and is configured correctly
        """
        wrap = config("issue:wrap")
        res = vault._get_role_id("test-minion", issue_params=None, wrap=wrap)
        lookup_approle.assert_called_with("test-minion")
        lookup_roleid.assert_called_with("test-minion", wrap=wrap)
        manage_approle.assert_not_called()
        manage_entity.assert_not_called()
        manage_entity_alias.assert_not_called()

        if wrap:
            assert res == wrapped_serialized
            lookup_roleid.return_value.serialize_for_minion.assert_called_once()
        else:
            assert res() == "test-role-id"
            lookup_roleid.return_value.serialize_for_minion.assert_not_called()

    @pytest.mark.parametrize(
        "config",
        [
            {"issue:type": "approle"},
            {"issue:type": "approle", "issue:allow_minion_override_params": True},
        ],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "issue_params", [None, {"token_explicit_max_ttl": 120, "token_num_uses": 3}]
    )
    def test_get_role_id_generate_new(
        self,
        config,
        lookup_approle,
        lookup_roleid,
        manage_approle,
        manage_entity,
        manage_entity_alias,
        wrapped_serialized,
        issue_params,
    ):
        """
        Ensure _get_role_id returns data in the expected format and does not
        try to generate a new AppRole if it exists and is configured correctly
        """
        lookup_approle.return_value = False
        wrap = config("issue:wrap")
        res = vault._get_role_id("test-minion", issue_params=issue_params, wrap=wrap)
        assert res == wrapped_serialized
        lookup_roleid.assert_called_with("test-minion", wrap=wrap)
        manage_approle.assert_called_once_with("test-minion", issue_params)
        manage_entity.assert_called_once_with("test-minion")
        manage_entity_alias.assert_called_once_with("test-minion")

    @pytest.mark.parametrize("config", [{"issue:type": "approle"}], indirect=True)
    def test_get_role_id_generate_new_errors_on_generation_failure(
        self, config, lookup_approle, lookup_roleid
    ):
        """
        Ensure _get_role_id returns an error if the AppRole generation failed
        """
        lookup_approle.return_value = False
        lookup_roleid.return_value = False
        with pytest.raises(
            salt.exceptions.SaltRunnerError,
            match="Failed to create AppRole for minion.*",
        ):
            vault._get_role_id("test-minion", issue_params=None, wrap=False)


@pytest.mark.parametrize(
    "config",
    [{"issue:type": "approle"}, {"issue:type": "approle", "issue:wrap": False}],
    indirect=True,
)
def test_generate_secret_id(
    config, validate_signature, wrapped_serialized, approle_meta, secret_id_serialized
):
    """
    Ensure generate_secret_id returns data in the expected format
    """
    expected = {
        "server": config("server"),
        "data": {},
        "misc_data": {"secret_id_num_uses": approle_meta["secret_id_num_uses"]},
    }
    if config("issue:wrap"):
        expected.update(wrapped_serialized)
    else:
        expected["data"].update(secret_id_serialized)
    with patch("salt.runners.vault._get_secret_id", autospec=True) as gen, patch(
        "salt.runners.vault._approle_params_match", autospec=True, return_value=True
    ) as matcher, patch(
        "salt.runners.vault._lookup_approle_cached", autospec=True
    ) as lookup_approle:

        def res_or_wrap(*args, **kwargs):
            if kwargs.get("wrap"):
                res = Mock(spec=vaultutil.VaultWrappedResponse)
                res.serialize_for_minion.return_value = wrapped_serialized
                return res
            secret_id = Mock(spec=vaultutil.VaultSecretId)
            secret_id.serialize_for_minion.return_value = secret_id_serialized
            return secret_id

        gen.side_effect = res_or_wrap
        lookup_approle.return_value = approle_meta
        res = vault.generate_secret_id("test-minion", "sig", issue_params=None)
        validate_signature.assert_called_once_with("test-minion", "sig", False)
        assert res == expected
        gen.assert_called_once_with("test-minion", wrap=config("issue:wrap"))
        matcher.assert_called_once()


@pytest.mark.usefixtures("validate_signature")
@pytest.mark.parametrize("config", [{"issue:type": "approle"}], indirect=True)
def test_generate_secret_id_nonexistent_approle(config):
    """
    Ensure generate_secret_id fails and prompts the minion to refresh cache if
    no associated AppRole could be found.
    """
    with patch(
        "salt.runners.vault._lookup_approle_cached", autospec=True
    ) as lookup_approle:
        lookup_approle.return_value = False
        res = vault.generate_secret_id("test-minion", "sig", issue_params=None)
        assert "error" in res
        assert "expire_cache" in res
        assert res["expire_cache"]


@pytest.mark.usefixtures("validate_signature")
@pytest.mark.parametrize("config", [{"issue:type": "token"}], indirect=True)
def test_get_secret_id_refuses_if_not_configured(config):
    """
    Ensure get_secret_id returns an error if not configured to issue AppRoles
    """
    res = vault.generate_secret_id("test-minion", "sig")
    assert "error" in res
    assert "Master does not issue AppRoles" in res["error"]


@pytest.mark.parametrize("config", [{"issue:type": "approle"}], indirect=True)
def test_generate_secret_id_updates_params(
    config, validate_signature, wrapped_serialized, approle_meta
):
    """
    Ensure generate_secret_id returns data in the expected format
    """
    expected = {
        "server": config("server"),
        "data": {},
        "misc_data": {"secret_id_num_uses": approle_meta["secret_id_num_uses"]},
        "wrap_info": wrapped_serialized["wrap_info"],
    }
    with patch("salt.runners.vault._get_secret_id", autospec=True) as gen, patch(
        "salt.runners.vault._approle_params_match", autospec=True, return_value=False
    ) as matcher, patch(
        "salt.runners.vault._manage_approle", autospec=True
    ) as manage_approle, patch(
        "salt.runners.vault._lookup_approle_cached", autospec=True
    ) as lookup_approle:
        res = Mock(spec=vaultutil.VaultWrappedResponse)
        res.serialize_for_minion.return_value = wrapped_serialized
        gen.return_value = res
        lookup_approle.return_value = approle_meta
        res = vault.generate_secret_id("test-minion", "sig", issue_params=None)
        validate_signature.assert_called_once_with("test-minion", "sig", False)
        assert res == expected
        gen.assert_called_once_with("test-minion", wrap=config("issue:wrap"))
        matcher.assert_called_once()
        manage_approle.assert_called_once()


@pytest.mark.parametrize("config", [{"issue:type": "token"}], indirect=True)
def test_list_approles_raises_exception_if_not_configured(config):
    """
    Ensure test_list_approles returns an error if not configured to issue AppRoles
    """
    with pytest.raises(
        salt.exceptions.SaltRunnerError, match="Master does not issue AppRoles.*"
    ):
        vault.list_approles()


@pytest.mark.parametrize(
    "config,expected",
    [
        ({"policies:assign": ["no-tokens-to-replace"]}, ["no-tokens-to-replace"]),
        ({"policies:assign": ["single-dict:{minion}"]}, ["single-dict:test-minion"]),
        (
            {
                "policies:assign": [
                    "should-not-cause-an-exception,but-result-empty:{foo}"
                ]
            },
            [],
        ),
        (
            {"policies:assign": ["Case-Should-Be-Lowered:{grains[mixedcase]}"]},
            ["case-should-be-lowered:up-low-up"],
        ),
        (
            {"policies:assign": ["pillar-rendering:{pillar[role]}"]},
            ["pillar-rendering:test"],
        ),
    ],
    indirect=["config"],
)
def test_get_policies(config, expected, grains, pillar):
    """
    Ensure _get_policies works as intended.
    The expansion of lists is tested in the vault utility module unit tests.
    """
    with patch(
        "salt.utils.minions.get_minion_data",
        MagicMock(return_value=(None, grains, pillar)),
    ):
        with patch(
            "salt.utils.vault.helpers.expand_pattern_lists",
            Mock(side_effect=lambda x, *args, **kwargs: [x]),
        ):
            res = vault._get_policies("test-minion", refresh_pillar=False)
            assert res == expected


@pytest.mark.parametrize(
    "config",
    [
        {"policies:assign": ["salt_minion_{minion}"]},
        {"policies:assign": ["salt_grain_{grains[id]}"]},
        {"policies:assign": ["unset_{foo}"]},
        {"policies:assign": ["salt_pillar_{pillar[role]}"]},
    ],
    indirect=True,
)
def test_get_policies_does_not_render_pillar_unnecessarily(config, grains, pillar):
    """
    The pillar data should only be refreshed in case items are accessed.
    """
    with patch("salt.utils.minions.get_minion_data", autospec=True) as get_minion_data:
        get_minion_data.return_value = (None, grains, None)
        with patch(
            "salt.utils.vault.helpers.expand_pattern_lists",
            Mock(side_effect=lambda x, *args, **kwargs: [x]),
        ):
            with patch("salt.pillar.get_pillar", autospec=True) as get_pillar:
                get_pillar.return_value.compile_pillar.return_value = pillar
                vault._get_policies("test-minion", refresh_pillar=True)
                assert get_pillar.call_count == int(
                    "pillar" in config("policies:assign")[0]
                )


@pytest.mark.parametrize(
    "config,expected",
    [
        ({"policies:assign": ["no-tokens-to-replace"]}, ["no-tokens-to-replace"]),
        ({"policies:assign": ["single-dict:{minion}"]}, ["single-dict:test-minion"]),
        ({"policies:assign": ["single-grain:{grains[os]}"]}, []),
    ],
    indirect=["config"],
)
def test_get_policies_for_nonexisting_minions(config, expected):
    """
    For non-existing minions, or the master-minion, grains will be None.
    """
    with patch("salt.utils.minions.get_minion_data", autospec=True) as get_minion_data:
        get_minion_data.return_value = (None, None, None)
        with patch(
            "salt.utils.vault.helpers.expand_pattern_lists",
            Mock(side_effect=lambda x, *args, **kwargs: [x]),
        ):
            res = vault._get_policies("test-minion", refresh_pillar=False)
            assert res == expected


@pytest.mark.parametrize(
    "metadata_patterns,expected",
    [
        (
            {"no-tokens-to-replace": "no-tokens-to-replace"},
            {"no-tokens-to-replace": "no-tokens-to-replace"},
        ),
        (
            {"single-dict:{minion}": "single-dict:{minion}"},
            {"single-dict:{minion}": "single-dict:test-minion"},
        ),
        (
            {"should-not-cause-an-exception,but-result-empty:{foo}": "empty:{foo}"},
            {"should-not-cause-an-exception,but-result-empty:{foo}": ""},
        ),
        (
            {
                "Case-Should-Not-Be-Lowered": "Case-Should-Not-Be-Lowered:{pillar[mixedcase]}"
            },
            {"Case-Should-Not-Be-Lowered": "Case-Should-Not-Be-Lowered:UP-low-UP"},
        ),
        (
            {"pillar-rendering:{pillar[role]}": "pillar-rendering:{pillar[role]}"},
            {"pillar-rendering:{pillar[role]}": "pillar-rendering:test"},
        ),
    ],
)
def test_get_metadata(metadata_patterns, expected, pillar):
    """
    Ensure _get_policies works as intended.
    The expansion of lists is tested in the vault utility module unit tests.
    """
    with patch("salt.utils.minions.get_minion_data", autospec=True) as get_minion_data:
        get_minion_data.return_value = (None, None, pillar)
        with patch(
            "salt.utils.vault.helpers.expand_pattern_lists",
            Mock(side_effect=lambda x, *args, **kwargs: [x]),
        ):
            res = vault._get_metadata(
                "test-minion", metadata_patterns, refresh_pillar=False
            )
            assert res == expected


def test_get_metadata_list():
    """
    Test that lists are concatenated to an alphabetically sorted
    comma-separated list string since the API does not allow
    composite metadata values
    """
    with patch("salt.utils.minions.get_minion_data", autospec=True) as get_minion_data:
        get_minion_data.return_value = (None, None, None)
        with patch(
            "salt.utils.vault.helpers.expand_pattern_lists", autospec=True
        ) as expand:
            expand.return_value = ["salt_role_foo", "salt_role_bar"]
            res = vault._get_metadata(
                "test-minion",
                {"salt_role": "salt_role_{pillar[roles]}"},
                refresh_pillar=False,
            )
            assert res == {"salt_role": "salt_role_bar,salt_role_foo"}


@pytest.mark.parametrize(
    "config,issue_params,expected",
    [
        (
            {"issue:token:params": {"explicit_max_ttl": None, "num_uses": None}},
            None,
            {},
        ),
        (
            {"issue:token:params": {"explicit_max_ttl": 1337, "num_uses": None}},
            None,
            {"explicit_max_ttl": 1337},
        ),
        (
            {"issue:token:params": {"explicit_max_ttl": None, "num_uses": 3}},
            None,
            {"num_uses": 3},
        ),
        (
            {"issue:token:params": {"explicit_max_ttl": 1337, "num_uses": 3}},
            None,
            {"explicit_max_ttl": 1337, "num_uses": 3},
        ),
        (
            {
                "issue:token:params": {
                    "explicit_max_ttl": 1337,
                    "num_uses": 3,
                    "invalid": True,
                }
            },
            None,
            {"explicit_max_ttl": 1337, "num_uses": 3},
        ),
        (
            {"issue:token:params": {"explicit_max_ttl": None, "num_uses": None}},
            {"num_uses": 42, "explicit_max_ttl": 1338},
            {},
        ),
        (
            {"issue:token:params": {"explicit_max_ttl": 1337, "num_uses": None}},
            {"num_uses": 42, "explicit_max_ttl": 1338},
            {"explicit_max_ttl": 1337},
        ),
        (
            {"issue:token:params": {"explicit_max_ttl": None, "num_uses": 3}},
            {"num_uses": 42, "explicit_max_ttl": 1338},
            {"num_uses": 3},
        ),
        (
            {"issue:token:params": {"explicit_max_ttl": 1337, "num_uses": 3}},
            {"num_uses": 42, "explicit_max_ttl": 1338, "invalid": True},
            {"explicit_max_ttl": 1337, "num_uses": 3},
        ),
        (
            {
                "issue:token:params": {"explicit_max_ttl": None, "num_uses": None},
                "issue:allow_minion_override_params": True,
            },
            {"num_uses": None, "explicit_max_ttl": None},
            {},
        ),
        (
            {
                "issue:token:params": {"explicit_max_ttl": None, "num_uses": 3},
                "issue:allow_minion_override_params": True,
            },
            {"num_uses": 42, "explicit_max_ttl": None},
            {"num_uses": 42},
        ),
        (
            {
                "issue:token:params": {"explicit_max_ttl": 1337, "num_uses": None},
                "issue:allow_minion_override_params": True,
            },
            {"num_uses": None, "explicit_max_ttl": 1338},
            {"explicit_max_ttl": 1338},
        ),
        (
            {
                "issue:token:params": {"explicit_max_ttl": 1337, "num_uses": None},
                "issue:allow_minion_override_params": True,
            },
            {"num_uses": 42, "explicit_max_ttl": None},
            {"num_uses": 42, "explicit_max_ttl": 1337},
        ),
        (
            {
                "issue:token:params": {"explicit_max_ttl": None, "num_uses": 3},
                "issue:allow_minion_override_params": True,
            },
            {"num_uses": None, "explicit_max_ttl": 1338},
            {"num_uses": 3, "explicit_max_ttl": 1338},
        ),
        (
            {
                "issue:token:params": {"explicit_max_ttl": None, "num_uses": None},
                "issue:allow_minion_override_params": True,
            },
            {"num_uses": 42, "explicit_max_ttl": 1338},
            {"num_uses": 42, "explicit_max_ttl": 1338},
        ),
        (
            {
                "issue:token:params": {"explicit_max_ttl": 1337, "num_uses": 3},
                "issue:allow_minion_override_params": True,
            },
            {"num_uses": 42, "explicit_max_ttl": 1338, "invalid": True},
            {"num_uses": 42, "explicit_max_ttl": 1338},
        ),
        ({"issue:type": "approle", "issue:approle:params": {}}, None, {}),
        (
            {
                "issue:type": "approle",
                "issue:approle:params": {
                    "token_explicit_max_ttl": 1337,
                    "token_num_uses": 3,
                    "secret_id_num_uses": 3,
                    "secret_id_ttl": 60,
                },
            },
            None,
            {
                "token_explicit_max_ttl": 1337,
                "token_num_uses": 3,
                "secret_id_num_uses": 3,
                "secret_id_ttl": 60,
            },
        ),
        (
            {
                "issue:type": "approle",
                "issue:approle:params": {
                    "token_explicit_max_ttl": 1337,
                    "token_num_uses": 3,
                    "secret_id_num_uses": 3,
                    "secret_id_ttl": 60,
                },
            },
            {
                "token_explicit_max_ttl": 1338,
                "token_num_uses": 42,
                "secret_id_num_uses": 42,
                "secret_id_ttl": 1338,
            },
            {
                "token_explicit_max_ttl": 1337,
                "token_num_uses": 3,
                "secret_id_num_uses": 3,
                "secret_id_ttl": 60,
            },
        ),
        (
            {
                "issue:type": "approle",
                "issue:allow_minion_override_params": True,
                "issue:approle:params": {},
            },
            {
                "token_explicit_max_ttl": 1338,
                "token_num_uses": 42,
                "secret_id_num_uses": 42,
                "secret_id_ttl": 1338,
            },
            {
                "token_explicit_max_ttl": 1338,
                "token_num_uses": 42,
                "secret_id_num_uses": 42,
                "secret_id_ttl": 1338,
            },
        ),
        (
            {
                "issue:type": "approle",
                "issue:allow_minion_override_params": True,
                "issue:approle:params": {
                    "token_explicit_max_ttl": 1337,
                    "token_num_uses": 3,
                    "secret_id_num_uses": 3,
                    "secret_id_ttl": 60,
                },
            },
            {
                "token_explicit_max_ttl": 1338,
                "token_num_uses": 42,
                "secret_id_num_uses": 42,
                "secret_id_ttl": 1338,
            },
            {
                "token_explicit_max_ttl": 1338,
                "token_num_uses": 42,
                "secret_id_num_uses": 42,
                "secret_id_ttl": 1338,
            },
        ),
    ],
    indirect=["config"],
)
def test_parse_issue_params(config, issue_params, expected):
    """
    Ensure all known parameters can only be overridden if it was configured
    on the master. Also ensure the mapping to API requests is correct (for tokens).
    """
    res = vault._parse_issue_params(issue_params)
    assert res == expected


@pytest.mark.parametrize(
    "config,issue_params,expected",
    [
        (
            {"issue:type": "approle", "issue:approle:params": {}},
            {"bind_secret_id": False},
            False,
        ),
        (
            {"issue:type": "approle", "issue:approle:params": {}},
            {"bind_secret_id": True},
            False,
        ),
        (
            {"issue:type": "approle", "issue:approle:params": {"bind_secret_id": True}},
            {"bind_secret_id": False},
            True,
        ),
        (
            {
                "issue:type": "approle",
                "issue:approle:params": {"bind_secret_id": False},
            },
            {"bind_secret_id": True},
            False,
        ),
    ],
    indirect=["config"],
)
def test_parse_issue_params_does_not_allow_bind_secret_id_override(
    config, issue_params, expected
):
    """
    Ensure bind_secret_id can only be set on the master.
    """
    res = vault._parse_issue_params(issue_params)
    assert res.get("bind_secret_id", False) == expected


@pytest.mark.usefixtures("config", "policies")
def test_manage_approle(approle_api, policies_default):
    """
    Ensure _manage_approle calls the API as expected.
    """
    vault._manage_approle("test-minion", None)
    approle_api.write_approle.assert_called_once_with(
        "test-minion",
        mount="salt-minions",
        explicit_max_ttl=9999999999,
        num_uses=1,
        token_policies=policies_default,
    )


@pytest.mark.usefixtures("config")
def test_delete_approle(approle_api):
    """
    Ensure _delete_approle calls the API as expected.
    """
    vault._delete_approle("test-minion")
    approle_api.delete_approle.assert_called_once_with(
        "test-minion", mount="salt-minions"
    )


@pytest.mark.usefixtures("config")
def test_lookup_approle(approle_api, approle_meta):
    """
    Ensure _lookup_approle calls the API as expected.
    """
    approle_api.read_approle.return_value = approle_meta
    res = vault._lookup_approle("test-minion")
    assert res == approle_meta
    approle_api.read_approle.assert_called_once_with(
        "test-minion", mount="salt-minions"
    )


@pytest.mark.usefixtures("config")
def test_lookup_approle_nonexistent(approle_api):
    """
    Ensure _lookup_approle catches VaultNotFoundErrors and returns False.
    """
    approle_api.read_approle.side_effect = vaultutil.VaultNotFoundError
    res = vault._lookup_approle("test-minion")
    assert res is False


@pytest.mark.usefixtures("config")
@pytest.mark.parametrize("wrap", ["30s", False])
def test_lookup_role_id(approle_api, wrap):
    """
    Ensure _lookup_role_id calls the API as expected.
    """
    vault._lookup_role_id("test-minion", wrap=wrap)
    approle_api.read_role_id.assert_called_once_with(
        "test-minion", mount="salt-minions", wrap=wrap
    )


@pytest.mark.usefixtures("config")
def test_lookup_role_id_nonexistent(approle_api):
    """
    Ensure _lookup_role_id catches VaultNotFoundErrors and returns False.
    """
    approle_api.read_role_id.side_effect = vaultutil.VaultNotFoundError
    res = vault._lookup_role_id("test-minion", wrap=False)
    assert res is False


@pytest.mark.usefixtures("config")
@pytest.mark.parametrize("wrap", ["30s", False])
def test_get_secret_id(approle_api, wrap):
    """
    Ensure _get_secret_id calls the API as expected.
    """
    vault._get_secret_id("test-minion", wrap=wrap)
    approle_api.generate_secret_id.assert_called_once_with(
        "test-minion",
        metadata=ANY,
        wrap=wrap,
        mount="salt-minions",
    )


@pytest.mark.usefixtures("config")
def test_lookup_entity_by_alias(identity_api):
    """
    Ensure _lookup_entity_by_alias calls the API as expected.
    """
    with patch("salt.runners.vault._lookup_role_id", return_value="test-role-id"):
        vault._lookup_entity_by_alias("test-minion")
        identity_api.read_entity_by_alias.assert_called_once_with(
            alias="test-role-id", mount="salt-minions"
        )


@pytest.mark.usefixtures("config")
def test_lookup_entity_by_alias_failed(identity_api):
    """
    Ensure _lookup_entity_by_alias returns False if the lookup fails.
    """
    with patch("salt.runners.vault._lookup_role_id", return_value="test-role-id"):
        identity_api.read_entity_by_alias.side_effect = vaultutil.VaultNotFoundError
        res = vault._lookup_entity_by_alias("test-minion")
        assert res is False


@pytest.mark.usefixtures("config")
def test_fetch_entity_by_name(identity_api):
    """
    Ensure _fetch_entity_by_name calls the API as expected.
    """
    vault._fetch_entity_by_name("test-minion")
    identity_api.read_entity.assert_called_once_with(name="salt_minion_test-minion")


@pytest.mark.usefixtures("config")
def test_fetch_entity_by_name_failed(identity_api):
    """
    Ensure _fetch_entity_by_name returns False if the lookup fails.
    """
    identity_api.read_entity.side_effect = vaultutil.VaultNotFoundError
    res = vault._fetch_entity_by_name("test-minion")
    assert res is False


@pytest.mark.usefixtures("config")
def test_manage_entity(identity_api, metadata, metadata_entity_default):
    """
    Ensure _manage_entity calls the API as expected.
    """
    vault._manage_entity("test-minion")
    identity_api.write_entity.assert_called_with(
        "salt_minion_test-minion", metadata=metadata_entity_default
    )


@pytest.mark.usefixtures("config")
def test_delete_entity(identity_api):
    """
    Ensure _delete_entity calls the API as expected.
    """
    vault._delete_entity("test-minion")
    identity_api.delete_entity.assert_called_with("salt_minion_test-minion")


@pytest.mark.usefixtures("config")
def test_manage_entity_alias(identity_api):
    """
    Ensure _manage_entity_alias calls the API as expected.
    """
    with patch("salt.runners.vault._lookup_role_id", return_value="test-role-id"):
        vault._manage_entity_alias("test-minion")
        identity_api.write_entity_alias.assert_called_with(
            "salt_minion_test-minion", alias_name="test-role-id", mount="salt-minions"
        )


@pytest.mark.usefixtures("config")
def test_manage_entity_alias_raises_errors(identity_api):
    """
    Ensure _manage_entity_alias raises exceptions.
    """
    identity_api.write_entity_alias.side_effect = vaultutil.VaultNotFoundError
    with patch("salt.runners.vault._lookup_role_id", return_value="test-role-id"):
        with pytest.raises(
            salt.exceptions.SaltRunnerError,
            match="Cannot create alias.* no entity found.",
        ):
            vault._manage_entity_alias("test-minion")


def test_revoke_token_by_token(client):
    """
    Ensure _revoke_token calls the API as expected.
    """
    vault._revoke_token(token="test-token")
    client.post.assert_called_once_with(
        "auth/token/revoke", payload={"token": "test-token"}
    )


def test_revoke_token_by_accessor(client):
    """
    Ensure _revoke_token calls the API as expected.
    """
    vault._revoke_token(accessor="test-accessor")
    client.post.assert_called_once_with(
        "auth/token/revoke-accessor", payload={"accessor": "test-accessor"}
    )
