"""
:maintainer:    SaltStack
:maturity:      new
:platform:      all

Utilities supporting modules for Hashicorp Vault. Configuration instructions are
documented in the execution module docs.
"""

import base64
import logging
import os
import string
import tempfile
import time

import requests

import salt.crypt
import salt.exceptions
import salt.utils.json
import salt.utils.versions

log = logging.getLogger(__name__)


# Load the __salt__ dunder if not already loaded (when called from utils-module)
__salt__ = None


def __virtual__():
    try:
        global __salt__  # pylint: disable=global-statement
        if not __salt__:
            __salt__ = salt.loader.minion_mods(__opts__)
            logging.getLogger("requests").setLevel(logging.WARNING)
            return True
    except Exception as e:  # pylint: disable=broad-except
        log.error("Could not load __salt__: %s", e)
        return False


def _get_token_and_url_from_master():
    """
    Get a token with correct policies for the minion, and the url to the Vault
    service
    """
    minion_id = __grains__["id"]
    pki_dir = __opts__["pki_dir"]
    # Allow minion override salt-master settings/defaults
    try:
        uses = __opts__.get("vault", {}).get("auth", {}).get("uses", None)
        ttl = __opts__.get("vault", {}).get("auth", {}).get("ttl", None)
    except (TypeError, AttributeError):
        # If uses or ttl are not defined, just use defaults
        uses = None
        ttl = None

    # When rendering pillars, the module executes on the master, but the token
    # should be issued for the minion, so that the correct policies are applied
    if __opts__.get("__role", "minion") == "minion":
        private_key = "{}/minion.pem".format(pki_dir)
        log.debug("Running on minion, signing token request with key %s", private_key)
        signature = base64.b64encode(salt.crypt.sign_message(private_key, minion_id))
        result = __salt__["publish.runner"](
            "vault.generate_token", arg=[minion_id, signature, False, ttl, uses]
        )
    else:
        private_key = "{}/master.pem".format(pki_dir)
        log.debug(
            "Running on master, signing token request for %s with key %s",
            minion_id,
            private_key,
        )
        signature = base64.b64encode(salt.crypt.sign_message(private_key, minion_id))
        result = __salt__["saltutil.runner"](
            "vault.generate_token",
            minion_id=minion_id,
            signature=signature,
            impersonated_by_master=True,
            ttl=ttl,
            uses=uses,
        )
    if not result:
        log.error(
            "Failed to get token from master! No result returned - "
            "is the peer publish configuration correct?"
        )
        raise salt.exceptions.CommandExecutionError(result)
    if not isinstance(result, dict):
        log.error("Failed to get token from master! Response is not a dict: %s", result)
        raise salt.exceptions.CommandExecutionError(result)
    if "error" in result:
        log.error(
            "Failed to get token from master! An error was returned: %s",
            result["error"],
        )
        raise salt.exceptions.CommandExecutionError(result)
    if "session" in result.get("token_backend", "session"):
        # This is the only way that this key can be placed onto __context__
        # Thus is tells the minion that the master is configured for token_backend: session
        log.debug("Using session storage for vault credentials")
        __context__["vault_secret_path_metadata"] = {}
    return {
        "url": result["url"],
        "token": result["token"],
        "verify": result.get("verify", None),
        "namespace": result.get("namespace"),
        "uses": result.get("uses", 1),
        "lease_duration": result["lease_duration"],
        "issued": result["issued"],
    }


