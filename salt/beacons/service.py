"""
Send events covering service status
"""

import logging
import os
import time

import salt.utils.beacons
from salt._logging import LOG_LEVELS

log = logging.getLogger(__name__)

LAST_STATUS = {}

__virtualname__ = "service"


def _service_status(service, output_loglevel=None):
    """
    Check the service status. When ``output_loglevel`` is configured it is
    passed to ``service.status`` so the logging of the executed commands can
    be tuned. Not every ``service`` module accepts ``output_loglevel``, so
    fall back to a plain call for those.
    """
    if output_loglevel is None:
        return __salt__["service.status"](service)
    try:
        return __salt__["service.status"](service, output_loglevel=output_loglevel)
    except TypeError:
        return __salt__["service.status"](service)


def _check_loglevel(loglevel):
    """
    Return an error message if ``loglevel`` is not valid, otherwise None
    """
    if loglevel is None:
        return None
    if isinstance(loglevel, str) and (
        loglevel.lower() == "quiet" or loglevel.lower() in LOG_LEVELS
    ):
        return None
    return "output_loglevel for service beacon must be 'quiet' or one of: {}.".format(
        ", ".join(sorted(LOG_LEVELS))
    )


def validate(config):
    """
    Validate the beacon configuration
    """
    # Configuration for service beacon should be a list of dicts
    if not isinstance(config, list):
        return False, "Configuration for service beacon must be a list."
    else:
        config = salt.utils.beacons.list_to_dict(config)

        if "services" not in config:
            return False, "Configuration for service beacon requires services."
        else:
            if not isinstance(config["services"], dict):
                return (
                    False,
                    "Services configuration item for service beacon must "
                    "be a dictionary.",
                )
            for config_item in config["services"]:
                if not isinstance(config["services"][config_item], dict):
                    return (
                        False,
                        "Configuration for service beacon must "
                        "be a list of dictionaries.",
                    )
                err = _check_loglevel(
                    config["services"][config_item].get("output_loglevel")
                )
                if err:
                    return False, err
            err = _check_loglevel(config.get("output_loglevel"))
            if err:
                return False, err

    return True, "Valid beacon configuration"


