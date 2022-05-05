"""
Netmiko Execution Module
========================

.. versionadded:: 2019.2.0

Execution module to interface the connection with a remote network device. It is
flexible enough to execute the commands both when running under a Netmiko Proxy
Minion, as well as running under a Regular Minion by specifying the connection
arguments, i.e., ``device_type``, ``ip``, ``username``, ``password`` etc.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net> & Kirk Byers <ktbyers@twb-tech.com>
:maturity:   new
:depends:    netmiko
:platform:   unix

Dependencies
------------

The ``netmiko`` proxy modules requires Netmiko to be installed: ``pip install netmiko``.

Usage
-----

This module can equally be used via the :mod:`netmiko <salt.proxy.netmiko_px>`
Proxy module (check documentation), or directly from an arbitrary (Proxy) Minion
that is running on a server (computer) having access to the network device, and
has the ``netmiko`` library installed.

When running outside of the :mod:`netmiko Proxy <salt.proxy.netmiko_px>` (i.e.,
from another Proxy Minion type, or regular Minion), the netmiko connection
arguments can be either specified from the CLI when executing the command, or
in a configuration block under the ``netmiko`` key in the configuration opts
(i.e., (Proxy) Minion configuration file), or Pillar. The module supports these
simultaneously. These fields are the exact same supported by the ``netmiko``
Proxy Module:

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

Example (when not running in a ``netmiko`` Proxy Minion):

.. code-block:: yaml

  netmiko:
    username: test
    password: test

In case the ``username`` and ``password`` are the same on any device you are
targeting, the block above (besides other parameters specific to your
environment you might need) should suffice to be able to execute commands from
outside a ``netmiko`` Proxy, e.g.:

.. code-block:: bash

    salt '*' netmiko.send_command 'show version' host=router1.example.com device_type=juniper
    salt '*' netmiko.send_config https://bit.ly/2sgljCB host=sw2.example.com device_type=cisco_ios

.. note::

    Remember that the above applies only when not running in a ``netmiko`` Proxy
    Minion. If you want to use the :mod:`<salt.proxy.netmiko_px>`, please follow
    the documentation notes for a proper setup.
"""

import logging

import salt.utils.platform
from salt.exceptions import CommandExecutionError
from salt.utils.args import clean_kwargs

try:
    from netmiko import ConnectHandler
    from netmiko import BaseConnection

    HAS_NETMIKO = True
except ImportError:
    HAS_NETMIKO = False

# -----------------------------------------------------------------------------
# execution module properties
# -----------------------------------------------------------------------------

__proxyenabled__ = ["*"]
# Any Proxy Minion should be able to execute these (not only netmiko)

__virtualname__ = "netmiko"
# The Execution Module will be identified as ``netmiko``

# -----------------------------------------------------------------------------
# globals
# -----------------------------------------------------------------------------

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# propery functions
# -----------------------------------------------------------------------------


def __virtual__():
    """
    Execution module available only if Netmiko is installed.
    """
    if not HAS_NETMIKO:
        return (
            False,
            "The netmiko execution module requires netmiko library to be installed.",
        )
    if (
        salt.utils.platform.is_proxy()
        and __opts__["proxy"]["proxytype"] == "deltaproxy"
    ):
        return (
            False,
            "Unsupported proxy minion type.",
        )

    return __virtualname__


# -----------------------------------------------------------------------------
# helper functions
# -----------------------------------------------------------------------------


def _prepare_connection(**kwargs):
    """
    Prepare the connection with the remote network device, and clean up the key
    value pairs, removing the args used for the connection init.
    """
    init_args = {}
    fun_kwargs = {}
    netmiko_kwargs = __salt__["config.get"]("netmiko", {})
    netmiko_kwargs.update(kwargs)  # merge the CLI args with the opts/pillar
    netmiko_init_args, _, _, netmiko_defaults = __utils__["args.get_function_argspec"](
        BaseConnection.__init__
    )
    check_self = netmiko_init_args.pop(0)
    for karg, warg in netmiko_kwargs.items():
        if karg not in netmiko_init_args:
            if warg is not None:
                fun_kwargs[karg] = warg
            continue
        if warg is not None:
            init_args[karg] = warg
    conn = ConnectHandler(**init_args)
    return conn, fun_kwargs


# -----------------------------------------------------------------------------
# callable functions
# -----------------------------------------------------------------------------


