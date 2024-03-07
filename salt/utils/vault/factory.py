import base64
import copy
import logging

from requests.exceptions import ConnectionError

import salt.cache
import salt.crypt
import salt.exceptions
import salt.modules.publish
import salt.modules.saltutil
import salt.utils.context
import salt.utils.data
import salt.utils.dictupdate
import salt.utils.json
import salt.utils.vault.api as vapi
import salt.utils.vault.auth as vauth
import salt.utils.vault.cache as vcache
import salt.utils.vault.client as vclient
import salt.utils.vault.helpers as hlp
import salt.utils.vault.kv as vkv
import salt.utils.vault.leases as vleases
import salt.utils.versions
from salt.defaults import NOT_SET
from salt.utils.vault.exceptions import (
    VaultAuthExpired,
    VaultConfigExpired,
    VaultException,
    VaultPermissionDeniedError,
    VaultUnwrapException,
)

log = logging.getLogger(__name__)
logging.getLogger("requests").setLevel(logging.WARNING)


TOKEN_CKEY = "__token"
CLIENT_CKEY = "_vault_authd_client"


def get_authd_client(opts, context, force_local=False, get_config=False):
    """
    Returns an AuthenticatedVaultClient that is valid for at least one query.
    """

    def try_build():
        client = config = None
        retry = False
        try:
            client, config = _build_authd_client(opts, context, force_local=force_local)
        except (VaultConfigExpired, VaultPermissionDeniedError, ConnectionError):
            clear_cache(opts, context, connection=True, force_local=force_local)
            retry = True
        except VaultUnwrapException as err:
            # ensure to notify about potential intrusion attempt
            _get_event(opts)(tag="vault/security/unwrapping/error", data=err.event_data)
            raise
        return client, config, retry

    cbank = vcache._get_cache_bank(opts, force_local=force_local)
    retry = False
    client = config = None

    # First, check if an already initialized instance is available
    # and still valid
    if cbank in context and CLIENT_CKEY in context[cbank]:
        log.debug("Fetching client instance and config from context")
        client, config = context[cbank][CLIENT_CKEY]
        if not client.token_valid(remote=False):
            log.debug("Cached client instance was invalid")
            client = config = None
            context[cbank].pop(CLIENT_CKEY)

    # Otherwise, try to build one from possibly cached data
    if client is None or config is None:
        try:
            client, config, retry = try_build()
        except VaultAuthExpired:
            clear_cache(opts, context, session=True, force_local=force_local)
            client, config, retry = try_build()

    # Check if the token needs to be and can be renewed.
    # Since this needs to check the possibly active session and does not care
    # about valid secret IDs etc, we need to inspect the actual token.
    if (
        not retry
        and config["auth"]["token_lifecycle"]["renew_increment"] is not False
        and client.auth.get_token().is_renewable()
        and not client.auth.get_token().is_valid(
            config["auth"]["token_lifecycle"]["minimum_ttl"]
        )
    ):
        log.debug("Renewing token")
        client.token_renew(
            increment=config["auth"]["token_lifecycle"]["renew_increment"]
        )

    # Check if the current token could not be renewed for a sufficient amount of time.
    if not retry and not client.token_valid(
        config["auth"]["token_lifecycle"]["minimum_ttl"] or 0, remote=False
    ):
        clear_cache(opts, context, session=True, force_local=force_local)
        client, config, retry = try_build()

    if retry:
        log.debug("Requesting new authentication credentials")
        try:
            client, config = _build_authd_client(opts, context, force_local=force_local)
        except VaultUnwrapException as err:
            _get_event(opts)(tag="vault/security/unwrapping/error", data=err.event_data)
            raise
        if not client.token_valid(
            config["auth"]["token_lifecycle"]["minimum_ttl"] or 0, remote=False
        ):
            if not config["auth"]["token_lifecycle"]["minimum_ttl"]:
                raise VaultException(
                    "Could not build valid client. This is most likely a bug."
                )
            log.warning(
                "Configuration error: auth:token_lifecycle:minimum_ttl cannot be "
                "honored because fresh tokens are issued with less ttl. Continuing anyways."
            )

    if cbank not in context:
        context[cbank] = {}
    context[cbank][CLIENT_CKEY] = (client, config)

    if get_config:
        return client, config
    return client


