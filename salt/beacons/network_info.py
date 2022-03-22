"""
Beacon to monitor statistics from ethernet adapters

.. versionadded:: 2015.5.0
"""
import logging

import salt.utils.beacons

try:
    import salt.utils.psutil_compat as psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


log = logging.getLogger(__name__)

__virtualname__ = "network_info"

__attrs = [
    "bytes_sent",
    "bytes_recv",
    "packets_sent",
    "packets_recv",
    "errin",
    "errout",
    "dropin",
    "dropout",
]


def _to_list(obj):
    """
    Convert snetinfo object to list
    """
    ret = {}

    for attr in __attrs:
        if hasattr(obj, attr):
            ret[attr] = getattr(obj, attr)
    return ret


def __virtual__():
    if not HAS_PSUTIL:
        err_msg = "psutil not available"
        log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
        return False, err_msg
    return __virtualname__


def validate(config):
    """
    Validate the beacon configuration
    """

    VALID_ITEMS = [
        "type",
        "bytes_sent",
        "bytes_recv",
        "packets_sent",
        "packets_recv",
        "errin",
        "errout",
        "dropin",
        "dropout",
    ]

    # Configuration for load beacon should be a list of dicts
    if not isinstance(config, list):
        return False, "Configuration for network_info beacon must be a list."
    else:

        config = salt.utils.beacons.list_to_dict(config)

        for item in config.get("interfaces", {}):
            if not isinstance(config["interfaces"][item], dict):
                return (
                    False,
                    "Configuration for network_info beacon must "
                    "be a list of dictionaries.",
                )
            else:
                if not any(j in VALID_ITEMS for j in config["interfaces"][item]):
                    return (
                        False,
                        "Invalid configuration item in Beacon configuration.",
                    )
    return True, "Valid beacon configuration"


def beacon(config):
    """
    Emit the network statistics of this host.

    Specify thresholds for each network stat
    and only emit a beacon if any of them are
    exceeded.

    Emit beacon when any values are equal to
    configured values.

    .. code-block:: yaml

        beacons:
          network_info:
            - interfaces:
                eth0:
                  type: equal
                  bytes_sent: 100000
                  bytes_recv: 100000
                  packets_sent: 100000
                  packets_recv: 100000
                  errin: 100
                  errout: 100
                  dropin: 100
                  dropout: 100

    Emit beacon when any values are greater
    than configured values.

    .. code-block:: yaml

        beacons:
          network_info:
            - interfaces:
                eth0:
                  type: greater
                  bytes_sent: 100000
                  bytes_recv: 100000
                  packets_sent: 100000
                  packets_recv: 100000
                  errin: 100
                  errout: 100
                  dropin: 100
                  dropout: 100


    """
    ret = []

    config = salt.utils.beacons.list_to_dict(config)

    log.debug("psutil.net_io_counters %s", psutil.net_io_counters)

    _stats = psutil.net_io_counters(pernic=True)

    log.debug("_stats %s", _stats)
    for interface in config.get("interfaces", {}):
        if interface in _stats:
            interface_config = config["interfaces"][interface]
            _if_stats = _stats[interface]
            _diff = False
            for attr in __attrs:
                if attr in interface_config:
                    if (
                        "type" in interface_config
                        and interface_config["type"] == "equal"
                    ):
                        if getattr(_if_stats, attr, None) == int(
                            interface_config[attr]
                        ):
                            _diff = True
                    elif (
                        "type" in interface_config
                        and interface_config["type"] == "greater"
                    ):
                        if getattr(_if_stats, attr, None) > int(interface_config[attr]):
                            _diff = True
                        else:
                            log.debug("attr %s", getattr(_if_stats, attr, None))
                    else:
                        if getattr(_if_stats, attr, None) == int(
                            interface_config[attr]
                        ):
                            _diff = True
            if _diff:
                ret.append(
                    {"interface": interface, "network_info": _to_list(_if_stats)}
                )
    return ret
