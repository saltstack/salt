import pytest

import salt.utils.vault as vaultutil
import salt.utils.vault.api as vapi
import salt.utils.vault.client as vclient
from tests.support.mock import Mock, patch


@pytest.fixture
def entity_lookup_response():
    return {
        "data": {
            "aliases": [],
            "creation_time": "2017-11-13T21:01:33.543497Z",
            "direct_group_ids": [],
            "group_ids": [],
            "id": "043fedec-967d-b2c9-d3af-0c467b04e1fd",
            "inherited_group_ids": [],
            "last_update_time": "2017-11-13T21:01:33.543497Z",
            "merged_entity_ids": None,
            "metadata": None,
            "name": "test-minion",
            "policies": None,
        }
    }


@pytest.fixture
def entity_fetch_response():
    return {
        "data": {
            "aliases": [],
            "creation_time": "2018-09-19T17:20:27.705389973Z",
            "direct_group_ids": [],
            "disabled": False,
            "group_ids": [],
            "id": "test-entity-id",
            "inherited_group_ids": [],
            "last_update_time": "2018-09-19T17:20:27.705389973Z",
            "merged_entity_ids": None,
            "metadata": {
                "minion-id": "test-minion",
            },
            "name": "salt_minion_test-minion",
            "policies": [
                "default",
                "saltstack/minions",
                "saltstack/minion/test-minion",
            ],
        }
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
def secret_id_lookup_accessor_response():
    return {
        "request_id": "28f2f9fb-26c0-6022-4970-baeb6366b085",
        "lease_id": "",
        "lease_duration": 0,
        "renewable": False,
        "data": {
            "cidr_list": [],
            "creation_time": "2022-09-09T15:11:28.358490481+00:00",
            "expiration_time": "2022-10-11T15:11:28.358490481+00:00",
            "last_updated_time": "2022-09-09T15:11:28.358490481+00:00",
            "metadata": {},
            "secret_id_accessor": "0380eb9f-3041-1c1c-234c-fde31a1a1fc1",
            "secret_id_num_uses": 1,
            "secret_id_ttl": 9999999999,
            "token_bound_cidrs": [],
        },
        "warnings": None,
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
def approle_meta(secret_id_serialized):
    return {
        "bind_secret_id": True,
        "local_secret_ids": False,
        "secret_id_bound_cidrs": [],
        "secret_id_num_uses": secret_id_serialized["secret_id_num_uses"],
        "secret_id_ttl": secret_id_serialized["secret_id_ttl"],
        "token_bound_cidrs": [],
        "token_explicit_max_ttl": 9999999999,
        "token_max_ttl": 0,
        "token_no_default_policy": False,
        "token_num_uses": 1,
        "token_period": 0,
        "token_policies": ["default"],
        "token_ttl": 0,
        "token_type": "default",
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
def lookup_mount_response():
    return {
        "request_id": "7a49be19-199b-ce19-c139-0c334bf07d72",
        "lease_id": "",
        "lease_duration": 0,
        "renewable": False,
        "data": {
            "accessor": "auth_approle_cafebabe",
            "config": {
                "allowed_response_headers": [""],
                "audit_non_hmac_request_keys": [""],
                "audit_non_hmac_response_keys": [""],
                "default_lease_ttl": 0,
                "force_no_cache": False,
                "max_lease_ttl": 0,
                "passthrough_request_headers": [""],
                "token_type": "default-service",
            },
            "deprecation_status": "supported",
            "description": "",
            "external_entropy_access": False,
            "local": False,
            "options": None,
            "plugin_version": "",
            "running_plugin_version": "v1.13.1+builtin.vault",
            "running_sha256": "",
            "seal_wrap": False,
            "type": "approle",
            "uuid": "testuuid",
        },
        "warnings": None,
    }


@pytest.fixture
def client():
    yield Mock(spec=vclient.AuthenticatedVaultClient)


@pytest.fixture
def approle_api(client):
    yield vapi.AppRoleApi(client)


@pytest.fixture
def identity_api(client):
    yield vapi.IdentityApi(client)


def test_list_approles(approle_api, client):
    """
    Ensure list_approles call the API as expected and returns only a list of names
    """
    client.list.return_value = {"data": {"keys": ["foo", "bar"]}}
    res = approle_api.list_approles(mount="salt-minions")
    assert res == ["foo", "bar"]
    client.list.assert_called_once_with("auth/salt-minions/role")


def test_destroy_secret_id_by_secret_id(approle_api, client):
    """
    Ensure destroy_secret_id calls the API as expected.
    """
    approle_api.destroy_secret_id(
        "test-minion", secret_id="test-secret-id", mount="salt-minions"
    )
    client.post.assert_called_once_with(
        "auth/salt-minions/role/test-minion/secret-id/destroy",
        payload={"secret_id": "test-secret-id"},
    )


def test_destroy_secret_id_by_accessor(approle_api, client):
    """
    Ensure destroy_secret_id calls the API as expected.
    """
    approle_api.destroy_secret_id(
        "test-minion", accessor="test-accessor", mount="salt-minions"
    )
    client.post.assert_called_once_with(
        "auth/salt-minions/role/test-minion/secret-id-accessor/destroy",
        payload={"secret_id_accessor": "test-accessor"},
    )


@pytest.mark.parametrize(
    "aliases",
    [
        [],
        [
            {"mount_accessor": "test-accessor", "id": "test-entity-alias-id"},
            {"mount_accessor": "other-accessor", "id": "other-entity-alias-id"},
        ],
    ],
)
def test_write_entity_alias(client, aliases, entity_fetch_response, identity_api):
    """
    Ensure write_entity_alias calls the API as expected.
    """
    metadata = {"foo": "bar"}
    payload = {
        "canonical_id": "test-entity-id",
        "mount_accessor": "test-accessor",
        "name": "test-role-id",
        "custom_metadata": metadata,
    }
    if aliases:
        entity_fetch_response["data"]["aliases"] = aliases
        if aliases[0]["mount_accessor"] == "test-accessor":
            payload["id"] = aliases[0]["id"]

    with patch(
        "salt.utils.vault.api.IdentityApi._lookup_mount_accessor",
        return_value="test-accessor",
    ), patch(
        "salt.utils.vault.api.IdentityApi.read_entity",
        return_value=entity_fetch_response["data"],
    ):
        identity_api.write_entity_alias(
            "salt_minion_test-minion",
            alias_name="test-role-id",
            mount="salt-minions",
            custom_metadata=metadata,
        )
        client.post.assert_called_with("identity/entity-alias", payload=payload)


def test_write_entity(client, identity_api):
    """
    Ensure write_entity calls the API as expected.
    """
    metadata = {"foo": "bar"}
    identity_api.write_entity("salt_minion_test-minion", metadata=metadata)
    payload = {"metadata": metadata}
    client.post.assert_called_with(
        "identity/entity/name/salt_minion_test-minion", payload=payload
    )


def test_read_entity_by_alias_failed(client, identity_api):
    """
    Ensure read_entity_by_alias raises VaultNotFoundError if the lookup fails.
    """
    with patch(
        "salt.utils.vault.api.IdentityApi._lookup_mount_accessor",
        return_value="test-accessor",
    ):
        client.post.return_value = []
        with pytest.raises(vapi.VaultNotFoundError):
            identity_api.read_entity_by_alias(
                alias="test-role-id", mount="salt-minions"
            )


def test_read_entity_by_alias(client, entity_lookup_response, identity_api):
    """
    Ensure read_entity_by_alias calls the API as expected.
    """
    with patch(
        "salt.utils.vault.api.IdentityApi._lookup_mount_accessor",
        return_value="test-accessor",
    ):
        client.post.return_value = entity_lookup_response
        res = identity_api.read_entity_by_alias(
            alias="test-role-id", mount="salt-minions"
        )
        assert res == entity_lookup_response["data"]
        payload = {
            "alias_name": "test-role-id",
            "alias_mount_accessor": "test-accessor",
        }
        client.post.assert_called_once_with("identity/lookup/entity", payload=payload)


def test_lookup_mount_accessor(client, identity_api, lookup_mount_response):
    """
    Ensure _lookup_mount_accessor calls the API as expected.
    """
    client.get.return_value = lookup_mount_response
    res = identity_api._lookup_mount_accessor("salt-minions")
    client.get.assert_called_once_with("sys/auth/salt-minions")
    assert res == "auth_approle_cafebabe"


@pytest.mark.parametrize("wrap", ["30s", False])
def test_generate_secret_id(
    client, wrapped_response, secret_id_response, wrap, approle_api
):
    """
    Ensure generate_secret_id calls the API as expected.
    """

    def res_or_wrap(*args, **kwargs):
        if kwargs.get("wrap"):
            return vaultutil.VaultWrappedResponse(**wrapped_response["wrap_info"])
        return secret_id_response

    client.post.side_effect = res_or_wrap
    metadata = {"foo": "bar"}
    res = approle_api.generate_secret_id(
        "test-minion", mount="salt-minions", metadata=metadata, wrap=wrap
    )
    if wrap:
        assert res == vaultutil.VaultWrappedResponse(**wrapped_response["wrap_info"])
    else:
        assert res == vaultutil.VaultSecretId(**secret_id_response["data"])
    client.post.assert_called_once_with(
        "auth/salt-minions/role/test-minion/secret-id",
        payload={"metadata": '{"foo": "bar"}'},
        wrap=wrap,
    )


@pytest.mark.parametrize("wrap", ["30s", False])
def test_read_role_id(client, wrapped_response, wrap, approle_api):
    """
    Ensure read_role_id calls the API as expected.
    """

    def res_or_wrap(*args, **kwargs):
        if kwargs.get("wrap"):
            return vaultutil.VaultWrappedResponse(**wrapped_response["wrap_info"])
        return {"data": {"role_id": "test-role-id"}}

    client.get.side_effect = res_or_wrap
    res = approle_api.read_role_id("test-minion", mount="salt-minions", wrap=wrap)
    if wrap:
        assert res == vaultutil.VaultWrappedResponse(**wrapped_response["wrap_info"])
    else:
        assert res == "test-role-id"
    client.get.assert_called_once_with(
        "auth/salt-minions/role/test-minion/role-id", wrap=wrap
    )


def test_read_approle(client, approle_api, approle_meta):
    """
    Ensure read_approle calls the API as expected.
    """
    client.get.return_value = {"data": approle_meta}
    res = approle_api.read_approle("test-minion", mount="salt-minions")
    assert res == approle_meta
    client.get.assert_called_once_with("auth/salt-minions/role/test-minion")


def test_write_approle(approle_api, client):
    """
    Ensure _manage_approle calls the API as expected.
    """
    policies = {"foo": "bar"}
    payload = {
        "token_explicit_max_ttl": 9999999999,
        "token_num_uses": 1,
        "token_policies": policies,
    }
    approle_api.write_approle("test-minion", mount="salt-minions", **payload)
    client.post.assert_called_once_with(
        "auth/salt-minions/role/test-minion", payload=payload
    )