def clear_cache(
    opts, context, ckey=None, connection=True, session=False, force_local=False
):
    """
    Clears the Vault cache.
    Will ensure the current token and associated leases are revoked
    by default.

    It is organized in a hierarchy: ``/vault/connection/session/leases``.
    (*italics* mark data that is only cached when receiving configuration from a master)

    ``connection`` contains KV metadata (by default), *configuration* and *(AppRole) auth credentials*.
    ``session`` contains the currently active token.
    ``leases`` contains leases issued to the currently active token like database credentials.

    A master keeps a separate instance of the above per minion
    in ``minions/<minion_id>``.

    opts
        Pass ``__opts__``.

    context
        Pass ``__context__``.

    ckey
        Only clear this cache key instead of the whole cache bank.

    connection
        Only clear the cached data scoped to a connection. This includes
        configuration, auth credentials, the currently active auth token
        as well as leases and KV metadata (by default). Defaults to true.
        Set this to false to clear all Vault caches.

    session
        Only clear the cached data scoped to a session. This only includes
        leases and the currently active auth token, but not configuration
        or (AppRole) auth credentials. Defaults to false.
        Setting this to true will keep the connection cache, regardless
        of ``connection``.

    force_local
        Required on the master when the runner is issuing credentials during
        pillar compilation. Instructs the cache to use the ``/vault`` cache bank,
        regardless of determined run type. Defaults to false and should not
        be set by anything other than the runner.
    """
    cbank = vcache._get_cache_bank(
        opts, connection=connection, session=session, force_local=force_local
    )
    client, config = _build_revocation_client(opts, context, force_local=force_local)
    if (
        not ckey
        or (not (connection or session) and ckey == "connection")
        or (session and ckey == TOKEN_CKEY)
        or ((connection and not session) and ckey == "config")
    ):
        client, config = _build_revocation_client(
            opts, context, force_local=force_local
        )
        # config and client will both be None if the cached data is invalid
        if config:
            try:
                # Don't revoke the only token that is available to us
                if config["auth"]["method"] != "token" or not (
                    force_local
                    or hlp._get_salt_run_type(opts)
                    in (hlp.SALT_RUNTYPE_MASTER, hlp.SALT_RUNTYPE_MINION_LOCAL)
                ):
                    if config["cache"]["clear_attempt_revocation"]:
                        delta = config["cache"]["clear_attempt_revocation"]
                        if delta is True:
                            delta = 1
                        client.token_revoke(delta)
                    if (
                        config["cache"]["expire_events"]
                        and not force_local
                        and hlp._get_salt_run_type(opts)
                        not in [
                            hlp.SALT_RUNTYPE_MASTER_IMPERSONATING,
                            hlp.SALT_RUNTYPE_MASTER_PEER_RUN,
                        ]
                    ):
                        scope = cbank.split("/")[-1]
                        _get_event(opts)(  # pylint: disable=no-value-for-parameter
                            tag=f"vault/cache/{scope}/clear"
                        )
            except Exception as err:  # pylint: disable=broad-except
                log.error(
                    "Failed to revoke token or send event before clearing cache:\n%s: %s",
                    type(err).__name__,
                    err,
                )

    if cbank in context:
        if ckey is None:
            context.pop(cbank)
        else:
            context[cbank].pop(ckey, None)
            if connection and not session:
                # Ensure the active client gets recreated after altering the connection cache
                context[cbank].pop(CLIENT_CKEY, None)

    # also remove sub-banks from context to mimic cache behavior
    if ckey is None:
        for bank in list(context):
            if bank.startswith(cbank):
                context.pop(bank)
    cache = salt.cache.factory(opts)
    if cache.contains(cbank, ckey):
        return cache.flush(cbank, ckey)

    # In case the cache driver was overridden for the Vault integration
    local_opts = copy.copy(opts)
    opts["cache"] = "localfs"
    cache = salt.cache.factory(local_opts)
    return cache.flush(cbank, ckey)


