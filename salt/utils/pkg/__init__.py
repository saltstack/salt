"""
Common functions for managing package refreshes during states
"""

import errno
import fnmatch
import logging
import os
import re
import sys

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
            log.warning("Encountered error removing rtag: %s", exc)


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
            log.warning("Encountered error writing rtag: %s", exc)


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


def check_bundled():
    """
    Gather run-time information to indicate if we are running from source or bundled.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return True
    return False


def match_wildcard(current_pkgs, pkg_params):
    """
    Loop through pkg_params looking for any which contains a wildcard and get
    the real package names from the packages which are currently installed.

    current_pkgs
        List of currently installed packages as output by ``list_pkgs``

    pkg_params
        List of packages as processed by ``pkg_resource.parse_targets``
    """
    pkg_matches = {}

    for pkg_param in list(pkg_params):
        if "*" in pkg_param:
            pkg_matches = {
                pkg: pkg_params[pkg_param]
                for pkg in current_pkgs
                if fnmatch.fnmatch(pkg, pkg_param)
            }

            # Remove previous pkg_param
            pkg_params.pop(pkg_param)

    # Update pkg_params with the matches
    pkg_params.update(pkg_matches)

    return pkg_params
