"""
Manage GPG keychains
====================

.. versionadded:: 2016.3.0

"""

import logging

import salt.utils.dictupdate
import salt.utils.immutabletypes as immutabletypes
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

TRUST_MAP = immutabletypes.freeze(
    {
        "expired": "Expired",
        "unknown": "Unknown",
        "not_trusted": "Not Trusted",
        "marginally": "Marginally",
        "fully": "Fully Trusted",
        "ultimately": "Ultimately Trusted",
    }
)


class KeyNotContained(CommandExecutionError):
    """
    Raised when a data source does not contain a requested key
    """


def present(
    name,
    keys=None,
    user=None,
    keyserver=None,
    gnupghome=None,
    trust=None,
    keyring=None,
    source=None,
    skip_keyserver=False,
    text=None,
    **kwargs,
):
    """
    Ensure a GPG public key is present in the GPG keychain and
    that it is not expired.

    name
        The key ID of the GPG public key.

    keys
        The key ID or key IDs to add to the GPG keychain.

    user
        Add GPG keys to the specified user's keychain.

    keyserver
        The keyserver to retrieve the keys from.

    gnupghome
        Override GnuPG home directory.

    trust
        Trust level for the key in the keychain,
        ignored by default. Valid trust levels:
        expired, unknown, not_trusted, marginally,
        fully, ultimately

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    source
        A (list of) path(s)/URI to retrieve the key(s) from.
        By default, this works as a backup option in case retrieving a key
        from the keyserver fails.

        .. note::
            All listed sources will be iterated over in order until the first one found
            to contain the requested key. If multiple keys are managed in a single
            state, the effective sources are allowed to differ between keys.

        .. important::
            Internally, this uses :py:func:`gpg.read_key <salt.modules.gpg.read_key>`
            to list keys in the sources. If a source is not a keyring, on GnuPG <2.1,
            this can lead to unintentional decryption.

        .. versionadded:: 3008.0

    skip_keyserver
        Do not attempt to retrieve the key from the keyserver, only use ``source``.
        Irrelevant when ``text`` is passed. Defaults to false.

        .. versionadded:: 3008.0

    text
        Instead of retrieving the key(s) to import from a keyserver/URI,
        import them from this (armored) string.

        .. note::
            ``name`` or ``keys`` must still specify the expected key ID(s),
            so this cannot be used to indiscriminately import a keyring.
            Requires python-gnupg v0.5.1.

        .. versionadded:: 3008.0
    """

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    try:
        if not text and skip_keyserver and not source:
            raise SaltInvocationError(
                "When skipping keyservers, you must provide at least one source"
            )

        if trust and trust not in TRUST_MAP:
            raise SaltInvocationError(f"Invalid trust level {trust}")

        _current_keys = __salt__["gpg.list_keys"](
            user=user, gnupghome=gnupghome, keyring=keyring
        )
    except (CommandExecutionError, SaltInvocationError) as err:
        ret["result"] = False
        ret["comment"] = str(err)
        return ret

    current_keys = {}
    expired_keys = []
    for key in _current_keys:
        keyid = key["keyid"]
        current_keys[keyid] = {}
        current_keys[keyid]["trust"] = key["trust"]
        if key.get("expired"):
            expired_keys.append(keyid)

    if not keys:
        keys = name
    if isinstance(keys, str):
        keys = [keys]
    key_res = {}

    # First, ensure all keys are present
    for key in keys:
        key_res[key] = []
        try:
            refresh = key in expired_keys
            if key in current_keys and not refresh:
                key_res[key].append(f"GPG Public Key {key} already in keychain")
                continue
            if __opts__["test"]:
                ret["result"] = None
                key_res[key] = [f"Would have added {key} to GPG keychain"]
                salt.utils.dictupdate.set_dict_key_value(
                    ret, f"changes:{key}:added", True
                )
                if refresh:
                    key_res[key][-1] += " (the existing one was expired)"
                    salt.utils.dictupdate.set_dict_key_value(
                        ret, f"changes:{key}:refresh", True
                    )
                else:
                    current_keys[key] = {"trust": "unknown"}
                continue
            result = {}
            if text:
                result = _import_data(key, refresh, user, gnupghome, keyring, text=text)
            else:
                if not skip_keyserver:
                    result = __salt__["gpg.receive_keys"](
                        keyserver=keyserver,
                        keys=key,
                        user=user,
                        gnupghome=gnupghome,
                        keyring=keyring,
                    )
                    if refresh and result["res"]:
                        # If we're refreshing and no updated key could be found,
                        # ensure we're failing here.
                        result["res"] = any(
                            "updated: new" in x for x in result["message"]
                        )
                    result["message"] = "\n".join(result["message"])
                if (not result or result["res"] is False) and source:
                    if not isinstance(source, list):
                        source = [source]
                    prev_msg = ""
                    if result:
                        prev_msg = result["message"] + "\n"
                    for src in source:
                        sfn = __salt__["cp.cache_file"](src)
                        if sfn:
                            log.debug("Found source: %s", src)
                            try:
                                result = _import_data(
                                    key, refresh, user, gnupghome, keyring, path=sfn
                                )
                                break
                            except KeyNotContained as err:
                                if "expired" in str(err):
                                    log.warning(
                                        "Found source %s contains key %s, but it's expired",
                                        src,
                                        key,
                                    )
                    else:
                        raise CommandExecutionError(
                            prev_msg
                            + f"none of the specified sources were found or contained the (unexpired) key {key}."
                        )

            if result["res"] is False:
                raise CommandExecutionError(result["message"])
            new_key = __salt__["gpg.get_key"](
                keyid=key, user=user, gnupghome=gnupghome, keyring=keyring
            )
            if not new_key:
                raise CommandExecutionError(
                    result["message"]
                    + f"\nThe new key {key} could not be retrieved though."
                )
            salt.utils.dictupdate.set_dict_key_value(ret, f"changes:{key}:added", True)
            if new_key.get("expired"):
                raise CommandExecutionError(
                    result["message"] + f"\nThe new key {key} is expired though."
                )
            key_res[key].append(f"Added {key} to GPG keychain")
            current_keys[key] = {"trust": new_key["trust"]}
            if refresh:
                key_res[key][-1] += " (the existing one was expired)"
                salt.utils.dictupdate.set_dict_key_value(
                    ret, f"changes:{key}:refresh", True
                )
        except (CommandExecutionError, SaltInvocationError) as err:
            ret["result"] = False
            if refresh:
                key_res[key].append(
                    "Existing key is expired, tried to fetch updated one"
                )
            key_res[key].extend(str(err).splitlines())

    # Now all possible keys are present, manage their trust if requested
    if trust:
        for key in keys:
            if key not in current_keys:
                # This means the key was not present and could not be retrieved
                continue
            try:
                if current_keys[key]["trust"] == TRUST_MAP[trust]:
                    key_res[key].append(
                        f"GPG Public Key {key} already in correct trust state"
                    )
                    continue
                if __opts__["test"]:
                    ret["result"] = None
                    key_res[key].append(
                        f"Would have set trust level for {key} to {trust}"
                    )
                    salt.utils.dictupdate.set_dict_key_value(
                        ret, f"changes:{key}:trust", trust
                    )
                    continue
                result = __salt__["gpg.trust_key"](
                    keyid=key,
                    trust_level=trust,
                    user=user,
                    gnupghome=gnupghome,
                    keyring=keyring,
                )
                if result["res"] is False:
                    raise CommandExecutionError(result["message"])
                key_res[key].append(f"Set trust level for {key} to {trust}")
                salt.utils.dictupdate.set_dict_key_value(
                    ret, f"changes:{key}:trust", trust
                )
            except (CommandExecutionError, SaltInvocationError) as err:
                ret["result"] = False
                key_res[key].append(str(err))
    final_res = {
        key: "\n  * " + "\n  * ".join(msgs) for key, msgs in key_res.items() if msgs
    }
    ret["comment"] = "\n".join(f"Key {key}:{msg}" for key, msg in final_res.items())
    return ret


