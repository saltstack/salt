"""
NAPALM helpers
==============

Helpers for the NAPALM modules.

.. versionadded:: 2017.7.0
"""

import logging

import salt.utils.napalm
from salt.exceptions import CommandExecutionError
from salt.utils.decorators import depends
from salt.utils.napalm import proxy_napalm_wrap

try:
    from netmiko import BaseConnection

    HAS_NETMIKO = True
except ImportError:
    HAS_NETMIKO = False

try:
    import napalm.base.netmiko_helpers  # pylint: disable=no-name-in-module

    HAS_NETMIKO_HELPERS = True
except ImportError:
    HAS_NETMIKO_HELPERS = False

try:
    import jxmlease  # pylint: disable=unused-import

    HAS_JXMLEASE = True
except ImportError:
    HAS_JXMLEASE = False

try:
    import ciscoconfparse  # pylint: disable=unused-import

    HAS_CISCOCONFPARSE = True
except ImportError:
    HAS_CISCOCONFPARSE = False

try:
    import scp  # pylint: disable=unused-import

    HAS_SCP = True
except ImportError:
    HAS_SCP = False

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = "napalm"
__proxyenabled__ = ["*"]
# uses NAPALM-based proxy to interact with network devices

log = logging.getLogger(__file__)

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    """
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    """
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)


# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------


def _get_netmiko_args(optional_args):
    """
    Check for Netmiko arguments that were passed in as NAPALM optional arguments.

    Return a dictionary of these optional args that will be passed into the
    Netmiko ConnectHandler call.

    .. note::

        This is a port of the NAPALM helper for backwards compatibility with
        older versions of NAPALM, and stability across Salt features.
        If the netmiko helpers module is available however, it will prefer that
        implementation nevertheless.
    """
    if HAS_NETMIKO_HELPERS:
        return napalm.base.netmiko_helpers.netmiko_args(optional_args)
    # Older version don't have the netmiko_helpers module, the following code is
    # simply a port from the NAPALM code base, for backwards compatibility:
    # https://github.com/napalm-automation/napalm/blob/develop/napalm/base/netmiko_helpers.py
    netmiko_args, _, _, netmiko_defaults = __utils__["args.get_function_argspec"](
        BaseConnection.__init__
    )
    check_self = netmiko_args.pop(0)
    if check_self != "self":
        raise ValueError("Error processing Netmiko arguments")
    netmiko_argument_map = dict(zip(netmiko_args, netmiko_defaults))
    # Netmiko arguments that are integrated into NAPALM already
    netmiko_filter = ["ip", "host", "username", "password", "device_type", "timeout"]
    # Filter out all of the arguments that are integrated into NAPALM
    for k in netmiko_filter:
        netmiko_argument_map.pop(k)
    # Check if any of these arguments were passed in as NAPALM optional_args
    netmiko_optional_args = {}
    for k, v in netmiko_argument_map.items():
        try:
            netmiko_optional_args[k] = optional_args[k]
        except KeyError:
            pass
    # Return these arguments for use with establishing Netmiko SSH connection
    return netmiko_optional_args


def _inject_junos_proxy(napalm_device):
    """
    Inject the junos.conn key into the __proxy__, reusing the existing NAPALM
    connection to the Junos device.
    """

    def _ret_device():
        return napalm_device["DRIVER"].device

    __proxy__["junos.conn"] = _ret_device
    # Injecting the junos.conn key into the __proxy__ object, we can then
    # access the features that already exist into the junos module, as long
    # as the rest of the dependencies are installed (jxmlease).
    # junos-eznc is already installed, as part of NAPALM, and the napalm
    # driver for junos already makes use of the Device class from this lib.
    # So pointing the __proxy__ object to this object already loaded into
    # memory, we can go and re-use the features from the existing junos
    # Salt module.


def _junos_prep_fun(napalm_device):
    """
    Prepare the Junos function.
    """
    if __grains__["os"] != "junos":
        return {
            "out": None,
            "result": False,
            "comment": "This function is only available on Junos",
        }
    if not HAS_JXMLEASE:
        return {
            "out": None,
            "result": False,
            "comment": (
                "Please install jxmlease (``pip install jxmlease``) to be able to use"
                " this function."
            ),
        }
    _inject_junos_proxy(napalm_device)
    return {"result": True}


@proxy_napalm_wrap
def _netmiko_conn(**kwargs):
    """
    .. versionadded:: 2019.2.0

    Return the connection object with the network device, over Netmiko, passing
    the authentication details from the existing NAPALM connection.

    .. warning::

        This function is not suitable for CLI usage, more rather to be used
        in various Salt modules.

    USAGE Example:

    .. code-block:: python

        conn = __salt__['napalm.netmiko_conn']()
        res = conn.send_command('show interfaces')
        conn.disconnect()
    """
    netmiko_kwargs = netmiko_args()
    kwargs.update(netmiko_kwargs)
    return __salt__["netmiko.get_connection"](**kwargs)


@proxy_napalm_wrap
def _pyeapi_conn(**kwargs):
    """
    .. versionadded:: 2019.2.0

    Return the connection object with the Arista switch, over ``pyeapi``,
    passing the authentication details from the existing NAPALM connection.

    .. warning::
        This function is not suitable for CLI usage, more rather to be used in
        various Salt modules, to reusing the established connection, as in
        opposite to opening a new connection for each task.

    Usage example:

    .. code-block:: python

        conn = __salt__['napalm.pyeapi_conn']()
        res1 = conn.run_commands('show version')
        res2 = conn.get_config(as_string=True)
    """
    pyeapi_kwargs = pyeapi_nxos_api_args(**kwargs)
    return __salt__["pyeapi.get_connection"](**pyeapi_kwargs)


# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


@proxy_napalm_wrap
def alive(**kwargs):  # pylint: disable=unused-argument
    """
    Returns the alive status of the connection layer.
    The output is a dictionary under the usual dictionary
    output of the NAPALM modules.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.alive

    Output Example:

    .. code-block:: yaml

        result: True
        out:
            is_alive: False
        comment: ''
    """
    return salt.utils.napalm.call(
        napalm_device, "is_alive", **{}  # pylint: disable=undefined-variable
    )


