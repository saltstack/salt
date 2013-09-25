# -*- coding: utf-8 -*-
'''
Manage RDP Service on Windows servers
'''


def __virtual__():
    '''
    Load only if network_win is loaded
    '''
    return 'rdp' if 'rdp.enable' in __salt__ else False


def enabled(name):
    '''
    Enable RDP the service on the server
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    stat = __salt__['rdp.status']()
    if not stat:
        ret['changes'] = {'enabled rdp': True}

    if __opts__['test']:
        ret['result'] = None
        return ret

    ret['result'] = __salt__['rdp.enable']()
    return ret


def disabled(name):
    '''
    Disable RDP the service on the server
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    stat = __salt__['rdp.status']()
    if stat:
        ret['changes'] = {'disable rdp': True}

    if __opts__['test']:
        return ret

    ret['result'] = __salt__['rdp.disable']()
    return ret
