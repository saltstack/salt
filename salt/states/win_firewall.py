# -*- coding: utf-8 -*-
'''
State for configuring Windows Firewall
'''


def __virtual__():
    '''
    Load if the module firewall is loaded
    '''
    return 'win_firewall' if 'firewall.get_config' in __salt__ else False


def disabled(name='allprofiles'):
    '''
    Disable all the firewall profiles (Windows only)
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # Determine what to do
    action = False
    check_name = None
    if name != 'allprofiles':
        check_name = True

    current_config = __salt__['firewall.get_config']()
    if check_name and name not in current_config:
        ret['result'] = False
        ret['comment'] = 'Profile {0} does not exist in firewall.get_config'.format(name)
        return ret

    for key in current_config:
        if current_config[key]:
            if check_name and key != name:
                continue
            action = True
            ret['changes'] = {'fw': 'disabled'}
            break

    if __opts__['test']:
        ret['result'] = not action or None
        return ret

    # Disable it
    if action:
        ret['result'] = __salt__['firewall.disable'](name)
        if not ret['result']:
            ret['comment'] = 'Could not disable the FW'
            if check_name:
                msg = 'Firewall profile {0} could not be disabled'.format(name)
            else:
                msg = 'Could not disable the FW'
            ret['comment'] = msg
    else:
        if check_name:
            msg = 'Firewall profile {0} is disabled'.format(name)
        else:
            msg = 'All the firewall profiles are disabled'
        ret['comment'] = msg

    return ret


def add_rule(name, localport, protocol="tcp", action="allow", dir="in"):
    '''
    Add a new firewall rule (Windows only)
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # Check if rule exists
    commit = False
    current_rules = __salt__['firewall.get_rule'](name)
    if not current_rules:
        commit = True
        ret['changes'] = {'new rule': name}

    if __opts__['test']:
        ret['result'] = not commit or None
        return ret

    # Add rule
    if commit:
        ret['result'] = __salt__['firewall.add_rule'](name, localport, protocol, action, dir)
        if not ret['result']:
            ret['comment'] = 'Could not add rule'
    else:
        ret['comment'] = 'A rule with that name already exists'

    return ret


def enabled(name='allprofiles'):
    '''
    Enable all the firewall profiles (Windows only)
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # Determine what to do
    action = False
    check_name = None
    if name != 'allprofiles':
        check_name = True

    current_config = __salt__['firewall.get_config']()
    if check_name and name not in current_config:
        ret['result'] = False
        ret['comment'] = 'Profile {0} does not exist in firewall.get_config'.format(name)
        return ret

    for key in current_config:
        if not current_config[key]:
            if check_name and key != name:
                continue
            action = True
            ret['changes'] = {'fw': 'enabled'}
            break

    if __opts__['test']:
        ret['result'] = not action or None
        return ret

    # Disable it
    if action:
        ret['result'] = __salt__['firewall.enable'](name)
        if not ret['result']:
            if check_name:
                msg = 'Firewall profile {0} could not be enabled'.format(name)
            else:
                msg = 'Could not enable the FW'
            ret['comment'] = msg
    else:
        if check_name:
            msg = 'Firewall profile {0} is enabled'.format(name)
        else:
            msg = 'All the firewall profiles are enabled'
        ret['comment'] = msg

    return ret