def get_vault_connection():
    """
    Get the connection details for calling Vault, from local configuration if
    it exists, or from the master otherwise
    """

    def _use_local_config():
        log.debug("Using Vault connection details from local config")
        # Vault Enterprise requires a namespace
        namespace = __opts__["vault"].get("namespace")
        try:
            if __opts__["vault"]["auth"]["method"] == "approle":
                verify = __opts__["vault"].get("verify", None)
                if _selftoken_expired():
                    log.debug("Vault token expired. Recreating one")
                    # Requesting a short ttl token
                    url = "{}/v1/auth/approle/login".format(__opts__["vault"]["url"])
                    payload = {"role_id": __opts__["vault"]["auth"]["role_id"]}
                    if "secret_id" in __opts__["vault"]["auth"]:
                        payload["secret_id"] = __opts__["vault"]["auth"]["secret_id"]
                    if namespace is not None:
                        headers = {"X-Vault-Namespace": namespace}
                        response = requests.post(
                            url, headers=headers, json=payload, verify=verify
                        )
                    else:
                        response = requests.post(url, json=payload, verify=verify)
                    if response.status_code != 200:
                        errmsg = "An error occurred while getting a token from approle"
                        raise salt.exceptions.CommandExecutionError(errmsg)
                    __opts__["vault"]["auth"]["token"] = response.json()["auth"][
                        "client_token"
                    ]
            if __opts__["vault"]["auth"]["method"] == "wrapped_token":
                verify = __opts__["vault"].get("verify", None)
                if _wrapped_token_valid():
                    url = "{}/v1/sys/wrapping/unwrap".format(__opts__["vault"]["url"])
                    headers = {"X-Vault-Token": __opts__["vault"]["auth"]["token"]}
                    if namespace is not None:
                        headers["X-Vault-Namespace"] = namespace
                    response = requests.post(url, headers=headers, verify=verify)
                    if response.status_code != 200:
                        errmsg = "An error occured while unwrapping vault token"
                        raise salt.exceptions.CommandExecutionError(errmsg)
                    __opts__["vault"]["auth"]["token"] = response.json()["auth"][
                        "client_token"
                    ]
            return {
                "url": __opts__["vault"]["url"],
                "namespace": namespace,
                "token": __opts__["vault"]["auth"]["token"],
                "verify": __opts__["vault"].get("verify", None),
                "issued": int(round(time.time())),
                "ttl": 3600,
            }
        except KeyError as err:
            errmsg = 'Minion has "vault" config section, but could not find key "{}" within'.format(
                err
            )
            raise salt.exceptions.CommandExecutionError(errmsg)

    config = __opts__["vault"].get("config_location")
    if config:
        if config not in ["local", "master"]:
            log.error("config_location must be either local or master")
            return False
        if config == "local":
            return _use_local_config()
        elif config == "master":
            return _get_token_and_url_from_master()

    if "vault" in __opts__ and __opts__.get("__role", "minion") == "master":
        if "id" in __grains__:
            log.debug("Contacting master for Vault connection details")
            return _get_token_and_url_from_master()
        else:
            return _use_local_config()
    elif any(
        (
            __opts__.get("local", None),
            __opts__.get("file_client", None) == "local",
            __opts__.get("master_type", None) == "disable",
        )
    ):
        return _use_local_config()
    else:
        log.debug("Contacting master for Vault connection details")
        return _get_token_and_url_from_master()


def del_cache():
    """
    Delete cache
    """
    log.debug("Deleting session cache")
    if "vault_token" in __context__:
        del __context__["vault_token"]

    log.debug("Deleting cache file")
    cache_file = os.path.join(__opts__["cachedir"], "salt_vault_token")

    if os.path.exists(cache_file):
        os.remove(cache_file)
    else:
        log.debug("Attempted to delete vault cache file, but it does not exist.")


def write_cache(connection):
    """
    Write the vault token to cache
    """
    # If uses is 1 and unlimited_use_token is not true, then this is a single use token and should not be cached
    # In that case, we still want to cache the vault metadata lookup information for paths, so continue on
    if (
        connection.get("uses", None) == 1
        and "unlimited_use_token" not in connection
        and "vault_secret_path_metadata" not in connection
    ):
        log.debug("Not caching vault single use token")
        __context__["vault_token"] = connection
        return True
    elif (
        "vault_secret_path_metadata" in __context__
        and "vault_secret_path_metadata" not in connection
    ):
        # If session storage is being used, and info passed is not the already saved metadata
        log.debug("Storing token only for this session")
        __context__["vault_token"] = connection
        return True
    elif "vault_secret_path_metadata" in __context__:
        # Must have been passed metadata. This is already handled by _get_secret_path_metadata
        #  and does not need to be resaved
        return True
    temp_fp, temp_file = tempfile.mkstemp(dir=__opts__["cachedir"])
    cache_file = os.path.join(__opts__["cachedir"], "salt_vault_token")
    try:
        log.debug("Writing vault cache file")
        # Detect if token was issued without use limit
        if connection.get("uses") == 0:
            connection["unlimited_use_token"] = True
        else:
            connection["unlimited_use_token"] = False
        with salt.utils.files.fpopen(temp_file, "w", mode=0o600) as fp_:
            fp_.write(salt.utils.json.dumps(connection))
        os.close(temp_fp)
        # Atomic operation to pervent race condition with concurrent calls.
        os.rename(temp_file, cache_file)
        return True
    except OSError:
        log.error(
            "Failed to cache vault information", exc_info_on_loglevel=logging.DEBUG
        )
        return False


