"""
Proxy Minion to manage RESTCONF Devices

:codeauthor: Jamie (Bear) Murphy <jamiemurphyit@gmail.com>
:maturity:   new
:platform:   any

Usage
=====

.. note::

    To be able to use this module you need to enable RESTCONF on your device
    and have https enabled.

    Cisco Configuration example:

    .. code-block:: bash

        switch# conf t
        switch(config)# restconf
        switch(config)# ip http secure-server

.. note::

    RESTCONF requires modern OS distributions.
    This plugin has been written specifically to use JSON RESTCONF endpoints

Pillar
------

The ``restconf`` proxy configuration requires the following parameters in order
to connect to the network switch:

transport: ``https`` (str)
    Specifies the type of connection transport to use. Valid values for the
    connection are ``https``, and  ``http``.
    The RESTCONF standard explicitly requires https, but http is included as an option
    as some manufacturers have ignored this requirement.

hostname: (str)
    The IP address or DNS host name of the RESTCONF device.

username: (str)
    The username for the device to authenticate the RESTCONF requests.

password: (str)
    The password for the device to authenticate the RESTCONF requests.

verify: ``True`` or ``False`` (str, optional, default:true)
    Verify the RESTCONF SSL certificate?

    When there is no certificate configuration on the device and this option is
    set as ``True`` (default), the commands will fail with the following error:
    ``SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed``.

    .. warning::
      In this case, you either need to configure a proper certificate on the
      device (*recommended*), or bypass the checks setting this argument as ``False``
      with all the security risks considered as you may be MITM'd.

Proxy Pillar Example
--------------------

.. code-block:: yaml

    proxy:
      proxytype: restconf
      host: switch1.example.com
      username: example
      password: example
      verify: false
"""


import copy
import json
import logging

import salt.utils.http

# Import Salt modules
from salt.exceptions import SaltException

# -----------------------------------------------------------------------------
# proxy properties
# -----------------------------------------------------------------------------

__proxyenabled__ = ["restconf"]
# proxy name

# -----------------------------------------------------------------------------
# globals
# -----------------------------------------------------------------------------

__virtualname__ = "restconf"
log = logging.getLogger(__file__)
restconf_device = {}

# -----------------------------------------------------------------------------
# property functions
# -----------------------------------------------------------------------------


def __virtual__():
    """
    This Proxy Module is widely available as there are no external dependencies.
    """
    return __virtualname__


# -----------------------------------------------------------------------------
# proxy functions
# -----------------------------------------------------------------------------


def init(opts):
    """
    Required.
    Initialize device config and test an initial connection
    """
    log.debug("RESTCONF proxy init(opts) called...")
    # Open the connection to the RESTCONF Device.
    # As the communication is HTTP based, there is no connection to maintain,
    # however, in order to test the connectivity and make sure we are able to
    # bring up this Minion, we are checking the standard RESTCONF state path.

    conn_args = copy.deepcopy(opts.get("proxy", {}))
    opts["multiprocessing"] = conn_args.pop("multiprocessing", True)
    # This is not a SSH-based proxy, so it should be safe to enable
    # multiprocessing.

    # Proxy minimum init variables
    if "hostname" not in conn_args:
        log.critical("No 'hostname' key found in pillar for this proxy.")
        return False
    if "username" not in conn_args:
        log.critical("No 'username' key found in pillar for this proxy.")
        return False
    if "password" not in conn_args:
        log.critical("No 'password' key found in pillar for this proxy.")
        return False
    if "verify" not in conn_args:
        conn_args["verify"] = True
    if "transport" not in conn_args:
        conn_args["transport"] = "https"

    restconf_device["conn_args"] = conn_args
    try:
        response = connection_test()
        if response[0]:
            # Execute a very simple command to confirm we are able to connect properly
            restconf_device["initialized"] = True
            restconf_device["up"] = True
            log.info("Connected to %s", conn_args["hostname"], exc_info=True)

        else:
            restconf_device["initialized"] = False
            restconf_device["up"] = False
            log.error("Unable to connect to %s", conn_args["hostname"], exc_info=True)
    except SaltException:
        log.error("Unable to connect to %s", conn_args["hostname"], exc_info=True)
        raise


def connection_test():
    """
    Runs a connection test via http/https. Returns an array.
    """
    log.debug("RESTCONF proxy connection_test() called...")
    response = request("restconf/yang-library-version", method="GET", dict_payload=None)

    if "yang-library-version" in str(response):
        return True, response
    else:
        return False, response


def ping():
    """
    Triggers connection test.
    Returns True or False
    """
    log.debug("RESTCONF proxy ping() called...")
    # Connection open successfully?
    return connection_test()[0]


def initialized():
    """
    Connection finished initializing?
    """
    return restconf_device.get("initialized", False)


def shutdown(opts):
    """
    Closes connection with the device.
    """
    log.debug("Shutting down the RESTCONF Proxy Minion %s", opts["id"])


# -----------------------------------------------------------------------------
# callable functions
# -----------------------------------------------------------------------------


def request(path, method="GET", dict_payload=None):
    """
    Trigger http request to device
    """
    if dict_payload is None:
        data = ""
    elif isinstance(dict_payload, str):
        data = dict_payload
    else:
        data = json.dumps(dict_payload)
    response = salt.utils.http.query(
        "{transport}://{hostname}/{path}".format(
            path=path,
            **restconf_device["conn_args"],
        ),
        method=method,
        data=data,
        decode=True,
        status=True,
        verify_ssl=restconf_device["conn_args"]["verify"],
        username=restconf_device["conn_args"]["username"],
        password=restconf_device["conn_args"]["password"],
        header_list=[
            "Accept: application/yang-data+json,application/yang.data+json",
            "Content-Type: application/yang-data+json",
        ],
    )
    log.debug("proxy_restconf_request_response: %s", response)
    return response
