"""
Manage GPG keychains, add keys, create keys, retrieve keys from keyservers.
Sign, encrypt, sign plus encrypt and verify text and files.

.. versionadded:: 2015.5.0

.. note::

    The ``python-gnupg`` library and ``gpg`` binary are required to be
    installed.
    Be aware that the alternate ``gnupg`` and ``pretty-bad-protocol``
    libraries are not supported.

"""

import functools
import logging
import os
import re
import time

import salt.utils.data
import salt.utils.files
import salt.utils.immutabletypes as immutabletypes
import salt.utils.path
import salt.utils.stringutils
import salt.utils.versions
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "gpg"

LETTER_TRUST_DICT = immutabletypes.freeze(
    {
        "e": "Expired",
        "q": "Unknown",
        "n": "Not Trusted",
        "f": "Fully Trusted",
        "m": "Marginally Trusted",
        "u": "Ultimately Trusted",
        "r": "Revoked",
        "-": "Unknown",
    }
)

NUM_TRUST_DICT = immutabletypes.freeze(
    {
        "expired": "1",
        "unknown": "2",
        "not_trusted": "3",
        "marginally": "4",
        "fully": "5",
        "ultimately": "6",
    }
)

INV_NUM_TRUST_DICT = immutabletypes.freeze(
    {
        "1": "Expired",
        "2": "Unknown",
        "3": "Not Trusted",
        "4": "Marginally",
        "5": "Fully Trusted",
        "6": "Ultimately Trusted",
    }
)

VERIFY_TRUST_LEVELS = immutabletypes.freeze(
    {
        "0": "Undefined",
        "1": "Never",
        "2": "Marginal",
        "3": "Fully",
        "4": "Ultimate",
    }
)

TRUST_KEYS_TRUST_LEVELS = immutabletypes.freeze(
    {
        "expired": "TRUST_EXPIRED",
        "unknown": "TRUST_UNDEFINED",
        "never": "TRUST_NEVER",
        "marginally": "TRUST_MARGINAL",
        "fully": "TRUST_FULLY",
        "ultimately": "TRUST_ULTIMATE",
    }
)

_DEFAULT_KEY_SERVER = "keys.openpgp.org"

try:
    import gnupg

    HAS_GPG_BINDINGS = True
except ImportError:
    HAS_GPG_BINDINGS = False


def _gpg():
    """
    Returns the path to the gpg binary
    """
    # Get the path to the gpg binary.
    return salt.utils.path.which("gpg")


def __virtual__():
    """
    Makes sure that python-gnupg and gpg are available.
    """
    if not _gpg():
        return (
            False,
            "The gpg execution module cannot be loaded: gpg binary is not in the path.",
        )

    return (
        __virtualname__
        if HAS_GPG_BINDINGS
        else (
            False,
            "The gpg execution module cannot be loaded; the gnupg python module is not"
            " installed.",
        )
    )


def _get_user_info(user=None):
    """
    Wrapper for user.info Salt function
    """
    if not user:
        # Get user Salt running as
        user = __salt__["config.option"]("user")

    userinfo = __salt__["user.info"](user)

    if not userinfo:
        if user == "salt":
            # Special case with `salt` user:
            # if it doesn't exist then fall back to user Salt running as
            userinfo = _get_user_info()
        else:
            raise SaltInvocationError(f"User {user} does not exist")

    return userinfo


def _get_user_gnupghome(user):
    """
    Return default GnuPG home directory path for a user
    """
    if user == "salt":
        gnupghome = os.path.join(__salt__["config.get"]("config_dir"), "gpgkeys")
    else:
        gnupghome = os.path.join(_get_user_info(user)["home"], ".gnupg")

    return gnupghome


def _restore_ownership(func):
    @functools.wraps(func)
    def func_wrapper(*args, **kwargs):
        """
        Wrap gpg function calls to fix permissions
        """
        user = kwargs.get("user")
        gnupghome = kwargs.get("gnupghome") or _get_user_gnupghome(user)
        keyring = kwargs.get("keyring")

        userinfo = _get_user_info(user)
        run_user = _get_user_info()

        if userinfo["uid"] != run_user["uid"]:
            group = None
            if os.path.exists(gnupghome):
                # Given user is different from one who runs Salt process,
                # need to fix ownership permissions for GnuPG home dir
                group = __salt__["file.gid_to_group"](run_user["gid"])
                for path in [gnupghome] + __salt__["file.find"](gnupghome):
                    __salt__["file.chown"](path, run_user["name"], group)
            if keyring and os.path.exists(keyring):
                if group is None:
                    group = __salt__["file.gid_to_group"](run_user["gid"])
                __salt__["file.chown"](keyring, run_user["name"], group)

        # Filter special kwargs
        for key in list(kwargs):
            if key.startswith("__"):
                del kwargs[key]

        ret = func(*args, **kwargs)

        if userinfo["uid"] != run_user["uid"]:
            group = __salt__["file.gid_to_group"](userinfo["gid"])
            for path in [gnupghome] + __salt__["file.find"](gnupghome):
                __salt__["file.chown"](path, user, group)
            if keyring and os.path.exists(keyring):
                __salt__["file.chown"](keyring, user, group)
        return ret

    return func_wrapper


