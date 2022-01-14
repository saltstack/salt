"""
Beacon to emit system load averages
"""
import logging
import os

import salt.utils.beacons
import salt.utils.platform

log = logging.getLogger(__name__)

__virtualname__ = "load"

LAST_STATUS = {}


def __virtual__():
    if salt.utils.platform.is_windows():
        err_msg = "Not available for Windows systems."
        log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
        return False, err_msg
    else:
        return __virtualname__


def validate(config):
    """
    Validate the beacon configuration
    """

    # Configuration for load beacon should be a list of dicts
    if not isinstance(config, list):
        return False, "Configuration for load beacon must be a list."
    else:
        config = salt.utils.beacons.list_to_dict(config)

        if "emitatstartup" in config:
            if not isinstance(config["emitatstartup"], bool):
                return (
                    False,
                    "Configuration for load beacon option emitatstartup must be a"
                    " boolean.",
                )

        if "onchangeonly" in config:
            if not isinstance(config["onchangeonly"], bool):
                return (
                    False,
                    "Configuration for load beacon option onchangeonly must be a"
                    " boolean.",
                )

        if "averages" not in config:
            return False, "Averages configuration is required for load beacon."
        else:

            if not any(j in ["1m", "5m", "15m"] for j in config.get("averages", {})):
                return (
                    False,
                    "Averages configuration for load beacon must contain 1m, 5m or 15m"
                    " items.",
                )

            for item in ["1m", "5m", "15m"]:
                if not isinstance(config["averages"][item], list):
                    return (
                        False,
                        "Averages configuration for load beacon: 1m, 5m and 15m items"
                        " must be a list of two items.",
                    )
                else:
                    if len(config["averages"][item]) != 2:
                        return (
                            False,
                            "Configuration for load beacon: 1m, 5m and 15m items must"
                            " be a list of two items.",
                        )

    return True, "Valid beacon configuration"


def beacon(config):
    """
    Emit the load averages of this host.

    Specify thresholds for each load average
    and only emit a beacon if any of them are
    exceeded.

    `onchangeonly`: when `onchangeonly` is True the beacon will fire
    events only when the load average pass one threshold.  Otherwise, it will fire an
    event at each beacon interval.  The default is False.

    `emitatstartup`: when `emitatstartup` is False the beacon will not fire
     event when the minion is reload. Applicable only when `onchangeonly` is True.
     The default is True.

    .. code-block:: yaml

        beacons:
          load:
            - averages:
                1m:
                  - 0.0
                  - 2.0
                5m:
                  - 0.0
                  - 1.5
                15m:
                  - 0.1
                  - 1.0
            - emitatstartup: True
            - onchangeonly: False

    """
    log.trace("load beacon starting")

    config = salt.utils.beacons.list_to_dict(config)

    # Default config if not present
    if "emitatstartup" not in config:
        config["emitatstartup"] = True
    if "onchangeonly" not in config:
        config["onchangeonly"] = False

    ret = []
    avgs = os.getloadavg()
    avg_keys = ["1m", "5m", "15m"]
    avg_dict = dict(zip(avg_keys, avgs))

    if config["onchangeonly"]:
        if not LAST_STATUS:
            for k in ["1m", "5m", "15m"]:
                LAST_STATUS[k] = avg_dict[k]
            if not config["emitatstartup"]:
                log.debug("Don't emit because emitatstartup is False")
                return ret

    send_beacon = False

    # Check each entry for threshold
    for k in ["1m", "5m", "15m"]:
        if k in config.get("averages", {}):
            if config["onchangeonly"]:
                # Emit if current is more that threshold and old value less
                # that threshold
                if float(avg_dict[k]) > float(config["averages"][k][1]) and float(
                    LAST_STATUS[k]
                ) < float(config["averages"][k][1]):
                    log.debug(
                        "Emit because %f > %f and last was %f",
                        float(avg_dict[k]),
                        float(config["averages"][k][1]),
                        float(LAST_STATUS[k]),
                    )
                    send_beacon = True
                    break
                # Emit if current is less that threshold and old value more
                # that threshold
                if float(avg_dict[k]) < float(config["averages"][k][0]) and float(
                    LAST_STATUS[k]
                ) > float(config["averages"][k][0]):
                    log.debug(
                        "Emit because %f < %f and last was%f",
                        float(avg_dict[k]),
                        float(config["averages"][k][0]),
                        float(LAST_STATUS[k]),
                    )
                    send_beacon = True
                    break
            else:
                # Emit no matter LAST_STATUS
                if float(avg_dict[k]) < float(config["averages"][k][0]) or float(
                    avg_dict[k]
                ) > float(config["averages"][k][1]):
                    log.debug(
                        "Emit because %f < %f or > %f",
                        float(avg_dict[k]),
                        float(config["averages"][k][0]),
                        float(config["averages"][k][1]),
                    )
                    send_beacon = True
                    break

    if config["onchangeonly"]:
        for k in ["1m", "5m", "15m"]:
            LAST_STATUS[k] = avg_dict[k]

    if send_beacon:
        ret.append(avg_dict)

    return ret
