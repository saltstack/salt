"""
Runner functions supporting the Vault modules. Configuration instructions are
documented in the :ref:`execution module docs <vault-setup>`.

:maintainer:    SaltStack
:maturity:      new
:platform:      all
"""

import base64
import copy
import logging
import os
from collections.abc import Mapping

import salt.cache
import salt.crypt
import salt.exceptions
import salt.pillar
import salt.utils.data
import salt.utils.vault as vault
import salt.utils.versions
from salt.defaults import NOT_SET
from salt.exceptions import SaltInvocationError, SaltRunnerError

log = logging.getLogger(__name__)


def generate_token(
    minion_id, signature, impersonated_by_master=False, ttl=None, uses=None
):
    """
    .. deprecated:: 3006

    Generate a Vault token for minion minion_id

    minion_id
        The id of the minion that requests a token

    signature
        Cryptographic signature which validates that the request is indeed sent
        by the minion (or the master, see impersonated_by_master).

    impersonated_by_master
        If the master needs to create a token on behalf of the minion, this is
        True. This happens when the master generates minion pillars.

    ttl
        Ticket time to live in seconds, 1m minutes, or 2h hrs

    uses
        Number of times a token can be used
    """
    log.debug(
        "Token generation request for %s (impersonated by master: %s)",
        minion_id,
        impersonated_by_master,
    )
    _validate_signature(minion_id, signature, impersonated_by_master)
    try:
        salt.utils.versions.warn_until(
            "Argon",
            "vault.generate_token endpoint is deprecated. Please update your minions.",
        )

        if _config("issue:type") != "token":
            log.warning(
                "Master is not configured to issue tokens. Since the minion uses "
                "this deprecated endpoint, issuing token anyways."
            )

        issue_params = {}
        if ttl is not None:
            issue_params["ttl"] = ttl
        if uses is not None:
            issue_params["uses"] = uses

        token = _generate_token(
            minion_id, issue_params=issue_params or None, wrap=False
        )
        ret = {
            "token": token["client_token"],
            "lease_duration": token["lease_duration"],
            "renewable": token["renewable"],
            "issued": token["creation_time"],
            "url": _config("server:url"),
            "verify": _config("server:verify"),
            "token_backend": _config("cache:backend"),
            "namespace": _config("server:namespace"),
        }
        if token["num_uses"] >= 0:
            ret["uses"] = token["num_uses"]

        return ret
    except Exception as err:  # pylint: disable=broad-except
        return {"error": "{}: {}".format(type(err).__name__, str(err))}


def generate_new_token(
    minion_id, signature, impersonated_by_master=False, issue_params=None
):
    """
    .. versionadded:: 3006

    Generate a Vault token for minion minion_id.

    minion_id
        The id of the minion that requests a token

    signature
        Cryptographic signature which validates that the request is indeed sent
        by the minion (or the master, see impersonated_by_master).

    impersonated_by_master
        If the master needs to create a token on behalf of the minion, this is
        True. This happens when the master generates minion pillars.

    issue_params
        Dictionary of parameters for the generated tokens.
        See master configuration vault:issue:token:params for possible values.
        Requires "allow_minion_override_params" master configuration setting to be effective.
    """
    log.debug(
        f"Token generation request for {minion_id} (impersonated by master: {impersonated_by_master})",
    )
    _validate_signature(minion_id, signature, impersonated_by_master)
    try:
        if _config("issue:type") != "token":
            raise SaltInvocationError("Master does not issue tokens.")

        ret = {
            "server": _config("server"),
            "auth": {},
        }

        wrap = _config("issue:wrap")
        token = _generate_token(minion_id, issue_params=issue_params, wrap=wrap)

        if wrap:
            ret.update(token)
        else:
            ret["auth"] = token

        return ret
    except Exception as err:  # pylint: disable=broad-except
        return {"error": "{}: {}".format(type(err).__name__, str(err))}


