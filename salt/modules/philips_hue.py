# -*- coding: utf-8 -*-
'''
Philips HUE lamps module for proxy.
'''

from __future__ import absolute_import
import sys

__virtualname__ = 'hue'
__proxyenabled__ = ['philips_hue']


def _proxy():
    '''
    Get proxy.
    '''
    return __opts__['proxymodule']


def __virtual__():
    '''
    Start the Philips HUE only for proxies.
    '''

    def _mkf(cmd_name, doc):
        def _cmd(*args, **kw):
            return _proxy()[_proxy().loaded_base_name + "." + cmd_name](*args, **kw)
        return _cmd

    import salt.proxy.philips_hue as hue
    for method in dir(hue):
        if method.startswith('call_'):
            setattr(sys.modules[__name__], method[5:], _mkf(method, getattr(hue, method).__doc__))
    del hue

    return _proxy() and __virtualname__ or False