def update_config(opts, context, keep_session=False):
    """
    Attempt to update the cached configuration without
    clearing the currently active Vault session.

    opts
        Pass __opts__.

    context
        Pass __context__.

    keep_session
        Only update configuration that can be updated without
        creating a new login session.
        If this is false, still tries to keep the active session,
        but might clear it if the server configuration has changed
        significantly.
        Defaults to False.
    """
    if hlp._get_salt_run_type(opts) in [
        hlp.SALT_RUNTYPE_MASTER,
        hlp.SALT_RUNTYPE_MINION_LOCAL,
    ]:
        # local configuration is not cached
        return True
    connection_cbank = vcache._get_cache_bank(opts)
    try:
        _get_connection_config(connection_cbank, opts, context, update=True)
        return True
    except VaultConfigExpired:
        pass
    if keep_session:
        return False
    clear_cache(opts, context, connection=True)
    get_authd_client(opts, context)
    return True


def _build_authd_client(opts, context, force_local=False):
    connection_cbank = vcache._get_cache_bank(opts, force_local=force_local)
    config, embedded_token, unauthd_client = _get_connection_config(
        connection_cbank, opts, context, force_local=force_local
    )
    # Tokens are cached in a distinct scope to enable cache per session
    session_cbank = vcache._get_cache_bank(opts, force_local=force_local, session=True)
    cache_ttl = (
        config["cache"]["secret"] if config["cache"]["secret"] != "ttl" else None
    )
    token_cache = vcache.VaultAuthCache(
        context,
        session_cbank,
        TOKEN_CKEY,
        vleases.VaultToken,
        cache_backend=vcache._get_cache_backend(config, opts),
        ttl=cache_ttl,
        flush_exception=VaultAuthExpired,
    )

    client = None

    if config["auth"]["method"] == "approle":
        secret_id = config["auth"]["secret_id"] or None
        cached_token = token_cache.get(10)
        secret_id_cache = None
        if secret_id:
            secret_id_cache = vcache.VaultAuthCache(
                context,
                connection_cbank,
                "secret_id",
                vleases.VaultSecretId,
                cache_backend=vcache._get_cache_backend(config, opts),
                ttl=cache_ttl,
            )
            secret_id = secret_id_cache.get()
            # Only fetch secret ID if there is no cached valid token
            if cached_token is None and secret_id is None:
                secret_id = _fetch_secret_id(
                    config,
                    opts,
                    secret_id_cache,
                    unauthd_client,
                    force_local=force_local,
                )
            if secret_id is None:
                # If the auth config is sourced locally, ensure the
                # SecretID is known regardless whether we have a valid token.
                # For remote sources, we would needlessly request one, so don't.
                if (
                    hlp._get_salt_run_type(opts)
                    in [hlp.SALT_RUNTYPE_MASTER, hlp.SALT_RUNTYPE_MINION_LOCAL]
                    or force_local
                ):
                    secret_id = _fetch_secret_id(
                        config,
                        opts,
                        secret_id_cache,
                        unauthd_client,
                        force_local=force_local,
                    )
                else:
                    secret_id = vauth.InvalidVaultSecretId()
        role_id = config["auth"]["role_id"]
        # this happens with wrapped response merging
        if isinstance(role_id, dict):
            role_id = role_id["role_id"]
        approle = vauth.VaultAppRole(role_id, secret_id)
        token_auth = vauth.VaultTokenAuth(cache=token_cache)
        auth = vauth.VaultAppRoleAuth(
            approle,
            unauthd_client,
            mount=config["auth"]["approle_mount"],
            cache=secret_id_cache,
            token_store=token_auth,
        )
        client = vclient.AuthenticatedVaultClient(
            auth, session=unauthd_client.session, **config["server"]
        )
    elif config["auth"]["method"] in ["token", "wrapped_token"]:
        token = _fetch_token(
            config,
            opts,
            token_cache,
            unauthd_client,
            force_local=force_local,
            embedded_token=embedded_token,
        )
        auth = vauth.VaultTokenAuth(token=token, cache=token_cache)
        client = vclient.AuthenticatedVaultClient(
            auth, session=unauthd_client.session, **config["server"]
        )

    if client is not None:
        return client, config
    raise salt.exceptions.SaltException("Connection configuration is invalid.")