def _read_cache_file():
    """
    Return contents of cache file
    """
    try:
        cache_file = os.path.join(__opts__["cachedir"], "salt_vault_token")
        with salt.utils.files.fopen(cache_file, "r") as contents:
            return salt.utils.json.load(contents)
    except FileNotFoundError:
        return {}


def get_cache():
    """
    Return connection information from vault cache file
    """

    def _gen_new_connection():
        log.debug("Refreshing token")
        connection = get_vault_connection()
        write_status = write_cache(connection)
        return connection

    connection = _read_cache_file()
    # If no cache, or only metadata info is saved in cache, generate a new token
    if not connection or "url" not in connection:
        return _gen_new_connection()

    # Drop 10 seconds from ttl to be safe
    if "lease_duration" in connection:
        ttl = connection["lease_duration"]
    else:
        ttl = connection["ttl"]
    ttl10 = connection["issued"] + ttl - 10
    cur_time = int(round(time.time()))

    # Determine if ttl still valid
    if ttl10 < cur_time:
        log.debug("Cached token has expired %s < %s: DELETING", ttl10, cur_time)
        del_cache()
        return _gen_new_connection()
    else:
        log.debug("Token has not expired %s > %s", ttl10, cur_time)
    return connection


def make_request(
    method,
    resource,
    token=None,
    vault_url=None,
    namespace=None,
    get_token_url=False,
    retry=False,
    **args
):
    """
    Make a request to Vault
    """
    if "vault_token" in __context__:
        connection = __context__["vault_token"]
    else:
        connection = get_cache()
    token = connection["token"] if not token else token
    vault_url = connection["url"] if not vault_url else vault_url
    namespace = namespace or connection.get("namespace")
    if "verify" in args:
        args["verify"] = args["verify"]
    else:
        try:
            args["verify"] = __opts__.get("vault").get("verify", None)
        except (TypeError, AttributeError):
            # Don't worry about setting verify if it doesn't exist
            pass
    url = "{}/{}".format(vault_url, resource)
    headers = {"X-Vault-Token": str(token), "Content-Type": "application/json"}
    if namespace is not None:
        headers["X-Vault-Namespace"] = namespace
    response = requests.request(method, url, headers=headers, **args)
    if not response.ok and response.json().get("errors", None) == ["permission denied"]:
        log.info("Permission denied from vault")
        del_cache()
        if not retry:
            log.debug("Retrying with new credentials")
            response = make_request(
                method,
                resource,
                token=None,
                vault_url=vault_url,
                get_token_url=get_token_url,
                retry=True,
                **args
            )
        else:
            log.error("Unable to connect to vault server: %s", response.text)
            return response
    elif not response.ok:
        log.error("Error from vault: %s", response.text)
        return response

    # Decrement vault uses, only on secret URL lookups and multi use tokens
    if (
        "uses" in connection
        and not connection.get("unlimited_use_token")
        and not resource.startswith("v1/sys")
    ):
        log.debug("Decrementing Vault uses on limited token for url: %s", resource)
        connection["uses"] -= 1
        if connection["uses"] <= 0:
            log.debug("Cached token has no more uses left.")
            if "vault_token" not in __context__:
                del_cache()
            else:
                log.debug("Deleting token from memory")
                del __context__["vault_token"]
        else:
            log.debug("Token has %s uses left", connection["uses"])
            write_cache(connection)

    if get_token_url:
        return response, token, vault_url
    else:
        return response


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
        if namespace is not None:
            headers["X-Vault-Namespace"] = namespace
        response = requests.get(url, headers=headers, verify=verify)
        if response.status_code != 200:
            return True
        return False
    except Exception as e:  # pylint: disable=broad-except
        raise salt.exceptions.CommandExecutionError(
            "Error while looking up self token : {}".format(e)
        )


def _wrapped_token_valid():
    """
    Validate the wrapped token exists and is still valid
    """
    try:
        verify = __opts__["vault"].get("verify", None)
        # Vault Enterprise requires a namespace
        namespace = __opts__["vault"].get("namespace")
        url = "{}/v1/sys/wrapping/lookup".format(__opts__["vault"]["url"])
        if "token" not in __opts__["vault"]["auth"]:
            return False
        headers = {"X-Vault-Token": __opts__["vault"]["auth"]["token"]}
        if namespace is not None:
            headers["X-Vault-Namespace"] = namespace
        response = requests.post(url, headers=headers, verify=verify)
        if response.status_code != 200:
            return False
        return True
    except Exception as e:  # pylint: disable=broad-except
        raise salt.exceptions.CommandExecutionError(
            "Error while looking up wrapped token : {}".format(e)
        )


