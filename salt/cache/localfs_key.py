"""
Backward compatible shim layer for pki interaction

.. versionadded:: 3008.0

The ``localfs_key`` is a shim driver meant to allow the salt.cache
subsystem to interact with the existing master pki folder/file structure
without any migration from previous versions of salt.  It is not meant for
general purpose use and should not be used outside of the master auth system.

The main difference from before is the 'state' of the key, ie accepted/rejected
is now stored in the data itself, as opposed to the cache equivalent of a bank
previously.

store and fetch handle ETL from new style, where data itself contains key
state, to old style, where folder and/or bank contain state.
flush/list/contains/updated are left as nearly equivalent to localfs, without
the .p file extension to work with legacy keys via banks.
"""

import errno
import logging
import os
import os.path

try:
    import pwd
except ImportError:
    pwd = None
import shutil
import stat
import tempfile
from pathlib import Path

import salt.utils.atomicfile
import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import SaltCacheError
from salt.utils.verify import clean_path, valid_id

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list"}


BASE_MAPPING = {
    "minions_pre": "pending",
    "minions_rejected": "rejected",
    "minions": "accepted",
    "minions_denied": "denied",
}

# master_keys keys that if fetched, even with cluster_id set, will still refer
# to pki_dir instead of cluster_pki_dir
NON_CLUSTERED_MASTER_KEYS = []


# we explicitly override cache dir to point to pki here
def init_kwargs(kwargs):
    """
    setup kwargs for cache functions
    """
    if __opts__["__role"] != "minion":
        global NON_CLUSTERED_MASTER_KEYS
        NON_CLUSTERED_MASTER_KEYS = [
            "master.pem",
            "master.pub",
            f"{__opts__['master_sign_key_name']}.pem",
            f"{__opts__['master_sign_key_name']}.pub",
            f"{__opts__['id'].removesuffix('_master')}.pub",
            f"{__opts__['id'].removesuffix('_master')}.pem",
            __opts__.get(
                "master_pubkey_signature", f"{__opts__['id']}_pubkey_signature"
            ),
        ]

    if "pki_dir" in kwargs:
        pki_dir = kwargs["pki_dir"]
    elif __opts__.get("cluster_id"):
        pki_dir = __opts__["cluster_pki_dir"]
    else:
        pki_dir = __opts__["pki_dir"]

    user = kwargs.get("user", __opts__.get("user"))

    return {"cachedir": pki_dir, "user": user}


def store(bank, key, data, cachedir, user, **kwargs):
    """
    Store key state information. storing a accepted/pending/rejected state
    means clearing it from the other 2. denied is handled separately
    """
    base = None
    if bank in ["keys", "denied_keys"] and not valid_id(__opts__, key):
        raise SaltCacheError(f"key {key} is not a valid minion_id")

    if bank not in ["keys", "denied_keys", "master_keys"]:
        raise SaltCacheError(f"Unrecognized bank: {bank}")

    if __opts__["permissive_pki_access"]:
        umask = 0o0700
    else:
        umask = 0o0750

    if bank == "keys":
        if data["state"] == "rejected":
            base = "minions_rejected"
        elif data["state"] == "pending":
            base = "minions_pre"
        elif data["state"] == "accepted":
            base = "minions"
        else:
            raise SaltCacheError("Unrecognized data/bank: {}".format(data["state"]))
        data = data["pub"]
    elif bank == "denied_keys":
        # denied keys is a list post migration, but is a single key in legacy
        data = data[0]
        base = "minions_denied"
    elif bank == "master_keys":
        # private keys are separate from permissive_pki_access
        umask = 0o277
        base = ""
        # even in clustered mode, master and signing keys live in the
        # non-clustered pki dir
        if key in NON_CLUSTERED_MASTER_KEYS:
            cachedir = __opts__["pki_dir"]

    savefn = Path(cachedir) / base / key
    base_dir = savefn.parent

    if not clean_path(cachedir, str(savefn), subdir=True):
        raise SaltCacheError(f"key {key} is not a valid key path.")

    try:
        os.makedirs(base_dir)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise SaltCacheError(
                f"The cache directory, {base_dir}, could not be created: {exc}"
            )

    # delete current state before re-serializing new state
    flush(bank, key, cachedir, **kwargs)

    tmpfh, tmpfname = tempfile.mkstemp(dir=base_dir)
    os.close(tmpfh)

    if user and not salt.utils.platform.is_windows():
        try:
            uid = pwd.getpwnam(user).pw_uid
            os.chown(tmpfname, uid, -1)
        except (KeyError, ImportError, OSError, NameError):
            # The specified user was not found, allow the backup systems to
            # report the error
            pass

    try:
        with salt.utils.files.set_umask(umask):
            with salt.utils.files.fopen(tmpfname, "w+b") as fh_:
                fh_.write(salt.utils.stringutils.to_bytes(data))

            if bank == "master_keys":
                os.chmod(tmpfname, 0o400)

        # On Windows, os.rename will fail if the destination file exists.
        salt.utils.atomicfile.atomic_rename(tmpfname, savefn)
    except OSError as exc:
        raise SaltCacheError(
            f"There was an error writing the cache file, base={base}: {exc}"
        )