@proxy_napalm_wrap
def reconnect(force=False, **kwargs):  # pylint: disable=unused-argument
    """
    Reconnect the NAPALM proxy when the connection
    is dropped by the network device.
    The connection can be forced to be restarted
    using the ``force`` argument.

    .. note::

        This function can be used only when running proxy minions.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.reconnect
        salt '*' napalm.reconnect force=True
    """
    default_ret = {"out": None, "result": True, "comment": "Already alive."}
    if not salt.utils.napalm.is_proxy(__opts__):
        # regular minion is always alive
        # otherwise, the user would not be able to execute this command
        return default_ret
    is_alive = alive()
    log.debug("Is alive fetch:")
    log.debug(is_alive)
    if (
        not is_alive.get("result", False)
        or not is_alive.get("out", False)
        or not is_alive.get("out", {}).get("is_alive", False)
        or force
    ):  # even if alive, but the user wants to force a restart
        proxyid = __opts__.get("proxyid") or __opts__.get("id")
        # close the connection
        log.info("Closing the NAPALM proxy connection with %s", proxyid)
        salt.utils.napalm.call(
            napalm_device, "close", **{}  # pylint: disable=undefined-variable
        )
        # and re-open
        log.info("Re-opening the NAPALM proxy connection with %s", proxyid)
        salt.utils.napalm.call(
            napalm_device, "open", **{}  # pylint: disable=undefined-variable
        )
        default_ret.update({"comment": "Connection restarted!"})
        return default_ret
    # otherwise, I have nothing to do here:
    return default_ret


@proxy_napalm_wrap
def call(method, *args, **kwargs):
    """
    Execute arbitrary methods from the NAPALM library.
    To see the expected output, please consult the NAPALM documentation.

    .. note::

        This feature is not recommended to be used in production.
        It should be used for testing only!

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.call get_lldp_neighbors
        salt '*' napalm.call get_firewall_policies
        salt '*' napalm.call get_bgp_config group='my-group'
    """
    clean_kwargs = {}
    for karg, warg in kwargs.items():
        # remove the __pub args
        if not karg.startswith("__pub_"):
            clean_kwargs[karg] = warg
    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        method,
        *args,
        **clean_kwargs
    )


@proxy_napalm_wrap
def compliance_report(filepath=None, string=None, renderer="jinja|yaml", **kwargs):
    """
    Return the compliance report.

    filepath
        The absolute path to the validation file.

        .. versionchanged:: 2019.2.0

        Beginning with release codename ``2019.2.0``, this function has been
        enhanced, to be able to leverage the multi-engine template rendering
        of Salt, besides the possibility to retrieve the file source from
        remote systems, the URL schemes supported being:

        - ``salt://``
        - ``http://`` and ``https://``
        - ``ftp://``
        - ``s3://``
        - ``swift:/``

        Or on the local file system (on the Minion).

        .. note::

            The rendering result does not necessarily need to be YAML, instead
            it can be any format interpreted by Salt's rendering pipeline
            (including pure Python).

    string
        .. versionadded:: 2019.2.0

        The compliance report send as inline string, to be used as the file to
        send through the renderer system. Note, not all renderer modules can
        work with strings; the 'py' renderer requires a file, for example.

    renderer: ``jinja|yaml``
        .. versionadded:: 2019.2.0

        The renderer pipe to send the file through; this is overridden by a
        "she-bang" at the top of the file.

    kwargs
        .. versionchanged:: 2019.2.0

        Keyword args to pass to Salt's compile_template() function.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.compliance_report ~/validate.yml
        salt '*' napalm.compliance_report salt://path/to/validator.sls

    Validation File Example (pure YAML):

    .. code-block:: yaml

        - get_facts:
            os_version: 4.17

        - get_interfaces_ip:
            Management1:
              ipv4:
                10.0.2.14:
                  prefix_length: 24
                _mode: strict

    Validation File Example (as Jinja + YAML):

    .. code-block:: yaml

        - get_facts:
            os_version: {{ grains.version }}
        - get_interfaces_ip:
            Loopback0:
              ipv4:
                {{ grains.lo0.ipv4 }}:
                  prefix_length: 24
                _mode: strict
        - get_bgp_neighbors: {{ pillar.bgp.neighbors }}

    Output Example:

    .. code-block:: yaml

        device1:
            ----------
            comment:
            out:
                ----------
                complies:
                    False
                get_facts:
                    ----------
                    complies:
                        False
                    extra:
                    missing:
                    present:
                        ----------
                        os_version:
                            ----------
                            actual_value:
                                15.1F6-S1.4
                            complies:
                                False
                            nested:
                                False
                get_interfaces_ip:
                    ----------
                    complies:
                        False
                    extra:
                    missing:
                        - Management1
                    present:
                        ----------
                skipped:
            result:
                True
    """
    validation_string = __salt__["slsutil.renderer"](
        path=filepath, string=string, default_renderer=renderer, **kwargs
    )
    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        "compliance_report",
        validation_source=validation_string,
    )


@proxy_napalm_wrap
def netmiko_args(**kwargs):
    """
    .. versionadded:: 2019.2.0

    Return the key-value arguments used for the authentication arguments for
    the netmiko module.

    When running in a non-native NAPALM driver (e.g., ``panos``, `f5``, ``mos`` -
    either from https://github.com/napalm-automation-community or defined in
    user's own environment, one can specify the Netmiko device type (the
    ``device_type`` argument) via the ``netmiko_device_type_map`` configuration
    option / Pillar key, e.g.,

    .. code-block:: yaml

        netmiko_device_type_map:
          f5: f5_ltm
          dellos10: dell_os10

    The configuration above defines the mapping between the NAPALM ``os`` Grain
    and the Netmiko ``device_type``, e.g., when the NAPALM Grain is ``f5``, it
    would use the ``f5_ltm`` SSH Netmiko driver to execute commands over SSH on
    the remote network device.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.netmiko_args
    """
    if not HAS_NETMIKO:
        raise CommandExecutionError(
            "Please install netmiko to be able to use this feature."
        )
    kwargs = {}
    napalm_opts = salt.utils.napalm.get_device_opts(__opts__, salt_obj=__salt__)
    optional_args = napalm_opts["OPTIONAL_ARGS"]
    netmiko_args = _get_netmiko_args(optional_args)
    kwargs["host"] = napalm_opts["HOSTNAME"]
    kwargs["username"] = napalm_opts["USERNAME"]
    kwargs["password"] = napalm_opts["PASSWORD"]
    kwargs["timeout"] = napalm_opts["TIMEOUT"]
    kwargs.update(netmiko_args)
    netmiko_device_type_map = {
        "junos": "juniper_junos",
        "ios": "cisco_ios",
        "iosxr": "cisco_xr",
        "eos": "arista_eos",
        "nxos_ssh": "cisco_nxos",
        "asa": "cisco_asa",
        "fortios": "fortinet",
        "panos": "paloalto_panos",
        "aos": "alcatel_aos",
        "vyos": "vyos",
        "f5": "f5_ltm",
        "ce": "huawei",
        "s350": "cisco_s300",
    }
    # If you have a device type that is not listed here, please submit a PR
    # to add it, and/or add the map into your opts/Pillar: netmiko_device_type_map
    # Example:
    #
    # netmiko_device_type_map:
    #   junos: juniper_junos
    #   ios: cisco_ios
    #
    # etc.
    netmiko_device_type_map.update(
        __salt__["config.get"]("netmiko_device_type_map", {})
    )
    kwargs["device_type"] = netmiko_device_type_map[__grains__["os"]]
    return kwargs


