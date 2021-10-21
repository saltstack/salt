"""
Send events covering process status
"""
import logging

import salt.utils.beacons

try:
    import salt.utils.psutil_compat as psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


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
        return False, "Configuration for ps beacon must be a list."
    else:
        config = salt.utils.beacons.list_to_dict(config)

        if "processes" not in config:
            return False, "Configuration for ps beacon requires processes."
        else:
            if not isinstance(config["processes"], dict):
                return False, "Processes for ps beacon must be a dictionary."

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
        try:
            _name = proc.name()
        except psutil.NoSuchProcess:
            # The process is now gone
            continue
        if _name not in procs:
            procs.append(_name)

    config = salt.utils.beacons.list_to_dict(config)

    for process in config.get("processes", {}):
        ret_dict = {}
        if config["processes"][process] == "running":
            if process in procs:
                ret_dict[process] = "Running"
                ret.append(ret_dict)
        elif config["processes"][process] == "stopped":
            if process not in procs:
                ret_dict[process] = "Stopped"
                ret.append(ret_dict)
        else:
            if process not in procs:
                ret_dict[process] = False
                ret.append(ret_dict)
    return ret