def _build_revocation_client(opts, context, force_local=False):
    """
    Tries to build an AuthenticatedVaultClient solely from caches.
    This client is used to revoke all leases before forgetting about them.
    """
    connection_cbank = vcache._get_cache_bank(opts, force_local=force_local)
    # Disregard a possibly returned locally configured token since
    # it is cached with metadata if it has been used. Also, we do not want
    # to revoke statically configured tokens anyways.
    config, _, unauthd_client = _get_connection_config(
        connection_cbank, opts, context, force_local=force_local, pre_flush=True
    )
    if config is None:
        return None, None

    # Tokens are cached in a distinct scope to enable cache per session
    session_cbank = vcache._get_cache_bank(opts, force_local=force_local, session=True)
    token_cache = vcache.VaultAuthCache(
        context,
        session_cbank,
        TOKEN_CKEY,
        vleases.VaultToken,
        cache_backend=vcache._get_cache_backend(config, opts),
    )

    token = token_cache.get(flush=False)

    if token is None:
        return None, None
    auth = vauth.VaultTokenAuth(token=token, cache=token_cache)
    client = vclient.AuthenticatedVaultClient(auth, **config["server"])
    return client, config


def _get_connection_config(
    cbank, opts, context, force_local=False, pre_flush=False, update=False
):
    if (
        hlp._get_salt_run_type(opts)
        in [hlp.SALT_RUNTYPE_MASTER, hlp.SALT_RUNTYPE_MINION_LOCAL]
        or force_local
    ):
        # only cache config fetched from remote
        return _use_local_config(opts)

    if pre_flush and update:
        raise VaultException("`pre_flush` and `update` are mutually exclusive")

    log.debug("Using Vault server connection configuration from remote.")
    config_cache = vcache._get_config_cache(opts, context, cbank)
    if pre_flush:
        # ensure any cached data is tried when building a client for revocation
        config_cache.ttl = None
    # In case cached data is available, this takes care of bubbling up
    # an exception indicating all connection-scoped data should be flushed
    # if the config is outdated.
    config = config_cache.get()
    if config is not None and not update:
        log.debug("Using cached Vault server connection configuration.")
        return config, None, vclient.VaultClient(**config["server"])

    if pre_flush:
        # used when building a client that revokes leases before clearing cache
        return None, None, None

    log.debug("Using new Vault server connection configuration.")
    try:
        issue_params = parse_config(opts.get("vault", {}), validate=False)[
            "issue_params"
        ]
        new_config, unwrap_client = _query_master(
            "get_config",
            opts,
            issue_params=issue_params or None,
            config_only=update,
        )
    except VaultConfigExpired as err:
        # Make sure to still work with old peer_run configuration
        if "Peer runner return was empty" not in err.message or update:
            raise
        log.warning(
            "Got empty response to Vault config request. Falling back to vault.generate_token. "
            "Please update your master peer_run configuration."
        )
        new_config, unwrap_client = _query_master(
            "generate_token",
            opts,
            ttl=issue_params.get("explicit_max_ttl"),
            uses=issue_params.get("num_uses"),
            upgrade_request=True,
        )
    new_config = parse_config(new_config, opts=opts, require_token=not update)
    # do not couple token cache with configuration cache
    embedded_token = new_config["auth"].pop("token", None)
    new_config = {
        "auth": new_config["auth"],
        "cache": new_config["cache"],
        "server": new_config["server"],
    }
    if update and config:
        if new_config["server"] != config["server"]:
            raise VaultConfigExpired()
        if new_config["auth"]["method"] != config["auth"]["method"]:
            raise VaultConfigExpired()
        if new_config["auth"]["method"] == "approle" and (
            new_config["auth"]["role_id"] != config["auth"]["role_id"]
            or new_config["auth"]["secret_id"] is not config["auth"]["secret_id"]
        ):
            # enabling/disabling response wrapping will trigger this as well,
            # but that's fine
            raise VaultConfigExpired()
        if new_config["cache"]["backend"] != config["cache"]["backend"]:
            raise VaultConfigExpired()
        config_cache.flush(cbank=False)

    config_cache.store(new_config)
    return new_config, embedded_token, unwrap_client


