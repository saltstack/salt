# -*- coding: utf-8 -*-
'''
State for configuring Windows Firewall
'''


def __virtual__():
    '''
    Load if the module firewall is loaded
    '''
    return 'win_firewall' if 'firewall.get_config' in __salt__ else False


def disabled(name):
    '''
    Disable all the firewall profiles (Windows only)
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # Determine what to do
    action = False
    current_config = __salt__['firewall.get_config']()
    for key in current_config:
        if current_config[key]:
            action = True
            ret['changes'] = {'fw': 'disabled'}
            break

    if __opts__['test']:
        ret['result'] = None
        return ret

    # Disable it
    if action:
        ret['result'] = __salt__['firewall.disable']()
        if not ret['result']:
            ret['comment'] = 'Could not disable the FW'
    else:
        ret['comment'] = 'All the firewall profiles are disabled'

    return ret
