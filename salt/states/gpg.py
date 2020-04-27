# -*- coding: utf-8 -*-
"""
Management of the GPG keychains
===============================

.. versionadded:: 2016.3.0

"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os

# Import salt libs
from salt.exceptions import SaltInvocationError, CheckError

# Import 3rd-party libs
from salt.ext import six
import salt.utils.data
import salt.utils.dictupdate
import salt.utils.path

log = logging.getLogger(__name__)

TRUST_MAP = {
    "expired": "Expired",
    "unknown": "Unknown",
    "not_trusted": "Not Trusted",
    "marginally": "Marginally",
    "fully": "Fully Trusted",
    "ultimately": "Ultimately Trusted",
}
_VALID_TRUST_VALUES = TRUST_MAP.keys()


def __virtual__():
    """
    This state can only be used if the required functions exist.
    """
    requirements = [
        "gpg.list_keys",
        "gpg.receive_keys",
        "gpg.delete_key",
        "gpg.trust_key",
    ]
    for req in requirements:
        if req not in __salt__:
            return False, 'A required function "{}" was not loaded.'.format(req)
    return True


def present(
    name, keys=None, user=None, keyserver=None, keydata=None, gnupghome=None, trust=None
):
    """
    Ensure GPG key is present in the keychain specified by either ``user`` or
    ``gnupghome``. Also ensures GPG key is trusted at level ``trust``.

    Note for test mode: No attempt to trust keys that would have been added
    will be made.

    :param str name: The keyid or fingerprint for the GPG public key.
        This is ignored when ``keydata`` is provided.
    :param str/list keys: The (list of) keyid(s) or fingerprint(s) of keys to
        add to the GPG keychain. Overrides key provided in ``name``.
    :param str user: Add GPG keys to the specified user's keychain
    :param str keyserver: The keyserver to retrieve the keys from.
    :param str keydata: Armored keyblock to import instead of fetching from ``keyserver``.
    :param str gnupghome: Override GNUPG Home directory
    :param str trust: Trust level for the key in the keychain. Valid trust levels:
        expired, unknown, not_trusted, marginally, fully, ultimately
    """
    ret = {"name": name, "result": "changeme", "changes": {}, "comment": []}

    if not keys:
        keys = name
    if isinstance(keys, six.string_types):
        keys = [keys]
    if trust:
        if trust not in _VALID_TRUST_VALUES:
            ret["result"] = False
            ret["comment"].append("Invalid trust level {}".format(trust))
            return ret

    _current_keys = __salt__["gpg.list_keys"](user=user, gnupghome=gnupghome)

    trust_keys = []
    current_keys = {}
    fingerprints = {}
    for key in _current_keys:
        keyid = key["keyid"]
        current_keys[keyid] = key
        fingerprints[key["fingerprint"]] = key

    if keydata:
        if "gpg.get_fingerprint_from_data" in __salt__:
            fingerprint = __salt__["gpg.get_fingerprint_from_data"](keydata)
            if fingerprint in fingerprints:
                ret["result"] = True
                ret["comment"].append(
                    'GPG key with fingerprint "{}" from keydata '
                    "already in keychain."
                    "".format(fingerprint)
                )
        # Just (try to) import it
        if ret["result"] is not True and __opts__["test"]:
            ret["result"] = None
            ret["comment"].append("GPG key would have been imported.")
            salt.utils.dictupdate.update_dict_key_value(
                ret, "changes:old", {"key": None}
            )
            salt.utils.dictupdate.update_dict_key_value(
                ret, "changes:new", {"key": "Imported"}
            )
        elif ret["result"] is not True:
            res = __salt__["gpg.import_key"](
                text=keydata, user=user, gnupghome=gnupghome
            )
            if res["result"]:
                ret["result"] = True
                if res["message"] == "Key(s) already exist in keychain.":
                    ret["comment"].append("GPG key from keydata already in keychain.")
                else:
                    ret["comment"].append("GPG key from keydata added to GPG keychain.")
                    trust_keys.extend(list(set(res["fingerprints"])))
                    for fingerprint in res["fingerprints"]:
                        salt.utils.dictupdate.set_dict_key_value(
                            ret, "changes:old", {fingerprint: None},
                        )
                        salt.utils.dictupdate.update_dict_key_value(
                            ret,
                            "changes:new",
                            {fingerprint: {} if trust else "present"},
                        )
            else:
                ret["result"] = False
                ret["comment"].append(res["message"])
                del ret["changes"]["old"]
                del ret["changes"]["new"]
    else:
        for key in keys:
            if key in current_keys or key in fingerprints:
                ret["result"] = True
                ret["comment"].append(
                    'GPG public key "{}" already in keychain.' "".format(key)
                )
                trust_keys.append(key)
            else:
                salt.utils.dictupdate.update_dict_key_value(
                    ret, "changes:old", {key: None},
                )
                salt.utils.dictupdate.update_dict_key_value(
                    ret, "changes:new", {key: {} if trust else "present"},
                )
                if __opts__["test"]:
                    ret["result"] = None
                    ret["comment"].append(
                        'GPG public key "{}" would have been added.' "".format(key)
                    )
                else:
                    res = __salt__["gpg.receive_keys"](
                        keyserver=keyserver, keys=key, user=user, gnupghome=gnupghome,
                    )
                    if res["result"]:
                        ret["result"] = True
                        ret["comment"].append(
                            'GPG public key "{}" added to GPG keychain.' "".format(key)
                        )
                        trust_keys.append(key)
                    else:
                        ret["result"] = False
                        ret["comment"].append(res["message"])
                        del ret["changes"]["old"][key]
                        del ret["changes"]["new"][key]
    if trust and ret["result"]:
        for key in trust_keys:
            res = trusted(
                name, keys=trust_keys, user=user, gnupghome=gnupghome, trust=trust
            )
            if res["result"] and res["changes"]:
                if ret["changes"]["old"] and ret["changes"]["old"][key]:
                    # Only report old trust-level if key existed before.
                    salt.utils.dictupdate.update_dict_key_value(
                        ret,
                        "changes:old:{}".format(key),
                        {"trust": res["changes"]["old"][key]},
                    )
                salt.utils.dictupdate.update_dict_key_value(
                    ret,
                    "changes:new:{}".format(key),
                    {"trust": res["changes"]["new"][key]},
                )
            ret["result"] = res["result"]
            ret["comment"].extend(res["comment"])
    return ret


def absent(name, keys=None, user=None, passphrases=None, gnupghome=None):
    """
    Ensure GPG private/public key is absent in keychain.
    Note that a public key can only be removed after a private key is also removed,
    so if both exist, both will be removed.

    :param str name: The keyid or fingerprint for the GPG public key.
    :param str/list keys: The keyId(s) or fingerprint(s) to remove from the GPG keychain.
    :param str user: Remove GPG keys from the specified user's keychain
    :param str/list passphrases: The passphrase(s) of the keys that need them.
        For GPG version 2.1 and above, private keys can only be removed when the
        appropriate passphrase is provided.
        If ``keys`` is a list, this also needs to be a list with the passphrases
        having the same index as the matching key.
    :param str gnupghome: Override GNUPG Home directory
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": []}

    if not keys:
        keys = name
    if isinstance(keys, six.string_types):
        keys = [keys]
    if isinstance(passphrases, six.string_types):
        passphrases = [passphrases]
    elif passphrases is None:
        passphrases = []

    _current_keys = __salt__["gpg.list_keys"](user=user, gnupghome=gnupghome)

    keys_by_keyid = {}
    keys_by_fingerprint = {}
    for key in _current_keys:
        keys_by_keyid[key["keyid"]] = key
        keys_by_fingerprint[key["fingerprint"]] = key

    for index, key in enumerate(keys):
        current_key = keys_by_keyid.get(key, keys_by_fingerprint.get(key))
        if current_key:
            salt.utils.dictupdate.set_dict_key_value(
                ret, "changes:old:{}".format(key), "present"
            )
            salt.utils.dictupdate.set_dict_key_value(
                ret, "changes:new:{}".format(key), None
            )
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"].append(
                    'Key "{}" would have been removed from the '
                    "GPG keychain.".format(key)
                )
            else:
                delete_kwargs = salt.utils.data.filter_falsey(
                    {
                        "fingerprint": current_key["fingerprint"],
                        "user": user,
                        "gnupghome": gnupghome,
                        "delete_secret": True,
                        "passphrase": passphrases[index]
                        if index < len(passphrases)
                        else None,
                    }
                )
                res = __salt__["gpg.delete_key"](**delete_kwargs)
                if res["result"]:
                    ret["comment"].append('Deleted "{}" from GPG keychain'.format(key))
                else:
                    ret["result"] = False
                    ret["comment"].append(res["message"])
                    del ret["changes"]["old"][key]
                    del ret["changes"]["new"][key]
        else:
            ret["comment"].append('Key "{}" already not in GPG keychain'.format(key))
    return ret