def absent(
    name,
    keys=None,
    user=None,
    gnupghome=None,
    keyring=None,
    keyring_absent_if_empty=False,
    **kwargs,
):
    """
    Ensure a GPG public key is absent from the keychain.

    name
        The key ID of the GPG public key.

    keys
        The key ID or key IDs to remove from the GPG keychain.

    user
        Remove GPG keys from the specified user's keychain.

    gnupghome
        Override GnuPG home directory.

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    keyring_absent_if_empty
        Make sure to not leave behind an empty keyring file
        if ``keyring`` was specified. Defaults to false.

        .. versionadded:: 3007.0
    """

    ret = {"name": name, "result": True, "changes": {}, "comment": []}

    _current_keys = __salt__["gpg.list_keys"](
        user=user, gnupghome=gnupghome, keyring=keyring
    )

    current_keys = []
    for key in _current_keys:
        current_keys.append(key["keyid"])

    if not keys:
        keys = name

    if isinstance(keys, str):
        keys = [keys]

    for key in keys:
        if key in current_keys:
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"].append(f"Would have deleted {key} from GPG keychain")
                salt.utils.dictupdate.append_dict_key_value(ret, "changes:deleted", key)
                continue
            result = __salt__["gpg.delete_key"](
                keyid=key,
                user=user,
                gnupghome=gnupghome,
                keyring=keyring,
            )
            if result["res"] is False:
                ret["result"] = result["res"]
                ret["comment"].append(result["message"])
            else:
                ret["comment"].append(f"Deleted {key} from GPG keychain")
                salt.utils.dictupdate.append_dict_key_value(ret, "changes:deleted", key)
        else:
            ret["comment"].append(f"{key} not found in GPG keychain")

    if __opts__["test"] or not ret["result"]:
        return ret

    _new_keys = [
        x["keyid"]
        for x in __salt__["gpg.list_keys"](
            user=user, gnupghome=gnupghome, keyring=keyring
        )
    ]

    if set(keys) & set(_new_keys):
        remaining = set(keys) & set(_new_keys)
        ret["result"] = False
        ret["comment"].append(
            "State check revealed the following keys could not be deleted: "
            + ", ".join(remaining)
        )
        ret["changes"]["deleted"] = list(
            set(ret["changes"]["deleted"]) - set(_new_keys)
        )

    elif (
        not _new_keys
        and keyring
        and keyring_absent_if_empty
        and __salt__["file.file_exists"](keyring)
    ):
        __salt__["file.remove"](keyring)
        ret["comment"].append(f"Removed empty keyring file {keyring}")
        ret["changes"]["removed"] = keyring

    ret["comment"] = "\n".join(ret["comment"])
    return ret


def _import_data(key, refresh, user, gnupghome, keyring, text=None, path=None):
    has_key = __salt__["gpg.read_key"](
        text=text, path=path, keyid=key, gnupghome=gnupghome, user=user
    )
    if has_key:
        is_expired = has_key[0].get("expired")
        # Ensure we still import the expired key if it's not present
        if not is_expired or not refresh:
            log.debug("Passed text contains key %s", key)
            return __salt__["gpg.import_key"](
                text=text,
                filename=path,
                user=user,
                gnupghome=gnupghome,
                keyring=keyring,
                select=key,
            )
        raise KeyNotContained(f"Passed text contained the key {key}, but it's expired")
    raise KeyNotContained(f"Passed text did not contain the requested key {key}")
