# -*- coding: utf-8 -*-
"""
Proxy Minion interface module for managing Palo Alto firewall devices
=====================================================================

.. versionadded:: 2018.3.0

:codeauthor: ``Spencer Ervin <spencer_ervin@hotmail.com>``
:maturity:   new
:depends:    none
:platform:   unix

This proxy minion enables Palo Alto firewalls (hereafter referred to
as simply 'panos') to be treated individually like a Salt Minion.

The panos proxy leverages the XML API functionality on the Palo Alto
firewall. The Salt proxy must have access to the Palo Alto firewall on
HTTPS (tcp/443).

More in-depth conceptual reading on Proxy Minions can be found in the
:ref:`Proxy Minion <proxy-minion>` section of Salt's
documentation.


Configuration
=============

To use this integration proxy module, please configure the following:

Pillar
------

Proxy minions get their configuration from Salt's Pillar. Every proxy must
have a stanza in Pillar and a reference in the Pillar top-file that matches
the ID. There are four connection options available for the panos proxy module.

- Direct Device (Password)
- Direct Device (API Key)
- Panorama Pass-Through (Password)
- Panorama Pass-Through (API Key)


Direct Device (Password)
------------------------

The direct device configuration configures the proxy to connect directly to
the device with username and password.

.. code-block:: yaml

    proxy:
      proxytype: panos
      host: <ip or dns name of panos host>
      username: <panos username>
      password: <panos password>

proxytype
^^^^^^^^^

The ``proxytype`` key and value pair is critical, as it tells Salt which
interface to load from the ``proxy`` directory in Salt's install hierarchy,
or from ``/srv/salt/_proxy`` on the Salt Master (if you have created your
own proxy module, for example). To use this panos Proxy Module, set this to
``panos``.

host
^^^^

The location, or ip/dns, of the panos host. Required.

username
^^^^^^^^

The username used to login to the panos host. Required.

password
^^^^^^^^

The password used to login to the panos host. Required.

Direct Device (API Key)
------------------------

Palo Alto devices allow for access to the XML API with a generated 'API key'_
instead of username and password.

.. _API key: https://www.paloaltonetworks.com/documentation/71/pan-os/xml-api/get-started-with-the-pan-os-xml-api/get-your-api-key

.. code-block:: yaml

    proxy:
      proxytype: panos
      host: <ip or dns name of panos host>
      apikey: <panos generated api key>

proxytype
^^^^^^^^^

The ``proxytype`` key and value pair is critical, as it tells Salt which
interface to load from the ``proxy`` directory in Salt's install hierarchy,
or from ``/srv/salt/_proxy`` on the Salt Master (if you have created your
own proxy module, for example). To use this panos Proxy Module, set this to
``panos``.

host
^^^^

The location, or ip/dns, of the panos host. Required.

apikey
^^^^^^

The generated XML API key for the panos host. Required.

Panorama Pass-Through (Password)
--------------------------------

The Panorama pass-through method sends all connections through the Panorama
management system. It passes the connections to the appropriate device using
the serial number of the Palo Alto firewall.

This option will reduce the number of connections that must be present for the
proxy server. It will only require a connection to the Panorama server.

The username and password will be for authentication to the Panorama server,
not the panos device.

.. code-block:: yaml

    proxy:
      proxytype: panos
      serial: <serial number of panos host>
      host: <ip or dns name of the panorama server>
      username: <panorama server username>
      password: <panorama server password>

proxytype
^^^^^^^^^

The ``proxytype`` key and value pair is critical, as it tells Salt which
interface to load from the ``proxy`` directory in Salt's install hierarchy,
or from ``/srv/salt/_proxy`` on the Salt Master (if you have created your
own proxy module, for example). To use this panos Proxy Module, set this to
``panos``.

serial
^^^^^^

The serial number of the panos host. Required.

host
^^^^

The location, or ip/dns, of the Panorama server. Required.

username
^^^^^^^^

The username used to login to the Panorama server. Required.

password
^^^^^^^^

The password used to login to the Panorama server. Required.

Panorama Pass-Through (API Key)
-------------------------------

The Panorama server can also utilize a generated 'API key'_ for authentication.

.. _API key: https://www.paloaltonetworks.com/documentation/71/pan-os/xml-api/get-started-with-the-pan-os-xml-api/get-your-api-key

.. code-block:: yaml

    proxy:
      proxytype: panos
      serial: <serial number of panos host>
      host: <ip or dns name of the panorama server>
      apikey: <panos generated api key>

proxytype
^^^^^^^^^

The ``proxytype`` key and value pair is critical, as it tells Salt which
interface to load from the ``proxy`` directory in Salt's install hierarchy,
or from ``/srv/salt/_proxy`` on the Salt Master (if you have created your
own proxy module, for example). To use this panos Proxy Module, set this to
``panos``.

serial
^^^^^^

The serial number of the panos host. Required.

host
^^^^

The location, or ip/dns, of the Panorama server. Required.

apikey
^^^^^^^^

The generated XML API key for the Panorama server. Required.
"""