def _generate_token(minion_id, issue_params, wrap):
    endpoint = "auth/token/create"
    if _config("issue:token:role_name") is not None:
        endpoint += "/" + _config("issue:token:role_name")

    payload = _parse_issue_params(issue_params, issue_type="token")
    payload["policies"] = _get_policies_cached(
        minion_id,
        refresh_pillar=_config("policies:refresh_pillar"),
        expire=_config("policies:cache_time"),
    )

    if not payload["policies"]:
        raise SaltRunnerError("No policies matched minion.")

    payload["meta"] = _get_metadata(minion_id, _config("metadata:token"))
    client = _get_master_client()
    log.trace("Sending token creation request to Vault.")
    res = client.post(endpoint, payload=payload, wrap=wrap)

    if wrap:
        return res.serialize_for_minion()
    token = vault.VaultToken(**res["auth"])
    return token.serialize_for_minion()


def get_config(minion_id, signature, impersonated_by_master=False, issue_params=None):
    """
    .. versionadded:: 3006

    Return Vault configuration for minion <minion_id>.

    minion_id
        The id of the minion that requests the configuration.

    signature
        Cryptographic signature which validates that the request is indeed sent
        by the minion (or the master, see impersonated_by_master).

    impersonated_by_master
        If the master needs to contact the Vault server on behalf of the minion, this is
        True. This happens when the master generates minion pillars.

    issue_params
        Parameters for credential issuance. Needs allow_minion_override_params in master
        config set in order to apply.
    """
    log.debug(
        f"Config request for {minion_id} (impersonated by master: {impersonated_by_master})",
    )
    _validate_signature(minion_id, signature, impersonated_by_master)
    try:
        minion_config = {
            "auth": {
                "method": _config("issue:type"),
            },
            "cache": _config("cache"),
            "server": _config("server"),
            "wrap_info_nested": [],
        }
        wrap = _config("issue:wrap")

        if _config("issue:type") == "token":
            minion_config["auth"]["token"] = _generate_token(
                minion_id,
                issue_params=issue_params,
                wrap=wrap,
            )
            if wrap:
                minion_config["wrap_info_nested"].append("auth:token")
        if _config("issue:type") == "approle":
            minion_config["auth"]["approle_mount"] = _config("issue:approle:mount")
            minion_config["auth"]["approle_name"] = minion_id
            minion_config["auth"]["secret_id"] = _config(
                "issue:approle:params:bind_secret_id"
            )
            minion_config["auth"]["role_id"] = _get_role_id(
                minion_id, issue_params=issue_params, wrap=wrap
            )
            if wrap:
                minion_config["wrap_info_nested"].append("auth:role_id")

        return minion_config
    except Exception as err:  # pylint: disable=broad-except
        return {"error": "{}: {}".format(type(err).__name__, str(err))}


def get_role_id(minion_id, signature, impersonated_by_master=False, issue_params=None):
    """
    .. versionadded:: 3006

    Return the Vault role-id for minion <minion_id>. Requires the master to be configured
    to generate AppRoles for minions (configuration: ``vault:issue:type``).

    minion_id
        The id of the minion that requests a token

    signature
        Cryptographic signature which validates that the request is indeed sent
        by the minion (or the master, see impersonated_by_master).

    impersonated_by_master
        If the master needs to create a token on behalf of the minion, this is
        True. This happens when the master generates minion pillars.

    issue_params
        Dictionary of configuration values for the generated AppRole.
        See master configuration vault:issue:approle:params for possible values.
        Requires "allow_minion_override_params" master configuration setting to be effective.
    """
    log.debug(
        f"role-id request for {minion_id} (impersonated by master: {impersonated_by_master})",
    )
    _validate_signature(minion_id, signature, impersonated_by_master)

    try:
        if _config("issue:type") != "approle":
            raise SaltInvocationError("Master does not issue AppRoles.")

        ret = {
            "server": _config("server"),
            "data": {},
        }

        wrap = _config("issue:wrap")
        role_id = _get_role_id(minion_id, issue_params=issue_params, wrap=wrap)
        if wrap:
            ret.update(role_id)
        else:
            ret["data"]["role_id"] = role_id
        return ret
    except Exception as err:  # pylint: disable=broad-except
        return {"error": "{}: {}".format(type(err).__name__, str(err))}


