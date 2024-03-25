"""
Runner functions supporting the Vault modules. Configuration instructions are
documented in the execution module docs.

:maintainer:    SaltStack
:maturity:      new
:platform:      all
"""

import base64
import copy
import json
import logging
import time
from collections.abc import Mapping

import requests

import salt.cache
import salt.crypt
import salt.exceptions
import salt.pillar
from salt.defaults import NOT_SET
from salt.exceptions import SaltRunnerError

log = logging.getLogger(__name__)


def generate_token(
    minion_id, signature, impersonated_by_master=False, ttl=None, uses=None
):
    """
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
        config = __opts__.get("vault", {})
        verify = config.get("verify", None)
        # Vault Enterprise requires a namespace
        namespace = config.get("namespace")
        # Allow disabling of minion provided values via the master
        allow_minion_override = config["auth"].get("allow_minion_override", False)
        # This preserves the previous behavior of default TTL and 1 use
        if not allow_minion_override or uses is None:
            uses = config["auth"].get("uses", 1)
        if not allow_minion_override or ttl is None:
            ttl = config["auth"].get("ttl", None)
        storage_type = config["auth"].get("token_backend", "session")
        policies_refresh_pillar = config.get("policies_refresh_pillar", None)
        policies_cache_time = config.get("policies_cache_time", 60)

        if config["auth"]["method"] == "approle":
            if _selftoken_expired():
                log.debug("Vault token expired. Recreating one")
                # Requesting a short ttl token
                url = "{}/v1/auth/approle/login".format(config["url"])
                payload = {"role_id": config["auth"]["role_id"]}
                if "secret_id" in config["auth"]:
                    payload["secret_id"] = config["auth"]["secret_id"]
                # Vault Enterprise call requires headers
                headers = None
                if namespace is not None:
                    headers = {"X-Vault-Namespace": namespace}
                response = requests.post(
                    url, headers=headers, json=payload, verify=verify, timeout=120
                )
                if response.status_code != 200:
                    return {"error": response.reason}
                config["auth"]["token"] = response.json()["auth"]["client_token"]

        url = _get_token_create_url(config)
        headers = {"X-Vault-Token": config["auth"]["token"]}
        if namespace is not None:
            headers["X-Vault-Namespace"] = namespace
        audit_data = {
            "saltstack-jid": globals().get("__jid__", "<no jid set>"),
            "saltstack-minion": minion_id,
            "saltstack-user": globals().get("__user__", "<no user set>"),
        }
        payload = {
            "policies": _get_policies_cached(
                minion_id,
                config,
                refresh_pillar=policies_refresh_pillar,
                expire=policies_cache_time,
            ),
            "num_uses": uses,
            "meta": audit_data,
        }

        if ttl is not None:
            payload["explicit_max_ttl"] = str(ttl)

        if payload["policies"] == []:
            return {"error": "No policies matched minion"}

        log.trace("Sending token creation request to Vault")
        response = requests.post(
            url, headers=headers, json=payload, verify=verify, timeout=120
        )

        if response.status_code != 200:
            return {"error": response.reason}

        auth_data = response.json()["auth"]
        ret = {
            "token": auth_data["client_token"],
            "lease_duration": auth_data["lease_duration"],
            "renewable": auth_data["renewable"],
            "issued": int(round(time.time())),
            "url": config["url"],
            "verify": verify,
            "token_backend": storage_type,
            "namespace": namespace,
        }
        if uses >= 0:
            ret["uses"] = uses

        return ret
    except Exception as e:  # pylint: disable=broad-except
        return {"error": str(e)}


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
        ret = __utils__["vault.make_request"](
            "PUT", "v1/sys/unseal", data=json.dumps({"key": key})
        ).json()
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
    config = __opts__.get("vault", {})
    if refresh_pillar == NOT_SET:
        refresh_pillar = config.get("policies_refresh_pillar")
    expire = expire if expire is not None else config.get("policies_cache_time", 60)
    return _get_policies_cached(
        minion_id, config, refresh_pillar=refresh_pillar, expire=expire
    )


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
    minion_id, config, refresh_pillar=None, **kwargs
):  # pylint: disable=unused-argument
    """
    Get the policies that should be applied to a token for minion_id
    """
    grains, pillar = _get_minion_data(minion_id, refresh_pillar)
    policy_patterns = config.get(
        "policies", ["saltstack/minion/{minion}", "saltstack/minions"]
    )
    mappings = {"minion": minion_id, "grains": grains, "pillar": pillar}

    policies = []
    for pattern in policy_patterns:
        try:
            for expanded_pattern in __utils__["vault.expand_pattern_lists"](
                pattern, **mappings
            ):
                policies.append(
                    expanded_pattern.format(**mappings).lower()  # Vault requirement
                )
        except KeyError:
            log.warning(
                "Could not resolve policy pattern %s for minion %s", pattern, minion_id
            )

    log.debug("%s policies: %s", minion_id, policies)
    return policies


def _get_policies_cached(minion_id, config, refresh_pillar=None, expire=60):
    # expiration of 0 disables cache
    if not expire:
        return _get_policies(minion_id, config, refresh_pillar=refresh_pillar)
    cbank = f"minions/{minion_id}/vault"
    ckey = "policies"
    cache = salt.cache.factory(__opts__)
    policies = cache.cache(
        cbank,
        ckey,
        _get_policies,
        expire=expire,
        minion_id=minion_id,
        config=config,
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
            config=config,
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


def _selftoken_expired():
    """
    Validate the current token exists and is still valid
    """
    try:
        verify = __opts__["vault"].get("verify", None)
        # Vault Enterprise requires a namespace
        namespace = __opts__["vault"].get("namespace")
        url = "{}/v1/auth/token/lookup-self".format(__opts__["vault"]["url"])
        if "token" not in __opts__["vault"]["auth"]:
            return True
        headers = {"X-Vault-Token": __opts__["vault"]["auth"]["token"]}
        # Add Vault namespace to headers if Vault Enterprise enabled
        if namespace is not None:
            headers["X-Vault-Namespace"] = namespace
        response = requests.get(url, headers=headers, verify=verify, timeout=120)
        if response.status_code != 200:
            return True
        return False
    except Exception as e:  # pylint: disable=broad-except
        raise salt.exceptions.CommandExecutionError(
            f"Error while looking up self token : {str(e)}"
        )


def _get_token_create_url(config):
    """
    Create Vault url for token creation
    """
    role_name = config.get("role_name", None)
    auth_path = "/v1/auth/token/create"
    base_url = config["url"]
    return "/".join(x.strip("/") for x in (base_url, auth_path, role_name) if x)


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
