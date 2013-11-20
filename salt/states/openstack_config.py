# -*- coding: utf-8 -*-
'''
Manage OpenStack configuration file settings.

:maintainer: Jeffrey C. Ollie <jeff@ocjtech.us>
:maturity: new
:depends:
:platform: linux

'''

# Import salt libs
import salt.exceptions


def __virtual__():
    '''
    Only load if the openstack_config module is in __salt__
    '''
    if 'openstack_config.get' not in __salt__:
        return False
    if 'openstack_config.set' not in __salt__:
        return False
    if 'openstack_config.delete' not in __salt__:
        return False
    return 'openstack_config'


def present(name, filename, section, value, parameter=None):
    '''
    Ensure a value is set in an OpenStack configuration file.

    filename
        The full path to the configuration file

    section
        The section in which the parameter will be set

    parameter (optional)
        The parameter to change.  If the parameter is not supplied, the name will be used as the parameter.

    value
        The value to set

    '''

    if parameter is None:
        parameter = name

    try:
        old_value = __salt__['openstack_config.get'](filename=filename,
                                                     section=section,
                                                     parameter=parameter)

        if old_value == value:
            return {'name': name,
                    'changes': {},
                    'result': True,
                    'comment': 'The value is already set to the correct value'}

    except salt.exceptions.CommandExecutionError as e:
        if not e.message.lower().startswith('parameter not found:'):
            raise

    __salt__['openstack_config.set'](filename=filename,
                                     section=section,
                                     parameter=parameter,
                                     value=value)

    return {'name': name,
            'changes': {'Value': 'Updated'},
            'result': True,
            'comment': 'The value has been updated'}


def absent(name, filename, section, parameter=None):
    '''
    Ensure a value is not set in an OpenStack configuration file.

    filename
        The full path to the configuration file

    section
        The section in which the parameter will be set

    parameter (optional)
        The parameter to change.  If the parameter is not supplied, the name will be used as the parameter.

    '''

    if parameter is None:
        parameter = name

    try:
        old_value = __salt__['openstack_config.get'](filename=filename,
                                                     section=section,
                                                     parameter=parameter)
    except salt.exceptions.CommandExecutionError as e:
        if e.message.lower().startswith('parameter not found:'):
            return {'name': name,
                    'changes': {},
                    'result': True,
                    'comment': 'The value is already absent'}
        raise

    __salt__['openstack_config.delete'](filename=filename,
                                        section=section,
                                        parameter=parameter)

    return {'name': name,
            'changes': {'Value': 'Deleted'},
            'result': True,
            'comment': 'The value has been deleted'}
