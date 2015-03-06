# -*- coding: utf-8 -*-
'''
Send events covering service status
'''


def beacon(config):
    '''
    Scan for the configured services and fire events
    '''
    ret = {}
    for service in config:
        ret[service] = __salt__['service.status'](service)
    return ret
