# -*- coding: utf-8 -*-
"""
Module for working with the Zenoss API

.. versionadded:: 2016.3.0

:depends: requests

:configuration: This module requires a 'zenoss' entry in the master/minion config.

    For example:

    .. code-block:: yaml

        zenoss:
          hostname: https://zenoss.example.com
          username: admin
          password: admin123
"""


from __future__ import absolute_import, print_function, unicode_literals

import logging
import re

import salt.utils.json

try:
    import requests

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


# Disable INFO level logs from requests/urllib3
urllib3_logger = logging.getLogger("urllib3")
urllib3_logger.setLevel(logging.WARNING)


log = logging.getLogger(__name__)

__virtualname__ = "zenoss"


def __virtual__():
    """
    Only load if requests is installed
    """
    if HAS_LIBS:
        return __virtualname__
    else:
        return (
            False,
            "The '{0}' module could not be loaded: "
            "'requests' is not installed.".format(__virtualname__),
        )


ROUTERS = {
    "MessagingRouter": "messaging",
    "EventsRouter": "evconsole",
    "ProcessRouter": "process",
    "ServiceRouter": "service",
    "DeviceRouter": "device",
    "NetworkRouter": "network",
    "TemplateRouter": "template",
    "DetailNavRouter": "detailnav",
    "ReportRouter": "report",
    "MibRouter": "mib",
    "ZenPackRouter": "zenpack",
}


def _session():
    """
    Create a session to be used when connecting to Zenoss.
    """

    config = __salt__["config.option"]("zenoss")
    session = requests.session()
    session.auth = (config.get("username"), config.get("password"))
    session.verify = False
    session.headers.update({"Content-type": "application/json; charset=utf-8"})
    return session


def _router_request(router, method, data=None):
    """
    Make a request to the Zenoss API router
    """
    if router not in ROUTERS:
        return False

    req_data = salt.utils.json.dumps(
        [dict(action=router, method=method, data=data, type="rpc", tid=1)]
    )

    config = __salt__["config.option"]("zenoss")
    log.debug("Making request to router %s with method %s", router, method)
    url = "{0}/zport/dmd/{1}_router".format(config.get("hostname"), ROUTERS[router])
    response = _session().post(url, data=req_data)

    # The API returns a 200 response code even whe auth is bad.
    # With bad auth, the login page is displayed. Here I search for
    # an element on the login form to determine if auth failed.
    if re.search('name="__ac_name"', response.content):
        log.error("Request failed. Bad username/password.")
        raise Exception("Request failed. Bad username/password.")

    return salt.utils.json.loads(response.content).get("result", None)


def _determine_device_class():
    """
    If no device class is given when adding a device, this helps determine
    """
    if __salt__["grains.get"]("kernel") == "Linux":
        return "/Server/Linux"


def find_device(device=None):
    """
    Find a device in Zenoss. If device not found, returns None.

    Parameters:
        device:         (Optional) Will use the grain 'fqdn' by default

    CLI Example:
        salt '*' zenoss.find_device
    """

    data = [{"uid": "/zport/dmd/Devices", "params": {}, "limit": None}]
    all_devices = _router_request("DeviceRouter", "getDevices", data=data)
    for dev in all_devices["devices"]:
        if dev["name"] == device:
            # We need to save the has for later operations
            dev["hash"] = all_devices["hash"]
            log.info("Found device %s in Zenoss", device)
            return dev

    log.info("Unable to find device %s in Zenoss", device)
    return None


def device_exists(device=None):
    """
    Check to see if a device already exists in Zenoss.

    Parameters:
        device:         (Optional) Will use the grain 'fqdn' by default

    CLI Example:
        salt '*' zenoss.device_exists
    """

    if not device:
        device = __salt__["grains.get"]("fqdn")

    if find_device(device):
        return True
    return False


def add_device(device=None, device_class=None, collector="localhost", prod_state=1000):
    """
    A function to connect to a zenoss server and add a new device entry.

    Parameters:
        device:         (Optional) Will use the grain 'fqdn' by default.
        device_class:   (Optional) The device class to use. If none, will determine based on kernel grain.
        collector:      (Optional) The collector to use for this device. Defaults to 'localhost'.
        prod_state:     (Optional) The prodState to set on the device. If none, defaults to 1000 ( production )

    CLI Example:
        salt '*' zenoss.add_device
    """

    if not device:
        device = __salt__["grains.get"]("fqdn")

    if not device_class:
        device_class = _determine_device_class()
    log.info("Adding device %s to zenoss", device)
    data = dict(
        deviceName=device,
        deviceClass=device_class,
        model=True,
        collector=collector,
        productionState=prod_state,
    )
    response = _router_request("DeviceRouter", "addDevice", data=[data])
    return response


def set_prod_state(prod_state, device=None):
    """
    A function to set the prod_state in zenoss.

    Parameters:
        prod_state:     (Required) Integer value of the state
        device:         (Optional) Will use the grain 'fqdn' by default.

    CLI Example:
        salt zenoss.set_prod_state 1000 hostname
    """

    if not device:
        device = __salt__["grains.get"]("fqdn")

    device_object = find_device(device)

    if not device_object:
        return "Unable to find a device in Zenoss for {0}".format(device)

    log.info("Setting prodState to %d on %s device", prod_state, device)
    data = dict(
        uids=[device_object["uid"]],
        prodState=prod_state,
        hashcheck=device_object["hash"],
    )
    return _router_request("DeviceRouter", "setProductionState", [data])
