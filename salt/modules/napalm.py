# -*- coding: utf-8 -*-
'''
NAPALM helpers
==============

Helpers for the NAPALM modules.

.. versionadded:: 2017.7.0
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import python stdlib
import inspect
import logging
log = logging.getLogger(__file__)

# import NAPALM utils
import salt.utils.napalm
from salt.utils.napalm import proxy_napalm_wrap

# Import Salt modules
from salt.ext import six
from salt.exceptions import CommandExecutionError
try:
    from netmiko import BaseConnection
    HAS_NETMIKO = True
except ImportError:
    HAS_NETMIKO = False

try:
    import napalm.base.netmiko_helpers
    HAS_NETMIKO_HELPERS = True
except ImportError:
    HAS_NETMIKO_HELPERS = False

try:
    import jxmlease  # pylint: disable=unused-import
    HAS_JXMLEASE = True
except ImportError:
    HAS_JXMLEASE = False

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'napalm'
__proxyenabled__ = ['napalm']
# uses NAPALM-based proxy to interact with network devices

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    '''
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    '''
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------


def _get_netmiko_args(optional_args):
    '''
    Check for Netmiko arguments that were passed in as NAPALM optional arguments.

    Return a dictionary of these optional args that will be passed into the
    Netmiko ConnectHandler call.

    .. note::

        This is a port of the NAPALM helper for backwards compatibility with
        older versions of NAPALM, and stability across Salt features.
        If the netmiko helpers module is available however, it will prefer that
        implementation nevertheless.
    '''
    if HAS_NETMIKO_HELPERS:
        return napalm.base.netmiko_helpers.netmiko_args(optional_args)
    # Older version don't have the netmiko_helpers module, the following code is
    # simply a port from the NAPALM code base, for backwards compatibility:
    # https://github.com/napalm-automation/napalm/blob/develop/napalm/base/netmiko_helpers.py
    netmiko_args, _, _, netmiko_defaults = inspect.getargspec(BaseConnection.__init__)
    check_self = netmiko_args.pop(0)
    if check_self != 'self':
        raise ValueError('Error processing Netmiko arguments')
    netmiko_argument_map = dict(six.moves.zip(netmiko_args, netmiko_defaults))
    # Netmiko arguments that are integrated into NAPALM already
    netmiko_filter = ['ip', 'host', 'username', 'password', 'device_type', 'timeout']
    # Filter out all of the arguments that are integrated into NAPALM
    for k in netmiko_filter:
        netmiko_argument_map.pop(k)
    # Check if any of these arguments were passed in as NAPALM optional_args
    netmiko_optional_args = {}
    for k, v in six.iteritems(netmiko_argument_map):
        try:
            netmiko_optional_args[k] = optional_args[k]
        except KeyError:
            pass
    # Return these arguments for use with establishing Netmiko SSH connection
    return netmiko_optional_args


def _inject_junos_proxy(napalm_device):
    '''
    Inject the junos.conn key into the __proxy__, reusing the existing NAPALM
    connection to the Junos device.
    '''
    def _ret_device():
        return napalm_device['DRIVER'].device
    __proxy__['junos.conn'] = _ret_device
    # Injecting the junos.conn key into the __proxy__ object, we can then
    # access the features that already exist into the junos module, as long
    # as the rest of the dependencies are installed (jxmlease).
    # junos-eznc is already installed, as part of NAPALM, and the napalm
    # driver for junos already makes use of the Device class from this lib.
    # So pointing the __proxy__ object to this object already loaded into
    # memory, we can go and re-use the features from the existing junos
    # Salt module.


def _junos_prep_fun(napalm_device):
    '''
    Prepare the Junos function.
    '''
    if __grains__['os'] != 'junos':
        return {
            'out': None,
            'result': False,
            'comment': 'This function is only available on Junos'
        }
    if not HAS_JXMLEASE:
        return {
            'out': None,
            'result': False,
            'comment': 'Please install jxmlease (``pip install jxmlease``) to be able to use this function.'
        }
    _inject_junos_proxy(napalm_device)
    return {
        'result': True
    }

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


@proxy_napalm_wrap
def alive(**kwargs):  # pylint: disable=unused-argument
    '''
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
    '''
    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'is_alive',
        **{}
    )


@proxy_napalm_wrap
def reconnect(force=False, **kwargs):  # pylint: disable=unused-argument
    '''
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
    '''
    default_ret = {
        'out': None,
        'result': True,
        'comment': 'Already alive.'
    }
    if not salt.utils.napalm.is_proxy(__opts__):
        # regular minion is always alive
        # otherwise, the user would not be able to execute this command
        return default_ret
    is_alive = alive()
    log.debug('Is alive fetch:')
    log.debug(is_alive)
    if not is_alive.get('result', False) or\
       not is_alive.get('out', False) or\
       not is_alive.get('out', {}).get('is_alive', False) or\
       force:  # even if alive, but the user wants to force a restart
        proxyid = __opts__.get('proxyid') or __opts__.get('id')
        # close the connection
        log.info('Closing the NAPALM proxy connection with %s', proxyid)
        salt.utils.napalm.call(
            napalm_device,  # pylint: disable=undefined-variable
            'close',
            **{}
        )
        # and re-open
        log.info('Re-opening the NAPALM proxy connection with %s', proxyid)
        salt.utils.napalm.call(
            napalm_device,  # pylint: disable=undefined-variable
            'open',
            **{}
        )
        default_ret.update({
            'comment': 'Connection restarted!'
        })
        return default_ret
    # otherwise, I have nothing to do here:
    return default_ret


@proxy_napalm_wrap
def call(method, *args, **kwargs):
    '''
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
    '''
    clean_kwargs = {}
    for karg, warg in six.iteritems(kwargs):
        # remove the __pub args
        if not karg.startswith('__pub_'):
            clean_kwargs[karg] = warg
    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        method,
        *args,
        **clean_kwargs
    )


@proxy_napalm_wrap
def compliance_report(filepath=None,
                      string=None,
                      renderer='jinja|yaml',
                      **kwargs):
    '''
    Return the compliance report.

    filepath
        The absolute path to the validation file.

        .. versionchanged:: Fluorine

        Beginning with release codename ``Fluorine``, this function has been
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

        .. versionchanged:: Fluorine

        The compliance report send as inline string, to be used as the file to
        send through the renderer system. Note, not all renderer modules can
        work with strings; the 'py' renderer requires a file, for example.

    renderer: ``jinja|yaml``

        .. versionchanged:: Fluorine

        The renderer pipe to send the file through; this is overridden by a
        "she-bang" at the top of the file.

    kwargs

        .. versionchanged:: Fluorine

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
    '''
    validation_string = __salt__['slsutil.renderer'](path=filepath,
                                                     string=string,
                                                     default_renderer=renderer,
                                                     **kwargs)
    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'compliance_report',
        validation_source=validation_string
    )


@proxy_napalm_wrap
def netmiko_args(**kwargs):
    '''
    .. versionadded:: Fluorine

    Return the key-value arguments used for the authentication arguments for
    the netmiko module.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.netmiko_args
    '''
    if not HAS_NETMIKO:
        raise CommandExecutionError('Please install netmiko to be able to use this feature.')
    kwargs = {}
    napalm_opts = salt.utils.napalm.get_device_opts(__opts__, salt_obj=__salt__)
    optional_args = napalm_opts['OPTIONAL_ARGS']
    netmiko_args = _get_netmiko_args(optional_args)
    kwargs['host'] = napalm_opts['HOSTNAME']
    kwargs['username'] = napalm_opts['USERNAME']
    kwargs['password'] = napalm_opts['PASSWORD']
    kwargs['timeout'] = napalm_opts['TIMEOUT']
    kwargs.update(netmiko_args)
    netmiko_device_type_map = {
        'junos': 'juniper_junos',
        'ios': 'cisco_ios',
        'iosxr': 'cisco_xr',
        'eos': 'arista_eos',
        'nxos_ssh': 'cisco_nxos',
        'asa': 'cisco_asa',
        'fortios': 'fortinet',
        'panos': 'paloalto_panos',
        'aos': 'alcatel_aos',
        'vyos': 'vyos'
    }
    # If you have a device type that is not listed here, please submit a PR
    # to add it, and/or add the map into your opts/Pillar: netmiko_device_type_map
    # Example:
    #
    # netmiko_device_type_map:
    #   junos: juniper_junos
    #   ios: cisco_ios
    #
    #etc.
    netmiko_device_type_map.update(__salt__['config.get']('netmiko_device_type_map', {}))
    kwargs['device_type'] = netmiko_device_type_map[__grains__['os']]
    return kwargs


@proxy_napalm_wrap
def netmiko_fun(fun, *args, **kwargs):
    '''
    .. versionadded:: Fluorine

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
    '''
    if 'netmiko.' not in fun:
        fun = 'netmiko.{fun}'.format(fun=fun)
    netmiko_kwargs = netmiko_args()
    kwargs.update(netmiko_kwargs)
    return __salt__[fun](*args, **kwargs)


@proxy_napalm_wrap
def netmiko_call(method, *args, **kwargs):
    '''
    .. versionadded:: Fluorine

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
    '''
    netmiko_kwargs = netmiko_args()
    kwargs.update(netmiko_kwargs)
    return __salt__['netmiko.call'](method, *args, **kwargs)


@proxy_napalm_wrap
def netmiko_multi_call(*methods, **kwargs):
    '''
    .. versionadded:: Fluorine

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
    '''
    netmiko_kwargs = netmiko_args()
    kwargs.update(netmiko_kwargs)
    return __salt__['netmiko.multi_call'](*methods, **kwargs)


@proxy_napalm_wrap
def netmiko_commands(*commands, **kwargs):
    '''
    .. versionadded:: Fluorine

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
    '''
    conn = netmiko_conn(**kwargs)
    ret = []
    for cmd in commands:
        ret.append(conn.send_command(cmd))
    return ret


@proxy_napalm_wrap
def netmiko_config(*config_commands, **kwargs):
    '''
    .. versionadded:: Fluorine

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
    '''
    netmiko_kwargs = netmiko_args()
    kwargs.update(netmiko_kwargs)
    return __salt__['netmiko.send_config'](config_commands=config_commands,
                                           **kwargs)


@proxy_napalm_wrap
def netmiko_conn(**kwargs):
    '''
    .. versionadded:: Fluorine

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
    '''
    netmiko_kwargs = netmiko_args()
    kwargs.update(netmiko_kwargs)
    return __salt__['netmiko.get_connection'](**kwargs)


@proxy_napalm_wrap
def junos_rpc(cmd=None, dest=None, format=None, **kwargs):
    '''
    .. versionadded:: Fluorine

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
        salt '*' napalm.junos_rcp get-config <configuration><system><ntp/></system></configuration>
    '''
    prep = _junos_prep_fun(napalm_device)  # pylint: disable=undefined-variable
    if not prep['result']:
        return prep
    if not format:
        format = 'xml'
    rpc_ret = __salt__['junos.rpc'](cmd=cmd,
                                    dest=dest,
                                    format=format,
                                    **kwargs)
    rpc_ret['comment'] = rpc_ret.pop('message', '')
    rpc_ret['result'] = rpc_ret.pop('out', False)
    rpc_ret['out'] = rpc_ret.pop('rpc_reply', None)
    # The comment field is "message" in the Junos module
    return rpc_ret


@proxy_napalm_wrap
def junos_install_os(path=None, **kwargs):
    '''
    .. versionadded:: Fluorine

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
    '''
    prep = _junos_prep_fun(napalm_device)  # pylint: disable=undefined-variable
    if not prep['result']:
        return prep
    return __salt__['junos.install_os'](path=path, **kwargs)


@proxy_napalm_wrap
def junos_facts(**kwargs):
    '''
    .. versionadded:: Fluorine

    The complete list of Junos facts collected by ``junos-eznc``.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.junos_facts
    '''
    prep = _junos_prep_fun(napalm_device)  # pylint: disable=undefined-variable
    if not prep['result']:
        return prep
    facts = dict(napalm_device['DRIVER'].device.facts)  # pylint: disable=undefined-variable
    if 'version_info' in facts:
        facts['version_info'] = \
            dict(facts['version_info'])
    # For backward compatibility. 'junos_info' is present
    # only of in newer versions of facts.
    if 'junos_info' in facts:
        for re in facts['junos_info']:
            facts['junos_info'][re]['object'] = \
                dict(facts['junos_info'][re]['object'])
    return facts


@proxy_napalm_wrap
def junos_cli(command, format=None, dev_timeout=None, dest=None, **kwargs):
    '''
    .. versionadded:: Fluorine

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
    '''
    prep = _junos_prep_fun(napalm_device)  # pylint: disable=undefined-variable
    if not prep['result']:
        return prep
    return __salt__['junos.cli'](command,
                                 format=format,
                                 dev_timeout=dev_timeout,
                                 dest=dest,
                                 **kwargs)


@proxy_napalm_wrap
def junos_copy_file(src, dst, **kwargs):
    '''
    .. versionadded:: Fluorine

    Copies the file on the remote Junos device.

    src
        The source file path. This argument accepts the usual Salt URIs (e.g.,
        ``salt://``, ``http://``, ``https://``, ``s3://``, ``ftp://``, etc.).

    dst
        The destination path on the device where to copy the file.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.junos_copy_file https://example.com/junos.cfg /var/tmp/myjunos.cfg
    '''
    prep = _junos_prep_fun(napalm_device)  # pylint: disable=undefined-variable
    if not prep['result']:
        return prep
    cached_src = __salt__['cp.cache_file'](src)
    return __salt__['junos.file_copy'](cached_src, dst)


@proxy_napalm_wrap
def junos_call(fun, *args, **kwargs):
    '''
    .. versionadded:: Fluorine

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
    '''
    prep = _junos_prep_fun(napalm_device)  # pylint: disable=undefined-variable
    if not prep['result']:
        return prep
    if 'junos.' not in fun:
        mod_fun = 'junos.{}'.format(fun)
    else:
        mod_fun = fun
    if mod_fun not in __salt__:
        return {
            'out': None,
            'result': False,
            'comment': '{} is not a valid function'.format(fun)
        }
    return __salt__[mod_fun](*args, **kwargs)
