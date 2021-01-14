# -*- coding: utf-8 -*-
"""
Set grains describing the minion process.
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import os

import salt.utils.platform

# Import salt libs
import salt.utils.user


def _uid():
    """
    Grain for the minion User ID
    """
    return salt.utils.user.get_uid()


def _username():
    """
    Grain for the minion username
    """
    return salt.utils.user.get_user()


def _gid():
    """
    Grain for the minion Group ID
    """
    return salt.utils.user.get_gid()


def _groupname():
    """
    Grain for the minion groupname
    """
    try:
        return salt.utils.user.get_default_group(_username()) or ""
    except KeyError:
        return ""


def _pid():
    """
    Return the current process pid
    """
    return os.getpid()


def grains():
    """
    Return the grains dictionary
    """
    ret = {
        "username": _username(),
        "groupname": _groupname(),
        "pid": _pid(),
    }

    if not salt.utils.platform.is_windows():
        ret["gid"] = _gid()
        ret["uid"] = _uid()

    return ret