def trusted(name, keys=None, user=None, gnupghome=None, trust=None):
    """
    Ensures the gpgkey(s) specified is/are trusted to the specified trust level.

    :param str name: The unique name or keyid or fingerprint of the key.
    :param list keys: The list of names/keyids/fingerprints of keys to trust.
    :param str user: The user whose GPG keychain to work on.
    :param str gnupghome: Override GNUPG Home directory.
    :param str trust: Trust level for the key in the keychain, Valid trust levels:
        expired, unknown, not_trusted, marginally, fully, ultimately
    """
    ret = {"name": name, "result": True, "comment": [], "changes": {}}

    if trust and trust not in _VALID_TRUST_VALUES:
        ret["result"] = False
        ret["comment"].append("Invalid trust level {}".format(trust))
        return ret

    if not keys:
        keys = name
    if isinstance(keys, six.string_types):
        keys = [keys]

    _current_keys = __salt__["gpg.list_keys"](user=user, gnupghome=gnupghome)

    keys_by_keyid = {}
    keys_by_fingerprint = {}
    for key in _current_keys:
        keys_by_keyid[key["keyid"]] = key
        if "fingerprint" in key:
            keys_by_fingerprint[key["fingerprint"]] = key

    for key in keys:
        current_key = keys_by_keyid.get(key, keys_by_fingerprint.get(key))
        if current_key:
            if current_key["ownerTrust"] != TRUST_MAP[trust]:
                salt.utils.dictupdate.set_dict_key_value(
                    ret, "changes:old:{}".format(key), current_key["ownerTrust"]
                )
                salt.utils.dictupdate.set_dict_key_value(
                    ret, "changes:new:{}".format(key), trust
                )
                if __opts__["test"]:
                    ret["result"] = None
                    ret["comment"].append(
                        'Key "{}" would have been tusted to "{}".' "".format(key, trust)
                    )
                else:
                    params = salt.utils.data.filter_falsey(
                        {"trust_level": trust, "user": user, "gnupghome": gnupghome,}
                    )
                    if "fingerprint" in current_key:
                        params.update({"fingerprint": current_key["fingerprint"]})
                    else:
                        params.update({"keyid": current_key["keyid"]})
                    res = __salt__["gpg.trust_key"](**params)
                    if res["result"]:
                        ret["comment"].append(
                            'Set trust level for "{}" to "{}".'.format(key, trust)
                        )
                    else:
                        ret["result"] = False
                        ret["comment"].append(res["message"])
                        del ret["changes"]["old"][key]
                        del ret["changes"]["new"][key]
            else:
                ret["comment"].append(
                    'Trust level for key "{}" already set to "{}".'
                    "".format(key, trust)
                )
        else:
            ret["result"] = False
            ret["comment"].append(
                'Key "{}" not in keychain, cannot trust.' "".format(key)
            )
    return ret