def beacon(config):
    """
    Scan for the configured services and fire events

    Example Config

    .. code-block:: yaml

        beacons:
          service:
            - services:
                salt-master: {}
                mysql: {}

    The config above sets up beacons to check for
    the salt-master and mysql services.

    The config also supports two other parameters for each service:

    `onchangeonly`: when `onchangeonly` is True the beacon will fire
    events only when the service status changes.  Otherwise, it will fire an
    event at each beacon interval.  The default is False.

    `delay`: when `delay` is greater than 0 the beacon will fire events only
    after the service status changes, and the delay (in seconds) has passed.
    Applicable only when `onchangeonly` is True.  The default is 0.

    `emitatstartup`: when `emitatstartup` is False the beacon will not fire
    event when the minion is reload. Applicable only when `onchangeonly` is True.
    The default is True.

    `is_running_state`: This boolean parameter controls when the beacon will
    fire based on the service's running state. If `is_running_state` is set to
    `True`, the beacon will fire only when the service is running. If
    `is_running_state` is set to `False`, the beacon will fire only when the
    service is not running.

    `output_loglevel`: the log level used for the commands the beacon runs to
    check the service status (for example ``systemctl is-active``). By default
    the commands are logged at ``info`` level, as for any other ``cmd`` call.
    Set it to ``quiet`` to suppress the "Executing command" messages, which is
    useful when the beacon runs at a short interval. It can be set for a single
    service, or for all services at the top level of the beacon configuration;
    a per-service value overrides the top-level one. Only ``service`` modules
    that accept ``output_loglevel`` (currently ``systemd``) honour this option;
    it is ignored by the others.

    .. code-block:: yaml

        beacons:
          service:
            - services:
                sshd:
                  onchangeonly: True
                sssd: {}
                zabbix-agent2:
                  output_loglevel: info
            - output_loglevel: quiet
            - interval: 1

    In the example above ``sshd`` and ``sssd`` are checked quietly, while
    ``zabbix-agent2`` keeps logging at ``info``.

    `uncleanshutdown`: If `uncleanshutdown` is present it should point to the
    location of a pid file for the service.  Most services will not clean up
    this pid file if they are shutdown uncleanly (e.g. via `kill -9`) or if they
    are terminated through a crash such as a segmentation fault.  If the file is
    present, then the beacon will add `uncleanshutdown: True` to the event.  If
    not present, the field will be False.  The field is only added when the
    service is NOT running. Omitting the configuration variable altogether will
    turn this feature off.

    Please note that some init systems can remove the pid file if the service
    registers as crashed. One such example is nginx on CentOS 7, where the
    service unit removes the pid file when the service shuts down (IE: the pid
    file is observed as removed when kill -9 is sent to the nginx master
    process). The 'uncleanshutdown' option might not be of much use there,
    unless the unit file is modified.

    Here is an example that will fire an event 30 seconds after the state of nginx
    changes and report an uncleanshutdown.  This example is for Arch, which
    places nginx's pid file in `/run`.

    .. code-block:: yaml

        beacons:
          service:
            - services:
                nginx:
                  onchangeonly: True
                  delay: 30
                  uncleanshutdown: /run/nginx.pid
    """
    ret = []
    config = salt.utils.beacons.list_to_dict(config)

    for service in config.get("services", {}):
        ret_dict = {}

        service_config = config["services"][service]
        if not service_config:
            service_config = {}

        ret_dict[service] = {
            "running": _service_status(
                service,
                service_config.get("output_loglevel", config.get("output_loglevel")),
            )
        }
        ret_dict["service_name"] = service
        ret_dict["tag"] = service
        currtime = time.time()

        # If no options is given to the service, we fall back to the defaults
        # assign a False value to oncleanshutdown and onchangeonly. Those
        # key:values are then added to the service dictionary.
        if not service_config:
            service_config = {}
        if "oncleanshutdown" not in service_config:
            service_config["oncleanshutdown"] = False
        if "emitatstartup" not in service_config:
            service_config["emitatstartup"] = True
        if "onchangeonly" not in service_config:
            service_config["onchangeonly"] = False
        if "delay" not in service_config:
            service_config["delay"] = 0

        # We only want to report the nature of the shutdown
        # if the current running status is False
        # as well as if the config for the beacon asks for it
        if "uncleanshutdown" in service_config and not ret_dict[service]["running"]:
            filename = service_config["uncleanshutdown"]
            ret_dict[service]["uncleanshutdown"] = (
                True if os.path.exists(filename) else False
            )

        # If is_running_state does not match the current running state, skip it
        if (
            "is_running_state" in service_config
            and isinstance(service_config["is_running_state"], bool)
            and service_config["is_running_state"] != ret_dict[service]["running"]
        ):
            continue

        if "onchangeonly" in service_config and service_config["onchangeonly"] is True:
            if service not in LAST_STATUS:
                LAST_STATUS[service] = ret_dict[service]
                if not service_config["emitatstartup"]:
                    continue
                if service_config["delay"] > 0:
                    LAST_STATUS[service]["time"] = currtime
                else:
                    ret.append(ret_dict)

            if LAST_STATUS[service]["running"] != ret_dict[service]["running"]:
                LAST_STATUS[service] = ret_dict[service]
                if service_config["delay"] > 0:
                    LAST_STATUS[service]["time"] = currtime
                else:
                    ret.append(ret_dict)

            if "time" in LAST_STATUS[service]:
                elapsedtime = int(round(currtime - LAST_STATUS[service]["time"]))
                if elapsedtime > service_config["delay"]:
                    del LAST_STATUS[service]["time"]
                    ret.append(ret_dict)
        else:
            ret.append(ret_dict)

    return ret
