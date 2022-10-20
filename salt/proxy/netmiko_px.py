"""
Netmiko
=======

.. versionadded:: 2019.2.0

Proxy module for managing network devices via
`Netmiko <https://github.com/ktbyers/netmiko>`_.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net> & Kirk Byers <ktbyers@twb-tech.com>
:maturity:   new
:depends:    netmiko
:platform:   unix

Dependencies
------------

The ``netmiko`` proxy modules requires Netmiko to be installed: ``pip install netmiko``.

Pillar
------

The ``netmiko`` proxy configuration requires the following parameters in order
to connect to the network device:

- ``device_type`` - Class selection based on device type. Supported options:

  - ``a10``: A10 Networks
  - ``accedian``: Accedian Networks
  - ``alcatel_aos``: Alcatel AOS
  - ``alcatel_sros``: Alcatel SROS
  - ``apresia_aeos``: Apresia AEOS
  - ``arista_eos``: Arista EOS
  - ``aruba_os``: Aruba
  - ``avaya_ers``: Avaya ERS
  - ``avaya_vsp``: Avaya VSP
  - ``brocade_fastiron``: Brocade Fastiron
  - ``brocade_netiron``: Brocade Netiron
  - ``brocade_nos``: Brocade NOS
  - ``brocade_vdx``: Brocade NOS
  - ``brocade_vyos``: VyOS
  - ``checkpoint_gaia``: Check Point GAiA
  - ``calix_b6``: Calix B6
  - ``ciena_saos``: Ciena SAOS
  - ``cisco_asa``: Cisco SA
  - ``cisco_ios``: Cisco IOS
  - ``cisco_nxos``: Cisco NX-oS
  - ``cisco_s300``: Cisco S300
  - ``cisco_tp``: Cisco TpTcCe
  - ``cisco_wlc``: Cisco WLC
  - ``cisco_xe``: Cisco IOS
  - ``cisco_xr``: Cisco XR
  - ``coriant``: Coriant
  - ``dell_force10``: Dell Force10
  - ``dell_os10``: Dell OS10
  - ``dell_powerconnect``: Dell PowerConnect
  - ``eltex``: Eltex
  - ``enterasys``: Enterasys
  - ``extreme``: Extreme
  - ``extreme_wing``: Extreme Wing
  - ``f5_ltm``: F5 LTM
  - ``fortinet``: Fortinet
  - ``generic_termserver``: TerminalServer
  - ``hp_comware``: HP Comware
  - ``hp_procurve``: HP Procurve
  - ``huawei``: Huawei
  - ``huawei_vrpv8``: Huawei VRPV8
  - ``juniper``: Juniper Junos
  - ``juniper_junos``: Juniper Junos
  - ``linux``: Linux
  - ``mellanox``: Mellanox
  - ``mrv_optiswitch``: MrvOptiswitch
  - ``netapp_cdot``: NetAppcDot
  - ``netscaler``: Netscaler
  - ``ovs_linux``: OvsLinux
  - ``paloalto_panos``: PaloAlto Panos
  - ``pluribus``: Pluribus
  - ``quanta_mesh``: Quanta Mesh
  - ``ruckus_fastiron``: Ruckus Fastiron
  - ``ubiquiti_edge``: Ubiquiti Edge
  - ``ubiquiti_edgeswitch``: Ubiquiti Edge
  - ``vyatta_vyos``: VyOS
  - ``vyos``: VyOS
  - ``brocade_fastiron_telnet``: Brocade Fastiron over Telnet
  - ``brocade_netiron_telnet``: Brocade Netiron over Telnet
  - ``cisco_ios_telnet``: Cisco IOS over Telnet
  - ``apresia_aeos_telnet``: Apresia AEOS over Telnet
  - ``arista_eos_telnet``: Arista EOS over Telnet
  - ``hp_procurve_telnet``: HP Procurve over Telnet
  - ``hp_comware_telnet``: HP Comware over Telnet
  - ``juniper_junos_telnet``: Juniper Junos over Telnet
  - ``calix_b6_telnet``: Calix B6 over Telnet
  - ``dell_powerconnect_telnet``: Dell PowerConnect over Telnet
  - ``generic_termserver_telnet``: TerminalServer over Telnet
  - ``extreme_telnet``: Extreme Networks over Telnet
  - ``ruckus_fastiron_telnet``: Ruckus Fastiron over Telnet
  - ``cisco_ios_serial``: Cisco IOS over serial port

- ``ip`` - IP address of target device (not required if ``host`` is provided)

- ``host`` - Hostname of target device (not required if ``ip`` is provided)

- ``username`` - Username to authenticate against target device, if required

- ``password`` - Password to authenticate against target device, if required

- ``secret`` - The enable password if target device requires one

- ``port`` - The destination port used to connect to the target device

- ``global_delay_factor`` - Multiplication factor affecting Netmiko delays
  (default: ``1``)

- ``use_keys`` - Connect to target device using SSH keys (default: ``False``)

- ``key_file`` - Filename path of the SSH key file to use

- ``allow_agent`` - Enable use of SSH key-agent

- ``ssh_strict`` - Automatically reject unknown SSH host keys (default:
  ``False``, which means unknown SSH host keys will be accepted)

- ``system_host_keys`` - Load host keys from the user's "known_hosts" file
  (default: ``False``)

- ``alt_host_keys`` - If ``True``,  host keys will be loaded from the file
  specified in ``alt_key_file`` (default: ``False``)

- ``alt_key_file`` - SSH host key file to use (if ``alt_host_keys=True``)

- ``ssh_config_file`` - File name of OpenSSH configuration file

- ``timeout`` - Connection timeout, in seconds (default: ``90``)

- ``session_timeout`` - Set a timeout for parallel requests, in seconds
  (default: ``60``)

- ``keepalive`` - Send SSH keepalive packets at a specific interval, in
  seconds. Currently defaults to ``0``, for backwards compatibility (it will
  not attempt to keep the connection alive using the KEEPALIVE packets).

- ``default_enter`` - Character(s) to send to correspond to enter key (default:
  ``\\n``)

- ``response_return`` - Character(s) to use in normalized return data to
  represent enter key (default: ``\\n``)

- ``always_alive`` - In certain less dynamic environments, maintaining the
  remote connection permanently open with the network device is not always
  beneficial. In that case, the user can select to initialize the connection
  only when needed, by setting this option to ``False``. By default this option
  is set to ``True`` (maintains the connection with the remote network device)

- ``multiprocessing`` - Overrides the :conf_minion:`multiprocessing` option,
  per proxy minion, as the Netmiko communication channel is mainly SSH
  (default: ``False``)

- ``connection_timeout`` - The number of seconds to attempt to connect to
  the device in seconds.
  (default: ``300``)

Proxy Pillar Example
--------------------

.. code-block:: yaml

    proxy:
      proxytype: netmiko
      device_type: juniper_junos
      host: router1.example.com
      username: example
      password: example

.. code-block:: yaml

    proxy:
      proxytype: netmiko
      device_type: cisco_ios
      ip: 1.2.3.4
      username: test
      use_keys: true
      secret: w3@k
"""

