# -*- coding: utf-8 -*-
'''
NAPALM: Network Automation and Programmability Abstraction Layer with Multivendor support
=========================================================================================

Proxy minion for managing network devices via NAPALM_ library.

:codeauthor: Mircea Ulinic <mircea@cloudflare.com> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------

The ``napalm`` proxy module requires NAPALM_ library to be installed:  ``pip install napalm``
Please check Installation_ for complete details.

.. _NAPALM: https://napalm.readthedocs.io
.. _Installation: https://napalm.readthedocs.io/en/latest/installation.html


Pillar
------

The napalm proxy configuration requires four mandatory parameters in order to connect to the network device:

* driver: specifies the network device operating system. For a complete list of the supported operating systems \
please refer to the `NAPALM Read the Docs page`_.
* host: hostname
* username: username to be used when connecting to the device
* passwd: the password needed to establish the connection
* optional_args: dictionary with the optional arguments. Check the complete list of supported `optional arguments`_

.. _`NAPALM Read the Docs page`: https://napalm.readthedocs.io/en/latest/#supported-network-operating-systems
.. _`optional arguments`: http://napalm.readthedocs.io/en/latest/support/index.html#list-of-supported-optional-arguments


Example:

.. code-block:: yaml

    proxy:
        proxytype: napalm
        driver: junos
        host: core05.nrt02
        username: my_username
        passwd: my_password
        optional_args:
            port: 12201
            config_format: set

.. seealso::

    - :mod:`NAPALM grains: select network devices based on their characteristics <salt.grains.napalm>`
    - :mod:`NET module: network basic features <salt.modules.napalm_network>`
    - :mod:`NTP operational and configuration management module <salt.modules.napalm_ntp>`
    - :mod:`BGP operational and configuration management module <salt.modules.napalm_bgp>`
    - :mod:`Routes details <salt.modules.napalm_route>`
    - :mod:`SNMP configuration module <salt.modules.napalm_snmp>`
    - :mod:`Users configuration management <salt.modules.napalm_users>`

.. versionadded:: 2016.11.0
'''

from __future__ import absolute_import

# Import python lib
import logging
log = logging.getLogger(__file__)

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

from salt.ext import six
import salt.utils.napalm

# ----------------------------------------------------------------------------------------------------------------------
# proxy properties
# ----------------------------------------------------------------------------------------------------------------------

__proxyenabled__ = ['napalm']
# proxy name

# ----------------------------------------------------------------------------------------------------------------------
# global variables
# ----------------------------------------------------------------------------------------------------------------------

NETWORK_DEVICE = {}
DETAILS = {}

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    return HAS_NAPALM or (False, 'Please install the NAPALM library: `pip install napalm`!')

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# Proxy functions
# ----------------------------------------------------------------------------------------------------------------------


def init(opts):
    '''
    Opens the connection with the network device.
    '''
    NETWORK_DEVICE.update(salt.utils.napalm.get_device(opts))
    DETAILS['initialized'] = True
    return True


def alive(opts):
    '''
    Return the connection status with the remote device.

    .. versionadded:: Nitrogen
    '''
    if salt.utils.napalm.not_always_alive(opts):
        return True  # don't force reconnection for not-always alive proxies
        # or regular minion
    is_alive_ret = call('is_alive', **{})
    if not is_alive_ret.get('result', False):
        log.debug('[{proxyid}] Unable to execute `is_alive`: {comment}'.format(
            proxyid=opts.get('id'),
            comment=is_alive_ret.get('comment')
        ))
        # if `is_alive` is not implemented by the underneath driver,
        # will consider the connection to be still alive
        # we don't want overly request connection reestablishment
        # NOTE: revisit this if IOS is still not stable
        #       and return False to force reconnection
        return True
    flag = is_alive_ret.get('out', {}).get('is_alive', False)
    log.debug('Is {proxyid} still alive? {answ}'.format(
        proxyid=opts.get('id'),
        answ='Yes.' if flag else 'No.'
    ))
    return flag


def ping():
    '''
    Connection open successfully?
    '''
    return NETWORK_DEVICE.get('UP', False)


def initialized():
    '''
    Connection finished initializing?
    '''
    return DETAILS.get('initialized', False)


def get_device():
    '''
    Returns the network device object.
    '''
    return NETWORK_DEVICE


def get_grains():
    '''
    Retrieve facts from the network device.
    '''
    refresh_needed = False
    refresh_needed = refresh_needed or (not DETAILS.get('grains_cache', {}))
    refresh_needed = refresh_needed or (not DETAILS.get('grains_cache', {}).get('result', False))
    refresh_needed = refresh_needed or (not DETAILS.get('grains_cache', {}).get('out', {}))

    if refresh_needed:
        facts = call('get_facts', **{})
        DETAILS['grains_cache'] = facts

    return DETAILS.get('grains_cache', {})


def grains_refresh():
    '''
    Refresh the grains.
    '''
    DETAILS['grains_cache'] = {}
    return get_grains()


def fns():
    '''
    Method called by NAPALM grains module.
    '''
    return {
        'details': 'Network device grains.'
    }


def shutdown(opts):
    '''
    Closes connection with the device.
    '''
    try:
        if not NETWORK_DEVICE.get('UP', False):
            raise Exception('not connected!')
        NETWORK_DEVICE.get('DRIVER').close()
    except Exception as error:
        log.error(
            'Cannot close connection with {hostname}{port}! Please check error: {error}'.format(
                hostname=NETWORK_DEVICE.get('HOSTNAME', '[unknown hostname]'),
                port=(':{port}'.format(port=NETWORK_DEVICE.get('OPTIONAL_ARGS', {}).get('port'))
                      if NETWORK_DEVICE.get('OPTIONAL_ARGS', {}).get('port') else ''),
                error=error
            )
        )

    return True

# ----------------------------------------------------------------------------------------------------------------------
# Callable functions
# ----------------------------------------------------------------------------------------------------------------------


def call(method, *args, **kwargs):
    '''
    Calls a specific method from the network driver instance.
    Please check the readthedocs_ page for the updated list of getters.

    .. _readthedocs: http://napalm.readthedocs.org/en/latest/support/index.html#getters-support-matrix

    :param method: specifies the name of the method to be called
    :param params: contains the mapping between the name and the values of the parameters needed to call the method
    :return: A dictionary with three keys:

        * result (True/False): if the operation succeeded
        * out (object): returns the object as-is from the call
        * comment (string): provides more details in case the call failed
        * traceback (string): complete traceback in case of exeception. Please submit an issue including this traceback
        on the `correct driver repo`_ and make sure to read the FAQ_

    .. _`correct driver repo`: https://github.com/napalm-automation/napalm/issues/new
    .. FAQ_: https://github.com/napalm-automation/napalm#faq

    Example:

    .. code-block:: python

        __proxy__['napalm.call']('cli'
                                 **{
                                    'commands': [
                                        'show version',
                                        'show chassis fan'
                                    ]
                                 })
    '''
    kwargs_copy = {}
    kwargs_copy.update(kwargs)
    for karg, warg in six.iteritems(kwargs_copy):
        # will remove None values
        # thus the NAPALM methods will be called with their defaults
        if warg is None:
            kwargs.pop(karg)
    return salt.utils.napalm.call(NETWORK_DEVICE, method, *args, **kwargs)
