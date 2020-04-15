# -*- coding: utf-8 -*-
"""
:maintainer:    SaltStack
:maturity:      new
:platform:      all

Runner functions supporting the Vault modules. Configuration instructions are
documented in the execution module docs.
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import base64
import json
import logging
import string

import requests

# Import Salt libs
import salt.crypt
import salt.exceptions

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def generate_token(minion_id, signature, impersonated_by_master=False):
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
    """
    log.debug(
        "Token generation request for %s (impersonated by master: %s)",
        minion_id,
        impersonated_by_master,
    )
    _validate_signature(minion_id, signature, impersonated_by_master)

    try:
        config = __opts__["vault"]
        verify = config.get("verify", None)

        if config["auth"]["method"] == "approle":
            if _selftoken_expired():
                log.debug("Vault token expired. Recreating one")
                # Requesting a short ttl token
                url = "{0}/v1/auth/approle/login".format(config["url"])

                payload = {"role_id": config["auth"]["role_id"]}
                if "secret_id" in config["auth"]:
                    payload["secret_id"] = config["auth"]["secret_id"]
                response = requests.post(url, json=payload, verify=verify)
                if response.status_code != 200:
                    return {"error": response.reason}
                config["auth"]["token"] = response.json()["auth"]["client_token"]

        url = _get_token_create_url(config)
        headers = {"X-Vault-Token": config["auth"]["token"]}
        audit_data = {
            "saltstack-jid": globals().get("__jid__", "<no jid set>"),
            "saltstack-minion": minion_id,
            "saltstack-user": globals().get("__user__", "<no user set>"),
        }
        payload = {
            "policies": _get_policies(minion_id, config),
            "num_uses": 1,
            "meta": audit_data,
        }

        if payload["policies"] == []:
            return {"error": "No policies matched minion"}

        log.trace("Sending token creation request to Vault")
        response = requests.post(url, headers=headers, json=payload, verify=verify)

        if response.status_code != 200:
            return {"error": response.reason}

        auth_data = response.json()["auth"]
        return {
            "token": auth_data["client_token"],
            "url": config["url"],
            "verify": verify,
        }
    except Exception as e:  # pylint: disable=broad-except
        return {"error": six.text_type(e)}


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


def show_policies(minion_id):
    """
    Show the Vault policies that are applied to tokens for the given minion

    minion_id
        The minions id

    CLI Example:

    .. code-block:: bash

        salt-run vault.show_policies myminion
    """
    config = __opts__["vault"]
    return _get_policies(minion_id, config)


def _validate_signature(minion_id, signature, impersonated_by_master):
    """
    Validate that either minion with id minion_id, or the master, signed the
    request
    """
    pki_dir = __opts__["pki_dir"]
    if impersonated_by_master:
        public_key = "{0}/master.pub".format(pki_dir)
    else:
        public_key = "{0}/minions/{1}".format(pki_dir, minion_id)

    log.trace("Validating signature for %s", minion_id)
    signature = base64.b64decode(signature)
    if not salt.crypt.verify_signature(public_key, minion_id, signature):
        raise salt.exceptions.AuthenticationError(
            "Could not validate token request from {0}".format(minion_id)
        )
    log.trace("Signature ok")


def _get_policies(minion_id, config):
    """
    Get the policies that should be applied to a token for minion_id
    """
    _, grains, _ = salt.utils.minions.get_minion_data(minion_id, __opts__)
    policy_patterns = config.get(
        "policies", ["saltstack/minion/{minion}", "saltstack/minions"]
    )
    mappings = {"minion": minion_id, "grains": grains or {}}

    policies = []
    for pattern in policy_patterns:
        try:
            for expanded_pattern in _expand_pattern_lists(pattern, **mappings):
                policies.append(
                    expanded_pattern.format(**mappings).lower()  # Vault requirement
                )
        except KeyError:
            log.warning("Could not resolve policy pattern %s", pattern)

    log.debug("%s policies: %s", minion_id, policies)
    return policies


def _expand_pattern_lists(pattern, **mappings):
    """
    Expands the pattern for any list-valued mappings, such that for any list of
    length N in the mappings present in the pattern, N copies of the pattern are
    returned, each with an element of the list substituted.

    pattern:
        A pattern to expand, for example ``by-role/{grains[roles]}``

    mappings:
        A dictionary of variables that can be expanded into the pattern.

    Example: Given the pattern `` by-role/{grains[roles]}`` and the below grains

    .. code-block:: yaml

        grains:
            roles:
                - web
                - database

    This function will expand into two patterns,
    ``[by-role/web, by-role/database]``.

    Note that this method does not expand any non-list patterns.
    """
    expanded_patterns = []
    f = string.Formatter()
    """
    This function uses a string.Formatter to get all the formatting tokens from
    the pattern, then recursively replaces tokens whose expanded value is a
    list. For a list with N items, it will create N new pattern strings and
    then continue with the next token. In practice this is expected to not be
    very expensive, since patterns will typically involve a handful of lists at
    most.
    """  # pylint: disable=W0105
    for (_, field_name, _, _) in f.parse(pattern):
        if field_name is None:
            continue
        (value, _) = f.get_field(field_name, None, mappings)
        if isinstance(value, list):
            token = "{{{0}}}".format(field_name)
            expanded = [pattern.replace(token, six.text_type(elem)) for elem in value]
            for expanded_item in expanded:
                result = _expand_pattern_lists(expanded_item, **mappings)
                expanded_patterns += result
            return expanded_patterns
    return [pattern]


def _selftoken_expired():
    """
    Validate the current token exists and is still valid
    """
    try:
        verify = __opts__["vault"].get("verify", None)
        url = "{0}/v1/auth/token/lookup-self".format(__opts__["vault"]["url"])
        if "token" not in __opts__["vault"]["auth"]:
            return True
        headers = {"X-Vault-Token": __opts__["vault"]["auth"]["token"]}
        response = requests.get(url, headers=headers, verify=verify)
        if response.status_code != 200:
            return True
        return False
    except Exception as e:  # pylint: disable=broad-except
        raise salt.exceptions.CommandExecutionError(
            "Error while looking up self token : {0}".format(six.text_type(e))
        )


def _get_token_create_url(config):
    """
    Create Vault url for token creation
    """
    role_name = config.get("role_name", None)
    auth_path = "/v1/auth/token/create"
    base_url = config["url"]
    return "/".join(x.strip("/") for x in (base_url, auth_path, role_name) if x)