def _get_role_id(minion_id, issue_params, wrap):
    approle = _lookup_approle_cached(minion_id)
    issue_params_parsed = _parse_issue_params(issue_params)
    if approle is False or not _approle_params_match(approle, issue_params_parsed):
        # This means the role has to be created/updated first
        # create/update AppRole with role name <minion_id>
        # token_policies are set on the AppRole
        log.debug(f"Managing AppRole for {minion_id}.")
        _manage_approle(minion_id, issue_params)

    role_id = _lookup_role_id(minion_id, wrap=wrap)
    if role_id is False:
        raise SaltRunnerError(f"Failed to create AppRole for minion {minion_id}.")

    if approle is False:
        # This means the AppRole has just been created
        # create/update entity with name salt_minion_<minion_id>
        # metadata is set on the entity (to allow policy path templating)
        _manage_entity(minion_id)
        # ensure the new AppRole is mapped to the entity
        _manage_entity_alias(minion_id)

    if wrap:
        return role_id.serialize_for_minion()

    return role_id


def _approle_params_match(current, issue_params):
    req = _parse_issue_params(issue_params)
    for var in [
        "bind_secret_id",
        "secret_id_num_uses",
        "secret_id_ttl",
        "token_explicit_max_ttl",
        "token_num_uses",
    ]:
        if req.get(var) is not None and current.get(var) != req.get(var):
            return False
    return True


def generate_secret_id(
    minion_id, signature, impersonated_by_master=False, issue_params=None
):
    """
    .. versionadded:: 3006

    Generate a Vault secret-id for minion <minion_id>. Requires the master to be configured
    to generate AppRoles for minions (configuration: ``vault:issue:type``).

    minion_id
        The id of the minion that requests a token

    signature
        Cryptographic signature which validates that the request is indeed sent
        by the minion (or the master, see impersonated_by_master).

    impersonated_by_master
        If the master needs to create a token on behalf of the minion, this is
        True. This happens when the master generates minion pillars.

    issue_params
        Dictionary of configuration values for the generated AppRole.
        See master configuration vault:issue:approle:params for possible values.
        Requires "allow_minion_override_params" master configuration setting to be effective.
    """
    log.debug(
        f"secret-id generation request for {minion_id} (impersonated by master: {impersonated_by_master})",
    )
    _validate_signature(minion_id, signature, impersonated_by_master)
    try:
        if _config("issue:type") != "approle":
            raise SaltInvocationError("Master does not issue AppRoles nor secret-ids.")

        approle_meta = _lookup_approle_cached(minion_id)
        if approle_meta is False:
            raise vault.VaultNotFoundError(f"No AppRole found for minion {minion_id}.")

        if not _approle_params_match(approle_meta, issue_params):
            _manage_approle(minion_id, issue_params)
            approle_meta = _lookup_approle_cached(minion_id, refresh=True)

        ret = {
            "server": _config("server"),
            "data": {},
        }

        wrap = _config("issue:wrap")
        secret_id = _get_secret_id(minion_id, wrap=wrap)

        if wrap:
            ret.update(secret_id)
        else:
            ret["data"] = secret_id.serialize_for_minion()

        ret["misc_data"] = {
            "secret_id_num_uses": approle_meta["secret_id_num_uses"],
        }
        return ret
    except vault.VaultNotFoundError as err:
        # when the role does not exist, make sure the minion requests
        # new configuration details to generate one
        return {
            "expire_cache": True,
            "error": "{}: {}".format(type(err).__name__, str(err)),
        }
    except Exception as err:  # pylint: disable=broad-except
        return {"error": "{}: {}".format(type(err).__name__, str(err))}


def unseal():
    """
    Unseal Vault server

    This function uses the 'keys' from the 'vault' configuration to unseal vault server

    vault:
      keys:
        - n63/TbrQuL3xaIW7ZZpuXj/tIfnK1/MbVxO4vT3wYD2A
        - S9OwCvMRhErEA4NVVELYBs6w/Me6+urgUr24xGK44Uy3
        - F1j4b7JKq850NS6Kboiy5laJ0xY8dWJvB3fcwA+SraYl
        - 1cYtvjKJNDVam9c7HNqJUfINk4PYyAXIpjkpN/sIuzPv
        - 3pPK5X6vGtwLhNOFv1U2elahECz3HpRUfNXJFYLw6lid

    .. note: This function will send unsealed keys until the api returns back
             that the vault has been unsealed

    CLI Examples:

    .. code-block:: bash

        salt-run vault.unseal
    """
    for key in __opts__["vault"]["keys"]:
        ret = vault.query(
            "POST", "sys/unseal", __opts__, __context__, payload={"key": key}
        )
        if ret["sealed"] is False:
            return True
    return False


