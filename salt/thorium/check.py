# -*- coding: utf-8 -*-
'''
The check Thorium state is used to create gateways to commands, the checks
make it easy to make states that watch registers for changes and then just
succeed or fail based on the state of the register, this creates the pattern
of having a command execution get gated by a check state via a requisite.
'''
# import python libs
from __future__ import absolute_import


def gt(name, value):
    '''
    Only succeed if the value in the given register location is greater than
    the given value
    '''
    ret = {'name': name,
           'result': False,
           'comment': '',
           'changes': {}}
    if name not in __reg__:
        ret['result'] = None
        ret['comment'] = 'Value {0} not in register'.format(name)
        return ret
    if __reg__[name]['val'] > value:
        ret['result'] = True
    return ret


def lt(name, value):
    '''
    Only succeed if the value in the given register location is greater than
    the given value
    '''
    ret = {'name': name,
           'result': False,
           'comment': '',
           'changes': {}}
    if name not in __reg__:
        ret['result'] = None
        ret['comment'] = 'Value {0} not in register'.format(name)
        return ret
    if __reg__[name]['val'] < value:
        ret['result'] = True
    return ret


def contains(name, value):
    '''
    Only succeed if the value in the given register location is greater than
    the given value
    '''
    ret = {'name': name,
           'result': False,
           'comment': '',
           'changes': {}}
    if name not in __reg__:
        ret['result'] = None
        ret['comment'] = 'Value {0} not in register'.format(name)
        return ret
    try:
        if __reg__[name]['val'] in value:
            ret['result'] = True
    except TypeError:
        pass
    return ret
