# -*- coding: utf-8 -*-
'''
Utils for the NAPALM modules and proxy.

.. seealso::

    - :mod:`NAPALM grains: select network devices based on their characteristics <salt.grains.napalm>`
    - :mod:`NET module: network basic features <salt.modules.napalm_network>`
    - :mod:`NTP operational and configuration management module <salt.modules.napalm_ntp>`
    - :mod:`BGP operational and configuration management module <salt.modules.napalm_bgp>`
    - :mod:`Routes details <salt.modules.napalm_route>`
    - :mod:`SNMP configuration module <salt.modules.napalm_snmp>`
    - :mod:`Users configuration management <salt.modules.napalm_users>`

.. versionadded:: Nitrogen
'''

from __future__ import absolute_import

import traceback
import logging
log = logging.getLogger(__file__)

import salt.utils

# Import third party lib
try:
    # will try to import NAPALM
    # https://github.com/napalm-automation/napalm
    # pylint: disable=W0611
    import napalm_base
    # pylint: enable=W0611
    HAS_NAPALM = True
except ImportError:
    HAS_NAPALM = False

from salt.ext import six as six


def is_proxy(opts):
    '''
    Is this a NAPALM proxy?
    '''
    return salt.utils.is_proxy() and opts.get('proxy', {}).get('proxytype') == 'napalm'


def is_minion(opts):
    '''
    Is this a NAPALM straight minion?
    '''
    return not salt.utils.is_proxy() and 'napalm' in opts


def virtual(opts, virtualname, filename):
    '''
    Returns the __virtual__.
    '''
    if HAS_NAPALM and (is_proxy(opts) or is_minion(opts)):
        return virtualname
    else:
        return (
            False,
            (
                '"{vname}"" {filename} cannot be loaded: '
                'NAPALM is not installed or not running in a (proxy) minion'
            ).format(
                vname=virtualname,
                filename='({filename})'.format(filename=filename)
            )
        )


def call(napalm_device, method, *args, **kwargs):
    '''
    Calls arbitrary methods from the network driver instance.
    Please check the readthedocs_ page for the updated list of getters.

    .. _readthedocs: http://napalm.readthedocs.org/en/latest/support/index.html#getters-support-matrix

    method
        Specifies the name of the method to be called.

    *args
        Arguments.

    **kwargs
        More arguments.

    :return: A dictionary with three keys:

        * result (True/False): if the operation succeeded
        * out (object): returns the object as-is from the call
        * comment (string): provides more details in case the call failed
        * traceback (string): complete traceback in case of exeception. \
        Please submit an issue including this traceback \
        on the `correct driver repo`_ and make sure to read the FAQ_

    .. _`correct driver repo`: https://github.com/napalm-automation/napalm/issues/new
    .. FAQ_: https://github.com/napalm-automation/napalm#faq

    Example:

    .. code-block:: python

        salt.utils.napalm.call(
            napalm_object,
            'cli',
            [
                'show version',
                'show chassis fan'
            ]
        )
    '''
    result = False
    out = None
    try:
        if not napalm_device.get('UP', False):
            raise Exception('not connected')
        # if connected will try to execute desired command
        kwargs_copy = {}
        kwargs_copy.update(kwargs)
        for karg, warg in six.iteritems(kwargs_copy):
            # lets clear None arguments
            # to not be sent to NAPALM methods
            if warg is None:
                kwargs.pop(karg)
        out = getattr(napalm_device.get('DRIVER'), method)(*args, **kwargs)
        # calls the method with the specified parameters
        result = True
    except Exception as error:
        # either not connected
        # either unable to execute the command
        err_tb = traceback.format_exc()  # let's get the full traceback and display for debugging reasons.
        if isinstance(error, NotImplementedError):
            comment = '{method} is not implemented for the NAPALM {driver} driver!'.format(
                method=method,
                driver=napalm_device.get('DRIVER_NAME')
            )
        else:
            comment = 'Cannot execute "{method}" on {device}{port} as {user}. Reason: {error}!'.format(
                device=napalm_device.get('HOSTNAME', '[unspecified hostname]'),
                port=(':{port}'.format(port=napalm_device.get('OPTIONAL_ARGS', {}).get('port'))
                      if napalm_device.get('OPTIONAL_ARGS', {}).get('port') else ''),
                user=napalm_device.get('USERNAME', ''),
                method=method,
                error=error
            )
        log.error(comment)
        log.error(err_tb)
        return {
            'out': {},
            'result': False,
            'comment': comment,
            'traceback': err_tb
        }
    return {
        'out': out,
        'result': result,
        'comment': ''
    }


