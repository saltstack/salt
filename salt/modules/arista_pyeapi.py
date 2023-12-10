"""
Arista pyeapi
=============

.. versionadded:: 2019.2.0

Execution module to interface the connection with Arista switches, connecting to
the remote network device using the
`pyeapi <http://pyeapi.readthedocs.io/en/master/index.html>`_ library. It is
flexible enough to execute the commands both when running under an Arista Proxy
Minion, as well as running under a Regular Minion by specifying the connection
arguments, i.e., ``device_type``, ``host``, ``username``, ``password`` etc.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net>
:maturity:   new
:depends:    pyeapi
:platform:   unix

.. note::

    To understand how to correctly enable the eAPI on your switch, please check
    https://eos.arista.com/arista-eapi-101/.

Dependencies
------------

The ``pyeapi`` Execution module requires the Python Client for eAPI (pyeapi) to
be installed: ``pip install pyeapi``.

Usage
-----

This module can equally be used via the :mod:`pyeapi <salt.proxy.arista_pyeapi>`
Proxy module or directly from an arbitrary (Proxy) Minion that is running on a
machine having access to the network device API, and the ``pyeapi`` library is
installed.

When running outside of the :mod:`pyeapi Proxy <salt.proxy.arista_pyeapi>`
(i.e., from another Proxy Minion type, or regular Minion), the pyeapi connection
arguments can be either specified from the CLI when executing the command, or
in a configuration block under the ``pyeapi`` key in the configuration opts
(i.e., (Proxy) Minion configuration file), or Pillar. The module supports these
simultaneously. These fields are the exact same supported by the ``pyeapi``
Proxy Module:

transport: ``https``
    Specifies the type of connection transport to use. Valid values for the
    connection are ``socket``, ``http_local``, ``http``, and  ``https``.

host: ``localhost``
    The IP address or DNS host name of the connection device.

username: ``admin``
    The username to pass to the device to authenticate the eAPI connection.

password
    The password to pass to the device to authenticate the eAPI connection.

port
    The TCP port of the endpoint for the eAPI connection. If this keyword is
    not specified, the default value is automatically determined by the
    transport type (``80`` for ``http``, or ``443`` for ``https``).

enablepwd
    The enable mode password if required by the destination node.

Example (when not running in a ``pyeapi`` Proxy Minion):

.. code-block:: yaml

  pyeapi:
    username: test
    password: test

In case the ``username`` and ``password`` are the same on any device you are
targeting, the block above (besides other parameters specific to your
environment you might need) should suffice to be able to execute commands from
outside a ``pyeapi`` Proxy, e.g.:

.. code-block:: bash

    salt '*' pyeapi.run_commands 'show version' 'show interfaces'
    salt '*' pyeapi.config 'ntp server 1.2.3.4'

.. note::

    Remember that the above applies only when not running in a ``pyeapi`` Proxy
    Minion. If you want to use the :mod:`pyeapi Proxy <salt.proxy.arista_pyeapi>`,
    please follow the documentation notes for a proper setup.
"""

import difflib
import logging

from salt.exceptions import CommandExecutionError
from salt.utils.args import clean_kwargs

try:
    import pyeapi

    HAS_PYEAPI = True
except ImportError:
    HAS_PYEAPI = False

# -----------------------------------------------------------------------------
# execution module properties
# -----------------------------------------------------------------------------

__proxyenabled__ = ["*"]
# Any Proxy Minion should be able to execute these

__virtualname__ = "pyeapi"
# The Execution Module will be identified as ``pyeapi``

# -----------------------------------------------------------------------------
# globals
# -----------------------------------------------------------------------------

log = logging.getLogger(__name__)

PYEAPI_INIT_KWARGS = [
    "transport",
    "host",
    "username",
    "password",
    "enablepwd",
    "port",
    "timeout",
    "return_node",
]

# -----------------------------------------------------------------------------
# propery functions
# -----------------------------------------------------------------------------


