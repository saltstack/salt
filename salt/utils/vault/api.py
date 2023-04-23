import salt.utils.json
import salt.utils.vault.leases as vleases
from salt.utils.vault.exceptions import VaultInvocationError, VaultNotFoundError


class AppRoleApi:
    def __init__(self, client):
        self.client = client

    def list_approles(self, mount="approle"):
        endpoint = f"auth/{mount}/role"
        return self.client.list(endpoint)["data"]["keys"]

    def read_approle(self, name, mount="approle"):
        endpoint = f"auth/{mount}/role/{name}"
        return self.client.get(endpoint)["data"]

    def write_approle(
        self,
        name,
        bind_secret_id=None,
        secret_id_bound_cidrs=None,
        secret_id_num_uses=None,
        secret_id_ttl=None,
        local_secret_ids=None,
        token_ttl=None,
        token_max_ttl=None,
        token_policies=None,
        policies=None,
        token_bound_cidrs=None,
        token_explicit_max_ttl=None,
        token_no_default_policy=None,
        token_num_uses=None,
        token_period=None,
        token_type=None,
        mount="approle",
    ):
        endpoint = f"auth/{mount}/role/{name}"
        payload = self._filter_none(
            {
                "bind_secret_id": bind_secret_id,
                "secret_id_bound_cidrs": secret_id_bound_cidrs,
                "secret_id_num_uses": secret_id_num_uses,
                "secret_id_ttl": secret_id_ttl,
                "local_secret_ids": local_secret_ids,
                "token_ttl": token_ttl,
                "token_max_ttl": token_max_ttl,
                "token_policies": token_policies,
                "policies": policies,
                "token_bound_cidrs": token_bound_cidrs,
                "token_explicit_max_ttl": token_explicit_max_ttl,
                "token_no_default_policy": token_no_default_policy,
                "token_num_uses": token_num_uses,
                "token_period": token_period,
                "token_type": token_type,
            }
        )
        return self.client.post(endpoint, payload=payload)

    def delete_approle(self, name, mount="approle"):
        endpoint = f"auth/{mount}/role/{name}"
        return self.client.delete(endpoint)

    def read_role_id(self, name, wrap=False, mount="approle"):
        endpoint = f"auth/{mount}/role/{name}/role-id"
        role_id = self.client.get(endpoint, wrap=wrap)
        if wrap:
            return role_id
        return role_id["data"]["role_id"]

    def generate_secret_id(
        self,
        name,
        metadata=None,
        cidr_list=None,
        token_bound_cidrs=None,
        num_uses=None,
        ttl=None,
        wrap=False,
        mount="approle",
        meta_info=False,
    ):
        endpoint = f"auth/{mount}/role/{name}/secret-id"
        if metadata is not None:
            metadata = salt.utils.json.dumps(metadata)
        payload = self._filter_none(
            {
                "metadata": metadata,
                "cidr_list": cidr_list,
                "token_bound_cidrs": token_bound_cidrs,
                "num_uses": num_uses,
                "ttl": ttl,
            }
        )
        response = self.client.post(endpoint, payload=payload, wrap=wrap)
        if wrap:
            secret_id = response
        else:
            secret_id = vleases.VaultSecretId(**response["data"])
        if not meta_info:
            return secret_id
        # Sadly, secret_id_num_uses is not part of the information returned
        meta_info = self.client.post(
            endpoint + "-accessor/lookup",
            payload={"secret_id_accessor": secret_id.accessor},
        )["data"]
        return secret_id, meta_info

    def read_secret_id(self, name, secret_id=None, accessor=None, mount="approle"):
        if not secret_id and not accessor:
            raise VaultInvocationError(
                "Need either secret_id or accessor to read secret ID."
            )
        if secret_id:
            endpoint = f"auth/{mount}/role/{name}/secret-id/lookup"
            payload = {"secret_id": str(secret_id)}
        else:
            endpoint = f"auth/{mount}/role/{name}/secret-id-accessor/lookup"
            payload = {"secret_id_accessor": accessor}
        return self.client.post(endpoint, payload=payload)["data"]

    def destroy_secret_id(self, name, secret_id=None, accessor=None, mount="approle"):
        if not secret_id and not accessor:
            raise VaultInvocationError(
                "Need either secret_id or accessor to destroy secret ID."
            )
        if secret_id:
            endpoint = f"auth/{mount}/role/{name}/secret-id/destroy"
            payload = {"secret_id": str(secret_id)}
        else:
            endpoint = f"auth/{mount}/role/{name}/secret-id-accessor/destroy"
            payload = {"secret_id_accessor": accessor}
        return self.client.post(endpoint, payload=payload)

    def _filter_none(self, data):
        return {k: v for k, v in data.items() if v is not None}


class IdentityApi:
    def __init__(self, client):
        self.client = client

    def list_entities(self):
        endpoint = "identity/entity/name"
        return self.client.list(endpoint)["data"]["keys"]

    def read_entity(self, name):
        endpoint = f"identity/entity/name/{name}"
        return self.client.get(endpoint)["data"]

    def read_entity_by_alias(self, alias, mount):
        endpoint = "identity/lookup/entity"
        payload = {
            "alias_name": alias,
            "alias_mount_accessor": self._lookup_mount_accessor(mount),
        }
        entity = self.client.post(endpoint, payload=payload)
        if isinstance(entity, dict):
            return entity["data"]
        raise VaultNotFoundError()

    def write_entity(self, name, metadata=None):
        endpoint = f"identity/entity/name/{name}"
        payload = {
            "metadata": metadata,
        }
        return self.client.post(endpoint, payload=payload)

    def delete_entity(self, name):
        endpoint = f"identity/entity/name/{name}"
        return self.client.delete(endpoint)

    def write_entity_alias(self, name, alias_name, mount, custom_metadata=None):
        entity = self.read_entity(name)
        mount_accessor = self._lookup_mount_accessor(mount)
        payload = {
            "canonical_id": entity["id"],
            "mount_accessor": mount_accessor,
            "name": alias_name,
        }
        if custom_metadata is not None:
            payload["custom_metadata"] = custom_metadata

        for alias in entity["aliases"]:
            # Ensure an existing alias is updated
            if alias["mount_accessor"] == mount_accessor:
                payload["id"] = alias["id"]
                break
        return self.client.post("identity/entity-alias", payload=payload)

    def _lookup_mount_accessor(self, mount):
        endpoint = f"sys/auth/{mount}"
        return self.client.get(endpoint)["data"]["accessor"]
