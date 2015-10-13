# -*- coding: utf-8 -*-
'''
Generate baseline proxy minion grains for Dell FX2 chassis
'''
__proxyenabled__ = ['fx2']

__virtualname__ = 'fx2'

import salt.utils

def __virtual__():
    if salt.utils.is_proxy():
        return __virtualname__
    else:
        return False


def kernel():
    return {'kernel': 'proxy'}


def os():
    return {'os': 'RestExampleOS'}


def location():
    return {'location': 'In this darn virtual machine.  Let me out!'}


def os_family():
    return {'os_family': 'proxy'}


def os_data():
    return {'os_data': 'funkyHttp release 1.0.a.4.g'}
