"""
Beacon to monitor swap usage.

.. versionadded:: 3003

:depends: python-psutil
"""
import logging
import re

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

log = logging.getLogger(__name__)

__virtualname__ = "swapusage"


def __virtual__():
    if HAS_PSUTIL is False:
        return False
    else:
        return __virtualname__


def validate(config):
    """
    Validate the beacon configuration
    """
    # Configuration for swapusage beacon should be a list of dicts
    if not isinstance(config, list):
        return False, ("Configuration for swapusage beacon must be a list.")
    else:
        _config = {}
        list(map(_config.update, config))

        if "percent" not in _config:
            return False, ("Configuration for swapusage beacon requires percent.")

    return True, "Valid beacon configuration"


def beacon(config):
    """
    Monitor the swap usage of the minion

    Specify thresholds for percent used and only emit a beacon
    if it is exceeded.

    .. code-block:: yaml

        beacons:
          swapusage:
            - percent: 13%
    """
    ret = []

    _config = {}
    list(map(_config.update, config))

    _current_usage = psutil.swap_memory()

    current_usage = _current_usage.percent
    monitor_usage = _config["percent"]
    if "%" in monitor_usage:
        monitor_usage = re.sub("%", "", monitor_usage)
    monitor_usage = float(monitor_usage)
    if current_usage >= monitor_usage:
        ret.append({"swapusage": current_usage})
    return ret
