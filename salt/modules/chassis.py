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
    return False


def cmd(cmd, *args, **kwargs):
    proxyprefix = __opts__['proxy']['proxytype']
    kwargs['admin_username'] = __proxy__[proxyprefix+'.admin_username']()
    kwargs['admin_password'] = __proxy__[proxyprefix+'.admin_password']()
    kwargs['host'] = __proxy__[proxyprefix+'.host']()
    proxycmd = __opts__['proxy']['proxytype'] + '.chconfig'
    return __proxy__[proxycmd](cmd, *args, **kwargs)