def data_encrypted(
    name,
    source=None,
    contents=None,
    contents_pillar=None,
    recipients=None,
    symmetric=None,
    passphrase=None,
    passphrase_pillar=None,
    armor=None,
    sign=None,
    user=None,
    gnupghome=None,
):
    """
    Ensures file with name ``name`` contains encrypted data either from file ``source``,
    from ``contents`` or the pillar entry denoted by ``contents_pillar``.
    Does nothing if ``name`` already contains GPG-encrypted data, but overwrites
    it if it doesn't.

    :param str name: Path of the file to ensure contains encrypted contents.
    :param str source: The file containing the data to encrypt. This file can be
        hosted on either the salt master server (``salt://``), the salt minion
        local file system (``/``) or on an HTTP or FTP server (``http(s)://`` or
        ``ftp://``) since this will call ``cp.cache_file`` to retrieve the file.
    :param str contents: The contents to be stored encrypted in the target file.
    :param str contents_pillar: The pillar key for which the contents are to be
        stored encrypted in the target file.
    :param str recipients: The fingerprints for those recipients whom the data is
        being encrypted for.
    :type symmetric: bool or str
    :param symmetric: If ``True`` or equal to some string, will use symmetric encryption.
        The value passed will be interpreted to be the cipher to use. Default: ``None``.
        When ``True``, the default cipher will be set to AES256.
        When used, a passphrase will need to be supplied.
    :param str passphrase: Passphrase to use with the signing key or symmetric encryption.
        default is None.
    :param str passphrase_pillar: Pillar key to retrieve the passphrase from, default
        is None.
    :type sign: bool or str
    :param sign: Whether to sign, in addition to encrypt, the data. Set to ``True``
        to use default key or provide the fingerprint of a different key to sign with.
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.
    :param bool armor: Whether to use ASCII armor. If ``False``, binary data is produced.
        Default ``True``.
    """
    ret = {"name": name, "result": "changeme", "comment": [], "changes": {}}
    # Sanity-checking input
    if not salt.utils.data.exactly_one((source, contents, contents_pillar)):
        ret["result"] = False
        ret["comment"].append(
            "Exactly one of either source, contents or "
            "contents_pillar must be provided."
        )
    elif contents_pillar:
        # Sneakily preload data from pillar into contents variable
        contents = __salt__["pillar.get"](contents_pillar, None)
        if contents is None:
            ret["result"] = False
            ret["comment"].append(
                "No data found in pillar for {}".format(contents_pillar)
            )
    if not ret["result"]:
        return ret

    # Check if nothing needs to be done
    if __salt__["file.file_exists"](name):
        # Try to find out if it contains GPG encrypted things using `file`
        file_binary = salt.utils.path.which("file")
        if file_binary:
            res = __salt__["cmd.run_stdout"](file_binary + " " + name)
            if res and ("PGP message" in res or "PGP RSA encrypted" in res):
                ret["result"] = True
        else:
            # Open the file and check if it contains GPG magic bytes :)
            # From https://github.com/file/file/blob/master/magic/Magdir/pgp
            with salt.utils.files.flopen(name, "rb") as _fp:
                data = _fp.read(27)
                if (
                    data.startswith(b"-----BEGIN PGP MESSAGE-----")
                    or data.startswith(r"\x84\x8c\x03")  # Armored encrypted message
                    or data.startswith(r"\x85\x01\x0c\x03")  # 1024b RSA encrypted data
                    or data.startswith(r"\x85\x01\x8c\x03")  # 2048b RSA encrypted data
                    or data.startswith(r"\x85\x02\x0c\x03")  # 3072b RSA encrypted data
                    or data.startswith(  # 3072b RSA encrypted data
                        r"\x85\x04\x0c\x03"
                    )  # 4096b RSA encrypted data
                ):
                    ret["result"] = True
        if ret["result"] is True:
            ret["comment"].append("File already contains encrypted data")
            return ret
    # Encryption is go
    salt.utils.dictupdate.set_dict_key_value(
        ret, "changes:old:{}".format(name), None,
    )
    salt.utils.dictupdate.set_dict_key_value(
        ret, "changes:new:{}".format(name), "encrypted data",
    )
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"].append("File would have been created with encrypted data")
    else:
        encrypt_kwargs = salt.utils.data.filter_falsey(
            {
                "output": name,
                "user": user,
                "recipients": recipients,
                "symmetric": symmetric,
                "passphrase": passphrase,
                "passphrase_pillar": passphrase_pillar,
                "sign": sign,
                "gnupghome": gnupghome,
                "armor": armor,
            }
        )
        if source:
            cached_filename = __salt__["cp.cache_file"](source)
            if not cached_filename:
                ret["result"] = False
                ret["comment"].append("Failed to cache source locally.")
            else:
                encrypt_kwargs.update({"filename": cached_filename})
        else:
            encrypt_kwargs.update({"text": contents})
    if ret["result"]:
        try:
            res = __salt__["gpg.encrypt"](**encrypt_kwargs)
        except SaltInvocationError as exc:
            ret["result"] = False
            ret["comment"].append(str(exc))
        else:
            ret["result"] = res["result"]
            ret["comment"].append(res["message"])
        if source:
            # Cleanup cached file
            os.unlink(cached_filename)
    if ret["result"] is False:
        del ret["changes"]["old"]
        del ret["changes"]["new"]
    if ret["result"] and not isinstance(ret["result"], bool):
        raise CheckError("Internal error, result not properly specified.")
    return ret


