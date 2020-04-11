# -*- coding: utf-8 -*-
"""
Send events covering service status
"""

# Import Python Libs
from __future__ import absolute_import, unicode_literals

import logging
import os
import time

from salt.ext.six.moves import map

log = logging.getLogger(__name__)  # pylint: disable=invalid-name

LAST_STATUS = {}

__virtualname__ = "service"


def validate(config):
    """
    Validate the beacon configuration
    """
    # Configuration for service beacon should be a list of dicts
    if not isinstance(config, list):
        return False, ("Configuration for service beacon must be a list.")
    else:
        _config = {}
        list(map(_config.update, config))

        if "services" not in _config:
            return False, ("Configuration for service beacon requires services.")
        else:
            for config_item in _config["services"]:
                if not isinstance(_config["services"][config_item], dict):
                    return (
                        False,
                        (
                            "Configuration for service beacon must "
                            "be a list of dictionaries."
                        ),
                    )

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
    _config = {}
    list(map(_config.update, config))

    for service in _config.get("services", {}):
        ret_dict = {}

        service_config = _config["services"][service]

        ret_dict[service] = {"running": __salt__["service.status"](service)}
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
        if "onchangeonly" in service_config and service_config["onchangeonly"] is True:
            if service not in LAST_STATUS:
                LAST_STATUS[service] = ret_dict[service]
                if service_config["delay"] > 0:
                    LAST_STATUS[service]["time"] = currtime
                elif not service_config["emitatstartup"]:
                    continue
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