def _use_local_config(opts):
    log.debug("Using Vault connection details from local config.")
    config = parse_config(opts.get("vault", {}))
    embedded_token = config["auth"].pop("token", None)
    return (
        {
            "auth": config["auth"],
            "cache": config["cache"],
            "server": config["server"],
        },
        embedded_token,
        vclient.VaultClient(**config["server"]),
    )


def _fetch_secret_id(config, opts, secret_id_cache, unwrap_client, force_local=False):
    def cache_or_fetch(config, opts, secret_id_cache, unwrap_client):
        secret_id = secret_id_cache.get()
        if secret_id is not None:
            return secret_id

        log.debug("Fetching new Vault AppRole secret ID.")
        secret_id, _ = _query_master(
            "generate_secret_id",
            opts,
            unwrap_client=unwrap_client,
            unwrap_expected_creation_path=vclient._get_expected_creation_path(
                "secret_id", config
            ),
            issue_params=parse_config(opts.get("vault", {}), validate=False)[
                "issue_params"
            ]
            or None,
        )
        secret_id = vleases.VaultSecretId(**secret_id["data"])
        # Do not cache single-use secret IDs
        if secret_id.num_uses != 1:
            secret_id_cache.store(secret_id)
        return secret_id

    if (
        hlp._get_salt_run_type(opts)
        in [hlp.SALT_RUNTYPE_MASTER, hlp.SALT_RUNTYPE_MINION_LOCAL]
        or force_local
    ):
        secret_id = config["auth"]["secret_id"]
        if isinstance(secret_id, dict):
            if secret_id.get("wrap_info"):
                secret_id = unwrap_client.unwrap(
                    secret_id["wrap_info"]["token"],
                    expected_creation_path=vclient._get_expected_creation_path(
                        "secret_id", config
                    ),
                )
                secret_id = secret_id["data"]
            return vauth.LocalVaultSecretId(**secret_id)
        if secret_id:
            # assume locally configured secret_ids do not expire
            return vauth.LocalVaultSecretId(
                secret_id=config["auth"]["secret_id"],
                secret_id_ttl=0,
                secret_id_num_uses=0,
            )
        # When secret_id is falsey, the approle does not require secret IDs,
        # hence a call to this function is superfluous
        raise salt.exceptions.SaltException("This code path should not be hit at all.")

    log.debug("Using secret_id issued by master.")
    return cache_or_fetch(config, opts, secret_id_cache, unwrap_client)


