"""
Execution module to manage Cisco Nexus Switches (NX-OS) over the NX-API

.. versionadded:: 2019.2.0

Execution module used to interface the interaction with a remote or local Nexus
switch whether we're running in a Proxy Minion or regular Minion (or regular
Minion running directly on the Nexus switch).

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net>
:maturity:   new
:platform:   any

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

Usage
-----

This module can equally be used via the :mod:`nxos_api<salt.proxy.nxos_api>`
Proxy module or directly from an arbitrary (Proxy) Minion that is running on a
machine having access to the network device API. Given that there are no
external dependencies, this module can very well used when using the regular
Salt Minion directly installed on the switch.

When running outside of the :mod:`nxos_api Proxy<salt.proxy.nxos_api>`
(i.e., from another Proxy Minion type, or regular Minion), the NX-API connection
arguments can be either specified from the CLI when executing the command, or
in a configuration block under the ``nxos_api`` key in the configuration opts
(i.e., (Proxy) Minion configuration file), or Pillar. The module supports these
simultaneously. These fields are the exact same supported by the ``nxos_api``
Proxy Module:

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

Example (when not running in a ``nxos_api`` Proxy Minion):

.. code-block:: yaml

  nxos_api:
    username: test
    password: test

In case the ``username`` and ``password`` are the same on any device you are
targeting, the block above (besides other parameters specific to your
environment you might need) should suffice to be able to execute commands from
outside a ``nxos_api`` Proxy, e.g.:

.. code-block:: bash

    salt-call --local nxos_api.show 'show lldp neighbors' raw_text
    # The command above is available when running in a regular Minion where Salt is installed

    salt '*' nxos_api.show 'show version' raw_text=False

.. note::

    Remember that the above applies only when not running in a ``nxos_api`` Proxy
    Minion. If you want to use the :mod:`nxos_api Proxy<salt.proxy.nxos_api>`,
    please follow the documentation notes for a proper setup.
"""

import difflib
import logging

from salt.exceptions import CommandExecutionError, SaltException

# -----------------------------------------------------------------------------
# execution module properties
# -----------------------------------------------------------------------------

__proxyenabled__ = ["*"]
# Any Proxy Minion should be able to execute these

__virtualname__ = "nxos_api"
# The Execution Module will be identified as ``nxos_api``
# The ``nxos`` namespace is already taken, used for SSH-based connections.

# -----------------------------------------------------------------------------
# globals
# -----------------------------------------------------------------------------

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# propery functions
# -----------------------------------------------------------------------------


def __virtual__():
    """
    This module does not have external dependencies, hence it is widely
    available.
    """
    # No extra requirements, uses Salt native modules.
    return __virtualname__


# -----------------------------------------------------------------------------
# helper functions
# -----------------------------------------------------------------------------


def _cli_command(commands, method="cli", **kwargs):
    """
    Execute a list of CLI commands.
    """
    if not isinstance(commands, (list, tuple)):
        commands = [commands]
    rpc_responses = rpc(commands, method=method, **kwargs)
    txt_responses = []
    for rpc_reponse in rpc_responses:
        error = rpc_reponse.get("error")
        if error:
            cmd = rpc_reponse.get("command")
            if "data" in error:
                msg = 'The command "{cmd}" raised the error "{err}".'.format(
                    cmd=cmd, err=error["data"]["msg"]
                )
                raise SaltException(msg)
            else:
                msg = f'Invalid command: "{cmd}".'
                raise SaltException(msg)
        txt_responses.append(rpc_reponse["result"])
    return txt_responses


# -----------------------------------------------------------------------------
# callable functions
# -----------------------------------------------------------------------------