def is_v2(path):
    """
    Determines if a given secret path is kv version 1 or 2

    CLI Example:

    .. code-block:: bash

        salt '*' vault.is_v2 "secret/my/secret"
    """
    ret = {"v2": False, "data": path, "metadata": path, "delete": path, "type": None}
    path_metadata = _get_secret_path_metadata(path)
    if not path_metadata:
        # metadata lookup failed. Simply return not v2
        return ret
    ret["type"] = path_metadata.get("type", "kv")
    if (
        ret["type"] == "kv"
        and path_metadata["options"] is not None
        and path_metadata.get("options", {}).get("version", "1") in ["2"]
    ):
        ret["v2"] = True
        ret["data"] = _v2_the_path(path, path_metadata.get("path", path))
        ret["metadata"] = _v2_the_path(
            path, path_metadata.get("path", path), "metadata"
        )
        ret["destroy"] = _v2_the_path(path, path_metadata.get("path", path), "destroy")
    return ret


def _v2_the_path(path, pfilter, ptype="data"):
    """
    Given a path, a filter, and a path type, properly inject 'data' or 'metadata' into the path

    CLI Example:

    .. code-block:: python

        _v2_the_path('dev/secrets/fu/bar', 'dev/secrets', 'data') => 'dev/secrets/data/fu/bar'
    """
    possible_types = ["data", "metadata", "destroy"]
    assert ptype in possible_types
    msg = (
        "Path {} already contains {} in the right place - saltstack duct tape?".format(
            path, ptype
        )
    )

    path = path.rstrip("/").lstrip("/")
    pfilter = pfilter.rstrip("/").lstrip("/")

    together = pfilter + "/" + ptype

    otype = possible_types[0] if possible_types[0] != ptype else possible_types[1]
    other = pfilter + "/" + otype
    if path.startswith(other):
        path = path.replace(other, together, 1)
        msg = 'Path is a "{}" type but "{}" type requested - Flipping: {}'.format(
            otype, ptype, path
        )
    elif not path.startswith(together):
        msg = "Converting path to v2 {} => {}".format(
            path, path.replace(pfilter, together, 1)
        )
        path = path.replace(pfilter, together, 1)

    log.debug(msg)
    return path


def _get_secret_path_metadata(path):
    """
    Given a path, query vault to determine mount point, type, and version

    CLI Example:

    .. code-block:: python

        _get_secret_path_metadata('dev/secrets/fu/bar')
    """
    ckey = "vault_secret_path_metadata"

    # Attempt to lookup from cache
    if ckey in __context__:
        cache_content = __context__[ckey]
    else:
        cache_content = _read_cache_file()
    if ckey not in cache_content:
        cache_content[ckey] = {}

    ret = None
    if path.startswith(tuple(cache_content[ckey].keys())):
        log.debug("Found cached metadata for %s", path)
        ret = next(v for k, v in cache_content[ckey].items() if path.startswith(k))
    else:
        log.debug("Fetching metadata for %s", path)
        try:
            url = "v1/sys/internal/ui/mounts/{}".format(path)
            response = make_request("GET", url)
            if response.ok:
                response.raise_for_status()
            if response.json().get("data", False):
                log.debug("Got metadata for %s", path)
                ret = response.json()["data"]
                # Write metadata to cache file
                # Check for new cache content from make_request
                if "url" not in cache_content:
                    if ckey in __context__:
                        cache_content = __context__[ckey]
                    else:
                        cache_content = _read_cache_file()
                    if ckey not in cache_content:
                        cache_content[ckey] = {}
                cache_content[ckey][path] = ret
                write_cache(cache_content)
            else:
                raise response.json()
        except Exception as err:  # pylint: disable=broad-except
            log.error("Failed to get secret metadata %s: %s", type(err).__name__, err)
    return ret


def expand_pattern_lists(pattern, **mappings):
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

    # This function uses a string.Formatter to get all the formatting tokens from
    # the pattern, then recursively replaces tokens whose expanded value is a
    # list. For a list with N items, it will create N new pattern strings and
    # then continue with the next token. In practice this is expected to not be
    # very expensive, since patterns will typically involve a handful of lists at
    # most.

    for (_, field_name, _, _) in f.parse(pattern):
        if field_name is None:
            continue
        (value, _) = f.get_field(field_name, None, mappings)
        if isinstance(value, list):
            token = "{{{0}}}".format(field_name)
            expanded = [pattern.replace(token, str(elem)) for elem in value]
            for expanded_item in expanded:
                result = expand_pattern_lists(expanded_item, **mappings)
                expanded_patterns += result
            return expanded_patterns
    return [pattern]
