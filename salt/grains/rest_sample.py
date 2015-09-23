# -*- coding: utf-8 -*-
'''
Generate baseline proxy minion grains
'''
import logging

__proxyenabled__ = ['rest_sample']

__virtualname__ = 'rest_sample'

log = logging.getLogger(__file__)

def __virtual__():
    log.debug('In RestExample grains virtual-------------------------------')
    if 'proxy' not in __opts__:
        return False
    else:
        return __virtualname__


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
