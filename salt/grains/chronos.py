# -*- coding: utf-8 -*-
'''
Generate chronos proxy minion grains.

.. versionadded:: 2015.8.2

'''
from __future__ import absolute_import


import salt.utils
import salt.utils.http
__proxyenabled__ = ['chronos']
__virtualname__ = 'chronos'


def __virtual__():
    if not salt.utils.is_proxy() or 'proxy' not in __opts__:
        return False
    else:
        return __virtualname__


def kernel():
    return {'kernel': 'chronos'}


def os():
    return {'os': 'chronos'}


def os_family():
    return {'os_family': 'chronos'}


def os_data():
    return {'os_data': 'chronos'}
