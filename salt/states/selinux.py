# -*- coding: utf-8 -*-
'''
Management of SELinux rules
===========================

If SELinux is available for the running system, the mode can be managed and
booleans can be set.

.. code-block:: yaml

    enforcing:
        selinux.mode

    samba_create_home_dirs:
        selinux.boolean:
          - value: True
          - persist: True

.. note::
    Use of these states require that the :mod:`selinux <salt.modules.selinux>`
    execution module is available.
'''


def __virtual__():
    '''
    Only make this state available if the selinux module is available.
    '''
    return 'selinux' if 'selinux.getenforce' in __salt__ else False


def _refine_mode(mode):
    '''
    Return a mode value that is predictable
    '''
    mode = str(mode).lower()
    if any([mode.startswith('e'),
            mode == '1',
            mode == 'on']):
        return 'Enforcing'
    if any([mode.startswith('p'),
            mode == '0',
            mode == 'off']):
        return 'Permissive'
    return 'unknown'


def _refine_value(value):
    '''
    Return a yes/no value, or None if the input is invalid
    '''
    value = str(value).lower()
    if value in ('1', 'on', 'yes', 'true'):
        return 'on'
    if value in ('0', 'off', 'no', 'false'):
        return 'off'
    return None


def mode(name):
    '''
    Verifies the mode SELinux is running in, can be set to enforcing or
    permissive

    name
        The mode to run SELinux in, permissive or enforcing
    '''
    ret = {'name': name,
           'result': False,
           'comment': '',
           'changes': {}}
    tmode = _refine_mode(name)
    if tmode == 'unknown':
        ret['comment'] = '{0} is not an accepted mode'.format(name)
        return ret
    mode = __salt__['selinux.getenforce']()
    if mode == tmode:
        ret['result'] = True
        ret['comment'] = 'SELinux is already in {0} mode'.format(tmode)
        return ret
    # The mode needs to change...
    if __opts__['test']:
        ret['comment'] = 'SELinux mode is set to be changed to {0}'.format(
                tmode)
        ret['result'] = None
        return ret

    mode = __salt__['selinux.setenforce'](tmode)
    if mode == tmode:
        ret['result'] = True
        ret['comment'] = 'SELinux has been set to {0} mode'.format(tmode)
        return ret
    ret['comment'] = 'Failed to set SELinux to {0} mode'.format(tmode)
    return ret


def boolean(name, value, persist=False):
    '''
    Set up an SELinux boolean

    name
        The name of the boolean to set

    value
        The value to set on the boolean

    persist
        Defaults to False, set persist to true to make the boolean apply on a
        reboot
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}
    bools = __salt__['selinux.list_sebool']()
    if name not in bools:
        ret['comment'] = 'Boolean {0} is not available'.format(name)
        ret['result'] = False
        return ret
    rvalue = _refine_value(value)
    if rvalue is None:
        ret['comment'] = '{0} is not a valid value for the ' \
                         'boolean'.format(value)
        ret['result'] = False
        return ret
    state = bools[name]['State'] == rvalue
    default = bools[name]['Default'] == rvalue
    if persist:
        if state and default:
            ret['comment'] = 'Boolean is in the correct state'
            return ret
    else:
        if state:
            ret['comment'] = 'Boolean is in the correct state'
            return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Boolean {0} is set to be changed to {1}'.format(
                name, rvalue)
        return ret

    if __salt__['selinux.setsebool'](name, rvalue, persist):
        ret['comment'] = 'Boolean {0} has been set to {1}'.format(name, rvalue)
        return ret
    ret['comment'] = 'Failed to set the boolean {0} to {1}'.format(name, rvalue)
    return ret