def get_device(opts, salt_obj=None):
    '''
    Initialise the connection with the network device through NAPALM.
    :param: opts
    :return: the network device object
    '''
    log.debug('Setting up NAPALM connection')
    network_device = {}
    # by default, look in the proxy config details
    device_dict = opts.get('proxy', {}) or opts.get('napalm', {})
    if salt_obj and not device_dict:
        # get the connection details from the opts
        device_dict = salt_obj['config.option']('napalm')
    if not device_dict:
        # still not able to setup
        log.error('Incorrect minion config. Please specify at least the napalm driver name!')
    # either under the proxy hier, either under the napalm in the config file
    network_device['HOSTNAME'] = device_dict.get('host') or device_dict.get('hostname')
    network_device['USERNAME'] = device_dict.get('username') or device_dict.get('user')
    network_device['DRIVER_NAME'] = device_dict.get('driver') or device_dict.get('os')
    network_device['PASSWORD'] = device_dict.get('passwd') or device_dict.get('password') or device_dict.get('pass')
    network_device['TIMEOUT'] = device_dict.get('timeout', 60)
    network_device['OPTIONAL_ARGS'] = device_dict.get('optional_args', {})
    network_device['UP'] = False
    # get driver object form NAPALM
    if 'config_lock' not in list(network_device['OPTIONAL_ARGS'].keys()):
        network_device['OPTIONAL_ARGS']['config_lock'] = False
    _driver_ = napalm_base.get_network_driver(network_device.get('DRIVER_NAME'))
    try:
        network_device['DRIVER'] = _driver_(
            network_device.get('HOSTNAME', ''),
            network_device.get('USERNAME', ''),
            network_device.get('PASSWORD', ''),
            timeout=network_device['TIMEOUT'],
            optional_args=network_device['OPTIONAL_ARGS']
        )
        network_device.get('DRIVER').open()
        # no exception raised here, means connection established
        network_device['UP'] = True
    except napalm_base.exceptions.ConnectionException as error:
        base_err_msg = "Cannot connect to {hostname}{port} as {username}.".format(
            hostname=network_device.get('HOSTNAME', '[unspecified hostname]'),
            port=(':{port}'.format(port=network_device.get('OPTIONAL_ARGS', {}).get('port'))
                  if network_device.get('OPTIONAL_ARGS', {}).get('port') else ''),
            username=network_device.get('USERNAME', '')
        )
        log.error(base_err_msg)
        log.error(
            "Please check error: {error}".format(
                error=error
            )
        )
        raise napalm_base.exceptions.ConnectionException(base_err_msg)
    return network_device


def proxy_napalm_wrap(func):
    '''
    This decorator is used to make the execution module functions
    available outside a proxy minion, or when running inside a proxy
    minion. If we are running in a proxy, retrieve the connection details
    from the __proxy__ injected variable.  If we are not, then
    use the connection information from the opts.
    :param func:
    :return:
    '''
    def func_wrapper(*args, **kwargs):
        wrapped_global_namespace = func.__globals__
        # get __proxy__ from func_globals
        proxy = wrapped_global_namespace.get('__proxy__')

        # in any case, will inject the `napalm_device` global
        # the execution modules will make use of this variable from now on
        # previously they were accessing the device properties through the __proxy__ object
        if salt.utils.is_proxy():
            wrapped_global_namespace['napalm_device'] = proxy['napalm.get_device']()
        else:
            # get __opts__ and __salt__ from func_globals
            opts = wrapped_global_namespace.get('__opts__')
            _salt_obj = wrapped_global_namespace.get('__salt__')
            if 'inherit_napalm_device' not in kwargs or ('inherit_napalm_device' in kwargs and
                                                         not kwargs['inherit_napalm_device']):
                # try to open a new connection
                # but only if the function does not inherit the napalm driver
                # for configuration management this is very important,
                # in order to make sure we are editing the same session.
                try:
                    wrapped_global_namespace['napalm_device'] = get_device(opts, salt_obj=_salt_obj)
                except napalm_base.exceptions.ConnectionException as nce:
                    return '{base_msg}. See log for details.'.format(
                        base_msg=str(nce.msg)
                    )
            else:
                # in case the `inherit_napalm_device` is set
                # and it also has a non-empty value,
                # the global var `napalm_device` will be overriden.
                # this is extremely important for configuration-related features
                # as all actions must be issued within the same configuration session
                # otherwise we risk to open multiple sessions
                wrapped_global_namespace['napalm_device'] = kwargs['inherit_napalm_device']
        return func(*args, **kwargs)
    return func_wrapper