@proxy_napalm_wrap
def netmiko_fun(fun, *args, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Call an arbitrary function from the :mod:`Netmiko<salt.modules.netmiko_mod>`
    module, passing the authentication details from the existing NAPALM
    connection.

    fun
        The name of the function from the :mod:`Netmiko<salt.modules.netmiko_mod>`
        to invoke.

    args
        List of arguments to send to the execution function specified in
        ``fun``.

    kwargs
        Key-value arguments to send to the execution function specified in
        ``fun``.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.netmiko_fun send_command 'show version'
    """
    if "netmiko." not in fun:
        fun = "netmiko.{fun}".format(fun=fun)
    netmiko_kwargs = netmiko_args()
    kwargs.update(netmiko_kwargs)
    return __salt__[fun](*args, **kwargs)


@proxy_napalm_wrap
def netmiko_call(method, *args, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Execute an arbitrary Netmiko method, passing the authentication details from
    the existing NAPALM connection.

    method
        The name of the Netmiko method to execute.

    args
        List of arguments to send to the Netmiko method specified in ``method``.

    kwargs
        Key-value arguments to send to the execution function specified in
        ``method``.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.netmiko_call send_command 'show version'
    """
    netmiko_kwargs = netmiko_args()
    kwargs.update(netmiko_kwargs)
    return __salt__["netmiko.call"](method, *args, **kwargs)


@proxy_napalm_wrap
def netmiko_multi_call(*methods, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Execute a list of arbitrary Netmiko methods, passing the authentication
    details from the existing NAPALM connection.

    methods
        List of dictionaries with the following keys:

        - ``name``: the name of the Netmiko function to invoke.
        - ``args``: list of arguments to send to the ``name`` method.
        - ``kwargs``: key-value arguments to send to the ``name`` method.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.netmiko_multi_call "{'name': 'send_command', 'args': ['show version']}" "{'name': 'send_command', 'args': ['show interfaces']}"
    """
    netmiko_kwargs = netmiko_args()
    kwargs.update(netmiko_kwargs)
    return __salt__["netmiko.multi_call"](*methods, **kwargs)


@proxy_napalm_wrap
def netmiko_commands(*commands, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Invoke one or more commands to be executed on the remote device, via Netmiko.
    Returns a list of strings, with the output from each command.

    commands
        A list of commands to be executed.

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

        salt '*' napalm.netmiko_commands 'show version' 'show interfaces'
    """
    conn = _netmiko_conn(**kwargs)
    ret = []
    for cmd in commands:
        ret.append(conn.send_command(cmd))
    return ret


@proxy_napalm_wrap
def netmiko_config(*config_commands, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Load a list of configuration commands on the remote device, via Netmiko.

    .. warning::

        Please remember that ``netmiko`` does not have any rollback safeguards
        and any configuration change will be directly loaded into the running
        config if the platform doesn't have the concept of ``candidate`` config.

        On Junos, or other platforms that have this capability, the changes will
        not be loaded into the running config, and the user must set the
        ``commit`` argument to ``True`` to transfer the changes from the
        candidate into the running config before exiting.

    config_commands
        A list of configuration commands to be loaded on the remote device.

    config_file
        Read the configuration commands from a file. The file can equally be a
        template that can be rendered using the engine of choice (see
        ``template_engine``).

        This can be specified using the absolute path to the file, or using one
        of the following URL schemes:

        - ``salt://``, to fetch the file from the Salt fileserver.
        - ``http://`` or ``https://``
        - ``ftp://``
        - ``s3://``
        - ``swift://``

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

    commit: ``False``
        Commit the configuration changes before exiting the config mode. This
        option is by default disabled, as many platforms don't have this
        capability natively.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.netmiko_config 'set system ntp peer 1.2.3.4' commit=True
        salt '*' napalm.netmiko_config https://bit.ly/2sgljCB
    """
    netmiko_kwargs = netmiko_args()
    kwargs.update(netmiko_kwargs)
    return __salt__["netmiko.send_config"](config_commands=config_commands, **kwargs)


@proxy_napalm_wrap
def netmiko_conn(**kwargs):
    """
    .. versionadded:: 2019.2.0

    Return the connection object with the network device, over Netmiko, passing
    the authentication details from the existing NAPALM connection.

    .. warning::

        This function is not suitable for CLI usage, more rather to be used
        in various Salt modules.

    USAGE Example:

    .. code-block:: python

        conn = __salt__['napalm.netmiko_conn']()
        res = conn.send_command('show interfaces')
        conn.disconnect()
    """
    salt.utils.versions.warn_until(
        "Chlorine",
        "This 'napalm_mod.netmiko_conn' function as been deprecated and "
        "will be removed in the {version} release, as such, it has been "
        "made an internal function since it is not suitable for CLI usage",
    )
    return _netmiko_conn(**kwargs)


@proxy_napalm_wrap
def junos_rpc(cmd=None, dest=None, format=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Execute an RPC request on the remote Junos device.

    cmd
        The RPC request to the executed. To determine the RPC request, you can
        check the from the command line of the device, by executing the usual
        command followed by ``| display xml rpc``, e.g.,
        ``show lldp neighbors | display xml rpc``.

    dest
        Destination file where the RPC output is stored. Note that the file will
        be stored on the Proxy Minion. To push the files to the Master, use
        :mod:`cp.push <salt.modules.cp.push>` Execution function.

    format: ``xml``
        The format in which the RPC reply is received from the device.

    dev_timeout: ``30``
        The NETCONF RPC timeout.

    filter
        Used with the ``get-config`` RPC request to filter out the config tree.

    terse: ``False``
        Whether to return terse output.

        .. note::

            Some RPC requests may not support this argument.

    interface_name
        Name of the interface to query.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.junos_rpc get-lldp-neighbors-information
        salt '*' napalm.junos_rpc get-config <configuration><system><ntp/></system></configuration>
    """
    prep = _junos_prep_fun(napalm_device)  # pylint: disable=undefined-variable
    if not prep["result"]:
        return prep
    if not format:
        format = "xml"
    rpc_ret = __salt__["junos.rpc"](cmd=cmd, dest=dest, format=format, **kwargs)
    rpc_ret["comment"] = rpc_ret.pop("message", "")
    rpc_ret["result"] = rpc_ret.pop("out", False)
    rpc_ret["out"] = rpc_ret.pop("rpc_reply", None)
    # The comment field is "message" in the Junos module
    return rpc_ret


@proxy_napalm_wrap
def junos_commit(**kwargs):
    """
    .. versionadded:: 2019.2.0

    Commit the changes loaded in the candidate configuration.

    dev_timeout: ``30``
        The NETCONF RPC timeout (in seconds).

    comment
      Provide a comment for the commit.

    confirm
      Provide time in minutes for commit confirmation. If this option is
      specified, the commit will be rolled back in the specified amount of time
      unless the commit is confirmed.

    sync: ``False``
      When ``True``, on dual control plane systems, requests that the candidate
      configuration on one control plane be copied to the other control plane,
      checked for correct syntax, and committed on both Routing Engines.

    force_sync: ``False``
      When ``True``, on dual control plane systems, force the candidate
      configuration on one control plane to be copied to the other control
      plane.

    full
      When ``True``, requires all the daemons to check and evaluate the new
      configuration.

    detail
      When ``True``, return commit detail.

    CLI Examples:

    .. code-block:: bash

        salt '*' napalm.junos_commit comment='Commitiing via Salt' detail=True
        salt '*' napalm.junos_commit dev_timeout=60 confirm=10
        salt '*' napalm.junos_commit sync=True dev_timeout=90
    """
    prep = _junos_prep_fun(napalm_device)  # pylint: disable=undefined-variable
    if not prep["result"]:
        return prep
    return __salt__["junos.commit"](**kwargs)


@proxy_napalm_wrap
def junos_install_os(path=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Installs the given image on the device.

    path
        The image file source. This argument supports the following URIs:

        - Absolute path on the Minion.
        - ``salt://`` to fetch from the Salt fileserver.
        - ``http://`` and ``https://``
        - ``ftp://``
        - ``swift:/``
        - ``s3://``

    dev_timeout: ``30``
        The NETCONF RPC timeout (in seconds)

    reboot: ``False``
        Whether to reboot the device after the installation is complete.

    no_copy: ``False``
        If ``True`` the software package will not be copied to the remote
        device.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.junos_install_os salt://images/junos_16_1.tgz reboot=True
    """
    prep = _junos_prep_fun(napalm_device)  # pylint: disable=undefined-variable
    if not prep["result"]:
        return prep
    return __salt__["junos.install_os"](path=path, **kwargs)


@proxy_napalm_wrap
def junos_facts(**kwargs):
    """
    .. versionadded:: 2019.2.0

    The complete list of Junos facts collected by ``junos-eznc``.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.junos_facts
    """
    prep = _junos_prep_fun(napalm_device)  # pylint: disable=undefined-variable
    if not prep["result"]:
        return prep
    # pylint: disable=undefined-variable
    facts = dict(napalm_device["DRIVER"].device.facts)
    # pylint: enable=undefined-variable
    if "version_info" in facts:
        facts["version_info"] = dict(facts["version_info"])
    # For backward compatibility. 'junos_info' is present
    # only of in newer versions of facts.
    if "junos_info" in facts:
        for re in facts["junos_info"]:
            facts["junos_info"][re]["object"] = dict(facts["junos_info"][re]["object"])
    return facts


@proxy_napalm_wrap
def junos_cli(command, format=None, dev_timeout=None, dest=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Execute a CLI command and return the output in the specified format.

    command
        The command to execute on the Junos CLI.

    format: ``text``
        Format in which to get the CLI output (either ``text`` or ``xml``).

    dev_timeout: ``30``
        The NETCONF RPC timeout (in seconds).

    dest
        Destination file where the RPC output is stored. Note that the file will
        be stored on the Proxy Minion. To push the files to the Master, use
        :mod:`cp.push <salt.modules.cp.push>`.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.junos_cli 'show lldp neighbors'
    """
    prep = _junos_prep_fun(napalm_device)  # pylint: disable=undefined-variable
    if not prep["result"]:
        return prep
    return __salt__["junos.cli"](
        command, format=format, dev_timeout=dev_timeout, dest=dest, **kwargs
    )


@proxy_napalm_wrap
def junos_copy_file(src, dst, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Copies the file on the remote Junos device.

    src
        The source file path. This argument accepts the usual Salt URIs (e.g.,
        ``salt://``, ``http://``, ``https://``, ``s3://``, ``ftp://``, etc.).

    dst
        The destination path on the device where to copy the file.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.junos_copy_file https://example.com/junos.cfg /var/tmp/myjunos.cfg
    """
    prep = _junos_prep_fun(napalm_device)  # pylint: disable=undefined-variable
    if not prep["result"]:
        return prep
    cached_src = __salt__["cp.cache_file"](src)
    return __salt__["junos.file_copy"](cached_src, dst)


@proxy_napalm_wrap
def junos_call(fun, *args, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Execute an arbitrary function from the
    :mod:`junos execution module <salt.module.junos>`. To check what ``args``
    and ``kwargs`` you must send to the function, please consult the appropriate
    documentation.

    fun
        The name of the function. E.g., ``set_hostname``.

    args
        List of arguments to send to the ``junos`` function invoked.

    kwargs
        Dictionary of key-value arguments to send to the ``juno`` function
        invoked.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.junos_fun cli 'show system commit'
    """
    prep = _junos_prep_fun(napalm_device)  # pylint: disable=undefined-variable
    if not prep["result"]:
        return prep
    if "junos." not in fun:
        mod_fun = "junos.{}".format(fun)
    else:
        mod_fun = fun
    if mod_fun not in __salt__:
        return {
            "out": None,
            "result": False,
            "comment": "{} is not a valid function".format(fun),
        }
    return __salt__[mod_fun](*args, **kwargs)


def pyeapi_nxos_api_args(**prev_kwargs):
    """
    .. versionadded:: 2019.2.0

    Return the key-value arguments used for the authentication arguments for the
    :mod:`pyeapi execution module <salt.module.arista_pyeapi>`.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.pyeapi_nxos_api_args
    """
    kwargs = {}
    napalm_opts = salt.utils.napalm.get_device_opts(__opts__, salt_obj=__salt__)
    optional_args = napalm_opts["OPTIONAL_ARGS"]
    kwargs["host"] = napalm_opts["HOSTNAME"]
    kwargs["username"] = napalm_opts["USERNAME"]
    kwargs["password"] = napalm_opts["PASSWORD"]
    kwargs["timeout"] = napalm_opts["TIMEOUT"]

    if "transport" in optional_args and optional_args["transport"]:
        kwargs["transport"] = optional_args["transport"]
    else:
        kwargs["transport"] = "https"

    if "port" in optional_args and optional_args["port"]:
        kwargs["port"] = optional_args["port"]
    else:
        kwargs["port"] = 80 if kwargs["transport"] == "http" else 443

    kwargs["verify"] = optional_args.get("verify")
    prev_kwargs.update(kwargs)
    return prev_kwargs


@proxy_napalm_wrap
def pyeapi_run_commands(*commands, **kwargs):
    """
    Execute a list of commands on the Arista switch, via the ``pyeapi`` library.
    This function forwards the existing connection details to the
    :mod:`pyeapi.run_commands <salt.module.arista_pyeapi.run_commands>`
    execution function.

    commands
        A list of commands to execute.

    encoding: ``json``
        The requested encoding of the command output. Valid values for encoding
        are ``json`` (default) or ``text``.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.pyeapi_run_commands 'show version' encoding=text
        salt '*' napalm.pyeapi_run_commands 'show ip bgp neighbors'
    """
    pyeapi_kwargs = pyeapi_nxos_api_args(**kwargs)
    return __salt__["pyeapi.run_commands"](*commands, **pyeapi_kwargs)


@proxy_napalm_wrap
def pyeapi_call(method, *args, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Invoke an arbitrary method from the ``pyeapi`` library.
    This function forwards the existing connection details to the
    :mod:`pyeapi.run_commands <salt.module.arista_pyeapi.run_commands>`
    execution function.

    method
        The name of the ``pyeapi`` method to invoke.

    kwargs
        Key-value arguments to send to the ``pyeapi`` method.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.pyeapi_call run_commands 'show version' encoding=text
        salt '*' napalm.pyeapi_call get_config as_string=True
    """
    pyeapi_kwargs = pyeapi_nxos_api_args(**kwargs)
    return __salt__["pyeapi.call"](method, *args, **pyeapi_kwargs)


@proxy_napalm_wrap
def pyeapi_conn(**kwargs):
    """
    .. versionadded:: 2019.2.0

    Return the connection object with the Arista switch, over ``pyeapi``,
    passing the authentication details from the existing NAPALM connection.

    .. warning::
        This function is not suitable for CLI usage, more rather to be used in
        various Salt modules, to reusing the established connection, as in
        opposite to opening a new connection for each task.

    Usage example:

    .. code-block:: python

        conn = __salt__['napalm.pyeapi_conn']()
        res1 = conn.run_commands('show version')
        res2 = conn.get_config(as_string=True)
    """
    salt.utils.versions.warn_until(
        "Chlorine",
        "This 'napalm_mod.pyeapi_conn' function as been deprecated and "
        "will be removed in the {version} release, as such, it has been "
        "made an internal function since it is not suitable for CLI usage",
    )
    return _pyeapi_conn(**kwargs)


@proxy_napalm_wrap
def pyeapi_config(
    commands=None,
    config_file=None,
    template_engine="jinja",
    context=None,
    defaults=None,
    saltenv="base",
    **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Configures the Arista switch with the specified commands, via the ``pyeapi``
    library. This function forwards the existing connection details to the
    :mod:`pyeapi.run_commands <salt.module.arista_pyeapi.run_commands>`
    execution function.

    commands
        The list of configuration commands to load on the Arista switch.

        .. note::
            This argument is ignored when ``config_file`` is specified.

    config_file
        The source file with the configuration commands to be sent to the device.

        The file can also be a template that can be rendered using the template
        engine of choice. This can be specified using the absolute path to the
        file, or using one of the following URL schemes:

        - ``salt://``
        - ``https://``
        - ``ftp:/``
        - ``s3:/``
        - ``swift://``

    template_engine: ``jinja``
        The template engine to use when rendering the source file. Default:
        ``jinja``. To simply fetch the file without attempting to render, set
        this argument to ``None``.

    context: ``None``
        Variables to add to the template context.

    defaults: ``None``
        Default values of the ``context`` dict.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file. Ignored if
        ``config_file`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.pyeapi_config 'ntp server 1.2.3.4'
    """
    pyeapi_kwargs = pyeapi_nxos_api_args(**kwargs)
    return __salt__["pyeapi.config"](
        commands=commands,
        config_file=config_file,
        template_engine=template_engine,
        context=context,
        defaults=defaults,
        saltenv=saltenv,
        **pyeapi_kwargs
    )


@proxy_napalm_wrap
def nxos_api_rpc(commands, method="cli", **kwargs):
    """
    .. versionadded:: 2019.2.0

    Execute an arbitrary RPC request via the Nexus API.

    commands
        The RPC commands to be executed.

    method: ``cli``
        The type of the response, i.e., raw text (``cli_ascii``) or structured
        document (``cli``). Defaults to ``cli`` (structured data).

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.nxos_api_rpc 'show version'
    """
    nxos_api_kwargs = pyeapi_nxos_api_args(**kwargs)
    return __salt__["nxos_api.rpc"](commands, method=method, **nxos_api_kwargs)


@proxy_napalm_wrap
def nxos_api_config(
    commands=None,
    config_file=None,
    template_engine="jinja",
    context=None,
    defaults=None,
    saltenv="base",
    **kwargs
):
    """
     .. versionadded:: 2019.2.0

    Configures the Nexus switch with the specified commands, via the NX-API.

    commands
        The list of configuration commands to load on the Nexus switch.

        .. note::
            This argument is ignored when ``config_file`` is specified.

    config_file
        The source file with the configuration commands to be sent to the device.

        The file can also be a template that can be rendered using the template
        engine of choice. This can be specified using the absolute path to the
        file, or using one of the following URL schemes:

        - ``salt://``
        - ``https://``
        - ``ftp:/``
        - ``s3:/``
        - ``swift://``

    template_engine: ``jinja``
        The template engine to use when rendering the source file. Default:
        ``jinja``. To simply fetch the file without attempting to render, set
        this argument to ``None``.

    context: ``None``
        Variables to add to the template context.

    defaults: ``None``
        Default values of the ``context`` dict.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file. Ignored if
        ``config_file`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.nxos_api_config 'spanning-tree mode mstp'
        salt '*' napalm.nxos_api_config config_file=https://bit.ly/2LGLcDy context="{'servers': ['1.2.3.4']}"
    """
    nxos_api_kwargs = pyeapi_nxos_api_args(**kwargs)
    return __salt__["nxos_api.config"](
        commands=commands,
        config_file=config_file,
        template_engine=template_engine,
        context=context,
        defaults=defaults,
        saltenv=saltenv,
        **nxos_api_kwargs
    )


@proxy_napalm_wrap
def nxos_api_show(commands, raw_text=True, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Execute one or more show (non-configuration) commands.

    commands
        The commands to be executed.

    raw_text: ``True``
        Whether to return raw text or structured data.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.nxos_api_show 'show version'
        salt '*' napalm.nxos_api_show 'show bgp sessions' 'show processes' raw_text=False
    """
    nxos_api_kwargs = pyeapi_nxos_api_args(**kwargs)
    return __salt__["nxos_api.show"](commands, raw_text=raw_text, **nxos_api_kwargs)


@proxy_napalm_wrap
def rpc(command, **kwargs):
    """
    .. versionadded:: 2019.2.0

    This is a wrapper to execute RPC requests on various network operating
    systems supported by NAPALM, invoking the following functions for the NAPALM
    native drivers:

    - :py:func:`napalm.junos_rpc <salt.modules.napalm_mod.junos_rpc>` for ``junos``
    - :py:func:`napalm.pyeapi_run_commands <salt.modules.napalm_mod.pyeapi_run_commands>`
      for ``eos``
    - :py:func:`napalm.nxos_api_rpc <salt.modules.napalm_mod.nxos_api_rpc>` for
      ``nxos``
    - :py:func:`napalm.netmiko_commands <salt.modules.napalm_mod.netmiko_commands>`
      for ``ios``, ``iosxr``, and ``nxos_ssh``

    command
        The RPC command to execute. This depends on the nature of the operating
        system.

    kwargs
        Key-value arguments to be sent to the underlying Execution function.

    The function capabilities are extensible in the user environment via the
    ``napalm_rpc_map`` configuration option / Pillar, e.g.,

    .. code-block:: yaml

        napalm_rpc_map:
          f5: napalm.netmiko_commands
          panos: panos.call

    The mapping above reads: when the NAPALM ``os`` Grain is ``f5``, then call
    ``napalm.netmiko_commands`` for RPC requests.

    By default, if the user does not specify any map, non-native NAPALM drivers
    will invoke the ``napalm.netmiko_commands`` Execution function.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.rpc 'show version'
        salt '*' napalm.rpc get-interfaces
    """
    default_map = {
        "junos": "napalm.junos_rpc",
        "eos": "napalm.pyeapi_run_commands",
        "nxos": "napalm.nxos_api_rpc",
    }
    napalm_map = __salt__["config.get"]("napalm_rpc_map", {})
    napalm_map.update(default_map)
    fun = napalm_map.get(__grains__["os"], "napalm.netmiko_commands")
    return __salt__[fun](command, **kwargs)


@depends(HAS_CISCOCONFPARSE)
def config_find_lines(regex, source="running"):
    r"""
    .. versionadded:: 2019.2.0

    Return the configuration lines that match the regular expressions from the
    ``regex`` argument. The configuration is read from the network device
    interrogated.

    regex
        The regular expression to match the configuration lines against.

    source: ``running``
        The configuration type to retrieve from the network device. Default:
        ``running``. Available options: ``running``, ``startup``, ``candidate``.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.config_find_lines '^interface Ethernet1\d'
    """
    config_txt = __salt__["net.config"](source=source)["out"][source]
    return __salt__["ciscoconfparse.find_lines"](config=config_txt, regex=regex)


@depends(HAS_CISCOCONFPARSE)
def config_lines_w_child(parent_regex, child_regex, source="running"):
    r"""
     .. versionadded:: 2019.2.0

    Return the configuration lines that match the regular expressions from the
    ``parent_regex`` argument, having child lines matching ``child_regex``.
    The configuration is read from the network device interrogated.

    .. note::
        This function is only available only when the underlying library
        `ciscoconfparse <http://www.pennington.net/py/ciscoconfparse/index.html>`_
        is installed. See
        :py:func:`ciscoconfparse module <salt.modules.ciscoconfparse_mod>` for
        more details.

    parent_regex
        The regular expression to match the parent configuration lines against.

    child_regex
        The regular expression to match the child configuration lines against.

    source: ``running``
        The configuration type to retrieve from the network device. Default:
        ``running``. Available options: ``running``, ``startup``, ``candidate``.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.config_lines_w_child '^interface' 'ip address'
        salt '*' napalm.config_lines_w_child '^interface' 'shutdown' source=candidate
    """
    config_txt = __salt__["net.config"](source=source)["out"][source]
    return __salt__["ciscoconfparse.find_lines_w_child"](
        config=config_txt, parent_regex=parent_regex, child_regex=child_regex
    )


@depends(HAS_CISCOCONFPARSE)
def config_lines_wo_child(parent_regex, child_regex, source="running"):
    """
      .. versionadded:: 2019.2.0

    Return the configuration lines that match the regular expressions from the
    ``parent_regex`` argument, having the child lines *not* matching
    ``child_regex``.
    The configuration is read from the network device interrogated.

    .. note::
        This function is only available only when the underlying library
        `ciscoconfparse <http://www.pennington.net/py/ciscoconfparse/index.html>`_
        is installed. See
        :py:func:`ciscoconfparse module <salt.modules.ciscoconfparse_mod>` for
        more details.

    parent_regex
        The regular expression to match the parent configuration lines against.

    child_regex
        The regular expression to match the child configuration lines against.

    source: ``running``
        The configuration type to retrieve from the network device. Default:
        ``running``. Available options: ``running``, ``startup``, ``candidate``.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.config_lines_wo_child '^interface' 'ip address'
        salt '*' napalm.config_lines_wo_child '^interface' 'shutdown' source=candidate
    """
    config_txt = __salt__["net.config"](source=source)["out"][source]
    return __salt__["ciscoconfparse.find_lines_wo_child"](
        config=config_txt, parent_regex=parent_regex, child_regex=child_regex
    )


@depends(HAS_CISCOCONFPARSE)
def config_filter_lines(parent_regex, child_regex, source="running"):
    r"""
    .. versionadded:: 2019.2.0

    Return a list of detailed matches, for the configuration blocks (parent-child
    relationship) whose parent respects the regular expressions configured via
    the ``parent_regex`` argument, and the child matches the ``child_regex``
    regular expression. The result is a list of dictionaries with the following
    keys:

    - ``match``: a boolean value that tells whether ``child_regex`` matched any
      children lines.
    - ``parent``: the parent line (as text).
    - ``child``: the child line (as text). If no child line matched, this field
      will be ``None``.

    .. note::
        This function is only available only when the underlying library
        `ciscoconfparse <http://www.pennington.net/py/ciscoconfparse/index.html>`_
        is installed. See
        :py:func:`ciscoconfparse module <salt.modules.ciscoconfparse_mod>` for
        more details.

    parent_regex
        The regular expression to match the parent configuration lines against.

    child_regex
        The regular expression to match the child configuration lines against.

    source: ``running``
        The configuration type to retrieve from the network device. Default:
        ``running``. Available options: ``running``, ``startup``, ``candidate``.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.config_filter_lines '^interface' 'ip address'
        salt '*' napalm.config_filter_lines '^interface' 'shutdown' source=candidate
    """
    config_txt = __salt__["net.config"](source=source)["out"][source]
    return __salt__["ciscoconfparse.filter_lines"](
        config=config_txt, parent_regex=parent_regex, child_regex=child_regex
    )


def config_tree(source="running", with_tags=False):
    """
    .. versionadded:: 2019.2.0

    Transform Cisco IOS style configuration to structured Python dictionary.
    Depending on the value of the ``with_tags`` argument, this function may
    provide different views, valuable in different situations.

    source: ``running``
        The configuration type to retrieve from the network device. Default:
        ``running``. Available options: ``running``, ``startup``, ``candidate``.

    with_tags: ``False``
        Whether this function should return a detailed view, with tags.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.config_tree
    """
    config_txt = __salt__["net.config"](source=source)["out"][source]
    return __salt__["iosconfig.tree"](config=config_txt)


def config_merge_tree(
    source="running", merge_config=None, merge_path=None, saltenv="base"
):
    """
    .. versionadded:: 2019.2.0

    Return the merge tree of the ``initial_config`` with the ``merge_config``,
    as a Python dictionary.

    source: ``running``
        The configuration type to retrieve from the network device. Default:
        ``running``. Available options: ``running``, ``startup``, ``candidate``.

    merge_config
        The config to be merged into the initial config, sent as text. This
        argument is ignored when ``merge_path`` is set.

    merge_path
        Absolute or remote path from where to load the merge configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``merge_path`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.config_merge_tree merge_path=salt://path/to/merge.cfg
    """
    config_txt = __salt__["net.config"](source=source)["out"][source]
    return __salt__["iosconfig.merge_tree"](
        initial_config=config_txt,
        merge_config=merge_config,
        merge_path=merge_path,
        saltenv=saltenv,
    )


def config_merge_text(
    source="running", merge_config=None, merge_path=None, saltenv="base"
):
    """
    .. versionadded:: 2019.2.0

    Return the merge result of the configuration from ``source`` with the
    merge configuration, as plain text (without loading the config on the
    device).

    source: ``running``
        The configuration type to retrieve from the network device. Default:
        ``running``. Available options: ``running``, ``startup``, ``candidate``.

    merge_config
        The config to be merged into the initial config, sent as text. This
        argument is ignored when ``merge_path`` is set.

    merge_path
        Absolute or remote path from where to load the merge configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``merge_path`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.config_merge_text merge_path=salt://path/to/merge.cfg
    """
    config_txt = __salt__["net.config"](source=source)["out"][source]
    return __salt__["iosconfig.merge_text"](
        initial_config=config_txt,
        merge_config=merge_config,
        merge_path=merge_path,
        saltenv=saltenv,
    )


def config_merge_diff(
    source="running", merge_config=None, merge_path=None, saltenv="base"
):
    """
    .. versionadded:: 2019.2.0

    Return the merge diff, as text, after merging the merge config into the
    configuration source requested (without loading the config on the device).

    source: ``running``
        The configuration type to retrieve from the network device. Default:
        ``running``. Available options: ``running``, ``startup``, ``candidate``.

    merge_config
        The config to be merged into the initial config, sent as text. This
        argument is ignored when ``merge_path`` is set.

    merge_path
        Absolute or remote path from where to load the merge configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``merge_path`` is not a ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.config_merge_diff merge_path=salt://path/to/merge.cfg
    """
    config_txt = __salt__["net.config"](source=source)["out"][source]
    return __salt__["iosconfig.merge_diff"](
        initial_config=config_txt,
        merge_config=merge_config,
        merge_path=merge_path,
        saltenv=saltenv,
    )


def config_diff_tree(
    source1="candidate", candidate_path=None, source2="running", running_path=None
):
    """
    .. versionadded:: 2019.2.0

    Return the diff, as Python dictionary, between two different sources.
    The sources can be either specified using the ``source1`` and ``source2``
    arguments when retrieving from the managed network device.

    source1: ``candidate``
        The source from where to retrieve the configuration to be compared with.
        Available options: ``candidate``, ``running``, ``startup``. Default:
        ``candidate``.

    candidate_path
        Absolute or remote path from where to load the candidate configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    source2: ``running``
        The source from where to retrieve the configuration to compare with.
        Available options: ``candidate``, ``running``, ``startup``. Default:
        ``running``.

    running_path
        Absolute or remote path from where to load the running configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``candidate_path`` or ``running_path`` is not a
        ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.config_diff_text
        salt '*' napalm.config_diff_text candidate_path=https://bit.ly/2mAdq7z
        # Would compare the running config with the configuration available at
        # https://bit.ly/2mAdq7z

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.config_diff_tree
        salt '*' napalm.config_diff_tree running startup
    """
    get_config = __salt__["net.config"]()["out"]
    candidate_cfg = get_config[source1]
    running_cfg = get_config[source2]
    return __salt__["iosconfig.diff_tree"](
        candidate_config=candidate_cfg,
        candidate_path=candidate_path,
        running_config=running_cfg,
        running_path=running_path,
    )


def config_diff_text(
    source1="candidate", candidate_path=None, source2="running", running_path=None
):
    """
    .. versionadded:: 2019.2.0

    Return the diff, as text, between the two different configuration sources.
    The sources can be either specified using the ``source1`` and ``source2``
    arguments when retrieving from the managed network device.

    source1: ``candidate``
        The source from where to retrieve the configuration to be compared with.
        Available options: ``candidate``, ``running``, ``startup``. Default:
        ``candidate``.

    candidate_path
        Absolute or remote path from where to load the candidate configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    source2: ``running``
        The source from where to retrieve the configuration to compare with.
        Available options: ``candidate``, ``running``, ``startup``. Default:
        ``running``.

    running_path
        Absolute or remote path from where to load the running configuration
        text. This argument allows any URI supported by
        :py:func:`cp.get_url <salt.modules.cp.get_url>`), e.g., ``salt://``,
        ``https://``, ``s3://``, ``ftp:/``, etc.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``candidate_path`` or ``running_path`` is not a
        ``salt://`` URL.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.config_diff_text
        salt '*' napalm.config_diff_text candidate_path=https://bit.ly/2mAdq7z
        # Would compare the running config with the configuration available at
        # https://bit.ly/2mAdq7z
    """
    get_config = __salt__["net.config"]()["out"]
    candidate_cfg = get_config[source1]
    running_cfg = get_config[source2]
    return __salt__["iosconfig.diff_text"](
        candidate_config=candidate_cfg,
        candidate_path=candidate_path,
        running_config=running_cfg,
        running_path=running_path,
    )


@depends(HAS_SCP)
def scp_get(
    remote_path, local_path="", recursive=False, preserve_times=False, **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Transfer files and directories from remote network device to the localhost
    of the Minion.

    .. note::
        This function is only available only when the underlying library
        `scp <https://github.com/jbardin/scp.py>`_
        is installed. See
        :mod:`scp module <salt.modules.scp_mod>` for
        more details.

    remote_path
        Path to retrieve from remote host. Since this is evaluated by scp on the
        remote host, shell wildcards and environment variables may be used.

    recursive: ``False``
        Transfer files and directories recursively.

    preserve_times: ``False``
        Preserve ``mtime`` and ``atime`` of transferred files and directories.

    passphrase
        Used for decrypting private keys.

    pkey
        An optional private key to use for authentication.

    key_filename
        The filename, or list of filenames, of optional private key(s) and/or
        certificates to try for authentication.

    timeout
        An optional timeout (in seconds) for the TCP connect.

    socket_timeout: ``10``
        The channel socket timeout in seconds.

    buff_size: ``16384``
        The size of the SCP send buffer.

    allow_agent: ``True``
        Set to ``False`` to disable connecting to the SSH agent.

    look_for_keys: ``True``
        Set to ``False`` to disable searching for discoverable private key
        files in ``~/.ssh/``

    banner_timeout
        An optional timeout (in seconds) to wait for the SSH banner to be
        presented.

    auth_timeout
        An optional timeout (in seconds) to wait for an authentication
        response.

    auto_add_policy: ``False``
        Automatically add the host to the ``known_hosts``.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.scp_get /var/tmp/file /tmp/file auto_add_policy=True
    """
    conn_args = netmiko_args(**kwargs)
    conn_args["hostname"] = conn_args["host"]
    kwargs.update(conn_args)
    return __salt__["scp.get"](
        remote_path,
        local_path=local_path,
        recursive=recursive,
        preserve_times=preserve_times,
        **kwargs
    )


@depends(HAS_SCP)
def scp_put(
    files,
    remote_path=None,
    recursive=False,
    preserve_times=False,
    saltenv="base",
    **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Transfer files and directories to remote network device.

    .. note::
        This function is only available only when the underlying library
        `scp <https://github.com/jbardin/scp.py>`_
        is installed. See
        :mod:`scp module <salt.modules.scp_mod>` for
        more details.

    files
        A single path or a list of paths to be transferred.

    remote_path
        The path on the remote device where to store the files.

    recursive: ``True``
        Transfer files and directories recursively.

    preserve_times: ``False``
        Preserve ``mtime`` and ``atime`` of transferred files and directories.

    saltenv: ``base``
        The name of the Salt environment. Ignored when ``files`` is not a
        ``salt://`` URL.

    hostname
        The hostname of the remote device.

    port: ``22``
        The port of the remote device.

    username
        The username required for SSH authentication on the device.

    password
        Used for password authentication. It is also used for private key
        decryption if ``passphrase`` is not given.

    passphrase
        Used for decrypting private keys.

    pkey
        An optional private key to use for authentication.

    key_filename
        The filename, or list of filenames, of optional private key(s) and/or
        certificates to try for authentication.

    timeout
        An optional timeout (in seconds) for the TCP connect.

    socket_timeout: ``10``
        The channel socket timeout in seconds.

    buff_size: ``16384``
        The size of the SCP send buffer.

    allow_agent: ``True``
        Set to ``False`` to disable connecting to the SSH agent.

    look_for_keys: ``True``
        Set to ``False`` to disable searching for discoverable private key
        files in ``~/.ssh/``

    banner_timeout
        An optional timeout (in seconds) to wait for the SSH banner to be
        presented.

    auth_timeout
        An optional timeout (in seconds) to wait for an authentication
        response.

    auto_add_policy: ``False``
        Automatically add the host to the ``known_hosts``.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.scp_put /path/to/file /var/tmp/file auto_add_policy=True
    """
    conn_args = netmiko_args(**kwargs)
    conn_args["hostname"] = conn_args["host"]
    kwargs.update(conn_args)
    return __salt__["scp.put"](
        files,
        remote_path=remote_path,
        recursive=recursive,
        preserve_times=preserve_times,
        saltenv=saltenv,
        **kwargs
    )
