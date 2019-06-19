# -*- coding: utf-8 -*-
'''
NAPALM: Network Automation and Programmability Abstraction Layer with Multivendor support
=========================================================================================

.. versionadded:: 2016.11.0

Proxy minion for managing network devices via NAPALM_ library.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------

The ``napalm`` proxy module requires NAPALM_ library to be installed:  ``pip install napalm``
Please check Installation_ for complete details.

.. _NAPALM: https://napalm-automation.net/
.. _Installation: http://napalm.readthedocs.io/en/latest/installation/index.html

.. note::

    Beginning with Salt release 2017.7.3, it is recommended to use
    ``napalm`` >= ``2.0.0``. The library has been unified into a monolithic
    package, as in opposite to separate packages per driver. For more details
    you can check `this document <https://napalm-automation.net/reunification/>`_.
    While it will still work with the old packages, bear in mind that the NAPALM
    core team will maintain only the main ``napalm`` package.

    Moreover, for additional capabilities, the users can always define a
    library that extends NAPALM's base capabilities and configure the
    ``provider`` option (see below).

Pillar
------

The napalm proxy configuration requires the following parameters in order to connect to the network device:

driver
    Specifies the network device operating system.
    For a complete list of the supported operating systems please refer to the
    `NAPALM Read the Docs page`_.

host
    The IP Address or FQDN to use when connecting to the device. Alternatively,
    the following field names can be used instead: ``hostname``, ``fqdn``, ``ip``.

username
    The username to be used when connecting to the device.

passwd
    The password needed to establish the connection.

    .. note::

        This field may not be mandatory when working with SSH-based drivers, and
        the username has a SSH key properly configured on the device targeted to
        be managed.

optional_args
    Dictionary with the optional arguments.
    Check the complete list of supported `optional arguments`_.

always_alive: ``True``
    In certain less dynamic environments, maintaining the remote connection permanently
    open with the network device is not always beneficial. In that case, the user can
    select to initialize the connection only when needed, by specifying this field to ``false``.
    Default: ``true`` (maintains the connection with the remote network device).

    .. versionadded:: 2017.7.0

provider: ``napalm_base``
    The library that provides the ``get_network_device`` function.
    This option is useful when the user has more specific needs and requires
    to extend the NAPALM capabilities using a private library implementation.
    The only constraint is that the alternative library needs to have the
    ``get_network_device`` function available.

    .. versionadded:: 2017.7.1

multiprocessing: ``False``
    Overrides the :conf_minion:`multiprocessing` option, per proxy minion.
    The ``multiprocessing`` option must be turned off for SSH-based proxies.
    However, some NAPALM drivers (e.g. Arista, NX-OS) are not SSH-based.
    As multiple proxy minions may share the same configuration file,
    this option permits the configuration of the ``multiprocessing`` option
    more specifically, for some proxy minions.

    .. versionadded:: 2017.7.2


.. _`NAPALM Read the Docs page`: https://napalm.readthedocs.io/en/latest/#supported-network-operating-systems
.. _`optional arguments`: http://napalm.readthedocs.io/en/latest/support/index.html#list-of-supported-optional-arguments

Proxy pillar file example:

.. code-block:: yaml

    proxy:
      proxytype: napalm
      driver: junos
      host: core05.nrt02
      username: my_username
      passwd: my_password
      optional_args:
        port: 12201

Example using a user-specific library, extending NAPALM's capabilities, e.g. ``custom_napalm_base``:

.. code-block:: yaml

    proxy:
      proxytype: napalm
      driver: ios
      fqdn: cr1.th2.par.as1234.net
      username: salt
      password: ''
      provider: custom_napalm_base

.. seealso::

    - :mod:`NAPALM grains: select network devices based on their characteristics <salt.grains.napalm>`
    - :mod:`NET module: network basic features <salt.modules.napalm_network>`
    - :mod:`Network config state: Manage the configuration using arbitrary templates <salt.states.netconfig>`
    - :mod:`NAPALM YANG state: Manage the configuration according to the YANG models (OpenConfig/IETF) <salt.states.netyang>`
    - :mod:`Network ACL module: Generate and load ACL (firewall) configuration <salt.modules.napalm_acl>`
    - :mod:`Network ACL state: Manage the firewall configuration <salt.states.netacl>`
    - :mod:`NTP operational and configuration management module <salt.modules.napalm_ntp>`
    - :mod:`BGP operational and configuration management module <salt.modules.napalm_bgp>`
    - :mod:`Routes details <salt.modules.napalm_route>`
    - :mod:`SNMP configuration module <salt.modules.napalm_snmp>`
    - :mod:`Users configuration management <salt.modules.napalm_users>`

.. note::
    Beginning with release codename 2019.2.0, any NAPALM command executed when
    running under a NAPALM Proxy Minion supports the ``force_reconnect``
    magic argument.

    Proxy Minions generally establish a connection with the remote network
    device at the time of the Minion startup and that connection is going to be
    used forever.

    If one would need execute a command on the device but connecting using
    different parameters (due to various causes, e.g., unable to authenticate
    the user specified in the Pillar as the authentication system - say
    TACACS+ is not available, or the DNS resolver is currently down and would
    like to temporarily use the IP address instead, etc.), it implies updating
    the Pillar data and restarting the Proxy Minion process restart.
    In particular cases like that, you can pass the ``force_reconnect=True``
    keyword argument, together with the alternative connection details, to
    enforce the command to be executed over a separate connection.

    For example, if the usual command is ``salt '*' net.arp``, you can use the
    following to connect using a different username instead:
    ``salt '*' net.arp username=my-alt-usr force_reconnect=True``.
'''

from __future__ import absolute_import, print_function, unicode_literals

# Import python lib
import logging
log = logging.getLogger(__file__)

# Import Salt modules
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
    return salt.utils.napalm.virtual(__opts__, 'napalm', __file__)

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

    .. versionadded:: 2017.7.0
    '''
    if salt.utils.napalm.not_always_alive(opts):
        return True  # don't force reconnection for not-always alive proxies
        # or regular minion
    is_alive_ret = call('is_alive', **{})
    if not is_alive_ret.get('result', False):
        log.debug(
            '[%s] Unable to execute `is_alive`: %s',
            opts.get('id'), is_alive_ret.get('comment')
        )
        # if `is_alive` is not implemented by the underneath driver,
        # will consider the connection to be still alive
        # we don't want overly request connection reestablishment
        # NOTE: revisit this if IOS is still not stable
        #       and return False to force reconnection
        return True
    flag = is_alive_ret.get('out', {}).get('is_alive', False)
    log.debug('Is %s still alive? %s', opts.get('id'), 'Yes.' if flag else 'No.')
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
    return call('get_facts', **{})


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
        port = NETWORK_DEVICE.get('OPTIONAL_ARGS', {}).get('port')
        log.error(
            'Cannot close connection with %s%s! Please check error: %s',
            NETWORK_DEVICE.get('HOSTNAME', '[unknown hostname]'),
            ':{0}'.format(port) if port else '',
            error
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

    - result (True/False): if the operation succeeded
    - out (object): returns the object as-is from the call
    - comment (string): provides more details in case the call failed
    - traceback (string): complete traceback in case of exception. Please
      submit an issue including this traceback on the `correct driver repo`_
      and make sure to read the FAQ_

    .. _`correct driver repo`: https://github.com/napalm-automation/napalm/issues/new
    .. _FAQ: https://github.com/napalm-automation/napalm#faq

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
