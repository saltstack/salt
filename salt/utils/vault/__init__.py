"""
:maintainer:    SaltStack
:maturity:      new
:platform:      all

Utilities supporting modules for Hashicorp Vault. Configuration instructions are
documented in the :ref:`execution module docs <vault-setup>`.
"""

import logging

import requests

import salt.cache
import salt.crypt
import salt.exceptions
import salt.utils.data
import salt.utils.dictupdate
import salt.utils.json
import salt.utils.vault.helpers as hlp
import salt.utils.versions
from salt.utils.vault.auth import (
    InvalidVaultSecretId,
    InvalidVaultToken,
    LocalVaultSecretId,
    VaultAppRole,
)
from salt.utils.vault.exceptions import (
    VaultAuthExpired,
    VaultConfigExpired,
    VaultException,
    VaultInvocationError,
    VaultNotFoundError,
    VaultPermissionDeniedError,
    VaultPreconditionFailedError,
    VaultServerError,
    VaultUnavailableError,
    VaultUnsupportedOperationError,
    VaultUnwrapException,
)
from salt.utils.vault.factory import (
    clear_cache,
    get_authd_client,
    get_kv,
    get_lease_store,
    parse_config,
)
from salt.utils.vault.leases import (
    VaultLease,
    VaultSecretId,
    VaultToken,
    VaultWrappedResponse,
)

log = logging.getLogger(__name__)
logging.getLogger("requests").setLevel(logging.WARNING)


def query(
    method,
    endpoint,
    opts,
    context,
    payload=None,
    wrap=False,
    raise_error=True,
    is_unauthd=False,
    **kwargs,
):
    """
    Query the Vault API. Supplemental arguments to ``requests.request``
    can be passed as kwargs.

    method
        HTTP verb to use.

    endpoint
        API path to call (without leading ``/v1/``).

    opts
        Pass ``__opts__`` from the module.

    context
        Pass ``__context__`` from the module.

    payload
        Dictionary of payload values to send, if any.

    wrap
        Whether to request response wrapping. Should be a time string
        like ``30s`` or False (default).

    raise_error
        Whether to inspect the response code and raise exceptions.
        Defaults to True.

    is_unauthd
        Whether the queried endpoint is an unauthenticated one and hence
        does not deduct a token use. Only relevant for endpoints not found
        in ``sys``. Defaults to False.
    """
    client, config = get_authd_client(opts, context, get_config=True)
    try:
        return client.request(
            method,
            endpoint,
            payload=payload,
            wrap=wrap,
            raise_error=raise_error,
            is_unauthd=is_unauthd,
            **kwargs,
        )
    except VaultPermissionDeniedError:
        if not _check_clear(config, client):
            raise

    # in case policies have changed
    clear_cache(opts, context)
    client = get_authd_client(opts, context)
    return client.request(
        method,
        endpoint,
        payload=payload,
        wrap=wrap,
        raise_error=raise_error,
        is_unauthd=is_unauthd,
        **kwargs,
    )


def query_raw(
    method,
    endpoint,
    opts,
    context,
    payload=None,
    wrap=False,
    retry=True,
    is_unauthd=False,
    **kwargs,
):
    """
    Query the Vault API, returning the raw response object. Supplemental
    arguments to ``requests.request`` can be passed as kwargs.

    method
        HTTP verb to use.

    endpoint
        API path to call (without leading ``/v1/``).

    opts
        Pass ``__opts__`` from the module.

    context
        Pass ``__context__`` from the module.

    payload
        Dictionary of payload values to send, if any.

    retry
        Retry the query with cleared cache in case the permission
        was denied (to check for revoked cached credentials).
        Defaults to True.

    wrap
        Whether to request response wrapping. Should be a time string
        like ``30s`` or False (default).

    is_unauthd
        Whether the queried endpoint is an unauthenticated one and hence
        does not deduct a token use. Only relevant for endpoints not found
        in ``sys``. Defaults to False.
    """
    client, config = get_authd_client(opts, context, get_config=True)
    res = client.request_raw(
        method, endpoint, payload=payload, wrap=wrap, is_unauthd=is_unauthd, **kwargs
    )

    if not retry:
        return res

    if res.status_code == 403:
        if not _check_clear(config, client):
            return res

        # in case policies have changed
        clear_cache(opts, context)
        client = get_authd_client(opts, context)
        res = client.request_raw(
            method,
            endpoint,
            payload=payload,
            wrap=wrap,
            is_unauthd=is_unauthd,
            **kwargs,
        )
    return res