from __future__ import absolute_import, print_function, unicode_literals

# Import Python Libs
import logging

import salt.exceptions
import salt.utils.xmlutil as xml

# Import Salt Libs
from salt._compat import ElementTree as ET
from salt.ext import six

# This must be present or the Salt loader won't load this module.
__proxyenabled__ = ["panos"]

# Variables are scoped to this module so we can have persistent data.
GRAINS_CACHE = {"vendor": "Palo Alto"}
DETAILS = {}

# Set up logging
log = logging.getLogger(__file__)

# Define the module's virtual name
__virtualname__ = "panos"


def __virtual__():
    """
    Only return if all the modules are available.
    """
    return __virtualname__


def _strip_dirty(xmltree):
    """
    Removes dirtyID tags from the candidate config result. Palo Alto devices will make the candidate configuration with
    a dirty ID after a change. This can cause unexpected results when parsing.
    """
    dirty = xmltree.attrib.pop("dirtyId", None)
    if dirty:
        xmltree.attrib.pop("admin", None)
        xmltree.attrib.pop("time", None)

    for child in xmltree:
        child = _strip_dirty(child)

    return xmltree


def init(opts):
    """
    This function gets called when the proxy starts up. For
    panos devices, a determination is made on the connection type
    and the appropriate connection details that must be cached.
    """
    if "host" not in opts["proxy"]:
        log.critical("No 'host' key found in pillar for this proxy.")
        return False
    if "apikey" not in opts["proxy"]:
        # If we do not have an apikey, we must have both a username and password
        if "username" not in opts["proxy"]:
            log.critical("No 'username' key found in pillar for this proxy.")
            return False
        if "password" not in opts["proxy"]:
            log.critical("No 'passwords' key found in pillar for this proxy.")
            return False

    DETAILS["url"] = "https://{0}/api/".format(opts["proxy"]["host"])

    # Set configuration details
    DETAILS["host"] = opts["proxy"]["host"]
    if "serial" in opts["proxy"]:
        DETAILS["serial"] = opts["proxy"].get("serial")
        if "apikey" in opts["proxy"]:
            log.debug("Selected pan_key method for panos proxy module.")
            DETAILS["method"] = "pan_key"
            DETAILS["apikey"] = opts["proxy"].get("apikey")
        else:
            log.debug("Selected pan_pass method for panos proxy module.")
            DETAILS["method"] = "pan_pass"
            DETAILS["username"] = opts["proxy"].get("username")
            DETAILS["password"] = opts["proxy"].get("password")
    else:
        if "apikey" in opts["proxy"]:
            log.debug("Selected dev_key method for panos proxy module.")
            DETAILS["method"] = "dev_key"
            DETAILS["apikey"] = opts["proxy"].get("apikey")
        else:
            log.debug("Selected dev_pass method for panos proxy module.")
            DETAILS["method"] = "dev_pass"
            DETAILS["username"] = opts["proxy"].get("username")
            DETAILS["password"] = opts["proxy"].get("password")

    # Ensure connectivity to the device
    log.debug("Attempting to connect to panos proxy host.")
    query = {"type": "op", "cmd": "<show><system><info></info></system></show>"}
    call(query)
    log.debug("Successfully connected to panos proxy host.")

    DETAILS["initialized"] = True