def fetch(bank, key, cachedir, **kwargs):
    """
    Fetch and construct state data for a given minion based on the bank and id
    """
    if bank in ["keys", "denied_keys"] and not valid_id(__opts__, key):
        raise SaltCacheError(f"key {key} is not a valid minion_id")

    if bank not in ["keys", "denied_keys", "master_keys"]:
        raise SaltCacheError(f"Unrecognized bank: {bank}")

    if not clean_path(cachedir, key, subdir=True):
        raise SaltCacheError(f"key {key} is not a valid key path.")

    if key == ".key_cache":
        raise SaltCacheError("trying to read key_cache, there is a bug at call-site")
    try:
        if bank == "keys":
            for state, bank in [
                ("rejected", "minions_rejected"),
                ("pending", "minions_pre"),
                ("accepted", "minions"),
            ]:
                keyfile = Path(cachedir, bank, key)

                if not clean_path(cachedir, str(keyfile), subdir=True):
                    raise SaltCacheError(f"key {key} is not a valid key path.")

                if keyfile.is_file() and not keyfile.is_symlink():
                    with salt.utils.files.fopen(keyfile, "r") as fh_:
                        return {"state": state, "pub": fh_.read()}
            return None
        elif bank == "denied_keys":
            # there can be many denied keys per minion post refactor, but only 1
            # with the filesystem, so return a list of 1
            pubfn_denied = os.path.join(cachedir, "minions_denied", key)

            if not clean_path(cachedir, pubfn_denied, subdir=True):
                raise SaltCacheError(f"key {key} is not a valid key path.")

            if os.path.isfile(pubfn_denied):
                with salt.utils.files.fopen(pubfn_denied, "r") as fh_:
                    return [fh_.read()]
        elif bank == "master_keys":
            if key in NON_CLUSTERED_MASTER_KEYS:
                cachedir = __opts__["pki_dir"]

            keyfile = Path(cachedir, key)

            if not clean_path(cachedir, str(keyfile), subdir=True):
                raise SaltCacheError(f"key {key} is not a valid key path.")

            if keyfile.is_file() and not keyfile.is_symlink():
                with salt.utils.files.fopen(keyfile, "r") as fh_:
                    return fh_.read()
        else:
            raise SaltCacheError(f'unrecognized bank "{bank}"')
    except OSError as exc:
        raise SaltCacheError(
            'There was an error reading the cache bank "{}", key "{}": {}'.format(
                bank, key, exc
            )
        )


def updated(bank, key, cachedir, **kwargs):
    """
    Return the epoch of the mtime for this cache file
    """
    if not valid_id(__opts__, key):
        raise SaltCacheError(f"key {key} is not a valid minion_id")

    if bank == "keys":
        bases = [base for base in BASE_MAPPING if base != "minions_denied"]
    elif bank == "denied_keys":
        bases = ["minions_denied"]
    elif bank == "master_keys":
        if key in NON_CLUSTERED_MASTER_KEYS:
            cachedir = __opts__["pki_dir"]
        bases = [""]
    else:
        raise SaltCacheError(f"Unrecognized bank: {bank}")

    for dir in bases:
        keyfile = Path(cachedir, dir, key)

        if not clean_path(cachedir, str(keyfile), subdir=True):
            raise SaltCacheError(f"key {key} is not a valid key path.")

        if keyfile.is_file() and not keyfile.is_symlink():
            try:
                return int(os.path.getmtime(keyfile))
            except OSError as exc:
                raise SaltCacheError(
                    'There was an error reading the mtime for "{}": {}'.format(
                        keyfile, exc
                    )
                )
    log.debug('pki file "%s" does not exist in accepted/rejected/pending', key)
    return


def flush(bank, key=None, cachedir=None, **kwargs):
    """
    Remove the key from the cache bank with all the key content.
    flush can take a legacy bank or a keys/denied_keys modern bank
    """
    if bank in ["keys", "denied_keys"] and not valid_id(__opts__, key):
        raise SaltCacheError(f"key {key} is not a valid minion_id")

    if cachedir is None:
        raise SaltCacheError("cachedir missing")

    if bank == "keys":
        bases = [base for base in BASE_MAPPING if base != "minions_denied"]
    elif bank == "denied_keys":
        bases = ["minions_denied"]
    elif bank == "master_keys":
        if key in NON_CLUSTERED_MASTER_KEYS:
            cachedir = __opts__["pki_dir"]
        bases = [""]
    else:
        raise SaltCacheError(f"Unrecognized bank: {bank}")

    flushed = False

    for base in bases:
        try:
            if key is None:
                target = os.path.join(cachedir, base)
                if not os.path.isdir(target):
                    return False
                shutil.rmtree(target)
            else:
                target = os.path.join(cachedir, base, key)

                if not clean_path(cachedir, target, subdir=True):
                    raise SaltCacheError(f"key {key} is not a valid key path.")

                if not os.path.isfile(target):
                    continue

                # necessary on windows, otherwise PermissionError: [WinError 5] Access is denied
                os.chmod(target, stat.S_IWRITE)

                os.remove(target)
                flushed = True
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise SaltCacheError(f'There was an error removing "{target}": {exc}')

    return flushed


