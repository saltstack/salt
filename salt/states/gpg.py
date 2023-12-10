"""
Management of the GPG keychains
===============================

.. versionadded:: 2016.3.0

"""

import logging

import salt.utils.dictupdate

log = logging.getLogger(__name__)

_VALID_TRUST_VALUES = [
    "expired",
    "unknown",
    "not_trusted",
    "marginally",
    "fully",
    "ultimately",
]

TRUST_MAP = {
    "expired": "Expired",
    "unknown": "Unknown",
    "not_trusted": "Not Trusted",
    "marginally": "Marginally",
    "fully": "Fully Trusted",
    "ultimately": "Ultimately Trusted",
}


def present(
    name, keys=None, user=None, keyserver=None, gnupghome=None, trust=None, **kwargs
):
    """
    Ensure a GPG public key is present in the GPG keychain.

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
    """

    ret = {"name": name, "result": True, "changes": {}, "comment": []}

    _current_keys = __salt__["gpg.list_keys"](user=user, gnupghome=gnupghome)

    current_keys = {}
    for key in _current_keys:
        keyid = key["keyid"]
        current_keys[keyid] = {}
        current_keys[keyid]["trust"] = key["trust"]

    if not keys:
        keys = name

    if isinstance(keys, str):
        keys = [keys]

    for key in keys:
        if key in current_keys.keys():
            if trust:
                if trust in _VALID_TRUST_VALUES:
                    if current_keys[key]["trust"] != TRUST_MAP[trust]:
                        if __opts__["test"]:
                            ret["result"] = None
                            ret["comment"].append(
                                f"Would have set trust level for {key} to {trust}"
                            )
                            salt.utils.dictupdate.set_dict_key_value(
                                ret, f"changes:{key}:trust", trust
                            )
                            continue
                        # update trust level
                        result = __salt__["gpg.trust_key"](
                            keyid=key,
                            trust_level=trust,
                            user=user,
                        )
                        if result["res"] is False:
                            ret["result"] = result["res"]
                            ret["comment"].append(result["message"])
                        else:
                            salt.utils.dictupdate.set_dict_key_value(
                                ret, f"changes:{key}:trust", trust
                            )
                            ret["comment"].append(
                                f"Set trust level for {key} to {trust}"
                            )
                    else:
                        ret["comment"].append(
                            f"GPG Public Key {key} already in correct trust state"
                        )
                else:
                    ret["comment"].append(f"Invalid trust level {trust}")

            ret["comment"].append(f"GPG Public Key {key} already in keychain")

        else:
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"].append(f"Would have added {key} to GPG keychain")
                salt.utils.dictupdate.set_dict_key_value(
                    ret, f"changes:{key}:added", True
                )
                continue
            result = __salt__["gpg.receive_keys"](
                keyserver,
                key,
                user,
                gnupghome,
            )
            if result["res"] is False:
                ret["result"] = result["res"]
                ret["comment"].extend(result["message"])
            else:
                ret["comment"].append(f"Added {key} to GPG keychain")
                salt.utils.dictupdate.set_dict_key_value(
                    ret, f"changes:{key}:added", True
                )

            if trust:
                if trust in _VALID_TRUST_VALUES:
                    result = __salt__["gpg.trust_key"](
                        keyid=key,
                        trust_level=trust,
                        user=user,
                    )
                    if result["res"] is False:
                        ret["result"] = result["res"]
                        ret["comment"].append(result["message"])
                    else:
                        ret["comment"].append(f"Set trust level for {key} to {trust}")
                else:
                    ret["comment"].append(f"Invalid trust level {trust}")

    ret["comment"] = "\n".join(ret["comment"])
    return ret


def absent(name, keys=None, user=None, gnupghome=None, **kwargs):
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
    """

    ret = {"name": name, "result": True, "changes": {}, "comment": []}

    _current_keys = __salt__["gpg.list_keys"](user=user, gnupghome=gnupghome)

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
            )
            if result["res"] is False:
                ret["result"] = result["res"]
                ret["comment"].append(result["message"])
            else:
                ret["comment"].append(f"Deleted {key} from GPG keychain")
                salt.utils.dictupdate.append_dict_key_value(ret, "changes:deleted", key)
        else:
            ret["comment"].append(f"{key} not found in GPG keychain")
    ret["comment"] = "\n".join(ret["comment"])
    return ret