def _create_gpg(user=None, gnupghome=None, keyring=None):
    """
    Create the GPG object
    """
    if not gnupghome:
        gnupghome = _get_user_gnupghome(user)

    if keyring and not isinstance(keyring, str):
        raise SaltInvocationError(
            "Please pass keyring as a string. Multiple keyrings are not allowed"
        )

    gpg = gnupg.GPG(gnupghome=gnupghome, keyring=keyring)

    return gpg


def _list_keys(secret=False, user=None, gnupghome=None, keyring=None):
    """
    Helper function for listing keys
    """
    gpg = _create_gpg(user=user, gnupghome=gnupghome, keyring=keyring)
    _keys = gpg.list_keys(secret)
    return _keys


def _search_keys(text, keyserver, user=None, gnupghome=None):
    """
    Helper function for searching keys from keyserver
    """
    gpg = _create_gpg(user=user, gnupghome=gnupghome)
    if keyserver:
        _keys = gpg.search_keys(text, keyserver)
    else:
        _keys = gpg.search_keys(text)
    return _keys


def search_keys(text, keyserver=None, user=None, gnupghome=None):
    """
    Search for keys on a keyserver

    text
        Text to search the keyserver for, e.g. email address, keyID or fingerprint.

    keyserver
        Keyserver to use for searching for GPG keys, defaults to keys.openpgp.org.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.search_keys user@example.com

        salt '*' gpg.search_keys user@example.com keyserver=keyserver.ubuntu.com

        salt '*' gpg.search_keys user@example.com keyserver=keyserver.ubuntu.com user=username

    """
    if not keyserver:
        keyserver = _DEFAULT_KEY_SERVER

    _keys = []
    for _key in _search_keys(text, keyserver, user=user, gnupghome=gnupghome):
        tmp = {"keyid": _key["keyid"], "uids": _key["uids"]}

        expires = _key.get("expires", None)
        date = _key.get("date", None)
        length = _key.get("length", None)

        if expires:
            tmp["expires"] = time.strftime(
                "%Y-%m-%d", time.localtime(float(_key["expires"]))
            )
        if date:
            tmp["created"] = time.strftime(
                "%Y-%m-%d", time.localtime(float(_key["date"]))
            )
        if length:
            tmp["keyLength"] = _key["length"]
        _keys.append(tmp)
    return _keys


def list_keys(user=None, gnupghome=None, keyring=None):
    """
    List keys in GPG keychain

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.list_keys

    """
    _keys = []
    for _key in _list_keys(user=user, gnupghome=gnupghome, keyring=keyring):
        _keys.append(_render_key(_key))
    return _keys


def list_secret_keys(user=None, gnupghome=None, keyring=None):
    """
    List secret keys in GPG keychain

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.list_secret_keys

    """
    _keys = []
    for _key in _list_keys(
        user=user, gnupghome=gnupghome, keyring=keyring, secret=True
    ):
        _keys.append(_render_key(_key))
    return _keys


def _render_key(_key):
    tmp = {
        "keyid": _key["keyid"],
        "fingerprint": _key["fingerprint"],
        "uids": _key["uids"],
    }

    expires = _key.get("expires", None)
    date = _key.get("date", None)
    length = _key.get("length", None)
    owner_trust = _key.get("ownertrust", None)
    trust = _key.get("trust", None)

    if expires:
        tmp["expires"] = time.strftime(
            "%Y-%m-%d", time.localtime(float(_key["expires"]))
        )
    if date:
        tmp["created"] = time.strftime("%Y-%m-%d", time.localtime(float(_key["date"])))
    if length:
        tmp["keyLength"] = _key["length"]
    if owner_trust:
        tmp["ownerTrust"] = LETTER_TRUST_DICT[_key["ownertrust"]]
    if trust:
        tmp["trust"] = LETTER_TRUST_DICT[_key["trust"]]
    return tmp


@_restore_ownership
def create_key(
    key_type="RSA",
    key_length=1024,
    name_real="Autogenerated Key",
    name_comment="Generated by SaltStack",
    name_email=None,
    subkey_type=None,
    subkey_length=None,
    expire_date=None,
    use_passphrase=False,
    user=None,
    gnupghome=None,
    keyring=None,
):
    """
    Create a key in the GPG keychain

    .. note::

        GPG key generation requires *a lot* of entropy and randomness.
        Difficult to do over a remote connection, consider having
        another process available which is generating randomness for
        the machine. Also especially difficult on virtual machines,
        consider the `rng-tools
        <http://www.gnu.org/software/hurd/user/tlecarrour/rng-tools.html>`_
        package.

        The create_key process takes awhile so increasing the timeout
        may be necessary, e.g. -t 15.

    key_type
        The type of the primary key to generate. It must be capable of signing.
        'RSA' or 'DSA'.

    key_length
        The length of the primary key in bits.

    name_real
        The real name of the user identity which is represented by the key.

    name_comment
        A comment to attach to the user id.

    name_email
        An email address for the user.

    subkey_type
        The type of the secondary key to generate.

    subkey_length
        The length of the secondary key in bits.

    expire_date
        The expiration date for the primary and any secondary key.
        You can specify an ISO date, A number of days/weeks/months/years,
        an epoch value, or 0 for a non-expiring key.

    use_passphrase
        Whether to use a passphrase with the signing key. The passphrase is
        retrieved from the Pillar key ``gpg_passphrase``.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt -t 15 '*' gpg.create_key

    """
    ret = {"res": True, "fingerprint": "", "message": ""}

    create_params = {
        "key_type": key_type,
        "key_length": key_length,
        "name_real": name_real,
        "name_comment": name_comment,
    }

    gpg = _create_gpg(user=user, gnupghome=gnupghome, keyring=keyring)

    if name_email:
        create_params["name_email"] = name_email

    if subkey_type:
        create_params["subkey_type"] = subkey_type

    if subkey_length:
        create_params["subkey_length"] = subkey_length

    if expire_date:
        create_params["expire_date"] = expire_date

    if use_passphrase:
        gpg_passphrase = __salt__["pillar.get"]("gpg_passphrase")
        if not gpg_passphrase:
            ret["res"] = False
            ret["message"] = "gpg_passphrase not available in pillar."
            return ret
        else:
            create_params["passphrase"] = gpg_passphrase
    else:
        create_params["no_protection"] = True

    input_data = gpg.gen_key_input(**create_params)

    # This includes "%no-protection" in the input file for
    # passphraseless key generation in GnuPG >= 2.1 when the
    # python-gnupg library doesn't do that.
    if "No-Protection: True" in input_data:
        temp_data = input_data.splitlines()
        temp_data.remove("No-Protection: True")
        temp_data.insert(temp_data.index("%commit"), "%no-protection")
        input_data = "\n".join(temp_data) + "\n"

    key = gpg.gen_key(input_data)
    if key.fingerprint:
        ret["fingerprint"] = key.fingerprint
        ret["message"] = "GPG key pair successfully generated."
    else:
        ret["res"] = False
        ret["message"] = "Unable to generate GPG key pair."
    return ret


