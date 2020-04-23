# -*- coding: utf-8 -*-
"""
Interface with a Junos device via proxy-minion. To connect to a junos device \
via junos proxy, specify the host information in the pillar in '/srv/pillar/details.sls'

.. code-block:: yaml

    proxy:
      proxytype: junos
      host: <ip or dns name of host>
      username: <username>
      port: 830
      password: <secret>

In '/srv/pillar/top.sls' map the device details with the proxy name.

.. code-block:: yaml

    base:
      'vmx':
        - details

After storing the device information in the pillar, configure the proxy \
in '/etc/salt/proxy'

.. code-block:: yaml

    master: <ip or hostname of salt-master>

Run the salt proxy via the following command:

.. code-block:: bash

    salt-proxy --proxyid=vmx


"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import 3rd-party libs
try:
    HAS_JUNOS = True
    import jnpr.junos
    import jnpr.junos.utils
    import jnpr.junos.utils.config
    import jnpr.junos.utils.sw
    from jnpr.junos.exception import (
        RpcTimeoutError,
        ConnectClosedError,
        RpcError,
        ConnectError,
        ProbeError,
        ConnectAuthError,
        ConnectRefusedError,
        ConnectTimeoutError,
    )
    from ncclient.operations.errors import TimeoutExpiredError
except ImportError:
    HAS_JUNOS = False

__proxyenabled__ = ["junos"]

thisproxy = {}

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "junos"


def __virtual__():
    """
    Only return if all the modules are available
    """
    if not HAS_JUNOS:
        return (
            False,
            "Missing dependency: The junos proxy minion requires the 'jnpr' Python module.",
        )

    return __virtualname__


def init(opts):
    """
    Open the connection to the Junos device, login, and bind to the
    Resource class
    """
    opts["multiprocessing"] = False
    log.debug("Opening connection to junos")

    args = {"host": opts["proxy"]["host"]}
    optional_args = [
        "user",
        "username",
        "password",
        "passwd",
        "port",
        "gather_facts",
        "mode",
        "baud",
        "attempts",
        "auto_probe",
        "ssh_private_key_file",
        "ssh_config",
        "normalize",
    ]

    if "username" in opts["proxy"].keys():
        opts["proxy"]["user"] = opts["proxy"].pop("username")
    proxy_keys = opts["proxy"].keys()
    for arg in optional_args:
        if arg in proxy_keys:
            args[arg] = opts["proxy"][arg]

    thisproxy["conn"] = jnpr.junos.Device(**args)
    try:
        thisproxy["conn"].open()
    except (
        ProbeError,
        ConnectAuthError,
        ConnectRefusedError,
        ConnectTimeoutError,
        ConnectError,
    ) as ex:
        log.error("{} : not able to initiate connection to the device".format(str(ex)))
        thisproxy["initialized"] = False
        return

    if "timeout" in proxy_keys:
        timeout = int(opts["proxy"]["timeout"])
        try:
            thisproxy["conn"].timeout = timeout
        except Exception as ex:  # pylint: disable=broad-except
            log.error("Not able to set timeout due to: %s", str(ex))
        else:
            log.debug("RPC timeout set to %d seconds", timeout)

    try:
        thisproxy["conn"].bind(cu=jnpr.junos.utils.config.Config)
    except Exception as ex:  # pylint: disable=broad-except
        log.error("Bind failed with Config class due to: {}".format(str(ex)))

    try:
        thisproxy["conn"].bind(sw=jnpr.junos.utils.sw.SW)
    except Exception as ex:  # pylint: disable=broad-except
        log.error("Bind failed with SW class due to: {}".format(str(ex)))
    thisproxy["initialized"] = True


def initialized():
    return thisproxy.get("initialized", False)


def conn():
    return thisproxy["conn"]


def alive(opts):
    """
    Validate and return the connection status with the remote device.

    .. versionadded:: 2018.3.0
    """

    dev = conn()

    thisproxy["conn"].connected = ping()

    if not dev.connected:
        __salt__["event.fire_master"](
            {}, "junos/proxy/{}/stop".format(opts["proxy"]["host"])
        )
    return dev.connected


def ping():
    """
    Ping?  Pong!
    """

    dev = conn()
    # Check that the underlying netconf connection still exists.
    if dev._conn is None:
        return False

    # call rpc only if ncclient queue is empty. If not empty that means other
    # rpc call is going on.
    if hasattr(dev._conn, "_session"):
        if dev._conn._session._transport.is_active():
            # there is no on going rpc call. buffer tell can be 1 as it stores
            # remaining char after "]]>]]>" which can be a new line char
            if dev._conn._session._buffer.tell() <= 1 and dev._conn._session._q.empty():
                return _rpc_file_list(dev)
            else:
                log.debug("skipped ping() call as proxy already getting data")
                return True
        else:
            # ssh connection is lost
            return False
    else:
        # other connection modes, like telnet
        return _rpc_file_list(dev)


def _rpc_file_list(dev):
    try:
        dev.rpc.file_list(path="/dev/null", dev_timeout=5)
        return True
    except (RpcTimeoutError, ConnectClosedError):
        try:
            dev.close()
            return False
        except (RpcError, ConnectError, TimeoutExpiredError):
            return False
    except AttributeError as ex:
        if "'NoneType' object has no attribute 'timeout'" in str(ex):
            return False


def proxytype():
    """
    Returns the name of this proxy
    """
    return "junos"


def get_serialized_facts():
    facts = dict(thisproxy["conn"].facts)
    if "version_info" in facts:
        facts["version_info"] = dict(facts["version_info"])
    # For backward compatibility. 'junos_info' is present
    # only of in newer versions of facts.
    if "junos_info" in facts:
        for re in facts["junos_info"]:
            facts["junos_info"][re]["object"] = dict(facts["junos_info"][re]["object"])
    return facts


def shutdown(opts):
    """
    This is called when the proxy-minion is exiting to make sure the
    connection to the device is closed cleanly.
    """
    log.debug("Proxy module %s shutting down!!", opts["id"])
    try:
        thisproxy["conn"].close()

    except Exception:  # pylint: disable=broad-except
        pass