import contextlib
import logging
import time

import salt.utils.args

try:
    from netmiko import ConnectHandler

    try:
        from netmiko import NetMikoAuthenticationException, NetMikoTimeoutException
    except ImportError:
        from netmiko.ssh_exception import (
            NetMikoAuthenticationException,
            NetMikoTimeoutException,
        )

    HAS_NETMIKO = True
except ImportError:
    HAS_NETMIKO = False


# -----------------------------------------------------------------------------
# proxy properties
# -----------------------------------------------------------------------------

__proxyenabled__ = ["netmiko"]
# proxy name

# -----------------------------------------------------------------------------
# globals
# -----------------------------------------------------------------------------

__virtualname__ = "netmiko"
log = logging.getLogger(__name__)
netmiko_device = {}

DEFAULT_CONNECTION_TIMEOUT = 300

# -----------------------------------------------------------------------------
# propery functions
# -----------------------------------------------------------------------------


def __virtual__():
    """
    Proxy module available only if Netmiko is installed.
    """
    if not HAS_NETMIKO:
        return (
            False,
            "The netmiko proxy module requires netmiko library to be installed.",
        )
    return __virtualname__


# -----------------------------------------------------------------------------
# proxy functions
# -----------------------------------------------------------------------------


def init(opts):
    """
    Open the connection to the network device
    managed through netmiko.
    """
    __context__["netmiko_device"] = {}
    __context__["netmiko_device"]["opts"] = opts
    __context__["netmiko_device"]["id"] = opts["id"]
    log.debug("Init for %s", opts["id"])
    proxy_dict = opts.get("proxy", {})
    skip_connect = opts.get(
        "skip_connect_on_init", proxy_dict.get("skip_connect_on_init", False)
    )
    opts["multiprocessing"] = proxy_dict.get(
        "multiprocessing", opts.get("multiprocessing", False)
    )
    __context__["netmiko_device"]["connection_timeout"] = opts.get(
        "connection_timeout", DEFAULT_CONNECTION_TIMEOUT
    )

    netmiko_connection_args = proxy_dict.copy()
    netmiko_connection_args.pop("proxytype", None)
    netmiko_connection_args.pop("multiprocessing", None)
    netmiko_connection_args.pop("skip_connect_on_init", None)
    netmiko_connection_args.pop("connection_timeout", None)

    __context__["netmiko_device"]["args"] = netmiko_connection_args

    _always_alive = netmiko_connection_args.pop(
        "always_alive", opts.get("proxy_always_alive", True)
    )
    __context__["netmiko_device"]["always_alive"] = _always_alive

    if not skip_connect:
        try:
            with make_con() as con:
                __context__["netmiko_device"]["connection"] = con
                __context__["netmiko_device"]["initialized"] = True
                __context__["netmiko_device"]["up"] = True
        except NetMikoTimeoutException as t_err:
            log.error("Unable to setup the netmiko connection", exc_info=True)
        except NetMikoAuthenticationException as au_err:
            log.error("Unable to setup the netmiko connection", exc_info=True)
    else:
        __context__["netmiko_device"]["up"] = True
        __context__["netmiko_device"]["initialized"] = False
        return True