def data_decrypted(
    name,
    source=None,
    user=None,
    contents=None,
    contents_pillar=None,
    symmetric=None,
    passphrase=None,
    passphrase_pillar=None,
    gnupghome=None,
    always_trust=False,
    force=False,
):
    """
    Ensures file with name ``name`` contains decrypted data either from file ``source``,
    from ``contents`` or the pillar entry denoted by ``contents_pillar``.

    :param str name: Path of the file to ensure contains decrypted contents.
        Note that if this file already exists, nothing will be done unless ``force``
        is set to ``True``.
    :param str source: The file containing the data to decrypt. This file can be
        hosted on either the salt master server (``salt://``), the salt minion
        local file system (``/``) or on an HTTP or FTP server (``http(s)://`` or
        ``ftp://``) since this will call ``cp.cache_file`` to retrieve the file.
    :param str contents: The contents to be decrypted and stored in the target file.
    :param str contents_pillar: The pillar key for which the contents are to be
        decrypted and stored in the target file.
    :type symmetric: bool or str
    :param symmetric: If ``True`` or equal to some string, will use symmetric decryption.
        The value passed will be interpreted to be the cipher to use. Default: ``None``.
        When ``True``, the default cipher will be set to AES256.
        When used, a passphrase will need to be supplied.
    :param str passphrase: Passphrase to use with the decryption key or symmetric decryption.
        default is None.
    :param str passphrase_pillar: Pillar key to retrieve the passphrase from, default
        is None.
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.
    :param bool force: Set to ``True`` to overwrite the file ``name`` if it exists.
    """
    ret = {"name": name, "result": "changeme", "comment": [], "changes": {}}
    # Sanity-checking input
    if not salt.utils.data.exactly_one((source, contents, contents_pillar)):
        ret["result"] = False
        ret["comment"].append(
            "Exactly one of either source, contents or "
            "contents_pillar must be provided."
        )
    elif contents_pillar:
        # Sneakily preload data from pillar into contents variable
        contents = __salt__["pillar.get"](contents_pillar, None)
        if contents is None:
            ret["result"] = False
            ret["comment"].append(
                "No data found in pillar for {}".format(contents_pillar)
            )
    if not ret["result"]:
        return ret

    # Check if nothing needs to be done
    if __salt__["file.file_exists"](name) and not force:
        ret["result"] = True
        ret["comment"].append("Target file already exists. Not forcing overwrite.")
        return ret

    # If the file exists we need to decrypt anyway to determine if the contents
    # are the same.
    # Just check afterwards if the contents were the same and delete changes.

    salt.utils.dictupdate.set_dict_key_value(
        ret, "changes:old:{}".format(name), None,
    )
    salt.utils.dictupdate.set_dict_key_value(
        ret, "changes:new:{}".format(name), "decrypted data",
    )

    target_hash = None
    replacement_hash = None
    if __salt__["file.file_exists"](name):
        target_hash = __salt__["file.get_hash"](name)
        salt.utils.dictupdate.set_dict_key_value(
            ret, "changes:old:{}".format(name), target_hash,
        )

    decrypt_kwargs = salt.utils.data.filter_falsey(
        {
            "output": name,
            "user": user,
            "symmetric": symmetric,
            "passphrase": passphrase,
            "passphrase_pillar": passphrase_pillar,
            "gnupghome": gnupghome,
        }
    )

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"].append("File would have been created with decrypted data.")
    else:
        if source:
            cached_filename = __salt__["cp.cache_file"](source)
            if not cached_filename:
                ret["result"] = False
                ret["comment"].append("Failed to cache source locally.")
            else:
                decrypt_kwargs.update({"filename": cached_filename})
        else:
            decrypt_kwargs.update({"text": contents})

    if ret["result"]:
        try:
            res = __salt__["gpg.decrypt"](**decrypt_kwargs)
        except SaltInvocationError as exc:
            ret["result"] = False
            ret["comment"].append(str(exc))
        else:
            ret["result"] = res["result"]
            ret["comment"].append(res["message"])
            replacement_hash = __salt__["file.get_hash"](name)
        if source:
            # Cleanup cached file
            os.unlink(cached_filename)
    if ret["result"] is False or target_hash == replacement_hash:
        del ret["changes"]["old"]
        del ret["changes"]["new"]
    if ret["result"] and not isinstance(ret["result"], bool):
        raise CheckError("Internal error, result not properly specified.")
    return ret


