# -*- coding: utf-8 -*-
'''
Grains for junos.
NOTE this is a little complicated--junos can only be accessed via salt-proxy-minion.
Thus, some grains make sense to get them from the minion (PYTHONPATH), but others
don't (ip_interfaces)
'''
__proxyenabled__ = ['junos']

__virtualname__ = 'junos'


def __virtual__():
    if 'proxy' not in __opts__:
        return False
    else:
        return __virtualname__


def location():
    return {'location': 'dc-1-europe'}


def os_family():
    return {'os_family': 'junos'}


def os_data():
    facts = {}
    facts['version_info'] = {'major': '12,1', 'type': 'I', 'minor': '20131108_srx_12q1_x46_intgr', 'build': '0-613414'}
    facts['os_family'] = 'proxy'
    return facts