def delete_key(
    keyid=None,
    fingerprint=None,
    delete_secret=False,
    user=None,
    gnupghome=None,
    use_passphrase=True,
    keyring=None,
):
    """
    Delete a key from the GPG keychain.

    keyid
        The keyid of the key to be deleted.

    fingerprint
        The fingerprint of the key to be deleted.

    delete_secret
        Whether to delete a corresponding secret key prior to deleting the public key.
        Secret keys must be deleted before deleting any corresponding public keys.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    use_passphrase
        Whether to use a passphrase with the signing key. The passphrase is retrieved
        from the Pillar key ``gpg_passphrase``. Note that this defaults to True here,
        contrary to the rest of the module functions that provide this parameter.

        .. versionadded:: 3003

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.delete_key keyid=3FAD9F1E

        salt '*' gpg.delete_key fingerprint=53C96788253E58416D20BCD352952C84C3252192

        salt '*' gpg.delete_key keyid=3FAD9F1E user=username

        salt '*' gpg.delete_key keyid=3FAD9F1E user=username delete_secret=True

    """
    ret = {"res": True, "message": ""}

    if fingerprint and keyid:
        ret["res"] = False
        ret["message"] = "Only specify one argument, fingerprint or keyid"
        return ret

    if not fingerprint and not keyid:
        ret["res"] = False
        ret["message"] = "Required argument, fingerprint or keyid"
        return ret

    gpg = _create_gpg(user=user, gnupghome=gnupghome, keyring=keyring)
    key = get_key(
        keyid=keyid,
        fingerprint=fingerprint,
        user=user,
        gnupghome=gnupghome,
        keyring=keyring,
    )

    def __delete_key(fingerprint, secret, use_passphrase):
        if secret and use_passphrase:
            gpg_passphrase = __salt__["pillar.get"]("gpg_passphrase")
            if not gpg_passphrase:
                return "gpg_passphrase not available in pillar."
            else:
                out = gpg.delete_keys(fingerprint, secret, passphrase=gpg_passphrase)
        else:
            out = gpg.delete_keys(fingerprint, secret, expect_passphrase=False)
        return out

    if key:
        fingerprint = key["fingerprint"]
        skey = get_secret_key(
            keyid=keyid,
            fingerprint=fingerprint,
            user=user,
            gnupghome=gnupghome,
            keyring=keyring,
        )
        if skey:
            if not delete_secret:
                ret["res"] = False
                ret[
                    "message"
                ] = "Secret key exists, delete first or pass delete_secret=True."
                return ret
            else:
                out = __delete_key(fingerprint, True, use_passphrase)
                if str(out) == "ok":
                    # Delete the secret key
                    ret["message"] = f"Secret key for {fingerprint} deleted\n"
                else:
                    ret["res"] = False
                    ret[
                        "message"
                    ] = f"Failed to delete secret key for {fingerprint}: {out}"
                    return ret

        # Delete the public key
        out = __delete_key(fingerprint, False, use_passphrase)
        if str(out) == "ok":
            ret["res"] = True
            ret["message"] += f"Public key for {fingerprint} deleted"
        else:
            ret["res"] = False
            ret["message"] += f"Failed to delete public key for {fingerprint}: {out}"
    else:
        ret["res"] = False
        ret["message"] = "Key not available in keychain."
    return ret


