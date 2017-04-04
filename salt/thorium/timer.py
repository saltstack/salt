# -*- coding: utf-8 -*-
'''
Allow for flow based timers. These timers allow for a sleep to exist across
multiple runs of the flow
'''

from __future__ import absolute_import
import time


def hold(name, seconds):
    '''
    Wait for a given period of time, then fire a result of True, requireing
    this state allows for an action to be blocked for evaluation based on
    time
    '''
    ret = {'name': name,
           'result': False,
           'comment': '',
           'changes': {}}
    start = time.time()
    if 'timer' not in __context__:
        __context__['timer'] = {}
    if name not in __context__['timer']:
        __context__['timer'][name] = start
    if (start - __context__['timer'][name]) > seconds:
        ret['result'] = True
        __context__['timer'][name] = start
    return ret
