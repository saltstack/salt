# -*- coding: utf-8 -*-
'''
Glue execution module to link to the fx2 proxymodule.

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
    proxycmd = __opts__['proxy']['proxytype'] + '.chconfig'
    kwargs['admin_username'] = __pillar__['proxy']['admin_username']
    kwargs['admin_password'] = __pillar__['proxy']['admin_password']
    kwargs['host'] = __pillar__['proxy']['host']
    return __proxy__[proxycmd](cmd, *args, **kwargs)