def show_policies(minion_id, refresh_pillar=NOT_SET, expire=None):
    """
    Show the Vault policies that are applied to tokens for the given minion.

    minion_id
        The minion's id.

    refresh_pillar
        Whether to refresh the pillar data when rendering templated policies.
        None will only refresh when the cached data is unavailable, boolean values
        force one behavior always.
        Defaults to config value ``policies_refresh_pillar`` or None.

    expire
        Policy computation can be heavy in case pillar data is used in templated policies and
        it has not been cached. Therefore, a short-lived cache specifically for rendered policies
        is used. This specifies the expiration timeout in seconds.
        Defaults to config value ``policies_cache_time`` or 60.

    CLI Example:

    .. code-block:: bash

        salt-run vault.show_policies myminion
    """
    if refresh_pillar == NOT_SET:
        refresh_pillar = _config("policies:refresh_pillar")
    expire = expire if expire is not None else _config("policies:cache_time")
    return _get_policies_cached(minion_id, refresh_pillar=refresh_pillar, expire=expire)


def sync_approles(minions=None, up=False, down=False, issue_params=None):
    """
    Sync minion AppRole parameters with current settings, including associated
    token policies.

    .. note::
        Only updates existing AppRoles. They are issued during the first request
        for one by the minion.

    If no parameter is specified, will try to sync AppRoles for all known minions.

    CLI Example:

    .. code-block:: bash

        salt-run vault.sync_approles
        salt-run vault.sync_approles ecorp issue_params="{ttl: 0, num_uses: 1337}"

    minions
        (List of) ID(s) of the minion(s) to update the AppRole for.
        Defaults to None.

    up
        Find all minions that are up and update their AppRoles.
        Defaults to False.

    down
        Find all minions that are down and update their AppRoles.
        Defaults to False.

    issue_params
        Overrides for AppRole parameters. See ``issue:approle:params`` and
        ``issue:allow_minion_override_params`` (the latter for the description
        only since the runner works on the master-side).
    """
    if "approle" != _config("issue:type"):
        raise SaltRunnerError("Master does not issue AppRoles to minions.")
    if minions is not None:
        if not isinstance(minions, list):
            minions = [minions]
    elif up or down:
        minions = []
        if up:
            minions.extend(__salt__["manage.list_state"]())
        if down:
            minions.extend(__salt__["manage.list_not_state"]())
    else:
        minions = _list_all_known_minions()

    for minion in set(minions) & set(list_approles()):
        _manage_approle(minion, issue_params, params_from_master=True)
    return True


def list_approles():
    """
    List all AppRoles that have been created by the Salt master.
    They are named after the minions.

    CLI Example:

    .. code-block:: bash

        salt-run vault.list_approles
    """
    if "approle" != _config("issue:type"):
        raise SaltRunnerError("Master does not issue AppRoles to minions.")
    endpoint = "auth/{}/role".format(_config("issue:approle:mount"))
    client = _get_master_client()
    return client.list(endpoint)["data"]["keys"]


