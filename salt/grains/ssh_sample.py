# -*- coding: utf-8 -*-
'''
Generate baseline proxy minion grains
'''
from __future__ import absolute_import, print_function, unicode_literals
import salt.utils.platform

__proxyenabled__ = ['ssh_sample']

__virtualname__ = 'ssh_sample'


def __virtual__():
    try:
        if salt.utils.platform.is_proxy() and __opts__['proxy']['proxytype'] == 'ssh_sample':
            return __virtualname__
    except KeyError:
        pass

    return False


def kernel():
    return {'kernel': 'proxy'}


def proxy_functions(proxy):
    '''
    The loader will execute functions with one argument and pass
    a reference to the proxymodules LazyLoader object.  However,
    grains sometimes get called before the LazyLoader object is setup
    so `proxy` might be None.
    '''
    return {'proxy_functions': proxy['ssh_sample.fns']()}


def location():
    return {'location': 'At the other end of an SSH Tunnel!!'}


def os_data():
    return {'os_data': 'DumbShell Endpoint release 4.09.g'}