def data_signed(
    name,
    source=None,
    contents=None,
    contents_pillar=None,
    keyid=None,
    detach=False,
    passphrase=None,
    passphrase_pillar=None,
    user=None,
    gnupghome=None,
    force=None,
):
    """
    Ensures file with name ``name`` contains the data from ``source``, ``contents``
    or ``contents_pillar`` and signature using ``keyid``.

    If ``detach`` is set to ``True``, the file with name ``name`` will only contain
    the signature.

    :param str name: Path of the file to ensure signed contents (or signature, see
        ``detach`` below) into.
        Note that if this file already exists, nothing will be done unless ``force``
        is set to ``True``.
    :param str source: The file containing the data to sign. This file can be
        hosted on either the salt master server (``salt://``), the salt minion
        local file system (``/``) or on an HTTP or FTP server (``http(s)://`` or
        ``ftp://``) since this will call ``cp.cache_file`` to retrieve the file.
    :param str contents: The contents to be signed and stored in the target file.
    :param str contents_pillar: The pillar key for which the contents are to be
        signed and stored in the target file.
    :param str keyid: The keyid of the secret key to use to sign the data, defaults
        to first key in the secret keyring.
    :param bool detach: Only write the signature. Default ``False``.
    :param str passphrase: Passphrase to use with the signing key.
        default is None.
    :param str passphrase_pillar: Pillar key to retrieve the passphrase from, default
        is None.
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.
    :param bool force: Set to ``True`` to overwrite the file ``name`` if it exists.
    """
    ret = {"name": name, "result": "changeme", "comment": [], "changes": {}}
    # Sanity-checking input
    if not salt.utils.data.exactly_one((source, contents, contents_pillar)):
        ret["result"] = False
        ret["comment"].append(
            "Exactly one of either source, contents or "
            "contents_pillar must be provided."
        )
    elif contents_pillar:
        # Sneakily preload data from pillar into contents variable
        contents = __salt__["pillar.get"](contents_pillar, None)
        if contents is None:
            ret["result"] = False
            ret["comment"].append(
                "No data found in pillar for {}".format(contents_pillar)
            )
    if not ret["result"]:
        return ret

    # Check if nothing needs to be done
    if __salt__["file.file_exists"](name) and not force:
        ret["result"] = True
        ret["comment"].append("Target file already exists. Not forcing overwrite.")
        return ret

    salt.utils.dictupdate.set_dict_key_value(
        ret, "changes:old:{}".format(name), None,
    )
    salt.utils.dictupdate.set_dict_key_value(
        ret, "changes:new:{}".format(name), "signature" if detach else "signed data",
    )

    sign_kwargs = salt.utils.data.filter_falsey(
        {
            "keyid": keyid,
            "output": name,
            "gnupghome": gnupghome,
            "user": user,
            "passphrase": passphrase,
            "passphrase_pillar": passphrase_pillar,
            "detach": detach,
        }
    )

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"].append("Signature would have been created.")
    else:
        if source:
            cached_filename = __salt__["cp.cache_file"](source)
            if not cached_filename:
                ret["result"] = False
                ret["comment"].append("Failed to cache source locally.")
            else:
                sign_kwargs.update({"filename": cached_filename})
        else:
            sign_kwargs.update({"text": contents})

    if ret["result"]:
        try:
            res = __salt__["gpg.sign"](**sign_kwargs)
        except SaltInvocationError as exc:
            ret["result"] = False
            ret["comment"].append(str(exc))
        else:
            ret["result"] = res["result"]
            ret["comment"].append(res["message"])
        if source:
            # Cleanup cached file
            os.unlink(cached_filename)
    if ret["result"] is False:
        del ret["changes"]["old"]
        del ret["changes"]["new"]
    if ret["result"] and not isinstance(ret["result"], bool):
        raise CheckError("Internal error, result not properly specified.")
    return ret