def is_v2(path, opts=None, context=None):
    """
    Determines if a given secret path is kv version 1 or 2.
    """
    if opts is None or context is None:
        opts = globals().get("__opts__", {}) if opts is None else opts
        context = globals().get("__context__", {}) if context is None else context
        salt.utils.versions.warn_until(
            3008,
            "The __utils__ loader functionality will be removed. This will "
            "cause context/opts dunders to be unavailable in utility modules. "
            "Please pass opts and context from importing Salt modules explicitly.",
        )
    kv = get_kv(opts, context)
    return kv.is_v2(path)


def read_kv(path, opts, context, include_metadata=False):
    """
    Read secret at <path>.
    """
    kv, config = get_kv(opts, context, get_config=True)
    try:
        return kv.read(path, include_metadata=include_metadata)
    except VaultPermissionDeniedError:
        if not _check_clear(config, kv.client):
            raise

    # in case policies have changed
    clear_cache(opts, context)
    kv = get_kv(opts, context)
    return kv.read(path, include_metadata=include_metadata)


def write_kv(path, data, opts, context):
    """
    Write secret <data> to <path>.
    """
    kv, config = get_kv(opts, context, get_config=True)
    try:
        return kv.write(path, data)
    except VaultPermissionDeniedError:
        if not _check_clear(config, kv.client):
            raise

    # in case policies have changed
    clear_cache(opts, context)
    kv = get_kv(opts, context)
    return kv.write(path, data)


def patch_kv(path, data, opts, context):
    """
    Patch secret <data> at <path>.
    """
    kv, config = get_kv(opts, context, get_config=True)
    try:
        return kv.patch(path, data)
    except VaultAuthExpired:
        # patching can consume several token uses when
        # 1) `patch` cap unvailable 2) KV v1 3) KV v2 w/ old Vault versions
        kv = get_kv(opts, context)
        return kv.patch(path, data)
    except VaultPermissionDeniedError:
        if not _check_clear(config, kv.client):
            raise

    # in case policies have changed
    clear_cache(opts, context)
    kv = get_kv(opts, context)
    return kv.patch(path, data)


def delete_kv(path, opts, context, versions=None):
    """
    Delete secret at <path>. For KV v2, versions can be specified,
    which will be soft-deleted.
    """
    kv, config = get_kv(opts, context, get_config=True)
    try:
        return kv.delete(path, versions=versions)
    except VaultPermissionDeniedError:
        if not _check_clear(config, kv.client):
            raise

    # in case policies have changed
    clear_cache(opts, context)
    kv = get_kv(opts, context)
    return kv.delete(path, versions=versions)


def destroy_kv(path, versions, opts, context):
    """
    Destroy secret <versions> at <path>. Requires KV v2.
    """
    kv, config = get_kv(opts, context, get_config=True)
    try:
        return kv.destroy(path, versions)
    except VaultPermissionDeniedError:
        if not _check_clear(config, kv.client):
            raise

    # in case policies have changed
    clear_cache(opts, context)
    kv = get_kv(opts, context)
    return kv.destroy(path, versions)


def list_kv(path, opts, context):
    """
    List secrets at <path>.
    """
    kv, config = get_kv(opts, context, get_config=True)
    try:
        return kv.list(path)
    except VaultPermissionDeniedError:
        if not _check_clear(config, kv.client):
            raise

    # in case policies have changed
    clear_cache(opts, context)
    kv = get_kv(opts, context)
    return kv.list(path)


def _check_clear(config, client):
    """
    Called when encountering a VaultPermissionDeniedError.
    Decides whether caches should be cleared to retry with
    possibly updated token policies.
    """
    if config["cache"]["clear_on_unauthorized"]:
        return True
    try:
        # verify the current token is still valid
        return not client.token_valid(remote=True)
    except VaultAuthExpired:
        return True