def get_connection(**kwargs):
    """
    Return the Netmiko connection object.

    .. warning::

        This function returns an unserializable object, hence it is not meant
        to be used on the CLI. This should mainly be used when invoked from
        other modules for the low level connection with the network device.

    kwargs
        Key-value dictionary with the authentication details.

    USAGE Example:

    .. code-block:: python

        conn = __salt__['netmiko.get_connection'](host='router1.example.com',
                                                  username='example',
                                                  password='example')
        show_if = conn.send_command('show interfaces')
        conn.disconnect()
    """
    kwargs = clean_kwargs(**kwargs)
    if "netmiko.conn" in __proxy__:
        return __proxy__["netmiko.conn"]()
    conn, kwargs = _prepare_connection(**kwargs)
    return conn


def call(method, *args, **kwargs):
    """
    Invoke an arbitrary Netmiko method.

    method
        The name of the Netmiko method to invoke.

    args
        A list of arguments to send to the method invoked.

    kwargs
        Key-value dictionary to send to the method invoked.
    """
    kwargs = clean_kwargs(**kwargs)
    if "netmiko.call" in __proxy__:
        return __proxy__["netmiko.call"](method, *args, **kwargs)
    conn, kwargs = _prepare_connection(**kwargs)
    ret = getattr(conn, method)(*args, **kwargs)
    conn.disconnect()
    return ret


def multi_call(*methods, **kwargs):
    """
    Invoke multiple Netmiko methods at once, and return their output, as list.

    methods
        A list of dictionaries with the following keys:

        - ``name``: the name of the Netmiko method to be executed.
        - ``args``: list of arguments to be sent to the Netmiko method.
        - ``kwargs``: dictionary of arguments to be sent to the Netmiko method.

    kwargs
        Key-value dictionary with the connection details (when not running
        under a Proxy Minion).
    """
    kwargs = clean_kwargs(**kwargs)
    if "netmiko.conn" in __proxy__:
        conn = __proxy__["netmiko.conn"]()
    else:
        conn, kwargs = _prepare_connection(**kwargs)
    ret = []
    for method in methods:
        # Explicit unpacking
        method_name = method["name"]
        method_args = method.get("args", [])
        method_kwargs = method.get("kwargs", [])
        ret.append(getattr(conn, method_name)(*method_args, **method_kwargs))
    if "netmiko.conn" not in __proxy__:
        conn.disconnect()
    return ret


def send_command(command_string, **kwargs):
    """
    Execute command_string on the SSH channel using a pattern-based mechanism.
    Generally used for show commands. By default this method will keep waiting
    to receive data until the network device prompt is detected. The current
    network device prompt will be determined automatically.

    command_string
        The command to be executed on the remote device.

    expect_string
        Regular expression pattern to use for determining end of output.
        If left blank will default to being based on router prompt.

    delay_factor: ``1``
        Multiplying factor used to adjust delays (default: ``1``).

    max_loops: ``500``
        Controls wait time in conjunction with delay_factor. Will default to be
        based upon self.timeout.

    auto_find_prompt: ``True``
        Whether it should try to auto-detect the prompt (default: ``True``).

    strip_prompt: ``True``
        Remove the trailing router prompt from the output (default: ``True``).

    strip_command: ``True``
        Remove the echo of the command from the output (default: ``True``).

    normalize: ``True``
        Ensure the proper enter is sent at end of command (default: ``True``).

    use_textfsm: ``False``
        Process command output through TextFSM template (default: ``False``).

    CLI Example:

    .. code-block:: bash

        salt '*' netmiko.send_command 'show version'
        salt '*' netmiko.send_command 'show_version' host='router1.example.com' username='example' device_type='cisco_ios'
    """
    return call("send_command", command_string, **kwargs)


def send_command_timing(command_string, **kwargs):
    """
    Execute command_string on the SSH channel using a delay-based mechanism.
    Generally used for show commands.

    command_string
        The command to be executed on the remote device.

    delay_factor: ``1``
        Multiplying factor used to adjust delays (default: ``1``).

    max_loops: ``500``
        Controls wait time in conjunction with delay_factor. Will default to be
        based upon self.timeout.

    strip_prompt: ``True``
        Remove the trailing router prompt from the output (default: ``True``).

    strip_command: ``True``
        Remove the echo of the command from the output (default: ``True``).

    normalize: ``True``
        Ensure the proper enter is sent at end of command (default: ``True``).

    use_textfsm: ``False``
        Process command output through TextFSM template (default: ``False``).

    CLI Example:

    .. code-block:: bash

        salt '*' netmiko.send_command_timing 'show version'
        salt '*' netmiko.send_command_timing 'show version' host='router1.example.com' username='example' device_type='arista_eos'
    """
    return call("send_command_timing", command_string, **kwargs)