def make_con(connection_timeout=DEFAULT_CONNECTION_TIMEOUT):
    log.error("Creating connection to %s", __context__["netmiko_device"]["id"])
    args = __context__["netmiko_device"]["args"]
    start = time.time()
    args = args.copy()
    found_exception = None
    connection = None
    while True:
        try:
            connection = ConnectHandler(**args)
        except Exception as exc:  # pylint: disable=broad-except
            log.warning("Got exception %r", exc)
            found_exception = exc
        else:
            break
        if time.time() - start >= connection_timeout:
            if found_exception:
                raise found_exception
            else:
                raise Exception("Unable to create connection")
    return connection


@contextlib.contextmanager
def connection(connection_timeout=DEFAULT_CONNECTION_TIMEOUT):
    if "connection" in __context__["netmiko_device"]:
        con = __context__["netmiko_device"]["connection"]
        if con.remote_conn is None:
            con = make_con(connection_timeout)
            __context__["netmiko_device"]["connection"] = con
        if con.remote_conn.closed:
            con = make_con()
            __context__["netmiko_device"]["connection"] = con
    else:
        con = make_con(connection_timeout)
        __context__["netmiko_device"]["connection"] = con
    __context__["netmiko_device"]["initialized"] = True
    try:
        yield con
    finally:
        if not __context__["netmiko_device"]["always_alive"]:
            con.disconnect()


def alive(opts):
    """
    Return the connection status with the network device.
    """
    log.debug("Checking if %s is still alive", opts.get("id", ""))
    connection_timeout = __context__["netmiko_device"]["connection_timeout"]

    if not __context__["netmiko_device"]["always_alive"]:
        return True
    if ping() and initialized():
        with connection(connection_timeout) as con:
            return con.remote_conn.transport.is_alive()
    return False


def ping():
    """
    Connection open successfully?
    """
    return __context__["netmiko_device"].get("up", False)


def initialized():
    """
    Connection finished initializing?
    """
    return __context__["netmiko_device"].get("initialized", False)


def shutdown(opts):
    """
    Closes connection with the device.
    """
    return call("disconnect")


# -----------------------------------------------------------------------------
# callable functions
# -----------------------------------------------------------------------------


def conn():
    """
    Return the connection object.
    """
    return __context__["netmiko_device"].get("connection")


def args():
    """
    Return the Netmiko device args.
    """
    return __context__["netmiko_device"]["args"]


def call(method, *args, **kwargs):
    """
    Calls an arbitrary netmiko method.
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    connection_timeout = __context__["netmiko_device"]["connection_timeout"]

    with connection(connection_timeout) as con:
        return getattr(con, method)(*args, **kwargs)
