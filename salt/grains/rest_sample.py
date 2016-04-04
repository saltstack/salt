# -*- coding: utf-8 -*-
'''
Generate baseline proxy minion grains
'''
from __future__ import absolute_import
import salt.utils

__proxyenabled__ = ['rest_sample']

__virtualname__ = 'rest_sample'


def __virtual__():
    try:
        if salt.utils.is_proxy() and __opts__['proxy']['proxytype'] == 'rest_sample':
            return __virtualname__
    except KeyError:
        pass

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
