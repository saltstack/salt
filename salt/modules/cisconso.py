# -*- coding: utf-8 -*-
'''
Execution module for Cisco Network Services Orchestrator Proxy minions

.. versionadded: 2016.11.0

For documentation on setting up the cisconso proxy minion look in the documentation
for :mod:`salt.proxy.cisconso<salt.proxy.cisconso>`.
'''
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.platform
from salt.ext import six

__proxyenabled__ = ['cisconso']
__virtualname__ = 'cisconso'


def __virtual__():
    if salt.utils.platform.is_proxy():
        return __virtualname__
    return (False, 'The cisconso execution module failed to load: '
            'only available on proxy minions.')


def info():
    '''
    Return system information for grains of the NSO proxy minion

    .. code-block:: bash

        salt '*' cisconso.info
    '''
    return _proxy_cmd('info')


def get_data(datastore, path):
    '''
    Get the configuration of the device tree at the given path

    :param datastore: The datastore, e.g. running, operational.
        One of the NETCONF store IETF types
    :type  datastore: :class:`DatastoreType` (``str`` enum).

    :param path: The device path to set the value at,
        a list of element names in order, / separated
    :type  path: ``list``, ``str`` OR ``tuple``

    :return: The network configuration at that tree
    :rtype: ``dict``

    .. code-block:: bash

        salt cisco-nso cisconso.get_data running 'devices/ex0'
    '''
    if isinstance(path, six.string_types):
        path = '/'.split(path)
    return _proxy_cmd('get_data', datastore, path)


def set_data_value(datastore, path, data):
    '''
    Get a data entry in a datastore

    :param datastore: The datastore, e.g. running, operational.
        One of the NETCONF store IETF types
    :type  datastore: :class:`DatastoreType` (``str`` enum).

    :param path: The device path to set the value at,
        a list of element names in order, / separated
    :type  path: ``list``, ``str`` OR ``tuple``

    :param data: The new value at the given path
    :type  data: ``dict``

    :rtype: ``bool``
    :return: ``True`` if successful, otherwise error.

    .. code-block:: bash

        salt cisco-nso cisconso.set_data_value running 'devices/ex0/routes' 10.0.0.20/24
    '''
    if isinstance(path, six.string_types):
        path = '/'.split(path)
    return _proxy_cmd('set_data_value', datastore, path, data)


def get_rollbacks():
    '''
    Get a list of stored configuration rollbacks

    .. code-block:: bash

        salt cisco-nso cisconso.get_rollbacks
    '''
    return _proxy_cmd('get_rollbacks')


def get_rollback(name):
    '''
    Get the backup of stored a configuration rollback

    :param name: Typically an ID of the backup
    :type  name: ``str``

    :rtype: ``str``
    :return: the contents of the rollback snapshot

    .. code-block:: bash

        salt cisco-nso cisconso.get_rollback 52
    '''
    return _proxy_cmd('get_rollback', name)


def apply_rollback(datastore, name):
    '''
    Apply a system rollback

    :param datastore: The datastore, e.g. running, operational.
        One of the NETCONF store IETF types
    :type  datastore: :class:`DatastoreType` (``str`` enum).

    :param name: an ID of the rollback to restore
    :type  name: ``str``

    .. code-block:: bash

        salt cisco-nso cisconso.apply_rollback 52
    '''
    return _proxy_cmd('apply_rollback', datastore, name)


def _proxy_cmd(command, *args, **kwargs):
    '''
    run commands from __proxy__
    :mod:`salt.proxy.cisconso<salt.proxy.cisconso>`

    command
        function from `salt.proxy.cisconso` to run

    args
        positional args to pass to `command` function

    kwargs
        key word arguments to pass to `command` function
    '''
    proxy_prefix = __opts__['proxy']['proxytype']
    proxy_cmd = '.'.join([proxy_prefix, command])
    if proxy_cmd not in __proxy__:
        return False
    for k in kwargs:
        if k.startswith('__pub_'):
            kwargs.pop(k)
    return __proxy__[proxy_cmd](*args, **kwargs)
