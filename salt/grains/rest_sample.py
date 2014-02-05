# -*- coding: utf-8 -*-
'''
Generate baseline proxy minion grains
'''
__proxyenabled__ = ['rest_sample']

__virtualname__ = 'rest_sample'


def __virtual__():
    if 'proxy' not in __opts__:
        return False
    else:
        return __virtualname__


def location():
    return {'location': 'In this darn virtual machine.  Let me out!'}


def os_family():
    return {'os_family': 'proxy'}


def os_data():
    return __opts__['proxyobject'].grains()