def get_key(keyid=None, fingerprint=None, user=None, gnupghome=None, keyring=None):
    """
    Get a key from the GPG keychain

    keyid
        The key ID (short or long) of the key to be retrieved.

    fingerprint
        The fingerprint of the key to be retrieved.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.get_key keyid=3FAD9F1E

        salt '*' gpg.get_key fingerprint=53C96788253E58416D20BCD352952C84C3252192

        salt '*' gpg.get_key keyid=3FAD9F1E user=username

    """
    tmp = {}
    for _key in _list_keys(user=user, gnupghome=gnupghome, keyring=keyring):
        if (
            _key["fingerprint"] == fingerprint
            or _key["keyid"] == keyid
            or _key["keyid"][8:] == keyid
        ):
            tmp["keyid"] = _key["keyid"]
            tmp["fingerprint"] = _key["fingerprint"]
            tmp["uids"] = _key["uids"]

            expires = _key.get("expires", None)
            date = _key.get("date", None)
            length = _key.get("length", None)
            owner_trust = _key.get("ownertrust", None)
            trust = _key.get("trust", None)

            if expires:
                tmp["expires"] = time.strftime(
                    "%Y-%m-%d", time.localtime(float(_key["expires"]))
                )
            if date:
                tmp["created"] = time.strftime(
                    "%Y-%m-%d", time.localtime(float(_key["date"]))
                )
            if length:
                tmp["keyLength"] = _key["length"]
            if owner_trust:
                tmp["ownerTrust"] = LETTER_TRUST_DICT[_key["ownertrust"]]
            if trust:
                tmp["trust"] = LETTER_TRUST_DICT[_key["trust"]]
    if not tmp:
        return False
    else:
        return tmp


def get_secret_key(
    keyid=None, fingerprint=None, user=None, gnupghome=None, keyring=None
):
    """
    Get a secret key from the GPG keychain

    keyid
        The key ID (short or long) of the key to be retrieved.

    fingerprint
        The fingerprint of the key to be retrieved.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.get_secret_key keyid=3FAD9F1E

        salt '*' gpg.get_secret_key fingerprint=53C96788253E58416D20BCD352952C84C3252192

        salt '*' gpg.get_secret_key keyid=3FAD9F1E user=username

    """
    tmp = {}
    for _key in _list_keys(
        user=user, gnupghome=gnupghome, keyring=keyring, secret=True
    ):
        if (
            _key["fingerprint"] == fingerprint
            or _key["keyid"] == keyid
            or _key["keyid"][8:] == keyid
        ):
            tmp["keyid"] = _key["keyid"]
            tmp["fingerprint"] = _key["fingerprint"]
            tmp["uids"] = _key["uids"]

            expires = _key.get("expires", None)
            date = _key.get("date", None)
            length = _key.get("length", None)
            owner_trust = _key.get("ownertrust", None)
            trust = _key.get("trust", None)

            if expires:
                tmp["expires"] = time.strftime(
                    "%Y-%m-%d", time.localtime(float(_key["expires"]))
                )
            if date:
                tmp["created"] = time.strftime(
                    "%Y-%m-%d", time.localtime(float(_key["date"]))
                )
            if length:
                tmp["keyLength"] = _key["length"]
            if owner_trust:
                tmp["ownerTrust"] = LETTER_TRUST_DICT[_key["ownertrust"]]
            if trust:
                tmp["trust"] = LETTER_TRUST_DICT[_key["trust"]]
    if not tmp:
        return False
    else:
        return tmp


@_restore_ownership
def import_key(
    text=None, filename=None, user=None, gnupghome=None, keyring=None, select=None
):
    r"""
    Import a key from text or a file

    text
        The text containing the key to import.

    filename
        The path of the file containing the key to import.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    select
        Limit imported keys to a (list of) known identifier(s). This can be
        anything which GnuPG uses to identify keys like fingerprints, key IDs
        or email addresses.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.import_key text='-----BEGIN PGP PUBLIC KEY BLOCK-----\n ... -----END PGP PUBLIC KEY BLOCK-----'
        salt '*' gpg.import_key filename='/path/to/public-key-file'

    """

    def _import(gpg, path=None, data=None):
        if path:
            try:
                try:
                    imported_data = gpg.import_keys_file(path)
                except AttributeError:
                    # python-gnupg < 0.5.0
                    with salt.utils.files.flopen(filename, "rb") as _fp:
                        data = salt.utils.stringutils.to_unicode(_fp.read())
            except OSError:
                raise SaltInvocationError("filename does not exist.")
        if data:
            imported_data = gpg.import_keys(data)
        ret = {"res": True, "message": "", "fingerprints": imported_data.fingerprints}
        if imported_data.imported or imported_data.imported_rsa:
            ret["message"] = "Successfully imported key(s)."
        elif imported_data.unchanged:
            ret["message"] = "Key(s) already exist in keychain."
        elif imported_data.not_imported:
            ret["res"] = False
            ret["message"] = "Unable to import key."
        elif not imported_data.count:
            ret["res"] = False
            ret["message"] = "Unable to import key."
        return ret

    if not (text or filename):
        raise SaltInvocationError("filename or text must be passed.")
    if text and filename:
        raise SaltInvocationError("filename and text are mutually exclusive.")

    select = select or []
    if not isinstance(select, list):
        select = [select]

    if select:
        # GnuPG does not expose selective import behavior, so import everything
        # to a temporary keyring and then export only the wanted keys.
        tmpkeyring = __salt__["temp.file"]()
        tmpgpg = _create_gpg(user=user, gnupghome=gnupghome, keyring=tmpkeyring)
        res = _import(tmpgpg, path=filename, data=text)
        if not res["res"]:
            return res
        text = tmpgpg.export_keys(select)
        if not text:
            return {
                "res": True,
                "message": "After filtering, no keys to import were left.",
                "fingerprints": [],
            }
        filename = None

    gpg = _create_gpg(user=user, gnupghome=gnupghome, keyring=keyring)
    return _import(gpg, path=filename, data=text)


