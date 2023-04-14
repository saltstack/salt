import time
from copy import deepcopy

# this needs to be from! see test_iso_to_timestamp_polyfill
from datetime import datetime

import pytest
import requests

import salt.exceptions
import salt.utils.vault as vault
from tests.support.mock import ANY, MagicMock, Mock, call, patch


@pytest.fixture
def server_config():
    return {
        "url": "http://127.0.0.1:8200",
        "namespace": None,
        "verify": None,
    }


@pytest.fixture(params=["token", "approle"])
def test_config(server_config, request):
    defaults = {
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
            "config": 3600,
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
                    "token_explicit_max_ttl": 60,
                    "token_num_uses": 10,
                },
            },
            "token": {
                "role_name": None,
                "params": {
                    "explicit_max_ttl": None,
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
            "token": {
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
        "server": server_config,
    }

    if request.param == "token":
        defaults["auth"]["token"] = "test-token"
        return defaults

    if request.param == "wrapped_token":
        defaults["auth"]["method"] = "wrapped_token"
        defaults["auth"]["token"] = "test-wrapped-token"
        return defaults

    if request.param == "approle":
        defaults["auth"]["method"] = "approle"
        defaults["auth"]["role_id"] = "test-role-id"
        defaults["auth"]["secret_id"] = "test-secret-id"
        return defaults

    if request.param == "approle_no_secretid":
        defaults["auth"]["method"] = "approle"
        defaults["auth"]["role_id"] = "test-role-id"
        return defaults


@pytest.fixture(params=["token", "approle"])
def test_remote_config(server_config, request):
    defaults = {
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
            "config": 3600,
            "kv_metadata": "connection",
            "secret": "ttl",
        },
        "server": server_config,
    }

    if request.param == "token":
        defaults["auth"]["token"] = "test-token"
        return defaults

    if request.param == "wrapped_token":
        defaults["auth"]["method"] = "wrapped_token"
        defaults["auth"]["token"] = "test-wrapped-token"
        return defaults

    if request.param == "token_changed":
        defaults["auth"]["token"] = "test-token-changed"
        return defaults

    if request.param == "approle":
        defaults["auth"]["method"] = "approle"
        defaults["auth"]["role_id"] = "test-role-id"
        # actual remote config would not contain secret_id, but
        # this is used for testing both from local and from remote
        defaults["auth"]["secret_id"] = "test-secret-id"
        return defaults

    if request.param == "approle_no_secretid":
        defaults["auth"]["method"] = "approle"
        defaults["auth"]["role_id"] = "test-role-id"
        return defaults

    # this happens when wrapped role_ids are merged by _query_master
    if request.param == "approle_wrapped_roleid":
        defaults["auth"]["method"] = "approle"
        defaults["auth"]["role_id"] = {"role_id": "test-role-id"}
        # actual remote config does not contain secret_id
        defaults["auth"]["secret_id"] = True
        return defaults


@pytest.fixture
def role_id_response():
    return {
        "request_id": "c85838c5-ecfe-6d07-4b28-1935ac2e304a",
        "lease_id": "",
        "lease_duration": 0,
        "renewable": False,
        "data": {"role_id": "58b4c650-3d13-5932-a2fa-03865c8e85d7"},
        "warnings": None,
    }


@pytest.fixture
def secret_id_response():
    return {
        "request_id": "c85838c5-ecfe-6d07-4b28-1935ac2e304a",
        "lease_id": "",
        "lease_duration": 0,
        "renewable": False,
        "data": {
            "secret_id_accessor": "84896a0c-1347-aa90-a4f6-aca8b7558780",
            "secret_id": "841771dc-11c9-bbc7-bcac-6a3945a69cd9",
            "secret_id_ttl": 1337,
        },
        "warnings": None,
    }


@pytest.fixture
def secret_id_meta_response():
    return {
        "request_id": "7c97d03d-2166-6217-8da1-19604febae5c",
        "lease_id": "",
        "lease_duration": 0,
        "renewable": False,
        "data": {
            "cidr_list": [],
            "creation_time": "2022-08-22T17:37:07.753989459+00:00",
            "expiration_time": "2339-07-13T13:23:46.753989459+00:00",
            "last_updated_time": "2022-08-22T17:37:07.753989459+00:00",
            "metadata": {},
            "secret_id_accessor": "b1c88755-f2f5-2fd2-4bcc-cade95f6ba96",
            "secret_id_num_uses": 0,
            "secret_id_ttl": 9999999999,
            "token_bound_cidrs": [],
        },
        "warnings": None,
    }


@pytest.fixture
def wrapped_role_id_response():
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
            "creation_path": "auth/approle/role/test-minion/role-id",
            "wrapped_accessor": "",
        },
    }


@pytest.fixture
def wrapped_secret_id_response():
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
            "creation_path": "auth/approle/role/test-minion/secret-id",
            "wrapped_accessor": "",
        },
    }


@pytest.fixture
def wrapped_role_id_lookup_response():
    return {
        "request_id": "31e7020e-3ce3-2c63-e453-d5da8a9890f1",
        "lease_id": "",
        "renewable": False,
        "lease_duration": 0,
        "data": {
            "creation_path": "auth/approle/role/test-minion/role-id",
            "creation_time": "2022-09-10T13:37:12.123456789+00:00",
            "creation_ttl": 180,
        },
        "wrap_info": None,
        "warnings": None,
        "auth": None,
    }


@pytest.fixture
def wrapped_token_auth_response():
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
            "creation_path": "auth/token/create/salt-minion",
            "wrapped_accessor": "",
        },
    }


@pytest.fixture
def token_lookup_self_response():
    return {
        "request_id": "0e8c388e-2cb6-bcb2-83b7-625127d568bb",
        "lease_id": "",
        "lease_duration": 0,
        "renewable": False,
        "data": {
            "accessor": "test-token-accessor",
            "creation_time": 1661188581,
            "creation_ttl": 9999999999,
            "display_name": "",
            "entity_id": "",
            "expire_time": "2339-07-13T11:03:00.473212541+00:00",
            "explicit_max_ttl": 0,
            "id": "test-token",
            "issue_time": "2022-08-22T17:16:21.473219641+00:00",
            "meta": {},
            "num_uses": 0,
            "orphan": True,
            "path": "",
            "policies": ["default"],
            "renewable": True,
            "ttl": 9999999999,
            "type": "service",
        },
        "warnings": None,
    }


@pytest.fixture
def token_renew_self_response():
    return {
        "auth": {
            "client_token": "test-token",
            "policies": ["default", "renewed"],
            "metadata": {},
        },
        "lease_duration": 3600,
        "renewable": True,
    }


@pytest.fixture
def token_renew_other_response():
    return {
        "auth": {
            "client_token": "other-test-token",
            "policies": ["default", "renewed"],
            "metadata": {},
        },
        "lease_duration": 3600,
        "renewable": True,
    }


@pytest.fixture
def token_renew_accessor_response():
    return {
        "auth": {
            "client_token": "",
            "policies": ["default", "renewed"],
            "metadata": {},
        },
        "lease_duration": 3600,
        "renewable": True,
    }


@pytest.fixture
def token_auth():
    return {
        "request_id": "0e8c388e-2cb6-bcb2-83b7-625127d568bb",
        "lease_id": "",
        "lease_duration": 0,
        "renewable": False,
        "auth": {
            "client_token": "test-token",
            "renewable": True,
            "lease_duration": 9999999999,
            "num_uses": 0,
            "creation_time": 1661188581,
        },
    }


@pytest.fixture
def kvv1_meta_response():
    return {
        "request_id": "b82f2df7-a9b6-920c-0ed2-a3463b996f9e",
        "lease_id": "",
        "renewable": False,
        "lease_duration": 0,
        "data": {
            "accessor": "kv_f8731f1b",
            "config": {
                "default_lease_ttl": 0,
                "force_no_cache": False,
                "max_lease_ttl": 0,
            },
            "description": "key/value secret storage",
            "external_entropy_access": False,
            "local": False,
            "options": None,
            "path": "secret/",
            "seal_wrap": False,
            "type": "kv",
            "uuid": "1d9431ac-060a-9b63-4572-3ca7ffd78347",
        },
        "wrap_info": None,
        "warnings": None,
        "auth": None,
    }


@pytest.fixture
def kvv2_meta_response():
    return {
        "request_id": "b82f2df7-a9b6-920c-0ed2-a3463b996f9e",
        "lease_id": "",
        "renewable": False,
        "lease_duration": 0,
        "data": {
            "accessor": "kv_f8731f1b",
            "config": {
                "default_lease_ttl": 0,
                "force_no_cache": False,
                "max_lease_ttl": 0,
            },
            "description": "key/value secret storage",
            "external_entropy_access": False,
            "local": False,
            "options": {
                "version": "2",
            },
            "path": "secret/",
            "seal_wrap": False,
            "type": "kv",
            "uuid": "1d9431ac-060a-9b63-4572-3ca7ffd78347",
        },
        "wrap_info": None,
        "warnings": None,
        "auth": None,
    }


@pytest.fixture
def kvv1_info():
    return {
        "v2": False,
        "data": "secret/some/path",
        "metadata": "secret/some/path",
        "delete": "secret/some/path",
        "type": "kv",
    }


@pytest.fixture
def kvv2_info():
    return {
        "v2": True,
        "data": "secret/data/some/path",
        "metadata": "secret/metadata/some/path",
        "delete": "secret/data/some/path",
        "delete_versions": "secret/delete/some/path",
        "destroy": "secret/destroy/some/path",
        "type": "kv",
    }


@pytest.fixture
def no_kv_info():
    return {
        "v2": False,
        "data": "secret/some/path",
        "metadata": "secret/some/path",
        "delete": "secret/some/path",
        "type": None,
    }


@pytest.fixture
def kvv1_response():
    return {
        "request_id": "35df4df1-c3d8-b270-0682-ddb0160c7450",
        "lease_id": "",
        "renewable": False,
        "lease_duration": 0,
        "data": {
            "foo": "bar",
        },
        "wrap_info": None,
        "warnings": None,
        "auth": None,
    }


@pytest.fixture
def kvv2_response():
    return {
        "request_id": "35df4df1-c3d8-b270-0682-ddb0160c7450",
        "lease_id": "",
        "renewable": False,
        "lease_duration": 0,
        "data": {
            "data": {"foo": "bar"},
            "metadata": {
                "created_time": "2020-05-02T07:26:12.180848003Z",
                "deletion_time": "",
                "destroyed": False,
                "version": 1,
            },
        },
        "wrap_info": None,
        "warnings": None,
        "auth": None,
    }


@pytest.fixture
def kv_list_response():
    return {
        "request_id": "35df4df1-c3d8-b270-0682-ddb0160c7450",
        "lease_id": "",
        "renewable": False,
        "lease_duration": 0,
        "data": {
            "keys": ["foo"],
        },
        "wrap_info": None,
        "warnings": None,
        "auth": None,
    }


@pytest.fixture
def session():
    return Mock(spec=requests.Session)


@pytest.fixture
def req(session):
    yield session.request


@pytest.fixture
def req_failed(req, request):
    status_code = getattr(request, "param", 502)
    req.return_value = _mock_json_response({"errors": ["foo"]}, status_code=status_code)
    yield req


@pytest.fixture
def req_success(req):
    req.return_value = _mock_json_response(None, status_code=204)
    yield req


@pytest.fixture(params=[200])
def req_any(req, request):
    data = {}
    if request.param != 204:
        data["data"] = {"foo": "bar"}
    if request.param >= 400:
        data["errors"] = ["foo"]
    req.return_value = _mock_json_response(data, status_code=request.param)
    yield req


@pytest.fixture
def req_unwrapping(wrapped_role_id_lookup_response, role_id_response, req):
    req.side_effect = (
        lambda method, url, **kwargs: _mock_json_response(
            wrapped_role_id_lookup_response
        )
        if url.endswith("sys/wrapping/lookup")
        else _mock_json_response(role_id_response)
    )
    yield req


@pytest.fixture(params=["data"])
def unauthd_client_mock(server_config, request):
    client = Mock(spec=vault.VaultClient)
    client.get_config.return_value = server_config
    client.unwrap.return_value = {request.param: {"bar": "baz"}}
    yield client


