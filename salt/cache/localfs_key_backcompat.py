"""
Backward compatible shim layer for pki interaction

.. versionadded:: 3008.0

The ``localfs_keys_backcompat`` is a shim driver meant to allow the salt.cache
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
import shutil
import tempfile

import salt.utils.atomicfile
import salt.utils.files
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


# we explicitly override cache dir to point to pki here
def init_kwargs(kwargs):
    """
    setup kwargs for cache functions
    """
    if __opts__.get("cluster_id"):
        pki_dir = __opts__["cluster_pki_dir"]
    else:
        pki_dir = __opts__["pki_dir"]

    return {"cachedir": pki_dir, "user": kwargs.get("user")}


def store(bank, key, data, cachedir, user, **kwargs):
    """
    Store key state information. storing a accepted/pending/rejected state
    means clearing it from the other 2. denied is handled separately
    """
    if bank in ["keys", "denied_keys"] and not valid_id(__opts__, key):
        raise SaltCacheError(f"key {key} is not a valid minion_id")

    if bank not in ["keys", "denied_keys"]:
        raise SaltCacheError(f"Unrecognized bank: {bank}")

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

    base = os.path.join(cachedir, base)
    savefn = os.path.join(base, key)

    if not clean_path(cachedir, savefn, subdir=True):
        raise SaltCacheError(f"key {key} is not a valid key path.")

    try:
        os.makedirs(base)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise SaltCacheError(
                f"The cache directory, {base}, could not be created: {exc}"
            )

    # delete current state before re-serializing new state
    flush(bank, key, cachedir, **kwargs)

    if __opts__["permissive_pki_access"]:
        umask = 0o0700
    else:
        umask = 0o0750

    tmpfh, tmpfname = tempfile.mkstemp(dir=base)
    os.close(tmpfh)

    if user:
        try:
            import pwd

            uid = pwd.getpwnam(user).pw_uid
            os.chown(tmpfname, uid, -1)
        except (KeyError, ImportError, OSError):
            # The specified user was not found, allow the backup systems to
            # report the error
            pass

    try:
        with salt.utils.files.set_umask(umask):
            with salt.utils.files.fopen(tmpfname, "w+b") as fh_:
                fh_.write(data.encode("utf-8"))
        # On Windows, os.rename will fail if the destination file exists.
        salt.utils.atomicfile.atomic_rename(tmpfname, savefn)
    except OSError as exc:
        raise SaltCacheError(
            f"There was an error writing the cache file, {base}: {exc}"
        )


def fetch(bank, key, cachedir, **kwargs):
    """
    Fetch and construct state data for a given minion based on the bank and id
    """
    if bank in ["keys", "denied_keys"] and not valid_id(__opts__, key):
        raise SaltCacheError(f"key {key} is not a valid minion_id")

    if bank not in ["keys", "denied_keys"]:
        raise SaltCacheError(f"Unrecognized bank: {bank}")

    if key == ".key_cache":
        raise SaltCacheError("trying to read key_cache, there is a bug at call-site")
    try:
        if bank == "keys":
            for state, bank in [
                ("rejected", "minions_rejected"),
                ("pending", "minions_pre"),
                ("accepted", "minions"),
            ]:
                pubfn = os.path.join(cachedir, bank, key)
                if os.path.isfile(pubfn):
                    with salt.utils.files.fopen(pubfn, "r") as fh_:
                        return {"state": state, "pub": fh_.read()}
            return None
        elif bank == "denied_keys":
            # there can be many denied keys per minion post refactor, but only 1
            # with the filesystem, so return a list of 1
            pubfn_denied = os.path.join(cachedir, "minions_denied", key)

            if os.path.isfile(pubfn_denied):
                with salt.utils.files.fopen(pubfn_denied, "r") as fh_:
                    return [fh_.read()]
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
    else:
        raise SaltCacheError(f"Unrecognized bank: {bank}")

    for dir in bases:
        key_file = os.path.join(cachedir, dir, key)

        if not clean_path(cachedir, key_file, subdir=True):
            raise SaltCacheError(f"key {key} is not a valid key path.")

        if os.path.isfile(key_file):
            try:
                return int(os.path.getmtime(key_file))
            except OSError as exc:
                raise SaltCacheError(
                    'There was an error reading the mtime for "{}": {}'.format(
                        key_file, exc
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
                os.remove(target)
                flushed = True
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise SaltCacheError(f'There was an error removing "{target}": {exc}')
    return flushed


def list_(bank, cachedir, **kwargs):
    """
    Return an iterable object containing all entries stored in the specified bank.
    """
    if bank == "keys":
        bases = [base for base in BASE_MAPPING if base != "minions_denied"]
    elif bank == "denied_keys":
        bases = ["minions_denied"]
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
            if bank in ["keys", "denied_keys"] and not valid_id(__opts__, item):
                log.error("saw invalid id %s, discarding", item)
            else:
                ret.append(item)
    return ret


def contains(bank, key, cachedir, **kwargs):
    """
    Checks if the specified bank contains the specified key.
    """
    if not valid_id(__opts__, key):
        raise SaltCacheError(f"key {key} is not a valid minion_id")

    if bank == "keys":
        bases = [base for base in BASE_MAPPING if base != "minions_denied"]
    elif bank == "denied_keys":
        bases = ["minions_denied"]
    else:
        raise SaltCacheError(f"Unrecognized bank: {bank}")

    for base in bases:
        keyfile = os.path.join(cachedir, base, key)

        if not clean_path(cachedir, keyfile, subdir=True):
            raise SaltCacheError(f"key {key} is not a valid key path.")

        if os.path.isfile(keyfile):
            return True
    return False