def _fetch_token(
    config, opts, token_cache, unwrap_client, force_local=False, embedded_token=None
):
    def cache_or_fetch(config, opts, token_cache, unwrap_client, embedded_token):
        token = token_cache.get(10)
        if token is not None:
            log.debug("Using cached token.")
            return token

        if isinstance(embedded_token, dict):
            token = vleases.VaultToken(**embedded_token)

        if not isinstance(token, vleases.VaultToken) or not token.is_valid(10):
            log.debug("Fetching new Vault token.")
            token, _ = _query_master(
                "generate_new_token",
                opts,
                unwrap_client=unwrap_client,
                unwrap_expected_creation_path=vclient._get_expected_creation_path(
                    "token", config
                ),
                issue_params=parse_config(opts.get("vault", {}), validate=False)[
                    "issue_params"
                ]
                or None,
            )
            token = vleases.VaultToken(**token["auth"])

        # do not cache single-use tokens
        if token.num_uses != 1:
            token_cache.store(token)
        return token

    if (
        hlp._get_salt_run_type(opts)
        in [hlp.SALT_RUNTYPE_MASTER, hlp.SALT_RUNTYPE_MINION_LOCAL]
        or force_local
    ):
        token = None
        if isinstance(embedded_token, dict):
            if embedded_token.get("wrap_info"):
                embedded_token = unwrap_client.unwrap(
                    embedded_token["wrap_info"]["token"],
                    expected_creation_path=vclient._get_expected_creation_path(
                        "token", config
                    ),
                )["auth"]
            token = vleases.VaultToken(**embedded_token)
        elif config["auth"]["method"] == "wrapped_token":
            embedded_token = unwrap_client.unwrap(
                embedded_token,
                expected_creation_path=vclient._get_expected_creation_path(
                    "token", config
                ),
            )["auth"]
            token = vleases.VaultToken(**embedded_token)
        elif embedded_token is not None:
            # if the embedded plain token info has been cached before, don't repeat
            # the query unnecessarily
            token = token_cache.get()
            if token is None or embedded_token != str(token):
                # lookup and verify raw token
                token_info = unwrap_client.token_lookup(embedded_token, raw=True)
                if token_info.status_code != 200:
                    raise VaultException(
                        "Configured token cannot be verified. It is most likely expired or invalid."
                    )
                token_meta = token_info.json()["data"]
                token = vleases.VaultToken(
                    lease_id=embedded_token,
                    lease_duration=token_meta["ttl"],
                    **token_meta,
                )
                token_cache.store(token)
        if token is not None:
            return token
        raise VaultException("Invalid configuration, missing token.")

    log.debug("Using token generated by master.")
    return cache_or_fetch(config, opts, token_cache, unwrap_client, embedded_token)