@pytest.fixture(params=[None, "valid_token"])
def client(server_config, request, session):
    if request.param is None:
        return vault.VaultClient(**server_config, session=session)
    if request.param == "valid_token":
        token = request.getfixturevalue(request.param)
        auth = Mock(spec=vault.VaultTokenAuth)
        auth.is_renewable.return_value = True
        auth.is_valid.return_value = True
        auth.get_token.return_value = token
        return vault.AuthenticatedVaultClient(auth, **server_config, session=session)
    if request.param == "invalid_token":
        token = request.getfixturevalue(request.param)
        auth = Mock(spec=vault.VaultTokenAuth)
        auth.is_renewable.return_value = True
        auth.is_valid.return_value = False
        auth.get_token.side_effect = vault.VaultAuthExpired
        return vault.AuthenticatedVaultClient(auth, **server_config, session=session)


@pytest.fixture
def valid_token(token_auth):
    token = MagicMock(spec=vault.VaultToken, **token_auth["auth"])
    token.is_valid.return_value = True
    token.is_renewable.return_value = True
    token.payload.return_value = {"token": token_auth["auth"]["client_token"]}
    token.__str__.return_value = token_auth["auth"]["client_token"]
    token.to_dict.return_value = token_auth["auth"]
    return token


@pytest.fixture
def invalid_token(valid_token):
    valid_token.is_valid.return_value = False
    valid_token.is_renewable.return_value = False
    return valid_token


@pytest.fixture
def metadata_nocache():
    cache = Mock(spec=vault.VaultCache)
    cache.get.return_value = None
    return cache


@pytest.fixture(params=["v1", "v2"])
def kv_meta(request, metadata_nocache):
    client = Mock(spec=vault.AuthenticatedVaultClient)
    if request.param == "invalid":
        res = {"wrap_info": {}}
    else:
        res = request.getfixturevalue(f"kv{request.param}_meta_response")
    client.get.return_value = res
    return vault.VaultKV(client, metadata_nocache)


@pytest.fixture(params=["v1", "v2"])
def kv_meta_cached(request):
    cache = Mock(spec=vault.VaultCache)
    client = Mock(spec=vault.AuthenticatedVaultClient)
    kv_meta_response = request.getfixturevalue(f"kv{request.param}_meta_response")
    client.get.return_value = kv_meta_response
    cache.get.return_value = {"secret/some/path": kv_meta_response["data"]}
    return vault.VaultKV(client, cache)


@pytest.fixture
def kvv1(kvv1_info, kvv1_response, metadata_nocache, kv_list_response):
    client = Mock(spec=vault.AuthenticatedVaultClient)
    client.get.return_value = kvv1_response
    client.post.return_value = True
    client.patch.return_value = True
    client.list.return_value = kv_list_response
    client.delete.return_value = True
    with patch("salt.utils.vault.VaultKV.is_v2", Mock(return_value=kvv1_info)):
        yield vault.VaultKV(client, metadata_nocache)


@pytest.fixture
def kvv2(kvv2_info, kvv2_response, metadata_nocache, kv_list_response):
    client = Mock(spec=vault.AuthenticatedVaultClient)
    client.get.return_value = kvv2_response
    client.post.return_value = True
    client.patch.return_value = True
    client.list.return_value = kv_list_response
    client.delete.return_value = True
    with patch("salt.utils.vault.VaultKV.is_v2", Mock(return_value=kvv2_info)):
        yield vault.VaultKV(client, metadata_nocache)


def _mock_json_response(data, status_code=200, reason=""):
    """
    Mock helper for http response
    """
    response = Mock(spec=requests.models.Response)
    response.json.return_value = data
    response.status_code = status_code
    response.reason = reason
    if status_code < 400:
        response.ok = True
    else:
        response.ok = False
        response.raise_for_status.side_effect = requests.exceptions.HTTPError
    return response


@pytest.fixture(
    params=["MASTER", "MASTER_IMPERSONATING", "MINION_LOCAL", "MINION_REMOTE"]
)
def salt_runtype(request):
    runtype = Mock(spec=vault._get_salt_run_type)
    runtype.return_value = getattr(vault, f"SALT_RUNTYPE_{request.param}")
    with patch("salt.utils.vault._get_salt_run_type", runtype):
        yield


@pytest.fixture(
    params=[
        "master",
        "master_impersonating",
        "minion_local_1",
        "minion_local_2",
        "minion_local_3",
        "minion_remote",
    ]
)
def opts_runtype(request):
    return {
        "master": {
            "__role": "master",
            "vault": {},
        },
        "master_peer_run": {
            "__role": "master",
            "grains": {
                "id": "test-minion",
            },
            "vault": {},
        },
        "master_impersonating": {
            "__role": "master",
            "minion_id": "test-minion",
            "grains": {
                "id": "test-minion",
            },
            "vault": {},
        },
        "minion_local_1": {
            "grains": {"id": "test-minion"},
            "local": True,
        },
        "minion_local_2": {
            "file_client": "local",
            "grains": {"id": "test-minion"},
        },
        "minion_local_3": {
            "grains": {"id": "test-minion"},
            "master_type": "disable",
        },
        "minion_remote": {
            "grains": {"id": "test-minion"},
        },
    }[request.param]


############################################
# Wrapper functions tests
############################################


@pytest.mark.parametrize(
    "wrapper,param,result",
    [
        ("read_kv", None, {"foo": "bar"}),
        ("write_kv", {"foo": "bar"}, True),
        ("patch_kv", {"foo": "bar"}, True),
        ("delete_kv", None, True),
        ("destroy_kv", [0], True),
        ("list_kv", None, ["foo"]),
    ],
)
@pytest.mark.parametrize("exception", ["VaultPermissionDeniedError"])
def test_kv_wrapper_handles_auth_exceptions(wrapper, param, result, exception):
    """
    Test that *_kv wrappers retry with a new client if the authentication might
    be outdated.
    """
    func = getattr(vault, wrapper)
    exc = getattr(vault, exception)
    args = ["secret/some/path"]
    if param:
        args.append(param)
    args += [{}, {}]
    with patch("salt.utils.vault._get_kv", autospec=True) as getkv:
        with patch("salt.utils.vault.clear_cache", autospec=True) as cache:
            kv = Mock(spec=vault.VaultKV)
            getattr(kv, wrapper.rstrip("_kv")).side_effect = (exc, result)
            getkv.return_value = kv
            res = func(*args)
            assert res == result
            cache.assert_called_once()


############################################
# Factory tests
############################################


