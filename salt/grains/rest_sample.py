# -*- coding: utf-8 -*-
'''
Generate baseline proxy minion grains
'''
from __future__ import absolute_import
import salt.utils

__proxyenabled__ = ['rest_sample']

__virtualname__ = 'rest_sample'


def __virtual__():
    if not salt.utils.is_proxy():
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
