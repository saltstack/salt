# -*- coding: utf-8 -*-
'''
Glue execution module to link to the :doc:`fx2 proxymodule </ref/proxy/all/salt.proxy.fx2>`.

Depends: :doc:`iDRAC Remote execution module (salt.modules.dracr) </ref/modules/all/salt.modules.dracr>`

For documentation on commands that you can direct to a Dell chassis via proxy,
look in the documentation for :doc:`salt.modules.dracr </ref/modules/all/salt.modules.dracr>`.

This execution module calls through to a function in the fx2 proxy module
called ``chconfig``.  That function looks up the function passed in the ``cmd``
parameter in :doc:`salt.modules.dracr </ref/modules/all/salt.modules.dracr>` and calls it.

.. versionadded:: 2015.8.2
'''
from __future__ import absolute_import

# Import python libs
import logging
import salt.utils


log = logging.getLogger(__name__)

__proxyenabled__ = ['fx2']
__virtualname__ = 'chassis'


def __virtual__():
    '''
    Only work on proxy
    '''
    if salt.utils.is_proxy():
        return __virtualname__
    return (False, 'The chassis execution module cannot be loaded: '
            'this only works in proxy minions.')


def chassis_credentials():
    proxyprefix = __opts__['proxy']['proxytype']
    (username, password) = __proxy__[proxyprefix+'.find_credentials']()
    return (username, password)


def cmd(cmd, *args, **kwargs):
    proxyprefix = __opts__['proxy']['proxytype']
    (username, password) = chassis_credentials()
    kwargs['admin_username'] = username
    kwargs['admin_password'] = password
    kwargs['host'] = __proxy__[proxyprefix+'.host']()
    proxycmd = __opts__['proxy']['proxytype'] + '.chconfig'
    return __proxy__[proxycmd](cmd, *args, **kwargs)