def sync_entities(minions=None, up=False, down=False):
    """
    Sync minion entities with current settings. Only updates entities for minions
    with existing AppRoles.

    .. note::
        This updates associated metadata only. Entities are created only
        when issuing AppRoles to minions (``issue:type`` == ``approle``).

    If no parameter is specified, will try to sync entities for all known minions.

    CLI Example:

    .. code-block:: bash

        salt-run vault.sync_entities

    minions
        (List of) ID(s) of the minion(s) to update the entity for.
        Defaults to None.

    up
        Find all minions that are up and update their associated entities.
        Defaults to False.

    down
        Find all minions that are down and update their associated entities.
        Defaults to False.
    """
    if "approle" != _config("issue:type"):
        raise SaltRunnerError(
            "Master is not configured to issue AppRoles to minions, which is a "
            "requirement to use managed entities with Salt."
        )
    if minions is not None:
        if not isinstance(minions, list):
            minions = [minions]
    elif up or down:
        minions = []
        if up:
            minions.extend(__salt__["manage.list_state"]())
        if down:
            minions.extend(__salt__["manage.list_not_state"]())
    else:
        minions = _list_all_known_minions()

    for minion in set(minions) & set(list_approles()):
        _manage_entity(minion)
        entity = _lookup_entity_by_alias(minion)
        if not entity or not entity["name"] == f"salt_minion_{minion}":
            log.info(
                f"Fixing association of minion AppRole to minion entity for {minion}."
            )
            _manage_entity_alias(minion)
    return True


def cleanup_auth():
    """
    Removes AppRoles and entities associated with unknown minion IDs.
    Can only clean up entities if the AppRole still exists.

    .. warning::
        Make absolutely sure that the configured minion approle issue mount is
        exclusively dedicated to the Salt master, otherwise you might lose data
        by using this function! (config: ``issue:approle:mount``)

        This detects unknown existing AppRoles by listing all roles on the
        configured minion approle mount and deducting known minions from the
        returned list.

    CLI Example:

    .. code-block:: bash

        salt-run vault.cleanup_auth
    """
    ret = {"approles": [], "entities": []}

    for minion in set(list_approles()) - set(_list_all_known_minions()):
        if _fetch_entity_by_name(minion):
            _delete_entity(minion)
            ret["entities"].append(minion)
        _delete_approle(minion)
        ret["approles"].append(minion)
    return {"deleted": ret}


def _config(key=None):
    ckey = "vault_master_config"
    if ckey not in __context__:
        __context__[ckey] = vault.parse_config(__opts__.get("vault", {}))

    if key is None:
        return __context__[ckey]
    val = salt.utils.data.traverse_dict(__context__[ckey], key, vault.VaultException)
    if val == vault.VaultException:
        raise vault.VaultException("Requested configuration value does not exist.")
    return val


def _list_all_known_minions():
    return os.listdir(__opts__["pki_dir"] + "/minions")


def _validate_signature(minion_id, signature, impersonated_by_master):
    """
    Validate that either minion with id minion_id, or the master, signed the
    request
    """
    pki_dir = __opts__["pki_dir"]
    if impersonated_by_master:
        public_key = f"{pki_dir}/master.pub"
    else:
        public_key = f"{pki_dir}/minions/{minion_id}"

    log.trace("Validating signature for %s", minion_id)
    signature = base64.b64decode(signature)
    if not salt.crypt.verify_signature(public_key, minion_id, signature):
        raise salt.exceptions.AuthenticationError(
            f"Could not validate token request from {minion_id}"
        )
    log.trace("Signature ok")


# **kwargs because salt.cache.Cache does not pop "expire" from kwargs
def _get_policies(
    minion_id, refresh_pillar=None, **kwargs
):  # pylint: disable=unused-argument
    """
    Get the policies that should be applied to a token for minion_id
    """
    grains, pillar = _get_minion_data(minion_id, refresh_pillar)
    mappings = {"minion": minion_id, "grains": grains, "pillar": pillar}

    policies = []
    for pattern in _config("policies:assign"):
        try:
            for expanded_pattern in vault.expand_pattern_lists(pattern, **mappings):
                policies.append(
                    expanded_pattern.format(**mappings).lower()  # Vault requirement
                )
        except KeyError:
            log.warning(
                "Could not resolve policy pattern %s for minion %s", pattern, minion_id
            )

    log.debug("%s policies: %s", minion_id, policies)
    return policies