def list_(bank, cachedir, **kwargs):
    """
    Return an iterable object containing all entries stored in the specified bank.
    Uses internal mmap index for O(1) performance when available.
    """
    if bank == "keys":
        bases = [base for base in BASE_MAPPING if base != "minions_denied"]
    elif bank == "denied_keys":
        bases = ["minions_denied"]
    elif bank == "master_keys":
        bases = [""]
    else:
        raise SaltCacheError(f"Unrecognized bank: {bank}")

    ret = []
    for base in bases:
        base = os.path.join(cachedir, os.path.normpath(base))
        if not os.path.isdir(base):
            continue
        try:
            items = os.listdir(base)
        except OSError as exc:
            raise SaltCacheError(
                f'There was an error accessing directory "{base}": {exc}'
            )
        for item in items:
            # salt foolishly dumps a file here for key cache, ignore it
            if item == ".key_cache":
                continue

            keyfile = Path(cachedir, base, item)

            if (
                bank in ["keys", "denied_keys"] and not valid_id(__opts__, item)
            ) or not clean_path(cachedir, str(keyfile), subdir=True):
                log.error("saw invalid id %s, discarding", item)
                continue

            if keyfile.is_file() and not keyfile.is_symlink():
                ret.append(item)
    return ret


def list_all(bank, cachedir, include_data=False, **kwargs):
    """
    Return all entries with their data from the specified bank.
    This is much faster than calling list() + fetch() for each item.
    Returns a dict of {key: data}.

    If include_data is False (default), only the state is returned for 'keys' bank,
    avoiding expensive file reads.
    """
    if bank not in ["keys", "denied_keys"]:
        raise SaltCacheError(f"Unrecognized bank: {bank}")

    ret = {}

    if bank == "keys":
        # Map directory names to states
        state_mapping = {
            "minions": "accepted",
            "minions_pre": "pending",
            "minions_rejected": "rejected",
        }

        for dir_name, state in state_mapping.items():
            dir_path = os.path.join(cachedir, dir_name)
            if not os.path.isdir(dir_path):
                continue

            try:
                with os.scandir(dir_path) as it:
                    for entry in it:
                        if not entry.is_file() or entry.is_symlink():
                            continue
                        if entry.name.startswith("."):
                            continue
                        if not valid_id(__opts__, entry.name):
                            continue
                        if not clean_path(cachedir, entry.path, subdir=True):
                            continue

                        if include_data:

                            # Read the public key
                            try:
                                with salt.utils.files.fopen(entry.path, "r") as fh_:
                                    pub_key = fh_.read()
                                ret[entry.name] = {"state": state, "pub": pub_key}
                            except OSError as exc:
                                log.error(
                                    "Error reading key file %s: %s", entry.path, exc
                                )
                        else:
                            # Just return the state, no disk read
                            ret[entry.name] = {"state": state}
            except OSError as exc:
                log.error("Error scanning directory %s: %s", dir_path, exc)

    elif bank == "denied_keys":
        # Denied keys work differently - multiple keys per minion ID
        dir_path = os.path.join(cachedir, "minions_denied")
        if os.path.isdir(dir_path):
            try:
                with os.scandir(dir_path) as it:
                    for entry in it:
                        if not entry.is_file() or entry.is_symlink():
                            continue
                        if not valid_id(__opts__, entry.name):
                            continue
                        if not clean_path(cachedir, entry.path, subdir=True):
                            continue

                        try:
                            with salt.utils.files.fopen(entry.path, "r") as fh_:
                                ret[entry.name] = fh_.read()
                        except OSError as exc:
                            log.error(
                                "Error reading denied key %s: %s", entry.path, exc
                            )
            except OSError as exc:
                log.error("Error scanning denied keys directory: %s", exc)

    return ret


def contains(bank, key, cachedir, **kwargs):
    """
    Checks if the specified bank contains the specified key.
    Uses internal mmap index for O(1) performance when available.
    """
    if bank in ["keys", "denied_keys"] and not valid_id(__opts__, key):
        raise SaltCacheError(f"key {key} is not a valid minion_id")

    if bank == "keys":
        bases = [base for base in BASE_MAPPING if base != "minions_denied"]
    elif bank == "denied_keys":
        bases = ["minions_denied"]
    elif bank == "master_keys":
        if key in NON_CLUSTERED_MASTER_KEYS:
            cachedir = __opts__["pki_dir"]
        bases = [""]
    else:
        raise SaltCacheError(f"Unrecognized bank: {bank}")

    for base in bases:
        keyfile = Path(cachedir, base, key)

        if not clean_path(cachedir, str(keyfile), subdir=True):
            raise SaltCacheError(f"key {key} is not a valid key path.")

        if keyfile.is_file() and not keyfile.is_symlink():
            return True

    return False
