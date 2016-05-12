# -*- coding: utf-8 -*-
'''
Module for managing SNMP service settings on Windows servers.

'''

# Import python libs
from __future__ import absolute_import


def __virtual__():
    '''
    Load only on minions that have the win_snmp module.
    '''
    if 'win_snmp.get_agent_settings' in __salt__:
        return True
    return False


def agent_settings(name, contact, location, services=None):
    '''
    Manage the SNMP sysContact, sysLocation, and sysServices settings.

    :param str contact: The SNMP contact.
    :param str location: The SNMP location.
    :param str services: A list of selected services.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}

    ret_settings = dict()
    ret_settings['changes'] = {}
    ret_settings['failures'] = {}

    if not services:
        services = ['None']

    # Filter services for unique items, and sort them for comparison purposes.
    services = sorted(set(services))

    settings = {'contact': contact, 'location': location, 'services': services}

    current_settings = __salt__['win_snmp.get_agent_settings']()

    for setting in settings:
        if str(settings[setting]) != str(current_settings[setting]):
            ret_settings['changes'][setting] = {'old': current_settings[setting],
                                                'new': settings[setting]}
    if not ret_settings['changes']:
        ret['comment'] = 'Agent settings already contain the provided values.'
        ret['result'] = True
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Agent settings will be changed.'
        ret['changes'] = ret_settings
        return ret

    __salt__['win_snmp.set_agent_settings'](**settings)
    new_settings = __salt__['win_snmp.get_agent_settings']()

    for setting in settings:
        if settings[setting] != new_settings[setting]:
            ret_settings['failures'][setting] = {'old': current_settings[setting],
                                                 'new': new_settings[setting]}
            ret_settings['changes'].pop(setting, None)

    if ret_settings['failures']:
        ret['comment'] = 'Some agent settings failed to change.'
        ret['changes'] = ret_settings
        ret['result'] = False
    else:
        ret['comment'] = 'Set agent settings to contain the provided values.'
        ret['changes'] = ret_settings['changes']
        ret['result'] = True
    return ret


def auth_traps_enabled(name, status=True):
    '''
    Manage the sending of authentication traps.

    :param bool status: The enabled status.
    '''
    ret = {'name': name,
           'changes': {},
           'comment': str(),
           'result': None}

    vname = 'EnableAuthenticationTraps'
    current_status = __salt__['win_snmp.get_auth_traps_enabled']()

    if status == current_status:
        ret['comment'] = '{0} already contains the provided value.'.format(vname)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = '{0} will be changed.'.format(vname)
        ret['changes'] = {'old': current_status,
                          'new': status}
    else:
        ret['comment'] = 'Set {0} to contain the provided value.'.format(vname)
        ret['changes'] = {'old': current_status,
                          'new': status}
        ret['result'] = __salt__['win_snmp.set_auth_traps_enabled'](status=status)

    return ret