def _get_policies_cached(minion_id, refresh_pillar=None, expire=60):
    # expiration of 0 disables cache
    if not expire:
        return _get_policies(minion_id, refresh_pillar=refresh_pillar)
    cbank = f"minions/{minion_id}/vault"
    ckey = "policies"
    cache = salt.cache.factory(__opts__)
    policies = cache.cache(
        cbank,
        ckey,
        _get_policies,
        expire=expire,
        minion_id=minion_id,
        refresh_pillar=refresh_pillar,
    )
    if not isinstance(policies, list):
        log.warning("Cached vault policies were not formed as a list. Refreshing.")
        cache.flush(cbank, ckey)
        policies = cache.cache(
            cbank,
            ckey,
            _get_policies,
            expire=expire,
            minion_id=minion_id,
            refresh_pillar=refresh_pillar,
        )
    return policies


def _get_minion_data(minion_id, refresh_pillar=None):
    _, grains, pillar = salt.utils.minions.get_minion_data(minion_id, __opts__)

    if grains is None:
        # In case no cached minion data is available, make sure the utils module
        # can distinguish a pillar refresh run impersonating a minion from running
        # on the master.
        grains = {"id": minion_id}
        # To properly refresh minion grains, something like this could be used:
        # __salt__["salt.execute"](minion_id, "saltutil.refresh_grains", refresh_pillar=False)
        # This is deliberately not done since grains should not be used to target
        # secrets anyways.

    # salt.utils.minions.get_minion_data only returns data from cache or None.
    # To make sure the correct policies are available, the pillar needs to be
    # refreshed. This can cause an infinite loop if the pillar data itself
    # depends on the vault execution module, which relies on this function.
    # By default, only refresh when necessary. Boolean values force one way.
    if refresh_pillar is True or (refresh_pillar is None and pillar is None):
        if __opts__.get("_vault_runner_is_compiling_pillar_templates"):
            raise SaltRunnerError(
                "Cyclic dependency detected while refreshing pillar for vault policy templating. "
                "This is caused by some pillar value relying on the vault execution module. "
                "Either remove the dependency from your pillar, disable refreshing pillar data "
                "for policy templating or do not use pillar values in policy templates."
            )
        local_opts = copy.deepcopy(__opts__)
        # Relying on opts for ext_pillars does not work properly (only the first one runs
        # correctly).
        extra_minion_data = {"_vault_runner_is_compiling_pillar_templates": True}
        local_opts.update(extra_minion_data)
        pillar = LazyPillar(
            local_opts, grains, minion_id, extra_minion_data=extra_minion_data
        )
    elif pillar is None:
        # Make sure pillar is a dict. Necessary because a check on LazyPillar would
        # refresh it unconditionally (even when no pillar values are used)
        pillar = {}

    return grains, pillar


def _get_metadata(minion_id, metadata_patterns, refresh_pillar=None):
    _, pillar = _get_minion_data(minion_id, refresh_pillar)
    mappings = {
        "minion": minion_id,
        "pillar": pillar,
        "jid": globals().get("__jid__", "<no jid set>"),
        "user": globals().get("__user__", "<no user set>"),
    }
    metadata = {}
    for key, pattern in metadata_patterns.items():
        metadata[key] = []
        try:
            for expanded_pattern in vault.expand_pattern_lists(pattern, **mappings):
                metadata[key].append(expanded_pattern.format(**mappings))
        except KeyError:
            log.warning(
                "Could not resolve metadata pattern %s for minion %s",
                pattern,
                minion_id,
            )

    log.debug(f"{minion_id} metadata: {metadata}")
    return {k: ",".join(v) for k, v in metadata.items()}


def _parse_issue_params(params, issue_type=None, params_from_master=False):
    if (
        not (_config("issue:allow_minion_override_params") and not params_from_master)
        or params is None
    ):
        params = {}

    no_override_params = [
        "bind_secret_id",
        "secret_id_bound_cidrs",
        "token_policies",
        "token_bound_cidrs",
    ]

    # issue_type is used to override the configured type for minions using the old endpoint
    # TODO: remove this once the endpoint has been removed
    issue_type = issue_type or _config("issue:type")
    if "token" == issue_type:
        valid_params = {
            "ttl": "explicit_max_ttl",
            "uses": "num_uses",
        }
    elif "approle" == issue_type:
        valid_params = {
            "bind_secret_id": "bind_secret_id",
            "secret_id_num_uses": "secret_id_num_uses",
            "secret_id_ttl": "secret_id_ttl",
            "ttl": "token_explicit_max_ttl",
            "uses": "token_num_uses",
        }
    else:
        raise SaltRunnerError(
            "Invalid configuration for minion Vault authentication issuance."
        )

    configured_params = _config(f"issue:{issue_type}:params")
    ret = {}

    for valid_param, vault_param in valid_params.items():
        if (
            valid_param in configured_params
            and configured_params[valid_param] is not None
        ):
            ret[vault_param] = configured_params[valid_param]
        if (
            valid_param in params
            and vault_param not in no_override_params
            and params[valid_param] is not None
        ):
            ret[vault_param] = params[valid_param]

    return ret