####################################################################################
# The following functions were available in previous versions and are deprecated
# TODO: remove deprecated functions after v3008 (Argon)
####################################################################################


def get_vault_connection():
    """
    Get the connection details for calling Vault, from local configuration if
    it exists, or from the master otherwise
    """
    salt.utils.versions.warn_until(
        3008,
        "salt.utils.vault.get_vault_connection is deprecated, "
        "please use salt.utils.vault.get_authd_client.",
    )

    opts = globals().get("__opts__", {})
    context = globals().get("__context__", {})

    try:
        vault = get_authd_client(opts, context)
    except salt.exceptions.InvalidConfigError as err:
        # This exception class was raised previously
        raise salt.exceptions.CommandExecutionError(err) from err

    token = vault.auth.get_token()
    server_config = vault.get_config()

    ret = {
        "url": server_config["url"],
        "namespace": server_config["namespace"],
        "token": str(token),
        "verify": server_config["verify"],
        "issued": token.creation_time,
    }

    if hlp._get_salt_run_type(opts) in [
        hlp.SALT_RUNTYPE_MASTER_IMPERSONATING,
        hlp.SALT_RUNTYPE_MASTER_PEER_RUN,
        hlp.SALT_RUNTYPE_MINION_REMOTE,
    ]:
        ret["lease_duration"] = token.explicit_max_ttl
        ret["uses"] = token.num_uses
    else:
        ret["ttl"] = token.explicit_max_ttl

    return ret


def del_cache():
    """
    Delete cache file
    """
    salt.utils.versions.warn_until(
        3008,
        "salt.utils.vault.del_cache is deprecated, please use salt.utils.vault.clear_cache.",
    )
    clear_cache(
        globals().get("__opts__", {}),
        globals().get("__context__", {}),
        connection=False,
    )


def write_cache(connection):  # pylint: disable=unused-argument
    """
    Write the vault token to cache
    """
    salt.utils.versions.warn_until(
        3008,
        "salt.utils.vault.write_cache is deprecated without replacement.",
    )
    # always return false since cache is managed internally
    return False


def get_cache():
    """
    Return connection information from vault cache file
    """
    salt.utils.versions.warn_until(
        3008,
        "salt.utils.vault.get_cache is deprecated, please use salt.utils.vault.get_authd_client.",
    )
    return get_vault_connection()


def make_request(
    method,
    resource,
    token=None,
    vault_url=None,
    namespace=None,
    get_token_url=False,
    retry=False,
    **args,
):
    """
    Make a request to Vault
    """
    salt.utils.versions.warn_until(
        3008,
        "salt.utils.vault.make_request is deprecated, please use "
        "salt.utils.vault.query or salt.utils.vault.query_raw."
        "To override token/url/namespace, please make use of the "
        "provided classes directly.",
    )

    def _get_client(token, vault_url, namespace, args):
        vault = get_authd_client(opts, context)
        if token is not None:
            vault.session = requests.Session()
            vault.auth.cache = None
            vault.auth.token = VaultToken(
                client_token=token, renewable=False, lease_duration=60, num_uses=1
            )
        if vault_url is not None:
            vault.session = requests.Session()
            vault.url = vault_url
        if namespace is not None:
            vault.namespace = namespace
        if "verify" in args:
            vault.verify = args.pop("verify")

        return vault

    opts = globals().get("__opts__", {})
    context = globals().get("__context__", {})
    endpoint = resource.lstrip("/").lstrip("v1/")
    payload = args.pop("json", None)

    if "data" in args:
        payload = salt.utils.json.loads(args.pop("data"))

    vault = _get_client(token, vault_url, namespace, args)
    res = vault.request_raw(method, endpoint, payload=payload, wrap=False, **args)
    if res.status_code == 403 and not retry:
        # retry was used to indicate to only try once more
        clear_cache(opts, context)
        vault = _get_client(token, vault_url, namespace, args)
        res = vault.request_raw(method, endpoint, payload=payload, wrap=False, **args)

    if get_token_url:
        return res, str(vault.auth.token), vault.get_config()["url"]
    return res