class TestGetAuthdClient:
    @pytest.fixture
    def client_valid(self):
        client = Mock(spec=vault.AuthenticatedVaultClient)
        client.token_valid.return_value = True
        return client

    @pytest.fixture
    def client_invalid(self):
        client = Mock(spec=vault.AuthenticatedVaultClient)
        client.token_valid.return_value = False
        return client

    @pytest.fixture
    def client_renewable(self):
        client = Mock(spec=vault.AuthenticatedVaultClient)
        client.auth.get_token.return_value.is_renewable.return_value = True
        client.auth.get_token.return_value.is_valid.return_value = False
        client.token_valid.return_value = True
        return client

    @pytest.fixture
    def client_unrenewable(self):
        client = Mock(spec=vault.AuthenticatedVaultClient)
        client.auth.get_token.return_value.is_renewable.return_value = False
        client.auth.get_token.return_value.is_valid.return_value = False
        client.token_valid.side_effect = (False, True)
        return client

    @pytest.fixture
    def client_renewable_max_ttl(self):
        client = Mock(spec=vault.AuthenticatedVaultClient)
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
        with patch("salt.utils.vault._build_authd_client", autospec=True) as build:
            build.return_value = (client_valid, request.param)
            yield build

    @pytest.fixture(
        params=["VaultAuthExpired", "VaultConfigExpired", "VaultPermissionDeniedError"]
    )
    def build_fails(self, request):
        exception = request.param
        with patch("salt.utils.vault._build_authd_client", autospec=True) as build:
            build.side_effect = getattr(vault, exception)
            yield build

    @pytest.fixture(
        params=["VaultAuthExpired", "VaultConfigExpired", "VaultPermissionDeniedError"]
    )
    def build_exception_first(self, client_valid, request):
        exception = request.param
        with patch("salt.utils.vault._build_authd_client", autospec=True) as build:
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
        with patch("salt.utils.vault._build_authd_client", autospec=True) as build:
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
        with patch("salt.utils.vault._build_authd_client", autospec=True) as build:
            build.return_value = (client_renewable, request.param)
            yield build

    @pytest.fixture(
        params=[
            {"auth": {"token_lifecycle": {"minimum_ttl": 10, "renew_increment": 60}}}
        ]
    )
    def build_unrenewable(self, client_unrenewable, request):
        with patch("salt.utils.vault._build_authd_client", autospec=True) as build:
            build.return_value = (client_unrenewable, request.param)
            yield build

    @pytest.fixture(
        params=[
            {"auth": {"token_lifecycle": {"minimum_ttl": 10, "renew_increment": 60}}}
        ]
    )
    def build_renewable_max_ttl(self, client_renewable_max_ttl, request):
        with patch("salt.utils.vault._build_authd_client", autospec=True) as build:
            build.return_value = (client_renewable_max_ttl, request.param)
            yield build

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        with patch("salt.utils.vault.clear_cache", autospec=True) as clear:
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
        self, build_invalid_first, clear_cache, get_config
    ):
        """
        Ensure invalid clients are not returned but rebuilt after
        clearing cache.
        """
        client = vault.get_authd_client({}, {}, get_config=get_config)
        if get_config:
            client, config = client
        client.token_valid.assert_called_with(10, remote=False)
        assert client.token_valid()
        clear_cache.assert_called_once_with({}, ANY)
        assert build_invalid_first.call_count == 2
        if get_config:
            assert config == {
                "auth": {
                    "token_lifecycle": {"minimum_ttl": 10, "renew_increment": False}
                }
            }

    @pytest.mark.parametrize("get_config", [False, True])
    def test_get_authd_client_exception(
        self, build_exception_first, clear_cache, get_config
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
        clear_cache.assert_called_once_with({}, ANY)
        assert build_exception_first.call_count == 2
        if get_config:
            assert config == {
                "auth": {
                    "token_lifecycle": {"minimum_ttl": 10, "renew_increment": False}
                }
            }

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
        with patch("salt.utils.vault._get_cache_bank", autospec=True) as cbank:
            cbank.return_value = "vault"
            yield cbank

    @pytest.fixture(autouse=True)
    def conn_config(self):
        with patch(
            "salt.utils.vault._get_connection_config", autospec=True
        ) as conn_config:
            yield conn_config

    @pytest.fixture(autouse=True)
    def fetch_secret_id(self, secret_id_response):
        with patch(
            "salt.utils.vault._fetch_secret_id", autospec=True
        ) as fetch_secret_id:
            fetch_secret_id.return_value = vault.VaultSecretId(
                **secret_id_response["data"]
            )
            yield fetch_secret_id

    @pytest.fixture(autouse=True)
    def fetch_token(self, token_auth):
        with patch("salt.utils.vault._fetch_token", autospec=True) as fetch_token:
            fetch_token.return_value = vault.VaultToken(**token_auth["auth"])
            yield fetch_token

    @pytest.fixture(params=["token", "secret_id", "both", "none"])
    def cached(self, token_auth, secret_id_response, request):
        cached_what = request.param

        def _cache(context, cbank, ckey, *args, **kwargs):
            token = Mock(spec=vault.VaultAuthCache)
            token.get.return_value = None
            approle = Mock(spec=vault.VaultAuthCache)
            approle.get.return_value = None
            if cached_what in ["token", "both"]:
                token.get.return_value = vault.VaultToken(**token_auth["auth"])
            if cached_what in ["secret_id", "both"]:
                approle.get.return_value = vault.VaultSecretId(
                    **secret_id_response["data"]
                )
            return token if ckey == vault.TOKEN_CKEY else approle

        cache = MagicMock(spec=vault.VaultAuthCache)
        cache.side_effect = _cache
        with patch("salt.utils.vault.VaultAuthCache", cache):
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
        client, config = vault._build_authd_client({}, {})
        assert client.token_valid(remote=False)
        if test_remote_config["auth"]["method"] == "approle":
            if (
                not test_remote_config["auth"]["secret_id"]
                or cached(None, None, vault.TOKEN_CKEY).get()
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
        cache = Mock(spec=vault.VaultConfigCache)
        # cached config does not include tokens
        test_remote_config["auth"].pop("token", None)
        cache.get.return_value = test_remote_config
        with patch("salt.utils.vault._get_config_cache", autospec=True) as factory:
            factory.return_value = cache
            yield cache

    @pytest.fixture
    def uncached(self):
        cache = Mock(spec=vault.VaultConfigCache)
        cache.get.return_value = None
        with patch("salt.utils.vault._get_config_cache", autospec=True) as factory:
            factory.return_value = cache
            yield cache

    @pytest.fixture
    def local(self):
        with patch("salt.utils.vault._use_local_config", autospec=True) as local:
            yield local

    @pytest.fixture
    def remote(self, test_remote_config, unauthd_client_mock):
        with patch("salt.utils.vault._query_master") as query:
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
        vault._get_connection_config("vault", {}, {}, force_local=force_local)
        local.assert_called_once()

    def test_get_connection_config_cached(self, cached, remote):
        """
        Ensure cache is respected
        """
        res, embedded_token, _ = vault._get_connection_config("vault", {}, {})
        assert res == cached.get()
        assert embedded_token is None
        cached.store.assert_not_called()
        remote.assert_not_called()

    def test_get_connection_config_uncached(self, uncached, remote):
        """
        Ensure uncached configuration is treated as expected, especially
        that the embedded token is removed and returned separately.
        """
        res, embedded_token, _ = vault._get_connection_config("vault", {}, {})
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
                vault._get_connection_config("vault", opts, {})
        else:
            vault._get_connection_config("vault", opts, {})
            if called:
                remote.assert_called()
            else:
                remote.assert_not_called()


class TestFetchSecretId:
    @pytest.fixture
    def cached(self, secret_id_response):
        cache = Mock(spec=vault.VaultAuthCache)
        cache.get.return_value = vault.VaultSecretId(**secret_id_response["data"])
        return cache

    @pytest.fixture
    def uncached(self):
        cache = Mock(spec=vault.VaultConfigCache)
        cache.get.return_value = None
        return cache

    @pytest.fixture
    def remote(self, secret_id_response, server_config, unauthd_client_mock):
        with patch("salt.utils.vault._query_master") as query:
            query.return_value = (
                {"data": secret_id_response["data"], "server": server_config},
                unauthd_client_mock,
            )
            yield query

    @pytest.fixture
    def local(self):
        with patch("salt.utils.vault._use_local_config", autospec=True) as local:
            yield local

    @pytest.fixture(params=["plain", "wrapped", "dict"])
    def secret_id(self, secret_id_response, wrapped_secret_id_response, request):
        return {
            "plain": "test-secret-id",
            "wrapped": {"wrap_info": wrapped_secret_id_response["wrap_info"]},
            "dict": secret_id_response["data"],
        }[request.param]

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
        res = vault._fetch_secret_id(
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
        res = vault._fetch_secret_id(
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
        res = vault._fetch_secret_id(
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
        res = vault._fetch_secret_id(
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
                vault._fetch_secret_id(
                    test_remote_config, opts, uncached, unauthd_client_mock
                )
        else:
            vault._fetch_secret_id(
                test_remote_config, opts, uncached, unauthd_client_mock
            )
            if called:
                remote.assert_called()
            else:
                remote.assert_not_called()


class TestFetchToken:
    @pytest.fixture
    def cached(self, token_auth):
        cache = Mock(spec=vault.VaultAuthCache)
        cache.get.return_value = vault.VaultToken(**token_auth["auth"])
        return cache

    @pytest.fixture
    def uncached(self):
        cache = Mock(spec=vault.VaultConfigCache)
        cache.get.return_value = None
        return cache

    @pytest.fixture
    def remote(self, token_auth, server_config, unauthd_client_mock):
        with patch("salt.utils.vault._query_master", autospec=True) as query:
            query.return_value = (
                {"auth": token_auth["auth"], "server": server_config},
                unauthd_client_mock,
            )
            yield query

    @pytest.fixture
    def local(self):
        with patch("salt.utils.vault._use_local_config", autospec=True) as local:
            yield local

    @pytest.fixture(params=["plain", "wrapped", "dict"])
    def token(self, token_auth, wrapped_token_auth_response, request):
        return {
            "plain": token_auth["auth"]["client_token"],
            "wrapped": {"wrap_info": wrapped_token_auth_response["wrap_info"]},
            "dict": token_auth["auth"],
        }[request.param]

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
        res = vault._fetch_token(
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
        res = vault._fetch_token(
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
        res = vault._fetch_token(test_remote_config, {}, cached, unauthd_client_mock)
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
        res = vault._fetch_token(
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
        res = vault._fetch_token(test_remote_config, {}, uncached, unauthd_client_mock)
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
        res = vault._fetch_token(test_remote_config, {}, uncached, unauthd_client_mock)
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
                vault._fetch_token(
                    test_remote_config,
                    opts,
                    uncached,
                    unauthd_client_mock,
                    embedded_token=embedded_token,
                )
        else:
            vault._fetch_token(
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
                    "config": 3600,
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
                    "config": 3600,
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
    with patch("salt.utils.vault.parse_config", Mock(return_value=test_config)):
        output, token, _ = vault._use_local_config({})
        assert output == expected_config
        assert token == expected_token


class TestQueryMaster:
    @pytest.fixture(autouse=True)
    def publish_runner(self):
        runner = Mock(return_value={"success": True})
        with patch.dict(vault.__salt__, {"publish.runner": runner}):
            yield runner

    @pytest.fixture(autouse=True)
    def saltutil_runner(self):
        runner = Mock(return_value={"success": True})
        with patch.dict(vault.__salt__, {"saltutil.runner": runner}):
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
    def unwrap_client(self, server_config, request):
        with patch("salt.utils.vault.VaultClient", autospec=True) as unwrap_client:
            unwrap_client.return_value.get_config.return_value = server_config
            unwrap_client.return_value.unwrap.return_value = {
                request.param: {"bar": "baz"}
            }
            yield unwrap_client

    def test_query_master_loads_minion_mods_if_necessary(
        self, opts, saltutil_runner, publish_runner
    ):
        """
        Ensure that the runner requests loading execution modules
        if the global has not been populated.
        """
        with patch("salt.loader.minion_mods") as loader:
            loader.return_value = {
                "publish.runner": publish_runner,
                "saltutil.runner": saltutil_runner,
            }
            with patch.dict(vault.__salt__, {}, clear=True):
                vault._query_master("func", opts)
                loader.assert_called_once_with(opts)

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
        out, _ = vault._query_master("func", opts)
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
                vault._query_master("func", opts)
        else:
            with pytest.raises(salt.exceptions.CommandExecutionError):
                vault._query_master("func", opts)

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
            vault._query_master("func", opts)

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
        publish_runner,
        saltutil_runner,
        unwrap_client,
    ):
        """
        Ensure that VaultConfigExpired is raised when expected_server is passed
        and differs from what the server reports. Also ensure that the unwrapping
        still takes place (for security reasons) and with the correct server
        configuration.
        """
        publish_runner.return_value = saltutil_runner.return_value = {
            "server": {"url": url, "verify": verify, "namespace": namespace}
        }
        with pytest.raises(vault.VaultConfigExpired):
            vault._query_master("func", opts, expected_server=server_config)
            unwrap_client.unwrap.assert_called_once()

    @pytest.mark.parametrize(
        "url,verify,namespace",
        [
            ("new-url", None, None),
            ("http://127.0.0.1:8200", "/etc/ssl/certs.pem", None),
            ("http://127.0.0.1:8200", None, "test-namespace"),
        ],
    )
    def test_query_master_invalidates_cache_when_unwrap_client_has_different_server_config(
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
    ):
        """
        Ensure that VaultConfigExpired is raised when a passed unwrap client has a different
        configuration than the server reports. Also ensure that the unwrapping still takes
        place (for security reasons) and with the correct server configuration.
        """
        publish_runner.return_value = saltutil_runner.return_value = {
            "server": {"url": url, "verify": verify, "namespace": namespace},
            "wrap_info": wrapped_role_id_response["wrap_info"],
        }
        with pytest.raises(vault.VaultConfigExpired):
            vault._query_master("func", opts, unwrap_client=unauthd_client_mock)
            unauthd_client_mock.unwrap.assert_not_called()
            unwrap_client.unwrap.assert_called_once()

    def test_query_master_verify_does_not_interfere_with_expected_server(
        self,
        opts,
        publish_runner,
        saltutil_runner,
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
            "data": {"foo": "bar"},
        }
        expected_server = {
            "url": "http://127.0.0.1:8200",
            "verify": "/etc/ssl/certs.pem",
            "namespace": None,
        }
        expected_return = {
            "server": {
                "url": "http://127.0.0.1:8200",
                "verify": "/etc/ssl/certs.pem",
                "namespace": None,
            },
            "data": {"foo": "bar"},
        }
        opts["vault"] = {"server": {"verify": "/etc/ssl/certs.pem"}}

        ret, _ = vault._query_master("func", opts, expected_server=expected_server)
        assert ret == expected_return
        assert "Mismatch of cached and reported server data detected" not in caplog.text

    def test_query_master_verify_does_not_interfere_with_unwrap_client_config(
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
        ret, _ = vault._query_master("func", opts, unwrap_client=unauthd_client_mock)
        unwrap_client.assert_not_called()
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
        out, _ = vault._query_master("func", opts, unwrap_client=unauthd_client_mock)
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
        out, _ = vault._query_master("func", opts, unwrap_client=unauthd_client_mock)
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
        publish_runner.return_value = saltutil_runner.return_value = deepcopy(response)
        out, _ = vault._query_master("func", opts)
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
        publish_runner.return_value = saltutil_runner.return_value = deepcopy(response)
        out, _ = vault._query_master("func", opts)
        nested_key = misc_data.split(":")[1]
        assert nested_key in out[key]["nested"]
        assert "misc_data" not in out
        if nested_key in response[key]["nested"]:
            assert out[key]["nested"][nested_key] == "existing"
        else:
            assert out[key]["nested"][nested_key] == "merged"


############################################
# [Authenticated]VaultClient tests
############################################


@pytest.mark.parametrize(
    "endpoint",
    [
        "secret/some/path",
        "/secret/some/path",
        "secret/some/path/",
        "/secret/some/path/",
    ],
)
def test_vault_client_request_raw_url(endpoint, client, req):
    """
    Test that requests are sent to the correct endpoint, regardless of leading or trailing slashes
    """
    expected_url = f"{client.url}/v1/secret/some/path"
    client.request_raw("GET", endpoint)
    req.assert_called_with(
        "GET",
        expected_url,
        headers=ANY,
        json=None,
        verify=client.get_config()["verify"],
    )


def test_vault_client_request_raw_kwargs_passthrough(client, req):
    """
    Test that kwargs for requests.request are passed through
    """
    client.request_raw(
        "GET", "secret/some/path", allow_redirects=False, cert="/etc/certs/client.pem"
    )
    req.assert_called_with(
        "GET",
        ANY,
        headers=ANY,
        json=ANY,
        verify=ANY,
        allow_redirects=False,
        cert="/etc/certs/client.pem",
    )


@pytest.mark.parametrize("namespace", [None, "test-namespace"])
@pytest.mark.parametrize("client", [None], indirect=True)
def test_vault_client_request_raw_headers_namespace(namespace, client, req):
    """
    Test that namespace is present in the HTTP headers only if it was specified
    """
    if namespace is not None:
        client.namespace = namespace

    namespace_header = "X-Vault-Namespace"
    client.request_raw("GET", "secret/some/path")
    headers = req.call_args.kwargs.get("headers", {})
    if namespace is None:
        assert namespace_header not in headers
    else:
        assert headers.get(namespace_header) == namespace


@pytest.mark.parametrize("wrap", [False, 30, "1h"])
def test_vault_client_request_raw_headers_wrap(wrap, client, req):
    """
    Test that the wrap header is present only if it was specified and supports time strings
    """
    wrap_header = "X-Vault-Wrap-TTL"
    client.request_raw("GET", "secret/some/path", wrap=wrap)
    headers = req.call_args.kwargs.get("headers", {})
    if not wrap:
        assert wrap_header not in headers
    else:
        assert headers.get(wrap_header) == str(wrap)


@pytest.mark.parametrize("header", ["X-Custom-Header", "X-Existing-Header"])
def test_vault_client_request_raw_headers_additional(header, client, req):
    """
    Test that additional headers are passed correctly and override default ones
    """
    with patch.object(
        client, "_get_headers", Mock(return_value={"X-Existing-Header": "unchanged"})
    ):
        client.request_raw("GET", "secret/some/path", add_headers={header: "changed"})
        actual_header = req.call_args.kwargs.get("headers", {}).get(header)
        assert actual_header == "changed"


@pytest.mark.usefixtures("req_failed")
@pytest.mark.parametrize(
    "req_failed",
    [400, 403, 404, 502, 401],
    indirect=True,
)
@pytest.mark.parametrize(
    "client",
    [None],
    indirect=True,
)
def test_vault_client_request_raw_does_not_raise_http_exception(client):
    """
    request_raw should return the raw response object regardless of HTTP status code
    """
    res = client.request_raw("GET", "secret/some/path")
    with pytest.raises(requests.exceptions.HTTPError):
        res.raise_for_status()


@pytest.mark.parametrize(
    "req_failed,expected",
    [
        (400, vault.VaultInvocationError),
        (403, vault.VaultPermissionDeniedError),
        (404, vault.VaultNotFoundError),
        (405, vault.VaultUnsupportedOperationError),
        (412, vault.VaultPreconditionFailedError),
        (500, vault.VaultServerError),
        (502, vault.VaultServerError),
        (503, vault.VaultUnavailableError),
        (401, requests.exceptions.HTTPError),
    ],
    indirect=["req_failed"],
)
@pytest.mark.parametrize("raise_error", [True, False])
def test_vault_client_request_respects_raise_error(
    raise_error, req_failed, expected, client
):
    """
    request should inspect the response object and raise appropriate errors
    or fall back to raise_for_status if raise_error is true
    """
    if raise_error:
        with pytest.raises(expected):
            client.request("GET", "secret/some/path", raise_error=raise_error)
    else:
        res = client.request("GET", "secret/some/path", raise_error=raise_error)
        assert "errors" in res


def test_vault_client_request_returns_whole_response_data(
    role_id_response, req, client
):
    """
    request should return the whole returned payload, not auth/data etc only
    """
    req.return_value = _mock_json_response(role_id_response)
    res = client.request("GET", "auth/approle/role/test-minion/role-id")
    assert res == role_id_response


def test_vault_client_request_hydrates_wrapped_response(
    wrapped_role_id_response, req, client
):
    """
    request should detect wrapped responses and return an instance of VaultWrappedResponse
    instead of raw data
    """
    req.return_value = _mock_json_response(wrapped_role_id_response)
    res = client.request("GET", "auth/approle/role/test-minion/role-id", wrap="180s")
    assert isinstance(res, vault.VaultWrappedResponse)


@pytest.mark.usefixtures("req_success")
def test_vault_client_request_returns_true_when_no_data_is_reported(client):
    """
    HTTP 204 indicates success with no data returned
    """
    res = client.request("GET", "secret/some/path")
    assert res is True


def test_vault_client_get_config(server_config, client):
    """
    The returned configuration should match the one used to create an instance of VaultClient
    """
    assert client.get_config() == server_config


@pytest.mark.parametrize("client", [None], indirect=["client"])
def test_vault_client_token_valid_false(client):
    """
    The unauthenticated client should always report the token as being invalid
    """
    assert client.token_valid() is False


@pytest.mark.parametrize("client", ["valid_token", "invalid_token"], indirect=True)
@pytest.mark.parametrize("req_any", [200, 403], indirect=True)
@pytest.mark.parametrize("remote", [False, True])
def test_vault_client_token_valid(client, remote, req_any):
    valid = client.token_valid(remote=remote)
    if not remote or not client.auth.is_valid():
        req_any.assert_not_called()
    else:
        req_any.assert_called_once()
    should_be_valid = client.auth.is_valid() and (
        not remote or req_any("POST", "abc").status_code == 200
    )
    assert valid is should_be_valid


@pytest.mark.parametrize("func", ["get", "delete", "post", "list"])
def test_vault_client_wrapper_should_not_require_payload(func, client, req):
    """
    Check that wrappers for get/delete/post/list do not require a payload
    """
    req.return_value = _mock_json_response({}, status_code=200)
    tgt = getattr(client, func)
    res = tgt("auth/approle/role/test-role/secret-id")
    assert res == {}


@pytest.mark.parametrize("func", ["patch"])
def test_vault_client_wrapper_should_require_payload(func, client, req):
    """
    Check that patch wrapper does require a payload
    """
    req.return_value = _mock_json_response({}, status_code=200)
    tgt = getattr(client, func)
    with pytest.raises(TypeError):
        tgt("auth/approle/role/test-role/secret-id")


def test_vault_client_wrap_info_only_data(wrapped_role_id_lookup_response, client, req):
    """
    wrap_info should only return the data portion of the returned wrapping information
    """
    req.return_value = _mock_json_response(wrapped_role_id_lookup_response)
    res = client.wrap_info("test-wrapping-token")
    assert res == wrapped_role_id_lookup_response["data"]


@pytest.mark.parametrize(
    "req_failed,expected", [(502, vault.VaultServerError)], indirect=["req_failed"]
)
def test_vault_client_wrap_info_should_fail_with_sensible_response(
    req_failed, expected, client
):
    """
    wrap_info should return sensible Exceptions, not KeyError etc
    """
    with pytest.raises(expected):
        client.wrap_info("test-wrapping-token")


def test_vault_client_unwrap_returns_whole_response(role_id_response, client, req):
    """
    The unwrapped response should be returned as a whole, not auth/data etc only
    """
    req.return_value = _mock_json_response(role_id_response)
    res = client.unwrap("test-wrapping-token")
    assert res == role_id_response


def test_vault_client_unwrap_should_default_to_token_header_before_payload(
    role_id_response, client, req
):
    """
    When unwrapping a wrapping token, it can be used as the authentication token header.
    If the client has a valid token, it should be used in the header instead and the
    unwrapping token should be passed in the payload
    """
    token = "test-wrapping-token"
    req.return_value = _mock_json_response(role_id_response)
    client.unwrap(token)
    if client.token_valid(remote=False):
        payload = req.call_args.kwargs.get("json", {})
        assert payload.get("token") == token
    else:
        headers = req.call_args.kwargs.get("headers", {})
        assert headers.get("X-Vault-Token") == token


@pytest.mark.parametrize("func", ["unwrap", "token_lookup"])
@pytest.mark.parametrize(
    "req_failed,expected",
    [
        (400, vault.VaultInvocationError),
        (403, vault.VaultPermissionDeniedError),
        (404, vault.VaultNotFoundError),
        (502, vault.VaultServerError),
        (401, requests.exceptions.HTTPError),
    ],
    indirect=["req_failed"],
)
def test_vault_client_unwrap_should_raise_appropriate_errors(
    func, req_failed, expected, client
):
    """
    unwrap/token_lookup should raise exceptions the same way request does
    """
    with pytest.raises(expected):
        tgt = getattr(client, func)
        tgt("test-wrapping-token")


@pytest.mark.usefixtures("req_unwrapping")
@pytest.mark.parametrize(
    "path",
    [
        "auth/approle/role/test-minion/role-id",
        "auth/approle/role/[^/]+/role-id",
        ["incorrect/path", "[^a]+", "auth/approle/role/[^/]+/role-id"],
    ],
)
def test_vault_client_unwrap_should_match_check_expected_creation_path(
    path, role_id_response, client
):
    """
    Expected creation paths should be accepted as strings and list of strings,
    where the strings can be regex patterns
    """
    res = client.unwrap("test-wrapping-token", expected_creation_path=path)
    assert res == role_id_response


@pytest.mark.usefixtures("req_unwrapping")
@pytest.mark.parametrize(
    "path",
    [
        "auth/other_mount/role/test-minion/role-id",
        "auth/approle/role/[^tes/]+/role-id",
        ["incorrect/path", "[^a]+", "auth/approle/role/[^/]/role-id"],
    ],
)
def test_vault_client_unwrap_should_fail_on_unexpected_creation_path(path, client):
    """
    When none of the patterns match, a (serious) exception should be raised
    """
    with pytest.raises(vault.VaultUnwrapException):
        client.unwrap("test-wrapping-token", expected_creation_path=path)


def test_vault_client_token_lookup_returns_data_only(
    token_lookup_self_response, req, client
):
    """
    token_lookup should return "data" only, not the whole response payload
    """
    req.return_value = _mock_json_response(token_lookup_self_response)
    res = client.token_lookup("test-token")
    assert res == token_lookup_self_response["data"]


@pytest.mark.parametrize("raw", [False, True])
def test_vault_client_token_lookup_respects_raw(raw, req, client):
    """
    when raw is True, token_lookup should return the raw response
    """
    response_data = {"foo": "bar"}
    req.return_value = _mock_json_response({"data": response_data})
    res = client.token_lookup("test-token", raw=raw)
    if raw:
        assert res.json() == {"data": response_data}
    else:
        assert res == response_data


def test_vault_client_token_lookup_uses_accessor(client, req_any):
    """
    Ensure a client can lookup tokens with provided accessor
    """
    token = "test-token"
    if client.token_valid():
        token = None
    client.token_lookup(token=token, accessor="test-token-accessor")
    payload = req_any.call_args.kwargs.get("json", {})
    _, url = req_any.call_args[0]
    assert payload.get("accessor") == "test-token-accessor"
    assert url.endswith("lookup-accessor")


# VaultClient only


@pytest.mark.usefixtures("req")
@pytest.mark.parametrize("client", [None], indirect=["client"])
def test_vault_client_token_lookup_requires_token_for_unauthenticated_client(client):
    with pytest.raises(vault.VaultInvocationError):
        client.token_lookup()


# AuthenticatedVaultClient only


@pytest.mark.usefixtures("req_any")
@pytest.mark.parametrize("client", ["valid_token"], indirect=True)
@pytest.mark.parametrize(
    "endpoint,use",
    [
        ("secret/data/some/path", True),
        ("auth/approle/role/test-minion", True),
        ("sys/internal/ui/mounts", False),
        ("sys/internal/ui/mounts/secret", False),
        ("sys/wrapping/lookup", False),
        ("sys/internal/ui/namespaces", False),
        ("sys/health", False),
        ("sys/seal-status", False),
    ],
)
def test_vault_client_request_raw_increases_use_count_when_necessary_depending_on_path(
    endpoint, use, client
):
    """
    When a request is issued to an endpoint that consumes a use, ensure it is passed
    along to the token.
    https://github.com/hashicorp/vault/blob/d467681e15898041b6dd5f2bf7789bd7c236fb16/vault/logical_system.go#L119-L155
    """
    client.request_raw("GET", endpoint)
    assert client.auth.used.called is use


@pytest.mark.parametrize("client", ["valid_token"], indirect=True)
@pytest.mark.parametrize(
    "req_failed",
    [400, 403, 404, 405, 412, 500, 502, 503, 401],
    indirect=True,
)
def test_vault_client_request_raw_increases_use_count_when_necessary_depending_on_response(
    req_failed, client
):
    """
    When a request is issued to an endpoint that consumes a use, make sure that
    this is registered regardless of status code:
    https://github.com/hashicorp/vault/blob/c1cf97adac5c53301727623a74b828a5f12592cf/vault/request_handling.go#L864-L866
    ref: PR #62552
    """
    client.request_raw("GET", "secret/data/some/path")
    assert client.auth.used.called is True


@pytest.mark.usefixtures("req_any")
@pytest.mark.parametrize("client", ["valid_token"], indirect=True)
def test_vault_client_request_raw_does_not_increase_use_count_with_unauthd_endpoint(
    client,
):
    """
    Unauthenticated endpoints do not consume a token use. Since some cannot be detected
    easily because of customizable mount points for secret engines and auth methods,
    this can be specified in the request. Make sure it is honored.
    """
    client.request("GET", "pki/cert/ca", is_unauthd=True)
    client.auth.used.assert_not_called()


@pytest.mark.parametrize("client", ["valid_token"], indirect=True)
def test_vault_client_token_lookup_self_possible(client, req_any):
    """
    Ensure an authenticated client can lookup its own token
    """
    client.token_lookup()
    headers = req_any.call_args.kwargs.get("headers", {})
    _, url = req_any.call_args[0]
    assert headers.get("X-Vault-Token") == str(client.auth.get_token())
    assert url.endswith("lookup-self")


@pytest.mark.parametrize("client", ["valid_token"], indirect=True)
def test_vault_client_token_lookup_supports_token_arg(client, req_any):
    """
    Ensure an authenticated client can lookup other tokens
    """
    token = "other-test-token"
    client.token_lookup(token=token)
    headers = req_any.call_args.kwargs.get("headers", {})
    payload = req_any.call_args.kwargs.get("json", {})
    _, url = req_any.call_args[0]
    assert payload.get("token") == token
    assert headers.get("X-Vault-Token") == str(client.auth.get_token())
    assert url.endswith("lookup")


@pytest.mark.parametrize("client", ["valid_token"], indirect=True)
@pytest.mark.parametrize("renewable", [True, False])
def test_vault_client_token_renew_self_possible(
    token_renew_self_response, client, req, renewable
):
    """
    Ensure an authenticated client can renew its own token only when
    it is renewable and that the renewed data is passed along to the
    token store
    """
    req.return_value = _mock_json_response(token_renew_self_response)
    client.auth.is_renewable.return_value = renewable
    res = client.token_renew()
    if renewable:
        headers = req.call_args.kwargs.get("headers", {})
        _, url = req.call_args[0]
        assert headers.get("X-Vault-Token") == str(client.auth.get_token())
        assert url.endswith("renew-self")
        req.assert_called_once()
        client.auth.update_token.assert_called_once_with(
            token_renew_self_response["auth"]
        )
        assert res == token_renew_self_response["auth"]
    else:
        assert res is False


@pytest.mark.parametrize("client", ["valid_token"], indirect=True)
def test_vault_client_token_renew_supports_token_arg(
    token_renew_other_response, client, req
):
    """
    Ensure an authenticated client can renew other tokens
    """
    req.return_value = _mock_json_response(token_renew_other_response)
    token = "other-test-token"
    client.token_renew(token=token)
    headers = req.call_args.kwargs.get("headers", {})
    payload = req.call_args.kwargs.get("json", {})
    _, url = req.call_args[0]
    assert payload.get("token") == token
    assert headers.get("X-Vault-Token") == str(client.auth.get_token())
    assert url.endswith("renew")


@pytest.mark.parametrize("client", ["valid_token"], indirect=True)
def test_vault_client_token_renew_uses_accessor(
    token_renew_accessor_response, client, req
):
    """
    Ensure a client can renew tokens with provided accessor
    """
    req.return_value = _mock_json_response(token_renew_accessor_response)
    client.token_renew(accessor="test-token-accessor")
    payload = req.call_args.kwargs.get("json", {})
    _, url = req.call_args[0]
    assert payload.get("accessor") == "test-token-accessor"
    assert url.endswith("renew-accessor")


@pytest.mark.parametrize("client", ["valid_token"], indirect=True)
@pytest.mark.parametrize("token", [None, "other-test-token"])
def test_vault_client_token_renew_self_updates_token(
    token_renew_self_response, client, token, req
):
    """
    Ensure the current client token is updated when it is renewed, but not
    when another token is renewed
    """
    req.return_value = _mock_json_response(token_renew_self_response)
    client.token_renew(token=token)
    if token is None:
        assert client.auth.update_token.called
    else:
        assert not client.auth.update_token.called


@pytest.mark.parametrize("client", ["valid_token"], indirect=True)
@pytest.mark.parametrize(
    "token,accessor",
    [(None, None), ("other-test-token", None), (None, "test-accessor")],
)
def test_vault_client_token_renew_increment_is_honored(
    token, accessor, client, token_renew_self_response, req
):
    """
    Ensure the renew increment is passed to vault if provided
    """
    req.return_value = _mock_json_response(token_renew_self_response)
    client.token_renew(token=token, accessor=accessor, increment=3600)
    payload = req.call_args.kwargs.get("json", {})
    assert payload.get("increment") == 3600


############################################
# VaultLease tests
############################################


@pytest.mark.parametrize(
    "creation_time,expected",
    [
        ("2022-08-22T17:16:21-09:30", 1661222781),
        ("2022-08-22T17:16:21-01:00", 1661192181),
        ("2022-08-22T17:16:21+00:00", 1661188581),
        ("2022-08-22T17:16:21Z", 1661188581),
        ("2022-08-22T17:16:21+02:00", 1661181381),
        ("2022-08-22T17:16:21+12:30", 1661143581),
    ],
)
def test_iso_to_timestamp_polyfill(creation_time, expected):
    with patch("salt.utils.vault.datetime.datetime") as d:
        d.fromisoformat.side_effect = AttributeError
        # needs from datetime import datetime, otherwise results
        # in infinite recursion

        # pylint: disable=unnecessary-lambda
        d.side_effect = lambda *args: datetime(*args)
        res = vault.iso_to_timestamp(creation_time)
        assert res == expected


@pytest.mark.parametrize(
    "creation_time",
    [
        1661188581,
        "1661188581",
        "2022-08-22T17:16:21.473219641+00:00",
        "2022-08-22T17:16:21.47321964+00:00",
        "2022-08-22T17:16:21.4732196+00:00",
        "2022-08-22T17:16:21.473219+00:00",
        "2022-08-22T17:16:21.47321+00:00",
        "2022-08-22T17:16:21.4732+00:00",
        "2022-08-22T17:16:21.473+00:00",
        "2022-08-22T17:16:21.47+00:00",
        "2022-08-22T17:16:21.4+00:00",
    ],
)
def test_vault_lease_creation_time_normalization(creation_time):
    """
    Ensure the normalization of different creation_time formats works as expected -
    many token endpoints report a timestamp, while other endpoints report RFC3339-formatted
    strings that may have a variable number of digits for sub-second precision (0 omitted)
    while datetime.fromisoformat expects exactly 6 digits
    """
    data = {
        "lease_id": "id",
        "renewable": False,
        "lease_duration": 1337,
        "creation_time": creation_time,
        "data": None,
    }
    res = vault.VaultLease(**data)
    assert res.creation_time == 1661188581


@pytest.mark.parametrize(
    "tock,duration,offset,expected",
    [
        (0, 50, 0, True),
        (50, 10, 0, False),
        (0, 60, 10, True),
        (0, 60, 600, False),
    ],
)
def test_vault_lease_is_valid_accounts_for_time(tock, duration, offset, expected):
    """
    Ensure lease validity is checked correctly and can look into the future
    """
    data = {
        "lease_id": "id",
        "renewable": False,
        "lease_duration": duration,
        "creation_time": 0,
        "expire_time": duration,
        "data": None,
    }
    with patch("salt.utils.vault.time.time", return_value=tock):
        res = vault.VaultLease(**data)
        assert res.is_valid(offset) is expected


@pytest.mark.parametrize(
    "tock,duration,offset,expected",
    [
        (0, 50, 0, True),
        (50, 10, 0, False),
        (0, 60, 10, True),
        (0, 60, 600, False),
    ],
)
def test_vault_token_is_valid_accounts_for_time(tock, duration, offset, expected):
    """
    Ensure token time validity is checked correctly and can look into the future
    """
    data = {
        "client_token": "id",
        "renewable": False,
        "lease_duration": duration,
        "num_uses": 0,
        "creation_time": 0,
        "expire_time": duration,
    }
    with patch("salt.utils.vault.time.time", return_value=tock):
        res = vault.VaultToken(**data)
        assert res.is_valid(offset) is expected


@pytest.mark.parametrize(
    "num_uses,uses,expected",
    [(0, 999999, True), (1, 0, True), (1, 1, False), (1, 2, False)],
)
def test_vault_token_is_valid_accounts_for_num_uses(num_uses, uses, expected):
    """
    Ensure token uses validity is checked correctly
    """
    data = {
        "client_token": "id",
        "renewable": False,
        "lease_duration": 0,
        "num_uses": num_uses,
        "creation_time": 0,
        "use_count": uses,
    }
    with patch("salt.utils.vault.VaultLease.is_valid", Mock(return_value=True)):
        res = vault.VaultToken(**data)
        assert res.is_valid() is expected


@pytest.mark.parametrize(
    "tock,duration,offset,expected",
    [
        (0, 50, 0, True),
        (50, 10, 0, False),
        (0, 60, 10, True),
        (0, 60, 600, False),
    ],
)
def test_vault_approle_secret_id_is_valid_accounts_for_time(
    tock, duration, offset, expected
):
    """
    Ensure secret ID time validity is checked correctly and can look into the future
    """
    data = {
        "secret_id": "test-secret-id",
        "renewable": False,
        "creation_time": 0,
        "expire_time": duration,
        "secret_id_num_uses": 0,
        "secret_id_ttl": duration,
    }
    with patch("salt.utils.vault.time.time", return_value=tock):
        res = vault.VaultSecretId(**data)
        assert res.is_valid(offset) is expected


@pytest.mark.parametrize(
    "num_uses,uses,expected",
    [(0, 999999, True), (1, 0, True), (1, 1, False), (1, 2, False)],
)
def test_vault_approle_secret_id_is_valid_accounts_for_num_uses(
    num_uses, uses, expected
):
    """
    Ensure secret ID uses validity is checked correctly
    """
    data = {
        "secret_id": "test-secret-id",
        "renewable": False,
        "creation_time": 0,
        "secret_id_ttl": 0,
        "secret_id_num_uses": num_uses,
        "use_count": uses,
    }
    with patch("salt.utils.vault.VaultLease.is_valid", Mock(return_value=True)):
        res = vault.VaultSecretId(**data)
        assert res.is_valid() is expected


############################################
# Auth tests
############################################


class TestAuthMethods:
    @pytest.fixture
    def token(self, token_auth):
        return vault.VaultToken(**token_auth["auth"])

    @pytest.fixture
    def token_invalid(self, token_auth):
        token_auth["auth"]["num_uses"] = 1
        token_auth["auth"]["use_count"] = 1
        return vault.VaultToken(**token_auth["auth"])

    @pytest.fixture
    def token_unrenewable(self, token_auth):
        token_auth["auth"]["renewable"] = False
        return vault.VaultToken(**token_auth["auth"])

    @pytest.fixture
    def secret_id(self, secret_id_response):
        return vault.VaultSecretId(**secret_id_response["data"])

    @pytest.fixture
    def secret_id_invalid(self, secret_id_response):
        secret_id_response["data"]["secret_id_num_uses"] = 1
        secret_id_response["data"]["use_count"] = 1
        return vault.VaultSecretId(**secret_id_response["data"])

    @pytest.fixture(params=["secret_id"])
    def approle(self, request):
        secret_id = request.param
        if secret_id is not None:
            secret_id = request.getfixturevalue(secret_id)
        return vault.VaultAppRole("test-role-id", secret_id)

    @pytest.fixture
    def approle_invalid(self, secret_id_invalid):
        return vault.VaultAppRole("test-role-id", secret_id_invalid)

    @pytest.fixture
    def token_store(self, token):
        store = Mock(spec=vault.VaultTokenAuth)
        store.is_valid.return_value = True
        store.get_token.return_value = token
        return store

    @pytest.fixture
    def token_store_empty(self, token_store):
        token_store.is_valid.return_value = False
        token_store.get_token.side_effect = vault.VaultAuthExpired
        return token_store

    @pytest.fixture
    def token_store_empty_first(self, token_store, token):
        token_store.is_valid.side_effect = (False, True)
        token_store.get_token.side_effect = (token, vault.VaultException)
        return token_store

    @pytest.fixture
    def uncached(self):
        cache = Mock(spec=vault.VaultAuthCache)
        cache.exists.return_value = False
        cache.get.return_value = None
        return cache

    @pytest.fixture
    def cached_token(self, uncached, token):
        uncached.exists.return_value = True
        uncached.get.return_value = token
        return uncached

    @pytest.fixture
    def client(self, token_auth):
        token_auth["auth"]["client_token"] = "new-test-token"
        with patch("salt.utils.vault.VaultClient", autospec=True) as client:
            client.post.return_value = token_auth
            yield client

    def test_token_auth_uninitialized(self, uncached):
        """
        Test that an exception is raised when a token is requested
        and the authentication container was not passed a valid token.
        """
        auth = vault.VaultTokenAuth(cache=uncached)
        uncached.get.assert_called_once()
        assert auth.is_valid() is False
        assert auth.is_renewable() is False
        auth.used()
        with pytest.raises(vault.VaultAuthExpired):
            auth.get_token()

    def test_token_auth_cached(self, cached_token, token):
        """
        Test that tokens are read from cache.
        """
        auth = vault.VaultTokenAuth(cache=cached_token)
        assert auth.is_valid()
        assert auth.get_token() == token

    def test_token_auth_invalid_token(self, invalid_token):
        """
        Test that an exception is raised when a token is requested
        and the container's token is invalid.
        """
        auth = vault.VaultTokenAuth(token=invalid_token)
        assert auth.is_valid() is False
        assert auth.is_renewable() is False
        with pytest.raises(vault.VaultAuthExpired):
            auth.get_token()

    def test_token_auth_unrenewable_token(self, token_unrenewable):
        """
        Test that it is reported correctly by the container
        when a token is not renewable.
        """
        auth = vault.VaultTokenAuth(token=token_unrenewable)
        assert auth.is_valid() is True
        assert auth.is_renewable() is False
        assert auth.get_token() == token_unrenewable

    @pytest.mark.parametrize("num_uses", [0, 1, 10])
    def test_token_auth_used_num_uses(self, uncached, token, num_uses):
        """
        Ensure that cache writes for use count are only done when
        num_uses is not 0 (= unlimited)
        """
        token = token.with_renewed(num_uses=num_uses)
        auth = vault.VaultTokenAuth(cache=uncached, token=token)
        auth.used()
        if num_uses > 1:
            uncached.store.assert_called_once_with(token)
        elif num_uses:
            uncached.flush.assert_called_once()
        else:
            uncached.store.assert_not_called()

    @pytest.mark.parametrize("num_uses", [0, 1, 10])
    def test_token_auth_update_token(self, uncached, token, num_uses):
        """
        Ensure that partial updates to the token in use are possible
        and that the cache writes are independent from num_uses.
        Also ensure the token is treated as immutable
        """
        auth = vault.VaultTokenAuth(cache=uncached, token=token)
        old_token = token
        old_token_ttl = old_token.duration
        auth.update_token({"num_uses": num_uses, "ttl": 8483})
        updated_token = token.with_renewed(num_uses=num_uses, ttl=8483)
        assert auth.token == updated_token
        assert old_token.duration == old_token_ttl
        uncached.store.assert_called_once_with(updated_token)

    def test_token_auth_replace_token(self, uncached, token):
        """
        Ensure completely replacing the token is possible and
        results in a cache write. This is important when an
        InvalidVaultToken has to be replaced with a VaultToken,
        eg by a different authentication method.
        """
        auth = vault.VaultTokenAuth(cache=uncached)
        assert isinstance(auth.token, vault.InvalidVaultToken)
        auth.replace_token(token)
        assert isinstance(auth.token, vault.VaultToken)
        assert auth.token == token
        uncached.store.assert_called_once_with(token)

    @pytest.mark.parametrize("token", [False, True])
    @pytest.mark.parametrize("approle", [False, True])
    def test_approle_auth_is_valid(self, token, approle):
        """
        Test that is_valid reports true when either the token
        or the secret ID is valid
        """
        token = Mock(spec=vault.VaultToken)
        token.is_valid.return_value = token
        approle = Mock(spec=vault.VaultSecretId)
        approle.is_valid.return_value = approle
        auth = vault.VaultAppRoleAuth(approle, None, token_store=token)
        assert auth.is_valid() is (token or approle)

    def test_approle_auth_get_token_store_available(self, token_store, approle, token):
        """
        Ensure no login attempt is made when a cached token is available
        """
        auth = vault.VaultAppRoleAuth(approle, None, token_store=token_store)
        with patch("salt.utils.vault.VaultAppRoleAuth._login") as login:
            res = auth.get_token()
            login.assert_not_called()
            assert res == token

    def test_approle_auth_get_token_store_empty(
        self, token_store_empty, approle, token
    ):
        """
        Ensure a token is returned if no cached token is available
        """
        auth = vault.VaultAppRoleAuth(approle, None, token_store=token_store_empty)
        with patch("salt.utils.vault.VaultAppRoleAuth._login") as login:
            login.return_value = token
            res = auth.get_token()
            login.assert_called_once()
            assert res == token

    def test_approle_auth_get_token_invalid(self, token_store_empty, approle_invalid):
        """
        Ensure VaultAuthExpired is raised if a token request was made, but
        cannot be fulfilled
        """
        auth = vault.VaultAppRoleAuth(
            approle_invalid, None, token_store=token_store_empty
        )
        with pytest.raises(vault.VaultAuthExpired):
            auth.get_token()

    @pytest.mark.parametrize("mount", ["approle", "salt_minions"])
    @pytest.mark.parametrize("approle", ["secret_id", None], indirect=True)
    def test_approle_auth_get_token_login(
        self, approle, mount, client, token_store_empty_first, token
    ):
        """
        Ensure that login with secret-id returns a token that is passed to the
        token store/cache as well
        """
        auth = vault.VaultAppRoleAuth(
            approle, client, mount=mount, token_store=token_store_empty_first
        )
        res = auth.get_token()
        assert res == token
        args, kwargs = client.post.call_args
        endpoint = args[0]
        payload = kwargs.get("payload", {})
        assert endpoint == f"auth/{mount}/login"
        assert "role_id" in payload
        if approle.secret_id is not None:
            assert "secret_id" in payload
        token_store_empty_first.replace_token.assert_called_once_with(res)

    @pytest.mark.parametrize("num_uses", [0, 1, 10])
    def test_approle_auth_used_num_uses(
        self, token_store_empty_first, approle, client, uncached, num_uses, token
    ):
        """
        Ensure that cache writes for use count are only done when
        num_uses is not 0 (= unlimited)
        """
        approle.secret_id = approle.secret_id.with_renewed(num_uses=num_uses)
        auth = vault.VaultAppRoleAuth(
            approle, client, cache=uncached, token_store=token_store_empty_first
        )
        res = auth.get_token()
        assert res == token
        if num_uses > 1:
            uncached.store.assert_called_once_with(approle.secret_id)
        elif num_uses:
            uncached.store.assert_not_called()
            uncached.flush.assert_called_once()
        else:
            uncached.store.assert_not_called()

    def test_approle_auth_used_locally_configured(
        self, token_store_empty_first, approle, client, uncached, token
    ):
        """
        Ensure that locally configured secret IDs are not cached.
        """
        approle.secret_id = vault.LocalVaultSecretId(**approle.secret_id.to_dict())
        auth = vault.VaultAppRoleAuth(
            approle, client, cache=uncached, token_store=token_store_empty_first
        )
        res = auth.get_token()
        assert res == token
        uncached.store.assert_not_called()


def test_approle_allows_no_secret_id():
    """
    Ensure AppRole containers are still valid if no
    secret ID has been set (bind_secret_id can be set to False!)
    """
    role = vault.VaultAppRole("test-role-id")
    assert role.is_valid()


############################################
# Cache tests
############################################


@pytest.mark.parametrize("ckey", ["token", None])
@pytest.mark.parametrize("connection", [True, False])
def test_clear_cache(ckey, connection):
    """
    Make sure clearing cache works as expected, allowing for
    connection-scoped cache and global cache that survives
    a configuration refresh
    """
    cbank = "vault"
    if connection:
        cbank += "/connection"
    context = {cbank: {"token": "fake_token"}}
    with patch("salt.cache.factory", autospec=True) as factory:
        vault.clear_cache({}, context, ckey=ckey, connection=connection)
        factory.return_value.flush.assert_called_once_with(cbank, ckey)
        if ckey:
            assert ckey not in context[cbank]
        else:
            assert cbank not in context


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
    cbank = vault._get_cache_bank(opts, force_local=force_local, connection=connection)
    if connection:
        expected += "/connection"
    assert cbank == expected


class TestVaultCache:
    @pytest.fixture
    def cbank(self):
        return "vault/connection"

    @pytest.fixture
    def ckey(self):
        return "test"

    @pytest.fixture
    def data(self):
        return {"foo": "bar"}

    @pytest.fixture
    def context(self, cbank, ckey, data):
        return {cbank: {ckey: data}}

    @pytest.fixture
    def cache_factory(self):
        with patch("salt.cache.factory", autospec=True) as factory:
            yield factory

    @pytest.fixture
    def cached(self, cache_factory, data):
        cache = Mock(spec=salt.cache.Cache)
        cache.contains.return_value = True
        cache.fetch.return_value = data
        cache.updated.return_value = time.time()
        cache_factory.return_value = cache
        return cache

    @pytest.fixture
    def cached_outdated(self, cache_factory, data):
        cache = Mock(spec=salt.cache.Cache)
        cache.contains.return_value = True
        cache.fetch.return_value = data
        cache.updated.return_value = time.time() - 9999999
        cache_factory.return_value = cache
        return cache

    @pytest.fixture
    def uncached(self, cache_factory):
        cache = Mock(spec=salt.cache.Cache)
        cache.contains.return_value = False
        cache.fetch.return_value = None
        cache.updated.return_value = None
        cache_factory.return_value = cache
        return cache

    @pytest.mark.parametrize("config", ["session", "other"])
    def test_get_uncached(self, config, uncached, cbank, ckey):
        """
        Ensure that unavailable cached data is reported as None.
        """
        cache = vault.VaultCache(
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
        cache = vault.VaultCache(context, cbank, ckey, cache_backend=cached)
        res = cache.get()
        assert res == data
        cached.updated.assert_not_called()
        cached.fetch.assert_not_called()

    def test_get_cached_not_outdated(self, cached, cbank, ckey, data):
        """
        Ensure that cached data that is still valid is returned.
        """
        cache = vault.VaultCache({}, cbank, ckey, cache_backend=cached, ttl=3600)
        res = cache.get()
        assert res == data
        cached.updated.assert_called_once_with(cbank, ckey)
        cached.fetch.assert_called_once_with(cbank, ckey)

    def test_get_cached_outdated(self, cached_outdated, cbank, ckey):
        """
        Ensure that cached data that is not valid anymore is flushed
        and None is returned by default.
        """
        cache = vault.VaultCache({}, cbank, ckey, cache_backend=cached_outdated, ttl=1)
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
        cache = vault.VaultCache(
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
        cache = vault.VaultCache(
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
        cache = vault.VaultCache(
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
    def cbank(self):
        return "vault/connection"

    @pytest.fixture
    def ckey(self):
        return "test"

    @pytest.fixture
    def data(self, config):
        return {
            "cache": {
                "backend": "new",
                "config": 1337,
                "secret": "ttl",
            }
        }

    @pytest.fixture
    def context(self, cbank, ckey, data):
        return {cbank: {ckey: data}}

    # TODO: most of the following fixtures should patch the parent class
    @pytest.fixture
    def cache_factory(self):
        with patch("salt.cache.factory", autospec=True) as factory:
            yield factory

    @pytest.fixture
    def cached(self, cache_factory, data):
        cache = Mock(spec=salt.cache.Cache)
        cache.contains.return_value = True
        cache.fetch.return_value = data
        cache.updated.return_value = time.time()
        cache_factory.return_value = cache
        return cache

    @pytest.fixture
    def cached_outdated(self, cache_factory, data):
        cache = Mock(spec=salt.cache.Cache)
        cache.contains.return_value = True
        cache.fetch.return_value = data
        cache.updated.return_value = time.time() - 9999999
        cache_factory.return_value = cache
        return cache

    @pytest.fixture
    def uncached(self, cache_factory):
        cache = Mock(spec=salt.cache.Cache)
        cache.contains.return_value = False
        cache.fetch.return_value = None
        cache.updated.return_value = None
        cache_factory.return_value = cache
        return cache

    @pytest.mark.usefixtures("uncached")
    def test_get_config_cache_uncached(self, cbank, ckey):
        """
        Ensure an uninitialized instance is returned when there is no cache
        """
        res = vault._get_config_cache({}, {}, cbank, ckey)
        assert res.config is None

    def test_get_config_context_cached(self, uncached, cbank, ckey, context):
        """
        Ensure cached data in context wins
        """
        res = vault._get_config_cache({}, context, cbank, ckey)
        assert res.config == context[cbank][ckey]
        uncached.contains.assert_not_called()

    def test_get_config_other_cached(self, cached, cbank, ckey, data):
        """
        Ensure cached data from other sources is respected
        """
        res = vault._get_config_cache({}, {}, cbank, ckey)
        assert res.config == data
        cached.contains.assert_called_once_with(cbank, ckey)
        cached.fetch.assert_called_once_with(cbank, ckey)

    def test_reload(self, config, data, cbank, ckey):
        """
        Ensure that a changed configuration is reloaded correctly and
        during instantiation. When the config backend changes and the
        previous was not session only, it should be flushed.
        """
        with patch("salt.utils.vault.VaultConfigCache.flush") as flush:
            cache = vault.VaultConfigCache({}, cbank, ckey, {}, init_config=config)
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
        cache = vault.VaultConfigCache(context, cbank, ckey, {}, init_config=config)
        res = cache.exists()
        assert res is bool(config)

    def test_get(self, config, cached, context, cbank, ckey, data):
        """
        Ensure cached data is returned and backend settings honored,
        unless the instance has not been initialized yet
        """
        if config is not None and config["cache"]["backend"] != "session":
            context = {}
        cache = vault.VaultConfigCache(context, cbank, ckey, {}, init_config=config)
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
            context_old = deepcopy(context)
        cache = vault.VaultConfigCache(context, cbank, ckey, {}, init_config=config)
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
        cache = vault.VaultConfigCache({}, {}, cbank, ckey)
        assert cache.config is None
        with patch("salt.utils.vault.VaultConfigCache._load") as rld:
            with patch("salt.utils.vault.VaultCache.store") as store:
                cache.store(data)
                rld.assert_called_once_with(data)
                store.assert_called_once()


class TestVaultAuthCache:
    @pytest.fixture
    def uncached(self):
        with patch(
            "salt.utils.vault.CommonCache._ckey_exists",
            return_value=False,
            autospec=True,
        ):
            with patch(
                "salt.utils.vault.CommonCache._get_ckey",
                return_value=None,
                autospec=True,
            ) as get:
                yield get

    @pytest.fixture
    def cached(self, token_auth):
        with patch(
            "salt.utils.vault.CommonCache._ckey_exists",
            return_value=True,
            autospec=True,
        ):
            with patch(
                "salt.utils.vault.CommonCache._get_ckey",
                return_value=token_auth["auth"],
                autospec=True,
            ) as get:
                yield get

    @pytest.fixture
    def cached_invalid_flush(self, token_auth, cached):
        with patch("salt.utils.vault.CommonCache._flush", autospec=True) as flush:
            token_auth["auth"]["num_uses"] = 1
            token_auth["auth"]["use_count"] = 1
            cached.return_value = token_auth["auth"]
            yield flush

    @pytest.mark.usefixtures("uncached")
    def test_get_uncached(self):
        """
        Ensure that unavailable cached data is reported as None.
        """
        cache = vault.VaultAuthCache({}, None, None, vault.VaultToken)
        res = cache.get()
        assert res is None

    @pytest.mark.usefixtures("cached")
    def test_get_cached(self, token_auth):
        """
        Ensure that cached data that is still valid is returned.
        """
        cache = vault.VaultAuthCache({}, None, None, vault.VaultToken)
        res = cache.get()
        assert res is not None
        assert res == vault.VaultToken(**token_auth["auth"])

    def test_get_cached_invalid(self, cached_invalid_flush):
        """
        Ensure that cached data that is not valid anymore is flushed
        and None is returned.
        """
        cache = vault.VaultAuthCache({}, None, None, vault.VaultToken)
        res = cache.get()
        assert res is None
        cached_invalid_flush.assert_called_once()

    def test_store(self, token_auth):
        """
        Ensure that storing authentication data sends a dictionary
        representation to the store implementation of the parent class.
        """
        token = vault.VaultToken(**token_auth["auth"])
        cache = vault.VaultAuthCache({}, "cbank", "ckey", vault.VaultToken)
        with patch("salt.utils.vault.CommonCache._store_ckey") as store:
            cache.store(token)
            store.assert_called_once_with("ckey", token.to_dict())


############################################
# VaultKV tests
############################################


@pytest.mark.parametrize(
    "kv_meta,expected",
    [
        (
            "v1",
            "kvv1_info",
        ),
        (
            "v2",
            "kvv2_info",
        ),
        (
            "invalid",
            "no_kv_info",
        ),
    ],
    indirect=["kv_meta"],
)
def test_vault_kv_is_v2_no_cache(kv_meta, expected, request):
    """
    Ensure path metadata is requested as expected and cached
    if the lookup succeeds
    """
    expected_val = request.getfixturevalue(expected)
    res = kv_meta.is_v2("secret/some/path")
    kv_meta.metadata_cache.get.assert_called_once()
    kv_meta.client.get.assert_called_once_with(
        "sys/internal/ui/mounts/secret/some/path"
    )
    if expected != "no_kv_info":
        kv_meta.metadata_cache.store.assert_called_once()
    assert res == expected_val


@pytest.mark.parametrize(
    "kv_meta_cached,expected",
    [
        (
            "v1",
            "kvv1_info",
        ),
        (
            "v2",
            "kvv2_info",
        ),
    ],
    indirect=["kv_meta_cached"],
)
def test_vault_kv_is_v2_cached(kv_meta_cached, expected, request):
    """
    Ensure cache is respected for path metadata
    """
    expected = request.getfixturevalue(expected)
    res = kv_meta_cached.is_v2("secret/some/path")
    kv_meta_cached.metadata_cache.get.assert_called_once()
    kv_meta_cached.metadata_cache.store.assert_not_called()
    kv_meta_cached.client.assert_not_called()
    assert res == expected


class TestKVV1:
    path = "secret/some/path"

    @pytest.mark.parametrize("include_metadata", [False, True])
    def test_vault_kv_read(self, kvv1, include_metadata):
        """
        Ensure that VaultKV.read works for KV v1 and does not fail if
        metadata is requested, which is invalid for KV v1.
        """
        res = kvv1.read(self.path, include_metadata=include_metadata)
        kvv1.client.get.assert_called_once_with(self.path)
        assert res == {"foo": "bar"}

    def test_vault_kv_write(self, kvv1):
        """
        Ensure that VaultKV.write works for KV v1.
        """
        data = {"bar": "baz"}
        kvv1.write(self.path, data)
        kvv1.client.post.assert_called_once_with(self.path, payload=data)

    def test_vault_kv_patch(self, kvv1):
        """
        Ensure that VaultKV.patch fails for KV v1. This action was introduced
        in KV v2. It could be simulated in Python though.
        """
        with pytest.raises(vault.VaultInvocationError):
            kvv1.patch(self.path, {"bar": "baz"})

    def test_vault_kv_delete(self, kvv1):
        """
        Ensure that VaultKV.delete works for KV v1.
        """
        kvv1.delete(self.path)
        kvv1.client.request.assert_called_once_with("DELETE", self.path, payload=None)

    def test_vault_kv_delete_versions(self, kvv1):
        """
        Ensure that VaultKV.delete with versions raises an exception for KV v1.
        """
        with pytest.raises(
            vault.VaultInvocationError, match="Versioning support requires kv-v2.*"
        ):
            kvv1.delete(self.path, versions=[1, 2, 3, 4])

    def test_vault_kv_destroy(self, kvv1):
        """
        Ensure that VaultKV.destroy raises an exception for KV v1.
        """
        with pytest.raises(vault.VaultInvocationError):
            kvv1.destroy(self.path, [1, 2, 3, 4])

    def test_vault_kv_nuke(self, kvv1):
        """
        Ensure that VaultKV.nuke raises an exception for KV v1.
        """
        with pytest.raises(vault.VaultInvocationError):
            kvv1.nuke(self.path)

    def test_vault_kv_list(self, kvv1):
        """
        Ensure that VaultKV.list works for KV v1 and only returns keys.
        """
        res = kvv1.list(self.path)
        kvv1.client.list.assert_called_once_with(self.path)
        assert res == ["foo"]


class TestKVV2:
    path = "secret/some/path"
    paths = {
        "data": "secret/data/some/path",
        "metadata": "secret/metadata/some/path",
        "delete": "secret/data/some/path",
        "delete_versions": "secret/delete/some/path",
        "destroy": "secret/destroy/some/path",
    }

    @pytest.mark.parametrize(
        "versions,expected",
        [
            (0, [0]),
            ("1", [1]),
            ([2], [2]),
            (["3"], [3]),
        ],
    )
    def test_parse_versions(self, kvv2, versions, expected):
        """
        Ensure parsing versions works as expected:
        single integer/number string or list of those are allowed
        """
        assert kvv2._parse_versions(versions) == expected

    def test_parse_versions_raises_exception_when_unparsable(self, kvv2):
        """
        Ensure unparsable versions raise an exception
        """
        with pytest.raises(vault.VaultInvocationError):
            kvv2._parse_versions("four")

    def test_get_secret_path_metadata_lookup_unexpected_response(self, kvv2, caplog):
        """
        Ensure unexpected responses are treated as not KV
        """
        kvv2.client.get.return_value = MagicMock(
            _mock_json_response({"wrap_info": {}}, status_code=200)
        )
        res = kvv2._get_secret_path_metadata(self.path)
        assert res is None
        assert "Unexpected response to metadata query" in caplog.text

    def test_get_secret_path_metadata_lookup_request_error(self, kvv2, caplog):
        """
        Ensure HTTP error status codes are treated as not KV
        """
        kvv2.client.get.side_effect = vault.VaultPermissionDeniedError
        res = kvv2._get_secret_path_metadata(self.path)
        assert res is None
        assert "VaultPermissionDeniedError:" in caplog.text

    @pytest.mark.parametrize("include_metadata", [False, True])
    def test_vault_kv_read(self, kvv2, include_metadata, kvv2_response):
        """
        Ensure that VaultKV.read works for KV v2 and returns metadata
        if requested.
        """
        res = kvv2.read(self.path, include_metadata=include_metadata)
        kvv2.client.get.assert_called_once_with(self.paths["data"])
        if include_metadata:
            assert res == kvv2_response["data"]
        else:
            assert res == kvv2_response["data"]["data"]

    def test_vault_kv_write(self, kvv2):
        """
        Ensure that VaultKV.write works for KV v2.
        """
        data = {"bar": "baz"}
        kvv2.write(self.path, data)
        kvv2.client.post.assert_called_once_with(
            self.paths["data"], payload={"data": data}
        )

    def test_vault_kv_patch(self, kvv2):
        """
        Ensure that VaultKV.patch works for KV v2.
        """
        data = {"bar": "baz"}
        kvv2.patch(self.path, data)
        kvv2.client.patch.assert_called_once_with(
            self.paths["data"],
            payload={"data": data},
            add_headers={"Content-Type": "application/merge-patch+json"},
        )

    def test_vault_kv_delete(self, kvv2):
        """
        Ensure that VaultKV.delete works for KV v2.
        """
        kvv2.delete(self.path)
        kvv2.client.request.assert_called_once_with(
            "DELETE", self.paths["data"], payload=None
        )

    @pytest.mark.parametrize(
        "versions", [[1, 2], [2], 2, ["1", "2"], ["2"], "2", [1, "2"]]
    )
    def test_vault_kv_delete_versions(self, kvv2, versions):
        """
        Ensure that VaultKV.delete with versions works for KV v2.
        """
        if isinstance(versions, list):
            expected = [int(x) for x in versions]
        else:
            expected = [int(versions)]
        kvv2.delete(self.path, versions=versions)
        kvv2.client.request.assert_called_once_with(
            "POST", self.paths["delete_versions"], payload={"versions": expected}
        )

    @pytest.mark.parametrize(
        "versions", [[1, 2], [2], 2, ["1", "2"], ["2"], "2", [1, "2"]]
    )
    def test_vault_kv_destroy(self, kvv2, versions):
        """
        Ensure that VaultKV.destroy works for KV v2.
        """
        if isinstance(versions, list):
            expected = [int(x) for x in versions]
        else:
            expected = [int(versions)]
        kvv2.destroy(self.path, versions)
        kvv2.client.post.assert_called_once_with(
            self.paths["destroy"], payload={"versions": expected}
        )

    def test_vault_kv_nuke(self, kvv2):
        """
        Ensure that VaultKV.nuke works for KV v2.
        """
        kvv2.nuke(self.path)
        kvv2.client.delete.assert_called_once_with(self.paths["metadata"])

    def test_vault_kv_list(self, kvv2):
        """
        Ensure that VaultKV.list works for KV v2 and only returns keys.
        """
        res = kvv2.list(self.path)
        kvv2.client.list.assert_called_once_with(self.paths["metadata"])
        assert res == ["foo"]


############################################
# LeaseStore tests
############################################


class TestLeaseStore:
    @pytest.fixture(autouse=True, params=[0])
    def time_stopped(self, request):
        with patch(
            "salt.utils.vault.time.time", autospec=True, return_value=request.param
        ):
            yield

    @pytest.fixture
    def lease(self):
        return {
            "id": "database/creds/testrole/abcd",
            "lease_id": "database/creds/testrole/abcd",
            "renewable": True,
            "duration": 1337,
            "creation_time": 0,
            "expire_time": 1337,
            "data": {
                "username": "test",
                "password": "test",
            },
        }

    @pytest.fixture
    def lease_renewed_response(self):
        return {
            "lease_id": "database/creds/testrole/abcd",
            "renewable": True,
            "lease_duration": 2000,
        }

    @pytest.fixture
    def lease_renewed_extended_response(self):
        return {
            "lease_id": "database/creds/testrole/abcd",
            "renewable": True,
            "lease_duration": 3000,
        }

    @pytest.fixture
    def store(self):
        client = Mock(spec=vault.AuthenticatedVaultClient)
        cache = Mock(spec=vault.VaultLeaseCache)
        cache.exists.return_value = False
        cache.get.return_value = None
        return vault.LeaseStore(client, cache)

    @pytest.fixture
    def store_valid(self, store, lease, lease_renewed_response):
        store.cache.exists.return_value = True
        store.cache.get.return_value = vault.VaultLease(**lease)
        store.client.post.return_value = lease_renewed_response
        return store

    def test_get_uncached_or_invalid(self, store):
        """
        Ensure uncached or invalid leases are reported as None.
        """
        ret = store.get("test")
        assert ret is None
        store.client.post.assert_not_called()
        store.cache.flush.assert_not_called()
        store.cache.store.assert_not_called()

    def test_get_cached_valid(self, store_valid, lease):
        """
        Ensure valid leases are returned without extra behavior.
        """
        ret = store_valid.get("test")
        assert ret == lease
        store_valid.client.post.assert_not_called()
        store_valid.cache.flush.assert_not_called()
        store_valid.cache.store.assert_not_called()

    @pytest.mark.parametrize(
        "valid_for", [2000, pytest.param(2002, id="2002_renewal_leeway")]
    )
    def test_get_valid_renew_default_period(self, store_valid, lease, valid_for):
        """
        Ensure renewals are attempted by default, cache is updated accordingly
        and validity checks after renewal allow for a little leeway to account
        for latency.
        """
        ret = store_valid.get("test", valid_for=valid_for)
        lease["duration"] = lease["expire_time"] = 2000
        assert ret == lease
        store_valid.client.post.assert_called_once_with(
            "sys/leases/renew", payload={"lease_id": lease["id"]}
        )
        store_valid.cache.flush.assert_not_called()
        store_valid.cache.store.assert_called_once_with("test", ret)

    def test_get_valid_renew_increment(self, store_valid, lease):
        """
        Ensure renew_increment is honored when renewing.
        """
        ret = store_valid.get("test", valid_for=1400, renew_increment=2000)
        lease["duration"] = lease["expire_time"] = 2000
        assert ret == lease
        store_valid.client.post.assert_called_once_with(
            "sys/leases/renew", payload={"lease_id": lease["id"], "increment": 2000}
        )
        store_valid.cache.flush.assert_not_called()
        store_valid.cache.store.assert_called_once_with("test", ret)

    def test_get_valid_renew_increment_insufficient(self, store_valid, lease):
        """
        Ensure that when renewal_increment is set, valid_for is respected and that
        a second renewal using valid_for as increment is not attempted when the
        Vault server does not allow renewals for at least valid_for.
        """
        ret = store_valid.get("test", valid_for=2100, renew_increment=3000)
        assert ret is None
        store_valid.client.post.assert_called_once_with(
            "sys/leases/renew", payload={"lease_id": lease["id"], "increment": 3000}
        )
        store_valid.cache.flush.assert_called_once_with("test")
        store_valid.cache.store.assert_not_called()

    @pytest.mark.parametrize(
        "valid_for", [3000, pytest.param(3002, id="3002_renewal_leeway")]
    )
    def test_get_valid_renew_valid_for(
        self,
        store_valid,
        lease,
        valid_for,
        lease_renewed_response,
        lease_renewed_extended_response,
    ):
        """
        Ensure that, if renew_increment was not set and the default period
        does not yield valid_for, a second renewal is attempted by valid_for.
        There should be some leeway by default to account for latency.
        """
        store_valid.client.post.side_effect = (
            lease_renewed_response,
            lease_renewed_extended_response,
        )
        ret = store_valid.get("test", valid_for=valid_for)
        lease["duration"] = lease["expire_time"] = 3000
        assert ret == lease
        store_valid.client.post.assert_has_calls(
            (
                call("sys/leases/renew", payload={"lease_id": lease["id"]}),
                call(
                    "sys/leases/renew",
                    payload={"lease_id": lease["id"], "increment": valid_for},
                ),
            )
        )
        store_valid.cache.flush.assert_not_called()
        store_valid.cache.store.assert_called_once_with("test", ret)

    def test_get_valid_not_renew(self, store_valid):
        """
        Currently valid leases should not be returned if they undercut
        valid_for and cache should be flushed by default.
        """
        ret = store_valid.get("test", valid_for=2000, renew=False)
        assert ret is None
        store_valid.cache.flush.assert_called_once_with("test")
        store_valid.client.post.assert_not_called()
        store_valid.cache.store.assert_not_called()

    def test_get_valid_not_flush(self, store_valid):
        """
        Currently valid leases should not be returned if they undercut
        valid_for and cache should not be flushed if requested so.
        """
        ret = store_valid.get("test", valid_for=2000, flush=False, renew=False)
        assert ret is None
        store_valid.cache.flush.assert_not_called()
        store_valid.client.post.assert_not_called()
        store_valid.cache.store.assert_not_called()


############################################
# Miscellaneous tests
############################################


@pytest.mark.parametrize(
    "opts_runtype,expected",
    [
        ("master", vault.SALT_RUNTYPE_MASTER),
        ("master_peer_run", vault.SALT_RUNTYPE_MASTER_PEER_RUN),
        ("master_impersonating", vault.SALT_RUNTYPE_MASTER_IMPERSONATING),
        ("minion_local_1", vault.SALT_RUNTYPE_MINION_LOCAL),
        ("minion_local_2", vault.SALT_RUNTYPE_MINION_LOCAL),
        ("minion_local_3", vault.SALT_RUNTYPE_MINION_LOCAL),
        ("minion_remote", vault.SALT_RUNTYPE_MINION_REMOTE),
    ],
    indirect=["opts_runtype"],
)
def test_get_salt_run_type(opts_runtype, expected):
    """
    Ensure run types are detected as expected
    """
    assert vault._get_salt_run_type(opts_runtype) == expected


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
        vault.parse_config(config)


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
    ret = vault.parse_config(
        {"server": {"verify": "default"}}, validate=False, opts=opts
    )
    assert ret["server"]["verify"] == testval


@pytest.mark.parametrize(
    "secret,config,expected",
    [
        ("token", None, r"auth/token/create(/[^/]+)?"),
        ("secret_id", None, r"auth/[^/]+/role/[^/]+/secret\-id"),
        ("role_id", None, r"auth/[^/]+/role/[^/]+/role\-id"),
        (
            "secret_id",
            {"auth": {"approle_mount": "test_mount", "approle_name": "test_minion"}},
            r"auth/test_mount/role/test_minion/secret\-id",
        ),
        (
            "role_id",
            {"auth": {"approle_mount": "test_mount", "approle_name": "test_minion"}},
            r"auth/test_mount/role/test_minion/role\-id",
        ),
        (
            "secret_id",
            {"auth": {"approle_mount": "te$t-mount", "approle_name": "te$t-minion"}},
            r"auth/te\$t\-mount/role/te\$t\-minion/secret\-id",
        ),
        (
            "role_id",
            {"auth": {"approle_mount": "te$t-mount", "approle_name": "te$t-minion"}},
            r"auth/te\$t\-mount/role/te\$t\-minion/role\-id",
        ),
    ],
)
def test_get_expected_creation_path(secret, config, expected):
    """
    Ensure expected creation paths are resolved as expected
    """
    assert vault._get_expected_creation_path(secret, config) == expected


def test_get_expected_creation_path_fails_for_unknown_type():
    """
    Ensure unknown source types result in an exception
    """
    with pytest.raises(vault.VaultInvocationError):
        vault._get_expected_creation_path("nonexistent")


@pytest.mark.parametrize(
    "pattern,expected",
    [
        ("no-tokens-to-replace", ["no-tokens-to-replace"]),
        ("single-dict:{minion}", ["single-dict:{minion}"]),
        ("single-list:{grains[roles]}", ["single-list:web", "single-list:database"]),
        (
            "multiple-lists:{grains[roles]}+{grains[aux]}",
            [
                "multiple-lists:web+foo",
                "multiple-lists:web+bar",
                "multiple-lists:database+foo",
                "multiple-lists:database+bar",
            ],
        ),
        (
            "single-list-with-dicts:{grains[id]}+{grains[roles]}+{grains[id]}",
            [
                "single-list-with-dicts:{grains[id]}+web+{grains[id]}",
                "single-list-with-dicts:{grains[id]}+database+{grains[id]}",
            ],
        ),
        (
            "deeply-nested-list:{grains[deep][foo][bar][baz]}",
            [
                "deeply-nested-list:hello",
                "deeply-nested-list:world",
            ],
        ),
    ],
)
def test_expand_pattern_lists(pattern, expected):
    """
    Ensure expand_pattern_lists works as intended:
    - Expand list-valued patterns
    - Do not change non-list-valued tokens
    """
    pattern_vars = {
        "id": "test-minion",
        "roles": ["web", "database"],
        "aux": ["foo", "bar"],
        "deep": {"foo": {"bar": {"baz": ["hello", "world"]}}},
    }

    mappings = {"minion": "test-minion", "grains": pattern_vars}
    output = vault.expand_pattern_lists(pattern, **mappings)
    assert output == expected


@pytest.mark.parametrize(
    "inpt,expected",
    [
        (60.0, 60.0),
        (60, 60.0),
        ("60", 60.0),
        ("60s", 60.0),
        ("2m", 120.0),
        ("1h", 3600.0),
        ("1d", 86400.0),
        ("1.5s", 1.5),
        ("1.5m", 90.0),
        ("1.5h", 5400.0),
        ("7.5d", 648000.0),
    ],
)
def test_timestring_map(inpt, expected):
    assert vault.timestring_map(inpt) == expected


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
    parsed = vault.parse_config(config)
    assert rec(parsed, new) == oldval
