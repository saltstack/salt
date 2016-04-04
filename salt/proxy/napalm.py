# -*- coding: utf-8 -*-
"""
NAPALM
========

Proxy minion for managing network devices via NAPALM_ library.

.. _NAPALM: http://napalm.readthedocs.org

:codeauthor: Mircea Ulinic <mircea@cloudflare.com> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   linux

Dependencies
------------

- :doc:`napalm basic network functions (salt.modules.napalm_network) </ref/modules/all/salt.modules.napalm_network>`

See also
--------

- :doc:`NTP peers management module (salt.modules.napalm_ntp) </ref/modules/all/salt.modules.napalm_ntp>`

Pillar
------

The napalm proxy configuration requires four mandatory parameters in order to connect to the network device:

* driver: specifies the network device operating system. For a complete list of the supported operating systems \
please refer to the `NAPALM Read the Docs page`_.
* host: hostname
* username: username to be used when connecting to the device
* passwd: the password needed to establish the connection

.. _`NAPALM Read the Docs page`: http://napalm.readthedocs.org/en/latest/#supported-network-operating-systems

Example:

.. code-block:: yaml

    proxy:
        proxytype: napalm
        driver: junos
        host: core05.nrt02
        username: my_username
        passwd: my_password

.. versionadded: 2016.3
"""

from __future__ import absolute_import

# Import python lib
import logging
log = logging.getLogger(__file__)

# Import third party lib
import napalm

# ----------------------------------------------------------------------------------------------------------------------
# proxy properties
# ----------------------------------------------------------------------------------------------------------------------

__proxyenabled__ = ['napalm']
# proxy name

# ----------------------------------------------------------------------------------------------------------------------
# global variables
# ----------------------------------------------------------------------------------------------------------------------

NETWORK_DEVICE = {}

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    return True

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
    NETWORK_DEVICE['HOSTNAME'] = opts.get('proxy', {}).get('host')
    NETWORK_DEVICE['USERNAME'] = opts.get('proxy', {}).get('username')
    NETWORK_DEVICE['PASSWORD'] = opts.get('proxy', {}).get('passwd')
    NETWORK_DEVICE['DRIVER_NAME'] = opts.get('proxy', {}).get('driver')

    NETWORK_DEVICE['UP'] = False

    _driver_ = napalm.get_network_driver(NETWORK_DEVICE.get('DRIVER_NAME'))
    # get driver object form NAPALM

    optional_args = {
        'config_lock': False  # to avoid locking config DB
    }

    try:
        NETWORK_DEVICE['DRIVER'] = _driver_(
            NETWORK_DEVICE.get('HOSTNAME', ''),
            NETWORK_DEVICE.get('USERNAME', ''),
            NETWORK_DEVICE.get('PASSWORD', ''),
            timeout=120,
            optional_args=optional_args
        )
        NETWORK_DEVICE.get('DRIVER').open()
        # no exception raised here, means connection established
        NETWORK_DEVICE['UP'] = True
    except napalm.exceptions.ConnectionException as error:
        log.error(
            "Cannot connect to {hostname} as {username}. Please check error: {error}".format(
                hostname=NETWORK_DEVICE.get('HOSTNAME', ''),
                username=NETWORK_DEVICE.get('USERNAME', ''),
                error=error
            )
        )

    return True


def ping():
    '''
    Connection open successfully?
    '''
    return NETWORK_DEVICE['UP']


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
            'Cannot close connection with {hostname}! Please check error: {error}'.format(
                hostname=NETWORK_DEVICE.get('HOSTNAME', '[unknown hostname]'),
                error=error
            )
        )

    return True

# ----------------------------------------------------------------------------------------------------------------------
# Callable functions
# ----------------------------------------------------------------------------------------------------------------------


def call(method, **params):

    """
    Calls a specific method from the network driver instance.
    Please check the readthedocs_ page for the updated list of getters.

    .. _readthedocs: http://napalm.readthedocs.org/en/latest/support/index.html#getters-support-matrix

    :param method: specifies the name of the method to be called
    :param params: contains the mapping between the name and the values of the parameters needed to call the method
    :return: A dictionary with three keys:

        * result (True/False): if the operation succeeded
        * out (object): returns the object as-is from the call
        * comment (string): provides more details in case the call failed

    Example:

    .. code-block:: python

        __proxy__['napalm.call']('cli'
                                 **{
                                    'commands': [
                                        'show version',
                                        'show chassis fan'
                                    ]
                                 })
    """

    result = False
    out = None

    try:
        if not NETWORK_DEVICE.get('UP', False):
            raise Exception('not connected')
        # if connected will try to execute desired command
        out = getattr(NETWORK_DEVICE.get('DRIVER'), method)(**params)  # calls the method with the specified parameters
        result = True
    except Exception as error:
        # either not connected
        # either unable to execute the command
        return {
            'out': {},
            'result': False,
            'comment': 'Cannot execute "{method}" on {device}. Reason: {error}!'.format(
                device=NETWORK_DEVICE.get('HOSTNAME', '[unspecified hostname]'),
                method=method,
                error=error
            )
        }

    return {
        'out': out,
        'result': result,
        'comment': ''
    }
