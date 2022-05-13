"""
Common functions for managing package refreshes during states
"""

import errno
import logging
import os
import re

import salt.utils.data
import salt.utils.files
import salt.utils.versions

log = logging.getLogger(__name__)


def rtag(opts):
    """
    Return the rtag file location. This file is used to ensure that we don't
    refresh more than once (unless explicitly configured to do so).
    """
    return os.path.join(opts["cachedir"], "pkg_refresh")


def clear_rtag(opts):
    """
    Remove the rtag file
    """
    try:
        os.remove(rtag(opts))
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            # Using __str__() here to get the fully-formatted error message
            # (error number, error message, path)
            log.warning("Encountered error removing rtag: %s", exc.__str__())


def write_rtag(opts):
    """
    Write the rtag file
    """
    rtag_file = rtag(opts)
    if not os.path.exists(rtag_file):
        try:
            with salt.utils.files.fopen(rtag_file, "w+"):
                pass
        except OSError as exc:
            log.warning("Encountered error writing rtag: %s", exc.__str__())


def check_refresh(opts, refresh=None):
    """
    Check whether or not a refresh is necessary

    Returns:

    - True if refresh evaluates as True
    - False if refresh is False
    - A boolean if refresh is not False and the rtag file exists
    """
    return bool(
        salt.utils.data.is_true(refresh)
        or (os.path.isfile(rtag(opts)) and refresh is not False)
    )


def split_comparison(version):
    match = re.match(r"^(<=>|!=|>=|<=|>>|<<|<>|>|<|=)?\s?([^<>=]+)$", version)
    if match:
        comparison = match.group(1) or ""
        version = match.group(2)
    else:
        comparison = ""
    return comparison, version


def match_version(desired, available, cmp_func=None, ignore_epoch=False):
    """
    Returns the first version of the list of available versions which matches
    the desired version comparison expression, or None if no match is found.
    """
    oper, version = split_comparison(desired)
    if not oper:
        oper = "=="
    for candidate in available:
        if salt.utils.versions.compare(
            ver1=candidate,
            oper=oper,
            ver2=version,
            cmp_func=cmp_func,
            ignore_epoch=ignore_epoch,
        ):
            return candidate
    return None