def call(payload=None):
    """
    This function captures the query string and sends it to the Palo Alto device.
    """
    r = None
    try:
        if DETAILS["method"] == "dev_key":
            # Pass the api key without the target declaration
            conditional_payload = {"key": DETAILS["apikey"]}
            payload.update(conditional_payload)
            r = __utils__["http.query"](
                DETAILS["url"],
                data=payload,
                method="POST",
                decode_type="plain",
                decode=True,
                verify_ssl=False,
                status=True,
                raise_error=True,
            )
        elif DETAILS["method"] == "dev_pass":
            # Pass credentials without the target declaration
            r = __utils__["http.query"](
                DETAILS["url"],
                username=DETAILS["username"],
                password=DETAILS["password"],
                data=payload,
                method="POST",
                decode_type="plain",
                decode=True,
                verify_ssl=False,
                status=True,
                raise_error=True,
            )
        elif DETAILS["method"] == "pan_key":
            # Pass the api key with the target declaration
            conditional_payload = {
                "key": DETAILS["apikey"],
                "target": DETAILS["serial"],
            }
            payload.update(conditional_payload)
            r = __utils__["http.query"](
                DETAILS["url"],
                data=payload,
                method="POST",
                decode_type="plain",
                decode=True,
                verify_ssl=False,
                status=True,
                raise_error=True,
            )
        elif DETAILS["method"] == "pan_pass":
            # Pass credentials with the target declaration
            conditional_payload = {"target": DETAILS["serial"]}
            payload.update(conditional_payload)
            r = __utils__["http.query"](
                DETAILS["url"],
                username=DETAILS["username"],
                password=DETAILS["password"],
                data=payload,
                method="POST",
                decode_type="plain",
                decode=True,
                verify_ssl=False,
                status=True,
                raise_error=True,
            )
    except KeyError as err:
        raise salt.exceptions.CommandExecutionError(
            "Did not receive a valid response from host."
        )

    if not r:
        raise salt.exceptions.CommandExecutionError(
            "Did not receive a valid response from host."
        )

    if six.text_type(r["status"]) not in ["200", "201", "204"]:
        if six.text_type(r["status"]) == "400":
            raise salt.exceptions.CommandExecutionError(
                "The server cannot process the request due to a client error."
            )
        elif six.text_type(r["status"]) == "401":
            raise salt.exceptions.CommandExecutionError(
                "The server cannot process the request because it lacks valid authentication "
                "credentials for the target resource."
            )
        elif six.text_type(r["status"]) == "403":
            raise salt.exceptions.CommandExecutionError(
                "The server refused to authorize the request."
            )
        elif six.text_type(r["status"]) == "404":
            raise salt.exceptions.CommandExecutionError(
                "The requested resource could not be found."
            )
        else:
            raise salt.exceptions.CommandExecutionError(
                "Did not receive a valid response from host."
            )

    xmldata = ET.fromstring(r["text"])

    # If we are pulling the candidate configuration, we need to strip the dirtyId
    if payload["type"] == "config" and payload["action"] == "get":
        xmldata = _strip_dirty(xmldata)

    return xml.to_dict(xmldata, True)


def is_required_version(required_version="0.0.0"):
    """
    Because different versions of Palo Alto support different command sets, this function
    will return true if the current version of Palo Alto supports the required command.
    """
    if "sw-version" in DETAILS["grains_cache"]:
        current_version = DETAILS["grains_cache"]["sw-version"]
    else:
        # If we do not have the current sw-version cached, we cannot check version requirements.
        return False

    required_version_split = required_version.split(".")
    current_version_split = current_version.split(".")

    try:
        if int(current_version_split[0]) > int(required_version_split[0]):
            return True
        elif int(current_version_split[0]) < int(required_version_split[0]):
            return False

        if int(current_version_split[1]) > int(required_version_split[1]):
            return True
        elif int(current_version_split[1]) < int(required_version_split[1]):
            return False

        if int(current_version_split[2]) > int(required_version_split[2]):
            return True
        elif int(current_version_split[2]) < int(required_version_split[2]):
            return False

        # We have an exact match
        return True
    except Exception as err:  # pylint: disable=broad-except
        return False


def initialized():
    """
    Since grains are loaded in many different places and some of those
    places occur before the proxy can be initialized, return whether
    our init() function has been called
    """
    return DETAILS.get("initialized", False)


def grains():
    """
    Get the grains from the proxied device
    """
    if not DETAILS.get("grains_cache", {}):
        DETAILS["grains_cache"] = GRAINS_CACHE
        try:
            query = {"type": "op", "cmd": "<show><system><info></info></system></show>"}
            DETAILS["grains_cache"] = call(query)["result"]["system"]
        except Exception as err:  # pylint: disable=broad-except
            pass
    return DETAILS["grains_cache"]


def grains_refresh():
    """
    Refresh the grains from the proxied device
    """
    DETAILS["grains_cache"] = None
    return grains()


def ping():
    """
    Returns true if the device is reachable, else false.
    """
    try:
        query = {"type": "op", "cmd": "<show><system><info></info></system></show>"}
        if "result" in call(query):
            return True
        else:
            return False
    except Exception as err:  # pylint: disable=broad-except
        return False


def shutdown():
    """
    Shutdown the connection to the proxy device. For this proxy,
    shutdown is a no-op.
    """
    log.debug("Panos proxy shutdown() called.")
