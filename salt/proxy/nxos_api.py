# -*- coding: utf-8 -*-
"""
Proxy Minion to manage Cisco Nexus Switches (NX-OS) over the NX-API

.. versionadded:: 2019.2.0

Proxy module for managing Cisco Nexus switches via the NX-API.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net>
:maturity:   new
:platform:   any

Usage
=====

.. note::

    To be able to use this module you need to enable to NX-API on your switch,
    by executing ``feature nxapi`` in configuration mode.

    Configuration example:

    .. code-block:: bash

        switch# conf t
        switch(config)# feature nxapi

    To check that NX-API is properly enabled, execute ``show nxapi``.

    Output example:

    .. code-block:: bash

        switch# show nxapi
        nxapi enabled
        HTTPS Listen on port 443

.. note::

    NX-API requires modern NXOS distributions, typically at least 7.0 depending
    on the hardware. Due to reliability reasons it is recommended to run the
    most recent version.

    Check https://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus7000/sw/programmability/guide/b_Cisco_Nexus_7000_Series_NX-OS_Programmability_Guide/b_Cisco_Nexus_7000_Series_NX-OS_Programmability_Guide_chapter_0101.html
    for more details.

Pillar
------

The ``nxos_api`` proxy configuration requires the following parameters in order
to connect to the network switch:

transport: ``https``
    Specifies the type of connection transport to use. Valid values for the
    connection are ``http``, and  ``https``.

host: ``localhost``
    The IP address or DNS host name of the connection device.

username: ``admin``
    The username to pass to the device to authenticate the NX-API connection.

password
    The password to pass to the device to authenticate the NX-API connection.

port
    The TCP port of the endpoint for the NX-API connection. If this keyword is
    not specified, the default value is automatically determined by the
    transport type (``80`` for ``http``, or ``443`` for ``https``).

timeout: ``60``
    Time in seconds to wait for the device to respond. Default: 60 seconds.

verify: ``True``
    Either a boolean, in which case it controls whether we verify the NX-API
    TLS certificate, or a string, in which case it must be a path to a CA bundle
    to use. Defaults to ``True``.

    When there is no certificate configuration on the device and this option is
    set as ``True`` (default), the commands will fail with the following error:
    ``SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (_ssl.c:581)``.
    In this case, you either need to configure a proper certificate on the
    device (*recommended*), or bypass the checks setting this argument as ``False``
    with all the security risks considered.

    Check https://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus3000/sw/programmability/6_x/b_Cisco_Nexus_3000_Series_NX-OS_Programmability_Guide/b_Cisco_Nexus_3000_Series_NX-OS_Programmability_Guide_chapter_01.html
    to see how to properly configure the certificate.

All the arguments may be optional, depending on your setup.

Proxy Pillar Example
--------------------

.. code-block:: yaml

    proxy:
      proxytype: nxos_api
      host: switch1.example.com
      username: example
      password: example
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python stdlib
import copy
import logging

# Import Salt modules
from salt.exceptions import SaltException

# -----------------------------------------------------------------------------
# proxy properties
# -----------------------------------------------------------------------------

__proxyenabled__ = ["nxos_api"]
# proxy name

# -----------------------------------------------------------------------------
# globals
# -----------------------------------------------------------------------------

__virtualname__ = "nxos_api"
log = logging.getLogger(__name__)
nxos_device = {}

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
    Open the connection to the Nexsu switch over the NX-API.

    As the communication is HTTP based, there is no connection to maintain,
    however, in order to test the connectivity and make sure we are able to
    bring up this Minion, we are executing a very simple command (``show clock``)
    which doesn't come with much overhead and it's sufficient to confirm we are
    indeed able to connect to the NX-API endpoint as configured.
    """
    proxy_dict = opts.get("proxy", {})
    conn_args = copy.deepcopy(proxy_dict)
    conn_args.pop("proxytype", None)
    opts["multiprocessing"] = conn_args.pop("multiprocessing", True)
    # This is not a SSH-based proxy, so it should be safe to enable
    # multiprocessing.
    try:
        rpc_reply = __utils__["nxos_api.rpc"]("show clock", **conn_args)
        # Execute a very simple command to confirm we are able to connect properly
        nxos_device["conn_args"] = conn_args
        nxos_device["initialized"] = True
        nxos_device["up"] = True
    except SaltException:
        log.error("Unable to connect to %s", conn_args["host"], exc_info=True)
        raise
    return True


def ping():
    """
    Connection open successfully?
    """
    return nxos_device.get("up", False)


def initialized():
    """
    Connection finished initializing?
    """
    return nxos_device.get("initialized", False)


def shutdown(opts):
    """
    Closes connection with the device.
    """
    log.debug("Shutting down the nxos_api Proxy Minion %s", opts["id"])


# -----------------------------------------------------------------------------
# callable functions
# -----------------------------------------------------------------------------


def get_conn_args():
    """
    Returns the connection arguments of the Proxy Minion.
    """
    conn_args = copy.deepcopy(nxos_device["conn_args"])
    return conn_args


def rpc(commands, method="cli", **kwargs):
    """
    Executes an RPC request over the NX-API.
    """
    conn_args = nxos_device["conn_args"]
    conn_args.update(kwargs)
    return __utils__["nxos_api.rpc"](commands, method=method, **conn_args)