def __virtual__():
    """
    Execution module available only if pyeapi is installed.
    """
    if not HAS_PYEAPI:
        return (
            False,
            "The pyeapi execution module requires pyeapi library to be installed: ``pip"
            " install pyeapi``",
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
    pyeapi_kwargs = __salt__["config.get"]("pyeapi", {})
    pyeapi_kwargs.update(kwargs)  # merge the CLI args with the opts/pillar
    init_kwargs, fun_kwargs = __utils__["args.prepare_kwargs"](
        pyeapi_kwargs, PYEAPI_INIT_KWARGS
    )
    if "transport" not in init_kwargs:
        init_kwargs["transport"] = "https"
    conn = pyeapi.client.connect(**init_kwargs)
    node = pyeapi.client.Node(conn, enablepwd=init_kwargs.get("enablepwd"))
    return node, fun_kwargs


# -----------------------------------------------------------------------------
# callable functions
# -----------------------------------------------------------------------------


def get_connection(**kwargs):
    """
    Return the connection object to the pyeapi Node.

    .. warning::

        This function returns an unserializable object, hence it is not meant
        to be used on the CLI. This should mainly be used when invoked from
        other modules for the low level connection with the network device.

    kwargs
        Key-value dictionary with the authentication details.

    USAGE Example:

    .. code-block:: python

        conn = __salt__['pyeapi.get_connection'](host='router1.example.com',
                                                 username='example',
                                                 password='example')
        show_ver = conn.run_commands(['show version', 'show interfaces'])
    """
    kwargs = clean_kwargs(**kwargs)
    if "pyeapi.conn" in __proxy__:
        return __proxy__["pyeapi.conn"]()
    conn, kwargs = _prepare_connection(**kwargs)
    return conn


def call(method, *args, **kwargs):
    """
    Invoke an arbitrary pyeapi method.

    method
        The name of the pyeapi method to invoke.

    args
        A list of arguments to send to the method invoked.

    kwargs
        Key-value dictionary to send to the method invoked.

    transport: ``https``
        Specifies the type of connection transport to use. Valid values for the
        connection are ``socket``, ``http_local``, ``http``, and  ``https``.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    host: ``localhost``
        The IP address or DNS host name of the connection device.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    username: ``admin``
        The username to pass to the device to authenticate the eAPI connection.

         .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    password
        The password to pass to the device to authenticate the eAPI connection.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    port
        The TCP port of the endpoint for the eAPI connection. If this keyword is
        not specified, the default value is automatically determined by the
        transport type (``80`` for ``http``, or ``443`` for ``https``).

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    enablepwd
        The enable mode password if required by the destination node.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    CLI Example:

    .. code-block:: bash

        salt '*' pyeapi.call run_commands "['show version']"
    """
    kwargs = clean_kwargs(**kwargs)
    if "pyeapi.call" in __proxy__:
        return __proxy__["pyeapi.call"](method, *args, **kwargs)
    conn, kwargs = _prepare_connection(**kwargs)
    ret = getattr(conn, method)(*args, **kwargs)
    return ret


def run_commands(*commands, **kwargs):
    """
    Sends the commands over the transport to the device.

    This function sends the commands to the device using the nodes
    transport.  This is a lower layer function that shouldn't normally
    need to be used, preferring instead to use ``config()`` or ``enable()``.

    transport: ``https``
        Specifies the type of connection transport to use. Valid values for the
        connection are ``socket``, ``http_local``, ``http``, and  ``https``.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    host: ``localhost``
        The IP address or DNS host name of the connection device.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    username: ``admin``
        The username to pass to the device to authenticate the eAPI connection.

         .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    password
        The password to pass to the device to authenticate the eAPI connection.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    port
        The TCP port of the endpoint for the eAPI connection. If this keyword is
        not specified, the default value is automatically determined by the
        transport type (``80`` for ``http``, or ``443`` for ``https``).

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    enablepwd
        The enable mode password if required by the destination node.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    CLI Example:

    .. code-block:: bash

        salt '*' pyeapi.run_commands 'show version'
        salt '*' pyeapi.run_commands 'show version' encoding=text
        salt '*' pyeapi.run_commands 'show version' encoding=text host=cr1.thn.lon username=example password=weak

    Output example:

    .. code-block:: text

      veos1:
          |_
            ----------
            architecture:
                i386
            bootupTimestamp:
                1527541728.53
            hardwareRevision:
            internalBuildId:
                63d2e89a-220d-4b8a-a9b3-0524fa8f9c5f
            internalVersion:
                4.18.1F-4591672.4181F
            isIntlVersion:
                False
            memFree:
                501468
            memTotal:
                1893316
            modelName:
                vEOS
            serialNumber:
            systemMacAddress:
                52:54:00:3f:e6:d0
            version:
                4.18.1F
    """
    encoding = kwargs.pop("encoding", "json")
    send_enable = kwargs.pop("send_enable", True)
    output = call(
        "run_commands", commands, encoding=encoding, send_enable=send_enable, **kwargs
    )
    if encoding == "text":
        ret = []
        for res in output:
            ret.append(res["output"])
        return ret
    return output


def config(
    commands=None,
    config_file=None,
    template_engine="jinja",
    context=None,
    defaults=None,
    saltenv="base",
    **kwargs
):
    """
    Configures the node with the specified commands.

    This method is used to send configuration commands to the node.  It
    will take either a string or a list and prepend the necessary commands
    to put the session into config mode.

    Returns the diff after the configuration commands are loaded.

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
        The commands to send to the node in config mode.  If the commands
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
        Default values of the ``context`` dict.

    transport: ``https``
        Specifies the type of connection transport to use. Valid values for the
        connection are ``socket``, ``http_local``, ``http``, and  ``https``.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    host: ``localhost``
        The IP address or DNS host name of the connection device.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    username: ``admin``
        The username to pass to the device to authenticate the eAPI connection.

         .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    password
        The password to pass to the device to authenticate the eAPI connection.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    port
        The TCP port of the endpoint for the eAPI connection. If this keyword is
        not specified, the default value is automatically determined by the
        transport type (``80`` for ``http``, or ``443`` for ``https``).

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    enablepwd
        The enable mode password if required by the destination node.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    CLI Example:

    .. code-block:: bash

        salt '*' pyeapi.config commands="['ntp server 1.2.3.4', 'ntp server 5.6.7.8']"
        salt '*' pyeapi.config config_file=salt://config.txt
        salt '*' pyeapi.config config_file=https://bit.ly/2LGLcDy context="{'servers': ['1.2.3.4']}"
    """
    initial_config = get_config(as_string=True, **kwargs)
    if config_file:
        file_str = __salt__["cp.get_file_str"](config_file, saltenv=saltenv)
        if file_str is False:
            raise CommandExecutionError("Source file {} not found".format(config_file))
        log.debug("Fetched from %s", config_file)
        log.debug(file_str)
    elif commands:
        if isinstance(commands, str):
            commands = [commands]
        file_str = "\n".join(commands)
        # unify all the commands in a single file, to render them in a go
    if template_engine:
        file_str = __salt__["file.apply_template_on_contents"](
            file_str, template_engine, context, defaults, saltenv
        )
        log.debug("Rendered:")
        log.debug(file_str)
    # whatever the source of the commands would be, split them line by line
    commands = [line for line in file_str.splitlines() if line.strip()]
    # push the commands one by one, removing empty lines
    configured = call("config", commands, **kwargs)
    current_config = get_config(as_string=True, **kwargs)
    diff = difflib.unified_diff(
        initial_config.splitlines(1)[4:], current_config.splitlines(1)[4:]
    )
    return "".join([x.replace("\r", "") for x in diff])


def get_config(config="running-config", params=None, as_string=False, **kwargs):
    """
    Retrieves the config from the device.

    This method will retrieve the config from the node as either a string
    or a list object.  The config to retrieve can be specified as either
    the startup-config or the running-config.

    config: ``running-config``
        Specifies to return either the nodes ``startup-config``
        or ``running-config``.  The default value is the ``running-config``.

    params
        A string of keywords to append to the command for retrieving the config.

    as_string: ``False``
        Flag that determines the response.  If ``True``, then the configuration
        is returned as a raw string.  If ``False``, then the configuration is
        returned as a list.  The default value is ``False``.

    transport: ``https``
        Specifies the type of connection transport to use. Valid values for the
        connection are ``socket``, ``http_local``, ``http``, and  ``https``.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    host: ``localhost``
        The IP address or DNS host name of the connection device.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    username: ``admin``
        The username to pass to the device to authenticate the eAPI connection.

         .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    password
        The password to pass to the device to authenticate the eAPI connection.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    port
        The TCP port of the endpoint for the eAPI connection. If this keyword is
        not specified, the default value is automatically determined by the
        transport type (``80`` for ``http``, or ``443`` for ``https``).

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    enablepwd
        The enable mode password if required by the destination node.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    CLI Example:

    .. code-block:: bash

        salt '*' pyeapi.get_config
        salt '*' pyeapi.get_config params='section snmp-server'
        salt '*' pyeapi.get_config config='startup-config'
    """
    return call(
        "get_config", config=config, params=params, as_string=as_string, **kwargs
    )


def section(regex, config="running-config", **kwargs):
    """
    Return a section of the config.

    regex
        A valid regular expression used to select sections of configuration to
        return.

    config: ``running-config``
        The configuration to return. Valid values for config are
        ``running-config`` or ``startup-config``. The default value is
        ``running-config``.

    transport: ``https``
        Specifies the type of connection transport to use. Valid values for the
        connection are ``socket``, ``http_local``, ``http``, and  ``https``.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    host: ``localhost``
        The IP address or DNS host name of the connection device.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    username: ``admin``
        The username to pass to the device to authenticate the eAPI connection.

         .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    password
        The password to pass to the device to authenticate the eAPI connection.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    port
        The TCP port of the endpoint for the eAPI connection. If this keyword is
        not specified, the default value is automatically determined by the
        transport type (``80`` for ``http``, or ``443`` for ``https``).

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    enablepwd
        The enable mode password if required by the destination node.

        .. note::

            This argument does not need to be specified when running in a
            :mod:`pyeapi <salt.proxy.arista_pyeapi>` Proxy Minion.

    CLI Example:

    .. code-block:: bash

        salt '*'
    """
    return call("section", regex, config=config, **kwargs)