def _manage_approle(minion_id, issue_params, params_from_master=False):
    endpoint = "auth/{}/role/{}".format(_config("issue:approle:mount"), minion_id)
    payload = _parse_issue_params(issue_params, params_from_master=params_from_master)
    payload["token_policies"] = _get_policies_cached(minion_id, refresh_pillar=True)
    client = _get_master_client()
    log.debug(f"Creating/updating AppRole for minion {minion_id}.")
    return client.post(endpoint, payload=payload)


def _delete_approle(minion_id):
    endpoint = "auth/{}/role/{}".format(_config("issue:approle:mount"), minion_id)
    client = _get_master_client()
    log.debug(f"Deleting approle for minion {minion_id}.")
    return client.delete(endpoint)


def _lookup_approle(minion_id, **kwargs):  # pylint: disable=unused-argument
    endpoint = "auth/{}/role/{}".format(_config("issue:approle:mount"), minion_id)
    client = _get_master_client()
    try:
        return client.get(endpoint)["data"]
    except vault.VaultNotFoundError:
        return False


def _lookup_approle_cached(minion_id, expire=3600, refresh=False):
    # expiration of 0 disables cache
    if not expire:
        return _lookup_approle(minion_id)
    cbank = f"minions/{minion_id}/vault"
    ckey = "approle_meta"
    cache = salt.cache.factory(__opts__)
    if refresh:
        cache.flush(cbank, ckey)
    meta = cache.cache(
        cbank,
        ckey,
        _lookup_approle,
        expire=expire,
        minion_id=minion_id,
    )
    if not isinstance(meta, dict):
        log.warning(
            "Cached Vault AppRole meta information was not formed as a dictionary. Refreshing."
        )
        cache.flush(cbank, ckey)

        meta = cache.cache(
            cbank,
            ckey,
            _lookup_approle,
            expire=expire,
            minion_id=minion_id,
        )
    # falsey values are always refreshed by salt.cache.Cache
    return meta


def _lookup_role_id(minion_id, wrap):
    client = _get_master_client()
    endpoint = "auth/{}/role/{}/role-id".format(
        _config("issue:approle:mount"), minion_id
    )
    try:
        role_id = client.get(endpoint, wrap=wrap)
    except vault.VaultNotFoundError:
        return False
    if wrap:
        return role_id
    return role_id["data"]["role_id"]


def _get_secret_id(minion_id, wrap, meta_info=False):
    client = _get_master_client()
    endpoint = "auth/{}/role/{}/secret-id".format(
        _config("issue:approle:mount"), minion_id
    )
    response = client.post(endpoint, wrap=wrap)
    if wrap:
        # wrapped responses are always VaultWrappedResponse objects
        secret_id = response.serialize_for_minion()
        accessor = response.wrapped_accessor
    else:
        secret_id = vault.VaultAppRoleSecretId(**response["data"])
        accessor = response["data"]["secret_id_accessor"]
    if not meta_info:
        return secret_id
    # sadly, secret_id_num_uses is not part of the information returned
    meta_info = client.post(
        endpoint + "-accessor/lookup", payload={"secret_id_accessor": accessor}
    )["data"]

    return secret_id, meta_info


def _lookup_mount_accessor(mount):
    log.debug(f"Looking up mount accessor ID for mount {mount}.")
    endpoint = f"sys/auth/{mount}"
    client = _get_master_client()
    return client.get(endpoint)["accessor"]