def _query_master(
    func,
    opts,
    unwrap_client=None,
    unwrap_expected_creation_path=None,
    **kwargs,
):
    def check_result(
        result,
        unwrap_client=None,
        unwrap_expected_creation_path=None,
    ):
        if not result:
            log.error(
                "Failed to get Vault connection from master! No result returned - "
                "does the peer runner publish configuration include `vault.%s`?",
                func,
            )
            # Expire configuration in case this is the result of an auth method change.
            raise VaultConfigExpired(
                f"Peer runner return was empty. Make sure {func} is listed in the master peer_run config."
            )
        if not isinstance(result, dict):
            log.error(
                "Failed to get Vault connection from master! Response is not a dict: %s",
                result,
            )
            raise salt.exceptions.CommandExecutionError(result)
        if "error" in result:
            log.error(
                "Failed to get Vault connection from master! An error was returned: %s",
                result["error"],
            )
            if result.get("expire_cache"):
                log.warning("Master returned error and requested cache expiration.")
                raise VaultConfigExpired()
            raise salt.exceptions.CommandExecutionError(result)

        config_expired = False
        expected_server = None

        if result.get("expire_cache", False):
            log.info("Master requested Vault config expiration.")
            config_expired = True

        if "server" in result:
            # Ensure locally overridden verify parameter does not
            # always invalidate cache.
            reported_server = parse_config(result["server"], validate=False, opts=opts)[
                "server"
            ]
            result.update({"server": reported_server})

        if unwrap_client is not None:
            expected_server = unwrap_client.get_config()

        if expected_server is not None and result.get("server") != expected_server:
            log.info(
                "Mismatch of cached and reported server data detected. Invalidating cache."
            )
            # make sure to fetch wrapped data anyways for security reasons
            config_expired = True
            unwrap_expected_creation_path = None
            unwrap_client = None

        # This is used to augment some vault responses with data fetched by the master
        # e.g. secret_id_num_uses
        misc_data = result.get("misc_data", {})

        if result.get("wrap_info") or result.get("wrap_info_nested"):
            if unwrap_client is None:
                unwrap_client = vclient.VaultClient(**result["server"])

            for key in [""] + result.get("wrap_info_nested", []):
                if key:
                    wrapped = salt.utils.data.traverse_dict(result, key)
                else:
                    wrapped = result
                if not wrapped or "wrap_info" not in wrapped:
                    continue
                wrapped_response = vleases.VaultWrappedResponse(**wrapped["wrap_info"])
                try:
                    unwrapped_response = unwrap_client.unwrap(
                        wrapped_response,
                        expected_creation_path=unwrap_expected_creation_path,
                    )
                except VaultUnwrapException as err:
                    err.event_data.update({"func": f"vault.{func}"})
                    raise
                if key:
                    salt.utils.dictupdate.set_dict_key_value(
                        result,
                        key,
                        unwrapped_response.get("auth")
                        or unwrapped_response.get("data"),
                    )
                else:
                    if unwrapped_response.get("auth"):
                        result.update({"auth": unwrapped_response["auth"]})
                    if unwrapped_response.get("data"):
                        result.update({"data": unwrapped_response["data"]})

        if config_expired:
            raise VaultConfigExpired()

        for key, val in misc_data.items():
            tgt = "data" if result.get("data") is not None else "auth"
            if (
                salt.utils.data.traverse_dict_and_list(result, f"{tgt}:{key}", NOT_SET)
                == NOT_SET
            ):
                salt.utils.dictupdate.set_dict_key_value(
                    result,
                    f"{tgt}:{key}",
                    val,
                )

        result.pop("wrap_info", None)
        result.pop("wrap_info_nested", None)
        result.pop("misc_data", None)
        return result, unwrap_client

    minion_id = opts["grains"]["id"]
    pki_dir = opts["pki_dir"]

    # When rendering pillars, the module executes on the master, but the token
    # should be issued for the minion, so that the correct policies are applied
    if opts.get("__role", "minion") == "minion":
        private_key = f"{pki_dir}/minion.pem"
        log.debug(
            "Running on minion, signing request `vault.%s` with key %s",
            func,
            private_key,
        )
        signature = base64.b64encode(salt.crypt.sign_message(private_key, minion_id))
        arg = [
            ("minion_id", minion_id),
            ("signature", signature),
            ("impersonated_by_master", False),
        ] + list(kwargs.items())
        with salt.utils.context.func_globals_inject(
            salt.modules.publish.runner, __opts__=opts
        ):
            result = salt.modules.publish.runner(
                f"vault.{func}", arg=[{"__kwarg__": True, k: v} for k, v in arg]
            )
    else:
        private_key = f"{pki_dir}/master.pem"
        log.debug(
            "Running on master, signing request `vault.%s` for %s with key %s",
            func,
            minion_id,
            private_key,
        )
        signature = base64.b64encode(salt.crypt.sign_message(private_key, minion_id))
        with salt.utils.context.func_globals_inject(
            salt.modules.saltutil.runner, __opts__=opts
        ):
            result = salt.modules.saltutil.runner(
                f"vault.{func}",
                minion_id=minion_id,
                signature=signature,
                impersonated_by_master=True,
                **kwargs,
            )
    return check_result(
        result,
        unwrap_client=unwrap_client,
        unwrap_expected_creation_path=unwrap_expected_creation_path,
    )


def _get_event(opts):
    event = salt.utils.event.get_event(
        opts.get("__role", "minion"), sock_dir=opts["sock_dir"], opts=opts, listen=False
    )

    if opts.get("__role", "minion") == "minion":
        return event.fire_master
    return event.fire_event


def get_kv(opts, context, get_config=False):
    """
    Return an instance of VaultKV, which can be used
    to interact with the ``kv`` backend.
    """
    client, config = get_authd_client(opts, context, get_config=True)
    ttl = None
    connection = True
    if config["cache"]["kv_metadata"] != "connection":
        ttl = config["cache"]["kv_metadata"]
        connection = False
    cbank = vcache._get_cache_bank(opts, connection=connection)
    ckey = "secret_path_metadata"
    metadata_cache = vcache.VaultCache(
        context,
        cbank,
        ckey,
        cache_backend=vcache._get_cache_backend(config, opts),
        ttl=ttl,
    )
    kv = vkv.VaultKV(client, metadata_cache)
    if get_config:
        return kv, config
    return kv


