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
def compliance_report(filepath, **kwargs):
    '''
    Return the compliance report.

    filepath
        The absolute path to the validation file.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.compliance_report ~/validate.yml

    Validation File Example:

    .. code-block:: yaml

        - get_facts:
            os_version: 4.17

        - get_interfaces_ip:
            Management1:
                ipv4:
                    10.0.2.14:
                        prefix_length: 24
                    _mode: strict

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
    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'compliance_report',
        validation_file=filepath
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