def enter_config_mode(**kwargs):
    """
    Enter into config mode.

    config_command
        Configuration command to send to the device.

    pattern
        Pattern to terminate reading of channel.

    CLI Example:

    .. code-block:: bash

        salt '*' netmiko.enter_config_mode
        salt '*' netmiko.enter_config_mode device_type='juniper_junos' ip='192.168.0.1' username='example'
    """
    return call("config_mode", **kwargs)


def exit_config_mode(**kwargs):
    """
    Exit from configuration mode.

    exit_config
        Command to exit configuration mode.

    pattern
        Pattern to terminate reading of channel.

    CLI Example:

    .. code-block:: bash

        salt '*' netmiko.exit_config_mode
        salt '*' netmiko.exit_config_mode device_type='juniper' ip='192.168.0.1' username='example'
    """
    return call("exit_config_mode", **kwargs)


def send_config(
    config_file=None,
    config_commands=None,
    template_engine="jinja",
    commit=False,
    context=None,
    defaults=None,
    saltenv="base",
    **kwargs
):
    """
    Send configuration commands down the SSH channel.
    Return the configuration lines sent to the device.

    The function is flexible to send the configuration from a local or remote
    file, or simply the commands as list.

    config_file
        The source file with the configuration commands to be sent to the
        device.

        The file can also be a template that can be rendered using the template
        engine of choice.

        This can be specified using the absolute path to the file, or using one
        of the following URL schemes:

        - ``salt://``, to fetch the file from the Salt fileserver.
        - ``http://`` or ``https://``
        - ``ftp://``
        - ``s3://``
        - ``swift://``

    config_commands
        Multiple configuration commands to be sent to the device.

        .. note::

            This argument is ignored when ``config_file`` is specified.

    template_engine: ``jinja``
        The template engine to use when rendering the source file. Default:
        ``jinja``. To simply fetch the file without attempting to render, set
        this argument to ``None``.

    commit: ``False``
        Commit the configuration changes before exiting the config mode. This
        option is by default disabled, as many platforms don't have this
        capability natively.

    context
        Variables to add to the template context.

    defaults
        Default values of the context_dict.

    exit_config_mode: ``True``
        Determines whether or not to exit config mode after complete.

    delay_factor: ``1``
        Factor to adjust delays.

    max_loops: ``150``
        Controls wait time in conjunction with delay_factor (default: ``150``).

    strip_prompt: ``False``
        Determines whether or not to strip the prompt (default: ``False``).

    strip_command: ``False``
        Determines whether or not to strip the command (default: ``False``).

    config_mode_command
        The command to enter into config mode.

    CLI Example:

    .. code-block:: bash

        salt '*' netmiko.send_config config_commands="['interface GigabitEthernet3', 'no ip address']"
        salt '*' netmiko.send_config config_commands="['snmp-server location {{ grains.location }}']"
        salt '*' netmiko.send_config config_file=salt://config.txt
        salt '*' netmiko.send_config config_file=https://bit.ly/2sgljCB device_type='cisco_ios' ip='1.2.3.4' username='example'
    """
    if config_file:
        file_str = __salt__["cp.get_file_str"](config_file, saltenv=saltenv)
        if file_str is False:
            raise CommandExecutionError("Source file {} not found".format(config_file))
    elif config_commands:
        if isinstance(config_commands, ((str,), str)):
            config_commands = [config_commands]
        file_str = "\n".join(config_commands)
        # unify all the commands in a single file, to render them in a go
    if template_engine:
        file_str = __salt__["file.apply_template_on_contents"](
            file_str, template_engine, context, defaults, saltenv
        )
    # whatever the source of the commands would be, split them line by line
    config_commands = [line for line in file_str.splitlines() if line.strip()]
    kwargs = clean_kwargs(**kwargs)
    if "netmiko.conn" in __proxy__:
        conn = __proxy__["netmiko.conn"]()
        if not conn or not conn.is_alive():
            conn, _ = _prepare_connection(**__proxy__["netmiko.args"]())
    else:
        conn, kwargs = _prepare_connection(**kwargs)
    if commit:
        kwargs["exit_config_mode"] = False  # don't exit config mode after
        # loading the commands, wait for explicit commit
    ret = conn.send_config_set(config_commands=config_commands, **kwargs)
    if commit:
        ret += conn.commit()
    return ret


def commit(**kwargs):
    """
    Commit the configuration changes.

    .. warning::

        This function is supported only on the platforms that support the
        ``commit`` operation.

    CLI Example:

    .. code-block:: bash

        salt '*' netmiko.commit
    """
    return call("commit", **kwargs)
