# -*- coding: utf-8 -*-
"""
A simple beacon to watch journald for specific entries
"""

# Import Python libs
from __future__ import absolute_import, unicode_literals

import logging

import salt.ext.six

# Import salt libs
import salt.utils.data
from salt.ext.six.moves import map

# Import third party libs
try:
    import systemd.journal  # pylint: disable=no-name-in-module

    HAS_SYSTEMD = True
except ImportError:
    HAS_SYSTEMD = False


log = logging.getLogger(__name__)

__virtualname__ = "journald"


def __virtual__():
    if HAS_SYSTEMD:
        return __virtualname__
    return False


def _get_journal():
    """
    Return the active running journal object
    """
    if "systemd.journald" in __context__:
        return __context__["systemd.journald"]
    __context__["systemd.journald"] = systemd.journal.Reader()
    # get to the end of the journal
    __context__["systemd.journald"].seek_tail()
    __context__["systemd.journald"].get_previous()
    return __context__["systemd.journald"]


def validate(config):
    """
    Validate the beacon configuration
    """
    # Configuration for journald beacon should be a list of dicts
    if not isinstance(config, list):
        return (False, "Configuration for journald beacon must be a list.")
    else:
        _config = {}
        list(map(_config.update, config))

        for name in _config.get("services", {}):
            if not isinstance(_config["services"][name], dict):
                return (
                    False,
                    (
                        "Services configuration for journald beacon "
                        "must be a list of dictionaries."
                    ),
                )
    return True, "Valid beacon configuration"


def beacon(config):
    """
    The journald beacon allows for the systemd journal to be parsed and linked
    objects to be turned into events.

    This beacons config will return all sshd jornal entries

    .. code-block:: yaml

        beacons:
          journald:
            - services:
                sshd:
                  SYSLOG_IDENTIFIER: sshd
                  PRIORITY: 6
    """
    ret = []
    journal = _get_journal()

    _config = {}
    list(map(_config.update, config))

    while True:
        cur = journal.get_next()
        if not cur:
            break

        for name in _config.get("services", {}):
            n_flag = 0
            for key in _config["services"][name]:
                if isinstance(key, salt.ext.six.string_types):
                    key = salt.utils.data.decode(key)
                if key in cur:
                    if _config["services"][name][key] == cur[key]:
                        n_flag += 1
            if n_flag == len(_config["services"][name]):
                # Match!
                sub = salt.utils.data.simple_types_filter(cur)
                sub.update({"tag": name})
                ret.append(sub)
    return ret