def export_key(
    keyids=None,
    secret=False,
    user=None,
    gnupghome=None,
    use_passphrase=False,
    output=None,
    bare=False,
    keyring=None,
):
    """
    Export a key from the GPG keychain

    keyids
        The key ID(s) of the key(s) to be exported. Can be specified as a comma
        separated string or a list. Anything which GnuPG itself accepts to identify a key
        for example, the key ID, fingerprint, user ID or email address could be used.

    secret
        Export the secret key identified by the ``keyids`` information passed.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    use_passphrase
        Whether to use a passphrase to export the secret key.
        The passphrase is retrieved from the Pillar key ``gpg_passphrase``.

        .. versionadded:: 3003

    output
        Instead of printing to standard out, write the output to this path.

        .. versionadded:: 3006.0

    bare
        If ``True``, return the (armored) exported key block as a string without the
        standard comment/res dict.

        .. versionadded:: 3006.0

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.export_key keyids=3FAD9F1E

        salt '*' gpg.export_key keyids=3FAD9F1E secret=True

        salt '*' gpg.export_key keyids="['3FAD9F1E','3FBD8F1E']" user=username

    """
    ret = {"res": True}
    gpg = _create_gpg(user=user, gnupghome=gnupghome, keyring=keyring)

    if isinstance(keyids, str):
        keyids = keyids.split(",")

    if secret and use_passphrase:
        gpg_passphrase = __salt__["pillar.get"]("gpg_passphrase")
        if not gpg_passphrase:
            raise SaltInvocationError("gpg_passphrase not available in pillar.")
        result = gpg.export_keys(keyids, secret, passphrase=gpg_passphrase)
    else:
        result = gpg.export_keys(keyids, secret, expect_passphrase=False)

    if result and output:
        with salt.utils.files.flopen(output, "w") as fout:
            fout.write(salt.utils.stringutils.to_str(result))

    if result:
        if not bare:
            if output:
                ret["comment"] = f"Exported key data has been written to {output}"
            else:
                ret["comment"] = result
        else:
            ret = result
    else:
        if not bare:
            ret["res"] = False
        else:
            ret = False

    return ret


def read_key(
    path=None, text=None, fingerprint=None, keyid=None, user=None, gnupghome=None
):
    """
    .. versionadded:: 3008.0

    Read key(s) from the filesystem or a string.

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.read_key /tmp/my-shiny-key.asc

    path
        The path to the key file to read. Either this or ``text`` is required.

    text
        The string to read the key from. Either this or ``path`` is required.

        .. note::
            Requires python-gnupg v0.5.1.

    fingerprint
        Only return key information if it matches this fingerprint.

    keyid
        Only return key information if it matches this keyid.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    .. important::
        This can accidentally decrypt data on GnuPG versions below 2.1
        if the file is not a keyring.
    """
    if not (path or text):
        raise SaltInvocationError("Either `path` or `text` is required.")
    if path and text:
        raise SaltInvocationError("`path` and `text` are mutually exclusive.")
    gpg = _create_gpg(user=user, gnupghome=gnupghome)
    if path:
        keys = gpg.scan_keys(path)
    else:
        keys = gpg.scan_keys_mem(text)

    rets = []
    for _key in keys:
        if (
            not (fingerprint or keyid)
            or _key["fingerprint"] == fingerprint
            or _key["keyid"] == keyid
            or _key["keyid"][8:] == keyid
        ):
            rets.append(_render_key(_key))
    return rets


@_restore_ownership
def receive_keys(keyserver=None, keys=None, user=None, gnupghome=None, keyring=None):
    """
    Receive key(s) from keyserver and add them to the keychain

    keyserver
        Keyserver to use for searching for GPG keys, defaults to keys.openpgp.org

    keys
        The keyID(s) to retrieve from the keyserver. Can be specified as a comma
        separated string or a list.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.receive_keys keys='3FAD9F1E'

        salt '*' gpg.receive_keys keys="['3FAD9F1E','3FBD9F2E']"

        salt '*' gpg.receive_keys keys=3FAD9F1E user=username

    """
    ret = {"res": True, "message": []}

    gpg = _create_gpg(user=user, gnupghome=gnupghome, keyring=keyring)

    if not keyserver:
        keyserver = _DEFAULT_KEY_SERVER

    if isinstance(keys, str):
        keys = keys.split(",")

    recv_data = gpg.recv_keys(keyserver, *keys)
    try:
        if recv_data.results:
            for result in recv_data.results:
                if "ok" in result:
                    if result["ok"] == "1":
                        ret["message"].append(
                            f"Key {result['fingerprint']} added to keychain"
                        )
                    elif result["ok"] == "0":
                        ret["message"].append(
                            f"Key {result['fingerprint']} already exists in keychain"
                        )
                elif "problem" in result:
                    ret["message"].append(
                        f"Unable to add key to keychain: {result.get('text', 'No further description')}"
                    )

        if not recv_data:
            ret["res"] = False
            ret["message"].append(f"GPG reported failure: {recv_data.stderr}")
    except AttributeError:
        ret["res"] = False
        ret["message"] = ["Invalid return from python-gpg"]

    return ret