def data_verified(
    name,
    contents=None,
    contents_pillar=None,
    user=None,
    filename=None,
    gnupghome=None,
    signature=None,
    trustmodel=None,
):
    """
    Ensures file with name ``name`` or data provided in ``contents`` or
    ``contents_pillar`` verifies its signature check.
    Use ``signature`` to desginate a detached signature file (only for verifying ``name``).
    Note: This state does not return changes, as no data is changed.

    :param str name: The file containing the data to verify. This file can be
        hosted on either the salt master server (``salt://``), the salt minion
        local file system (``/``) or on an HTTP or FTP server (``http(s)://`` or
        ``ftp://``) since this will call ``cp.cache_file`` to retrieve the file.
    :param str contents: The contents to be verified. Causes ``name`` to be ignored.
    :param str contents_pillar: The pillar key for which the contents are to be verified.
        Causes ``name`` to be ignored. Cannot be used together with ``contents``.
    :param str user: Used to determine the gnupghome location with the user's
        keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to ``/etc/salt/gpgkeys``.
    :param str gnupghome: Specify the location where GPG keyring and related files
        are stored. This overrides the gnupghome derived from specifying ``user``.
    :param str signature: Provide the signature itself as GPG armored text, or
        the URL filename of the signature.
    :param str trustmodel: Explicitly define the used trust model. One of:
          - pgp
          - classic
          - tofu
          - tofu+pgp
          - direct
          - always
          - auto
    """
    ret = {"name": name, "result": "changeme", "comment": [], "changes": {}}
    # Sanity-checking input
    if contents_pillar:
        # Sneakily preload data from pillar into contents variable
        contents = __salt__["pillar.get"](contents_pillar, None)
        if contents is None:
            ret["result"] = False
            ret["comment"].append(
                "No data found in pillar for {}".format(contents_pillar)
            )
    if not ret["result"]:
        return ret

    verify_kwargs = salt.utils.data.filter_falsey(
        {
            "gnupghome": gnupghome,
            "user": user,
            "signature": signature,
            "trustmodel": trustmodel,
        }
    )

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"].append(
            ("data" if contents else name) + "would have been verified."
        )
    else:
        if contents:
            verify_kwargs.update({"text": contents})
        else:
            cached_filename = __salt__["cp.cache_file"](name)
            if not cached_filename:
                ret["result"] = False
                ret["comment"].append("Failed to cache source locally.")
            else:
                verify_kwargs.update({"filename": cached_filename})

    if ret["result"]:
        try:
            res = __salt__["gpg.verify"](**verify_kwargs)
        except SaltInvocationError as exc:
            ret["result"] = False
            ret["comment"].append(str(exc))
        else:
            ret["result"] = res["result"]
            ret["comment"].append(res["message"])
        if not contents:
            # Cleanup cached file
            os.unlink(cached_filename)
    if ret["result"] and not isinstance(ret["result"], bool):
        raise CheckError("Internal error, result not properly specified.")
    return ret