def rpc(commands, method="cli", **kwargs):
    """
    Execute an arbitrary RPC request via the Nexus API.

    commands
        The commands to be executed.

    method: ``cli``
        The type of the response, i.e., raw text (``cli_ascii``) or structured
        document (``cli``). Defaults to ``cli`` (structured data).

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

    CLI Example:

    .. code-block:: bash

        salt-call --local nxos_api.rpc 'show version'
    """
    nxos_api_kwargs = __salt__["config.get"]("nxos_api", {})
    nxos_api_kwargs.update(**kwargs)
    if (
        "nxos_api.rpc" in __proxy__
        and __salt__["config.get"]("proxy:proxytype") == "nxos_api"
    ):
        # If the nxos_api.rpc Proxy function is available and currently running
        # in a nxos_api Proxy Minion
        return __proxy__["nxos_api.rpc"](commands, method=method, **nxos_api_kwargs)
    nxos_api_kwargs = __salt__["config.get"]("nxos_api", {})
    nxos_api_kwargs.update(**kwargs)
    return __utils__["nxos_api.rpc"](commands, method=method, **nxos_api_kwargs)


def show(commands, raw_text=True, **kwargs):
    """
    Execute one or more show (non-configuration) commands.

    commands
        The commands to be executed.  Multiple commands should
        be specified as a list.

    raw_text: ``True``
        Whether to return raw text or structured data.

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

    CLI Example:

    .. code-block:: bash

        salt-call --local nxos_api.show 'show version'
        salt '*' nxos_api.show "['show bgp sessions','show processes']" raw_text=False
        salt 'regular-minion' nxos_api.show 'show interfaces' host=sw01.example.com username=test password=test
    """
    ret = []
    if raw_text:
        method = "cli_ascii"
        key = "msg"
    else:
        method = "cli"
        key = "body"
    response_list = _cli_command(commands, method=method, **kwargs)
    ret = [response[key] for response in response_list if response]
    return ret


def config(
    commands=None,
    config_file=None,
    template_engine="jinja",
    context=None,
    defaults=None,
    saltenv="base",
    **kwargs,
):
    """
    Configures the Nexus switch with the specified commands.

    This method is used to send configuration commands to the switch.  It
    will take either a string or a list and prepend the necessary commands
    to put the session into config mode.

    .. warning::

        All the commands will be applied directly into the running-config.

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

    commands
        The commands to send to the switch in config mode.  If the commands
        argument is a string it will be cast to a list.
        The list of commands will also be prepended with the necessary commands
        to put the session in config mode.

        .. note::

            This argument is ignored when ``config_file`` is specified.

    template_engine: ``jinja``
        The template engine to use when rendering the source file. Default:
        ``jinja``. To simply fetch the file without attempting to render, set
        this argument to ``None``.

    context
        Variables to add to the template context.

    defaults
        Default values of the context_dict.

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

    CLI Example:

    .. code-block:: bash

        salt '*' nxos_api.config commands="['spanning-tree mode mstp']"
        salt '*' nxos_api.config config_file=salt://config.txt
        salt '*' nxos_api.config config_file=https://bit.ly/2LGLcDy context="{'servers': ['1.2.3.4']}"
    """
    initial_config = show("show running-config", **kwargs)[0]
    if config_file:
        file_str = __salt__["cp.get_file_str"](config_file, saltenv=saltenv)
        if file_str is False:
            raise CommandExecutionError(f"Source file {config_file} not found")
    elif commands:
        if isinstance(commands, str):
            commands = [commands]
        file_str = "\n".join(commands)
        # unify all the commands in a single file, to render them in a go
    if template_engine:
        file_str = __salt__["file.apply_template_on_contents"](
            file_str, template_engine, context, defaults, saltenv
        )
    # whatever the source of the commands would be, split them line by line
    commands = [line for line in file_str.splitlines() if line.strip()]
    ret = _cli_command(commands, **kwargs)
    current_config = show("show running-config", **kwargs)[0]
    diff = difflib.unified_diff(
        initial_config.splitlines(1)[4:], current_config.splitlines(1)[4:]
    )
    return "".join([x.replace("\r", "") for x in diff])
