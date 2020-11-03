# -*- coding: utf-8 -*-
"""
Send events covering process status
"""

# Import Python Libs
from __future__ import absolute_import, unicode_literals

import logging

from salt.ext.six.moves import map

# Import third party libs
# pylint: disable=import-error
try:
    import salt.utils.psutil_compat as psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# pylint: enable=import-error

log = logging.getLogger(__name__)  # pylint: disable=invalid-name

__virtualname__ = "ps"


def __virtual__():
    if not HAS_PSUTIL:
        return (False, "cannot load ps beacon: psutil not available")
    return __virtualname__


def validate(config):
    """
    Validate the beacon configuration
    """
    # Configuration for ps beacon should be a list of dicts
    if not isinstance(config, list):
        return False, ("Configuration for ps beacon must be a list.")
    else:
        _config = {}
        list(map(_config.update, config))

        if "processes" not in _config:
            return False, ("Configuration for ps beacon requires processes.")
        else:
            if not isinstance(_config["processes"], dict):
                return False, ("Processes for ps beacon must be a dictionary.")

    return True, "Valid beacon configuration"


def beacon(config):
    """
    Scan for processes and fire events

    Example Config

    .. code-block:: yaml

        beacons:
          ps:
            - processes:
                salt-master: running
                mysql: stopped

    The config above sets up beacons to check that
    processes are running or stopped.
    """
    ret = []
    procs = []
    for proc in psutil.process_iter():
        _name = proc.name()
        if _name not in procs:
            procs.append(_name)

    _config = {}
    list(map(_config.update, config))

    for process in _config.get("processes", {}):
        ret_dict = {}
        if _config["processes"][process] == "running":
            if process in procs:
                ret_dict[process] = "Running"
                ret.append(ret_dict)
        elif _config["processes"][process] == "stopped":
            if process not in procs:
                ret_dict[process] = "Stopped"
                ret.append(ret_dict)
        else:
            if process not in procs:
                ret_dict[process] = False
                ret.append(ret_dict)
    return ret
