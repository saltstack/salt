# -*- coding: utf-8 -*-
'''
Execution module for Cisco NX OS Switches Proxy minions

.. versionadded: Carbon

For documentation on setting up the nxos proxy minion look in the documentation
for :doc:`salt.proxy.nxos</ref/proxy/all/salt.proxy.nxos>`.
'''
from __future__ import absolute_import

import salt.utils

__proxyenabled__ = ['nxos']
__virtualname__ = 'nxos'


def __virtual__():
    if salt.utils.is_proxy():
        return __virtualname__
    return (False, 'The nxos execution module failed to load: '
            'only available on proxy minions.')


def system_info():
    '''
    Return system information for grains of the NX OS proxy minion

    .. code-block:: bash

        salt '*' nxos.system_info
    '''
    return cmd('system_info')


def cmd(command, *args, **kwargs):
    '''
    run commands from __proxy__
    :doc:`salt.proxy.nxos</ref/proxy/all/salt.proxy.nxos>`

    command
        function from `salt.proxy.nxos` to run

    args
        positional args to pass to `command` function

    kwargs
        key word arguments to pass to `command` function

    .. code-block:: bash

        salt '*' nxos.cmd sendline 'show ver'
        salt '*' nxos.cmd show_run
        salt '*' nxos.cmd check_password username=admin password='$5$lkjsdfoi$blahblahblah' encrypted=True
    '''
    proxy_prefix = __opts__['proxy']['proxytype']
    proxy_cmd = '.'.join([proxy_prefix, command])
    if proxy_cmd not in __proxy__:
        return False
    for k in kwargs.keys():
        if k.startswith('__pub_'):
            kwargs.pop(k)
    return __proxy__[proxy_cmd](*args, **kwargs)