def get_lease_store(opts, context, get_config=False):
    """
    Return an instance of LeaseStore, which can be used
    to cache leases and handle operations like renewals and revocations.
    """
    client, config = get_authd_client(opts, context, get_config=True)
    session_cbank = vcache._get_cache_bank(opts, session=True)
    expire_events = None
    if config["cache"]["expire_events"]:
        expire_events = _get_event(opts)
    lease_cache = vcache.VaultLeaseCache(
        context,
        session_cbank + "/leases",
        cache_backend=vcache._get_cache_backend(config, opts),
        expire_events=expire_events,
    )
    store = vleases.LeaseStore(client, lease_cache, expire_events=expire_events)
    if get_config:
        return store, config
    return store


def get_approle_api(opts, context, force_local=False, get_config=False):
    """
    Return an instance of AppRoleApi containing an AuthenticatedVaultClient.
    """
    client, config = get_authd_client(
        opts, context, force_local=force_local, get_config=True
    )
    api = vapi.AppRoleApi(client)
    if get_config:
        return api, config
    return api


def get_identity_api(opts, context, force_local=False, get_config=False):
    """
    Return an instance of IdentityApi containing an AuthenticatedVaultClient.
    """
    client, config = get_authd_client(
        opts, context, force_local=force_local, get_config=True
    )
    api = vapi.IdentityApi(client)
    if get_config:
        return api, config
    return api


def parse_config(config, validate=True, opts=None, require_token=True):
    """
    Returns a vault configuration dictionary that has all
    keys with defaults. Checks if required data is available.
    """
    default_config = {
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
            "namespace": None,
            "verify": None,
        },
    }
    try:
        # Policy generation has params, the new config groups them together.
        if isinstance(config.get("policies", {}), list):
            config["policies"] = {"assign": config.pop("policies")}
        merged = salt.utils.dictupdate.merge(
            default_config,
            config,
            strategy="smart",
            merge_lists=False,
        )
        # ttl, uses were used as configuration for issuance and minion overrides as well
        # as token meta information. The new configuration splits those semantics.
        for old_token_conf, new_token_conf in [
            ("ttl", "explicit_max_ttl"),
            ("uses", "num_uses"),
        ]:
            if old_token_conf in merged["auth"]:
                merged["issue"]["token"]["params"][new_token_conf] = merged[
                    "issue_params"
                ][new_token_conf] = merged["auth"].pop(old_token_conf)
        # Those were found in the root namespace, but grouping them together
        # makes semantic and practical sense.
        for old_server_conf in ["namespace", "url", "verify"]:
            if old_server_conf in merged:
                merged["server"][old_server_conf] = merged.pop(old_server_conf)
        if "role_name" in merged:
            merged["issue"]["token"]["role_name"] = merged.pop("role_name")
        if "token_backend" in merged["auth"]:
            merged["cache"]["backend"] = merged["auth"].pop("token_backend")
        if "allow_minion_override" in merged["auth"]:
            merged["issue"]["allow_minion_override_params"] = merged["auth"].pop(
                "allow_minion_override"
            )
        if opts is not None and "vault" in opts:
            local_config = opts["vault"]
            # Respect locally configured verify parameter
            if local_config.get("verify", NOT_SET) != NOT_SET:
                merged["server"]["verify"] = local_config["verify"]
            elif local_config.get("server", {}).get("verify", NOT_SET) != NOT_SET:
                merged["server"]["verify"] = local_config["server"]["verify"]
            # same for token_lifecycle
            if local_config.get("auth", {}).get("token_lifecycle"):
                merged["auth"]["token_lifecycle"] = local_config["auth"][
                    "token_lifecycle"
                ]

        if not validate:
            return merged

        if merged["auth"]["method"] == "approle":
            if "role_id" not in merged["auth"]:
                raise AssertionError("auth:role_id is required for approle auth")
        elif merged["auth"]["method"] == "token":
            if require_token and "token" not in merged["auth"]:
                raise AssertionError("auth:token is required for token auth")
        else:
            raise AssertionError(
                f"`{merged['auth']['method']}` is not a valid auth method."
            )

        if "url" not in merged["server"]:
            raise AssertionError("server:url is required")
    except AssertionError as err:
        raise salt.exceptions.InvalidConfigError(
            f"Invalid vault configuration: {err}"
        ) from err
    return merged