def _lookup_entity_by_alias(minion_id):
    """
    This issues a lookup for the entity using the role-id and mount accessor,
    thus verifies that an entity and associated entity alias exists.
    """
    minion_mount_accessor = _lookup_mount_accessor(_config("issue:approle:mount"))
    role_id = _lookup_role_id(minion_id, wrap=False)
    client = _get_master_client()
    endpoint = "identity/lookup/entity"
    payload = {
        "alias_name": role_id,
        "alias_mount_accessor": minion_mount_accessor,
    }
    entity = client.post(endpoint, payload=payload)
    if isinstance(entity, dict):
        return entity["data"]
    return False


def _fetch_entity_by_name(minion_id):
    client = _get_master_client()
    endpoint = f"identity/entity/name/salt_minion_{minion_id}"
    try:
        return client.get(endpoint)["data"]
    except vault.VaultNotFoundError:
        return False


def _manage_entity(minion_id):
    endpoint = f"identity/entity/name/salt_minion_{minion_id}"
    payload = {
        "metadata": _get_metadata(minion_id, _config("metadata:entity"), True),
    }
    client = _get_master_client()
    client.post(endpoint, payload=payload)


def _delete_entity(minion_id):
    endpoint = f"identity/entity/name/salt_minion_{minion_id}"
    client = _get_master_client()
    client.delete(endpoint)


def _manage_entity_alias(minion_id):
    log.debug(f"Creating entity alias for minion {minion_id}.")
    minion_mount_accessor = _lookup_mount_accessor(_config("issue:approle:mount"))
    role_id = _lookup_role_id(minion_id, wrap=False)
    entity = _fetch_entity_by_name(minion_id)
    if not entity:
        raise SaltRunnerError(
            f"There is no entity to create an alias for for minion {minion_id}."
        )
    payload = {
        "canonical_id": entity["id"],
        "mount_accessor": minion_mount_accessor,
        "name": str(role_id),
    }
    for alias in entity["aliases"]:
        if alias["mount_accessor"] == minion_mount_accessor:
            payload["id"] = alias["id"]
    client = _get_master_client()
    client.post("identity/entity-alias", payload=payload)


def _get_master_client():
    # force_local is necessary when issuing credentials while impersonating
    # minions since the opts dict cannot be used to distinguish master from
    # minion in that case
    client = vault.get_authd_client(__opts__, __context__, force_local=True)
    return client


def _revoke_token(token=None, accessor=None):
    if not token and not accessor:
        raise SaltInvocationError("Need either token or accessor to revoke token.")
    endpoint = "auth/token/revoke"
    if token:
        payload = {"token": token}
    else:
        endpoint += "-accessor"
        payload = {"accessor": accessor}
    client = _get_master_client()
    return client.post(endpoint, payload=payload)


def _destroy_secret_id(minion_id, mount, secret_id=None, accessor=None):
    if not secret_id and not accessor:
        raise SaltInvocationError(
            "Need either secret_id or accessor to destroy secret-id."
        )
    if secret_id:
        endpoint = f"auth/{mount}/role/{minion_id}/secret-id/destroy"
        payload = {"secret_id": str(secret_id)}
    else:
        endpoint = f"auth/{mount}/role/{minion_id}/secret-id-accessor/destroy"
        payload = {"secret_id_accessor": accessor}
    client = _get_master_client()
    return client.post(endpoint, payload=payload)


class LazyPillar(Mapping):
    """
    Simulates a pillar dictionary. Only compiles the pillar
    once an item is requested.
    """

    def __init__(self, opts, grains, minion_id, extra_minion_data=None):
        self.opts = opts
        self.grains = grains
        self.minion_id = minion_id
        self.extra_minion_data = extra_minion_data or {}
        self._pillar = None

    def _load(self):
        log.info("Refreshing pillar for vault templating.")
        self._pillar = salt.pillar.get_pillar(
            self.opts,
            self.grains,
            self.minion_id,
            extra_minion_data=self.extra_minion_data,
        ).compile_pillar()

    def __getitem__(self, key):
        if self._pillar is None:
            self._load()
        return self._pillar[key]

    def __iter__(self):
        if self._pillar is None:
            self._load()
        yield from self._pillar

    def __len__(self):
        if self._pillar is None:
            self._load()
        return len(self._pillar)