def trust_key(
    keyid=None,
    fingerprint=None,
    trust_level=None,
    user=None,
    gnupghome=None,
    keyring=None,
):
    """
    Set the trust level for a key in the GPG keychain

    keyid
        The keyid of the key to set the trust level for.

    fingerprint
        The fingerprint of the key to set the trust level for.

    trust_level
        The trust level to set for the specified key, must be one
        of the following:
        expired, unknown, not_trusted, marginally, fully, ultimately

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

        .. versionadded:: 3007.0

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.trust_key keyid='3FAD9F1E' trust_level='marginally'
        salt '*' gpg.trust_key fingerprint='53C96788253E58416D20BCD352952C84C3252192' trust_level='not_trusted'
        salt '*' gpg.trust_key keys=3FAD9F1E trust_level='ultimately' user='username'

    """
    ret = {"res": True, "message": ""}

    if not salt.utils.data.exactly_one((keyid, fingerprint)):
        raise SaltInvocationError("Exactly one of keyid or fingerprint is required")

    if trust_level not in NUM_TRUST_DICT:
        raise SaltInvocationError(
            "ERROR: Valid trust levels - {}".format(",".join(NUM_TRUST_DICT.keys()))
        )

    key = get_key(
        keyid=keyid,
        fingerprint=fingerprint,
        user=user,
        gnupghome=gnupghome,
        keyring=keyring,
    )
    if not key:
        ret["res"] = False
        ret["message"] = f"Key {keyid or fingerprint} not in GPG keychain"
        return ret
    if not fingerprint and "fingerprint" not in key:
        ret["res"] = False
        ret["message"] = f"Fingerprint not found for keyID {keyid}"
        return ret
    fingerprint = fingerprint or key["fingerprint"]
    gpg = _create_gpg(user=user, gnupghome=gnupghome, keyring=keyring)

    try:
        res = gpg.trust_keys(fingerprint, TRUST_KEYS_TRUST_LEVELS[trust_level])
    except AttributeError:
        # python-gnupg < 0.4.2
        stdin = f"{fingerprint}:{NUM_TRUST_DICT[trust_level]}\n"
        gnupghome = gnupghome or _get_user_gnupghome(user)
        cmd = [_gpg(), "--homedir", gnupghome, "--import-ownertrust"]
        _user = user if user != "salt" else None

        if keyring:
            if not isinstance(keyring, str):
                raise SaltInvocationError(
                    "Please pass keyring as a string. Multiple keyrings are not allowed"
                )
            cmd.extend(["--no-default-keyring", "--keyring", keyring])

        res = __salt__["cmd.run_all"](cmd, stdin=stdin, runas=_user, python_shell=False)

        if not res["retcode"] == 0:
            ret["res"] = False
            ret["message"] = res["stderr"]
        else:
            if res["stderr"]:
                _match = re.findall(r"\d", res["stderr"])
                if len(_match) == 2:
                    ret["fingerprint"] = fingerprint
                    ret["message"] = "Changing ownership trust from {} to {}.".format(
                        INV_NUM_TRUST_DICT[_match[0]], INV_NUM_TRUST_DICT[_match[1]]
                    )
                else:
                    ret["fingerprint"] = fingerprint
                    ret["message"] = "Setting ownership trust to {}.".format(
                        INV_NUM_TRUST_DICT[_match[0]]
                    )
            else:
                ret["message"] = res["stderr"]
    else:
        if res.status == "ok":
            ret["res"] = True
            ret["fingerprint"] = fingerprint
            ret["message"] = "Setting ownership trust to {}.".format(
                INV_NUM_TRUST_DICT[NUM_TRUST_DICT[trust_level]]
            )
        else:
            ret["res"] = False
            ret["message"] = res.problem_reason

    return ret


def sign(
    user=None,
    keyid=None,
    text=None,
    filename=None,
    output=None,
    use_passphrase=False,
    gnupghome=None,
    keyring=None,
):
    """
    Sign a message or a file

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    keyid
        The keyid of the key to use for signing, defaults to the
        first key in the secret keyring.

    text
        The text to sign.

    filename
        The path of the file to sign.

    output
        Instead of printing to standard out, write the output to this path.

    use_passphrase
        Whether to use a passphrase with the signing key. The passphrase is
        retrieved from the Pillar key ``gpg_passphrase``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.sign text='Hello there.  How are you?'

        salt '*' gpg.sign filename='/path/to/important.file'

        salt '*' gpg.sign filename='/path/to/important.file' use_passphrase=True

    """
    if use_passphrase:
        gpg_passphrase = __salt__["pillar.get"]("gpg_passphrase")
        if not gpg_passphrase:
            raise SaltInvocationError("gpg_passphrase not available in pillar.")
    else:
        gpg_passphrase = None

    gpg = _create_gpg(user=user, gnupghome=gnupghome, keyring=keyring)

    if text:
        signed_data = gpg.sign(text, keyid=keyid, passphrase=gpg_passphrase)
    elif filename:
        with salt.utils.files.flopen(filename, "rb") as _fp:
            signed_data = gpg.sign_file(_fp, keyid=keyid, passphrase=gpg_passphrase)
        if output:
            with salt.utils.files.flopen(output, "wb") as fout:
                fout.write(salt.utils.stringutils.to_bytes(signed_data.data))
    else:
        raise SaltInvocationError("filename or text must be passed.")

    return signed_data.data


