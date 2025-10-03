import pytest
import requests

import salt.modules.event
import salt.utils.vault as vault
import salt.utils.vault.auth as vauth
import salt.utils.vault.client as vclient
import salt.utils.vault.helpers as hlp
from tests.support.mock import MagicMock, Mock, patch


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


@pytest.fixture(params=[{}])
def server_config(request):
    conf = {
        "url": "http://127.0.0.1:8200",
        "namespace": None,
        "verify": None,
    }
    conf.update(request.param)
    return conf


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
            "clear_attempt_revocation": 60,
            "clear_on_unauthorized": True,
            "config": 3600,
            "expire_events": False,
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
            "clear_attempt_revocation": 60,
            "clear_on_unauthorized": True,
            "config": 3600,
            "expire_events": False,
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
def lease_response():
    return {
        "request_id": "0e8c388e-2cb6-bcb2-83b7-625127d568bb",
        "lease_id": "database/creds/testrole/abcd",
        "lease_duration": 1337,
        "renewable": True,
        "data": {
            "username": "test",
            "password": "test",
        },
    }


@pytest.fixture
def lease():
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
    req.side_effect = lambda method, url, **kwargs: (
        _mock_json_response(wrapped_role_id_lookup_response)
        if url.endswith("sys/wrapping/lookup")
        else _mock_json_response(role_id_response)
    )
    yield req


@pytest.fixture(params=["data"])
def unauthd_client_mock(server_config, request):
    client = Mock(spec=vclient.VaultClient)
    client.get_config.return_value = server_config
    client.unwrap.return_value = {request.param: {"bar": "baz"}}
    yield client


@pytest.fixture(params=[None, "valid_token"])
def client(server_config, request, session):
    if request.param is None:
        return vclient.VaultClient(**server_config, session=session)
    if request.param == "valid_token":
        token = request.getfixturevalue(request.param)
        auth = Mock(spec=vauth.VaultTokenAuth)
        auth.is_renewable.return_value = True
        auth.is_valid.return_value = True
        auth.get_token.return_value = token
        return vclient.AuthenticatedVaultClient(auth, **server_config, session=session)
    if request.param == "invalid_token":
        token = request.getfixturevalue(request.param)
        auth = Mock(spec=vauth.VaultTokenAuth)
        auth.is_renewable.return_value = True
        auth.is_valid.return_value = False
        auth.get_token.side_effect = vault.VaultAuthExpired
        return vclient.AuthenticatedVaultClient(auth, **server_config, session=session)


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
def cache_factory():
    with patch("salt.cache.factory", autospec=True) as factory:
        yield factory


@pytest.fixture
def events():
    return Mock(spec=salt.modules.event.send)


@pytest.fixture(
    params=["MASTER", "MASTER_IMPERSONATING", "MINION_LOCAL", "MINION_REMOTE"]
)
def salt_runtype(request):
    runtype = Mock(spec=hlp._get_salt_run_type)
    runtype.return_value = getattr(hlp, f"SALT_RUNTYPE_{request.param}")
    with patch("salt.utils.vault.helpers._get_salt_run_type", runtype):
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
    rtype = {
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
    }
    return rtype[request.param]
