# -*- coding: utf-8 -*-
"""
Splay function calls across targeted minions
"""
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import time

import salt.utils.stringutils

log = logging.getLogger(__name__)

_DEFAULT_SPLAYTIME = 300
_HASH_SIZE = 8192
_HASH_VAL = None


def __init__(opts):
    global _HASH_VAL
    _HASH_VAL = _get_hash()


def _get_hash():
    """
    Jenkins One-At-A-Time Hash Function
    More Info: http://en.wikipedia.org/wiki/Jenkins_hash_function#one-at-a-time
    """
    # Using bitmask to emulate rollover behavior of C unsigned 32 bit int
    bitmask = 0xFFFFFFFF
    h = 0

    for i in bytearray(salt.utils.stringutils.to_bytes(__grains__["id"])):
        h = (h + i) & bitmask
        h = (h + (h << 10)) & bitmask
        h = (h ^ (h >> 6)) & bitmask

    h = (h + (h << 3)) & bitmask
    h = (h ^ (h >> 11)) & bitmask
    h = (h + (h << 15)) & bitmask

    return (h & (_HASH_SIZE - 1)) & bitmask


def _calc_splay(splaytime):
    return int(splaytime * _HASH_VAL / float(_HASH_SIZE))


def execute(opts, data, func, args, kwargs):
    """
    Splay a salt function call execution time across minions over
    a number of seconds (default: 300)

    .. note::
        You *probably* want to use --async here and look up the job results later.
        If you're dead set on getting the output from the CLI command, then make
        sure to set the timeout (with the -t flag) to something greater than the
        splaytime (max splaytime + time to execute job).
        Otherwise, it's very likely that the cli will time out before the job returns.

    CLI Example:

    .. code-block:: bash

        # With default splaytime
        salt --async --module-executors='[splay, direct_call]' '*' pkg.install cowsay version=3.03-8.el6

    .. code-block:: bash

        # With specified splaytime (5 minutes) and timeout with 10 second buffer
        salt -t 310 --module-executors='[splay, direct_call]' --executor-opts='{splaytime: 300}' '*' pkg.version cowsay
    """
    if "executor_opts" in data and "splaytime" in data["executor_opts"]:
        splaytime = data["executor_opts"]["splaytime"]
    else:
        splaytime = opts.get("splaytime", _DEFAULT_SPLAYTIME)
    if splaytime <= 0:
        raise ValueError("splaytime must be a positive integer")
    fun_name = data.get("fun")
    my_delay = _calc_splay(splaytime)
    log.debug("Splay is sleeping %s secs on %s", my_delay, fun_name)

    time.sleep(my_delay)
    return None