def verify(
    text=None,
    user=None,
    filename=None,
    gnupghome=None,
    signature=None,
    trustmodel=None,
    signed_by_any=None,
    signed_by_all=None,
    keyring=None,
):
    """
    Verify a message or a file

    text
        The text to verify.

    filename
        The path of the file to verify.

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    signature
        Specify the path of a detached signature.

        .. versionadded:: 2018.3.0

    trustmodel
        Explicitly define the used trust model. One of:
          - pgp
          - classic
          - tofu
          - tofu+pgp
          - direct
          - always
          - auto

        .. versionadded:: 2019.2.0

    signed_by_any
        A list of key fingerprints from which any valid signature
        will mark verification as passed. If none of the provided
        keys signed the data, verification will fail. Optional.
        Note that this does not take into account trust.

        .. versionadded:: 3007.0

    signed_by_all
        A list of key fingerprints whose signatures are required
        for verification to pass. If a single provided key did
        not sign the data, verification will fail. Optional.
        Note that this does not take into account trust.

        .. versionadded:: 3007.0

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.verify text='Hello there.  How are you?'
        salt '*' gpg.verify filename='/path/to/important.file'
        salt '*' gpg.verify filename='/path/to/important.file' trustmodel=direct

    """
    trustmodels = ("pgp", "classic", "tofu", "tofu+pgp", "direct", "always", "auto")

    if trustmodel and trustmodel not in trustmodels:
        msg = "Invalid trustmodel defined: {}. Use one of: {}".format(
            trustmodel, ", ".join(trustmodels)
        )
        log.warning(msg)
        return {"res": False, "message": msg}

    gpg = _create_gpg(user=user, gnupghome=gnupghome, keyring=keyring)
    extra_args = []

    if trustmodel:
        extra_args.extend(["--trust-model", trustmodel])

    if signed_by_any or signed_by_all:
        # batch mode stops processing on the first invalid signature.
        # This ensures all signatures are evaluated for validity.
        extra_args.append("--no-batch")
        # workaround https://github.com/vsajip/python-gnupg/issues/214
        # This issue should be fixed in versions greater than 0.5.0.
        if salt.utils.versions.version_cmp(gnupg.__version__, "0.5.0") <= 0:
            gpg.result_map["verify"] = FixedVerify

    if text:
        verified = gpg.verify(text, extra_args=extra_args)
    elif filename:
        if signature:
            # need to call with fopen instead of flopen due to:
            # https://bitbucket.org/vinay.sajip/python-gnupg/issues/76/verify_file-closes-passed-file-handle
            with salt.utils.files.fopen(signature, "rb") as _fp:
                verified = gpg.verify_file(_fp, filename, extra_args=extra_args)
        else:
            with salt.utils.files.flopen(filename, "rb") as _fp:
                verified = gpg.verify_file(_fp, extra_args=extra_args)
    else:
        raise SaltInvocationError("filename or text must be passed.")

    if not (signed_by_any or signed_by_all):
        ret = {}
        if verified.trust_level is not None:
            ret["res"] = True
            ret["username"] = verified.username
            ret["key_id"] = verified.key_id
            ret["trust_level"] = VERIFY_TRUST_LEVELS[str(verified.trust_level)]
            ret["message"] = "The signature is verified."
        else:
            ret["res"] = False
            ret["message"] = "The signature could not be verified."

        return ret

    signatures = [
        {
            "username": sig.get("username"),
            "key_id": sig["keyid"],
            "fingerprint": sig["pubkey_fingerprint"],
            "trust_level": VERIFY_TRUST_LEVELS[str(sig["trust_level"])]
            if "trust_level" in sig
            else None,
            "status": sig["status"],
        }
        for sig in verified.sig_info.values()
    ]
    ret = {"res": False, "message": "", "signatures": signatures}

    # be very explicit and do not default to result = True below
    any_check = all_check = False

    if signed_by_any:
        if not isinstance(signed_by_any, list):
            signed_by_any = [signed_by_any]
        any_signed = False
        for signer in signed_by_any:
            signer = str(signer)
            try:
                if any(
                    x["trust_level"] is not None and str(x["fingerprint"]) == signer
                    for x in signatures
                ):
                    any_signed = True
                    break
            except (KeyError, IndexError):
                pass

        if not any_signed:
            ret["res"] = False
            ret[
                "message"
            ] = "None of the public keys listed in signed_by_any provided a valid signature"
            return ret
        any_check = True

    if signed_by_all:
        if not isinstance(signed_by_all, list):
            signed_by_all = [signed_by_all]
        for signer in signed_by_all:
            signer = str(signer)
            try:
                if any(
                    x["trust_level"] is not None and str(x["fingerprint"]) == signer
                    for x in signatures
                ):
                    continue
            except (KeyError, IndexError):
                pass
            ret["res"] = False
            ret[
                "message"
            ] = f"Public key {signer} has not provided a valid signature, but was listed in signed_by_all"
            return ret
        all_check = True

    if bool(signed_by_any) is any_check and bool(signed_by_all) is all_check:
        ret["res"] = True
        ret["message"] = "All required keys have provided a signature"
        return ret

    ret["res"] = False
    ret[
        "message"
    ] = "Something went wrong while checking for specific signers. This is most likely a bug"
    return ret


