# -*- coding: utf-8 -*-
'''
Generate baseline proxy minion grains
'''
__proxyenabled__ = ['philips_hue']

__virtualname__ = 'hue'


def __virtual__():
    if 'proxy' not in __opts__:
        return False
    else:
        return __virtualname__


def kernel():
    return {'kernel': 'RTOS'}


def os():
    return {'os': 'FreeRTOS'}


def os_family():
    return {'os_family': 'RTOS'}


def vendor():
    return {'vendor': 'Philips'}


def product():
    return {'product': 'HUE'}
