"""
Stores eauth tokens in the filesystem of the master. Location is configured by the master config option 'token_dir'
"""

import hashlib
import logging
import os

import salt.payload
import salt.utils.files
import salt.utils.path
import salt.utils.verify
from salt.config import DEFAULT_HASH_TYPE

log = logging.getLogger(__name__)

__virtualname__ = "localfs"


def mk_token(opts, tdata):
    """
    Mint a new token using the config option hash_type and store tdata with 'token' attribute set
    to the token.
    This module uses the hash of random 512 bytes as a token.

    :param opts: Salt master config options
    :param tdata: Token data to be stored with 'token' attribute of this dict set to the token.
    :returns: tdata with token if successful. Empty dict if failed.
    """
    hash_type = getattr(hashlib, opts.get("hash_type", DEFAULT_HASH_TYPE))
    tok = str(hash_type(os.urandom(512)).hexdigest())
    t_path = os.path.join(opts["token_dir"], tok)
    temp_t_path = f"{t_path}.tmp"
    while os.path.isfile(t_path):
        tok = str(hash_type(os.urandom(512)).hexdigest())
        t_path = os.path.join(opts["token_dir"], tok)
    tdata["token"] = tok
    try:
        with salt.utils.files.set_umask(0o177):
            with salt.utils.files.fopen(temp_t_path, "w+b") as fp_:
                fp_.write(salt.payload.dumps(tdata))
        os.rename(temp_t_path, t_path)
    except OSError:
        log.warning('Authentication failure: can not write token file "%s".', t_path)
        return {}
    return tdata


def get_token(opts, tok):
    """
    Fetch the token data from the store.

    :param opts: Salt master config options
    :param tok: Token value to get
    :returns: Token data if successful. Empty dict if failed.
    """
    t_path = os.path.join(opts["token_dir"], tok)
    if not salt.utils.verify.clean_path(opts["token_dir"], t_path):
        return {}
    if not os.path.isfile(t_path):
        return {}
    try:
        with salt.utils.files.fopen(t_path, "rb") as fp_:
            tdata = salt.payload.loads(fp_.read())
            return tdata
    except OSError:
        log.warning('Authentication failure: can not read token file "%s".', t_path)
        return {}


def rm_token(opts, tok):
    """
    Remove token from the store.

    :param opts: Salt master config options
    :param tok: Token to remove
    :returns: Empty dict if successful. None if failed.
    """
    t_path = os.path.join(opts["token_dir"], tok)
    try:
        os.remove(t_path)
        return {}
    except OSError:
        log.warning("Could not remove token %s", tok)


def list_tokens(opts):
    """
    List all tokens in the store.

    :param opts: Salt master config options
    :returns: List of dicts (tokens)
    """
    ret = []
    for dirpath, dirnames, filenames in salt.utils.path.os_walk(opts["token_dir"]):
        for token in filenames:
            ret.append(token)
    return ret