def encrypt(
    user=None,
    recipients=None,
    text=None,
    filename=None,
    output=None,
    sign=None,
    use_passphrase=False,
    always_trust=False,
    gnupghome=None,
    bare=False,
    keyring=None,
):
    """
    Encrypt a message or a file

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    recipients
        The key ID, fingerprint, user ID or email address associated with the recipients
        key can be used.

    text
        The text to encrypt.

    filename
        The path of the file to encrypt.

    output
        Instead of printing to standard out, write the output to this path.

    sign
        Whether to sign, in addition to encrypt, the data. ``True`` to use
        default key or fingerprint to specify a different key to sign with.

    use_passphrase
        Whether to use a passphrase with the signing key.
        The passphrase is retrieved from the Pillar key ``gpg_passphrase``.

    always_trust
        Skip key validation and assume that used keys are fully trusted.

        .. versionadded:: 3006.0

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    bare
        If ``True``, return the (armored) encrypted block as a string without
        the standard comment/res dict.

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.encrypt text='Hello there.  How are you?' recipients=recipient@example.com

        salt '*' gpg.encrypt filename='/path/to/important.file' recipients=recipient@example.com

        salt '*' gpg.encrypt filename='/path/to/important.file' sign=True use_passphrase=True \\
                             recipients=recipient@example.com

    """
    ret = {"res": True, "comment": ""}
    if sign and use_passphrase:
        gpg_passphrase = __salt__["pillar.get"]("gpg_passphrase")
        if not gpg_passphrase:
            raise SaltInvocationError("gpg_passphrase not available in pillar.")
    else:
        gpg_passphrase = None

    gpg = _create_gpg(user=user, gnupghome=gnupghome, keyring=keyring)

    if text:
        result = gpg.encrypt(
            text,
            recipients,
            sign=sign,
            passphrase=gpg_passphrase,
            always_trust=always_trust,
            output=output,
        )
    elif filename:
        with salt.utils.files.flopen(filename, "rb") as _fp:
            result = gpg.encrypt_file(
                _fp,
                recipients,
                sign=sign,
                passphrase=gpg_passphrase,
                always_trust=always_trust,
                output=output,
            )
    else:
        raise SaltInvocationError("filename or text must be passed.")

    if result.ok:
        if not bare:
            if output:
                ret["comment"] = f"Encrypted data has been written to {output}"
            else:
                ret["comment"] = result.data
        else:
            ret = result.data
    else:
        if not bare:
            ret["res"] = False
            ret["comment"] = f"{result.status}.\nPlease check the salt-minion log."
        else:
            ret = False

        log.error(result.stderr)

    return ret


def decrypt(
    user=None,
    text=None,
    filename=None,
    output=None,
    use_passphrase=False,
    gnupghome=None,
    bare=False,
    keyring=None,
):
    """
    Decrypt a message or a file

    user
        Which user's keychain to access, defaults to user Salt is running as.
        Passing the user as ``salt`` will set the GnuPG home directory to
        ``/etc/salt/gpgkeys``.

    text
        The encrypted text to decrypt.

    filename
        The path of the encrypted file to decrypt.

    output
        Instead of printing to standard out, write the output to this path.

    use_passphrase
        Whether to use a passphrase with the signing key. The passphrase is retrieved
        from Pillar value ``gpg_passphrase``.

    gnupghome
        Specify the location where the GPG keyring and related files are stored.

    bare
        If ``True``, return the (armored) decrypted block as a string without the
        standard comment/res dict.

    keyring
        Limit the operation to this specific keyring, specified as
        a local filesystem path.

        .. versionadded:: 3007.0

    CLI Example:

    .. code-block:: bash

        salt '*' gpg.decrypt filename='/path/to/important.file.gpg'

        salt '*' gpg.decrypt filename='/path/to/important.file.gpg' use_passphrase=True

    """
    ret = {"res": True, "comment": ""}
    if use_passphrase:
        gpg_passphrase = __salt__["pillar.get"]("gpg_passphrase")
        if not gpg_passphrase:
            raise SaltInvocationError("gpg_passphrase not available in pillar.")
    else:
        gpg_passphrase = None

    gpg = _create_gpg(user=user, gnupghome=gnupghome, keyring=keyring)

    if text:
        result = gpg.decrypt(text, passphrase=gpg_passphrase)
    elif filename:
        with salt.utils.files.flopen(filename, "rb") as _fp:
            if output:
                result = gpg.decrypt_file(_fp, passphrase=gpg_passphrase, output=output)
            else:
                result = gpg.decrypt_file(_fp, passphrase=gpg_passphrase)
    else:
        raise SaltInvocationError("filename or text must be passed.")

    if result.ok:
        if not bare:
            if output:
                ret["comment"] = f"Decrypted data has been written to {output}"
            else:
                ret["comment"] = result.data
        else:
            ret = result.data
    else:
        if not bare:
            ret["res"] = False
            ret["comment"] = f"{result.status}.\nPlease check the salt-minion log."
        else:
            ret = False

        log.error(result.stderr)

    return ret


if HAS_GPG_BINDINGS:

    class FixedVerify(gnupg.Verify):
        """
        This is a workaround for https://github.com/vsajip/python-gnupg/issues/214.
        It ensures invalid or otherwise unverified signatures are not
        merged into sig_info in any way.

        https://github.com/vsajip/python-gnupg/commit/ee94a7ecc1a86484c9f02337e2bbdd05fd32b383
        """

        def handle_status(self, key, value):
            if "NEWSIG" == key:
                self.signature_id = None
            super().handle_status(key, value)
            if key in self.TRUST_LEVELS:
                self.signature_id = None
