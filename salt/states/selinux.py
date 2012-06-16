'''
Management of SELinux rules.
============================

If SELinux is available for the running system, the mode can be managed and
booleans can be set.

.. code-block:: yaml

    enforcing:
        selinux.mode

    samba_create_home_dirs:
        selinx.boolean:
          - value: True
          - persist: True

'''


def _refine_mode(mode):
    '''
    Return a mode value that is completely predictable
    '''
    if any([
        str(mode).startswith('e'),
        str(mode) == '1',
        str(mode).startswith('E'),
        str(mode) == 'on']):
        return 'Enforcing'
    if any([
        str(mode).startswith('p'),
        str(mode) == '0',
        str(mode).startswith('P'),
        str(mode) == 'off']):
        return 'Permissive'
    return 'unknown'


def _refine_value(value):
    '''
    Return a value that is completely predictable
    '''
    if any([
        str(value) == '1',
        str(value) == 'on']):
        return 'on'
    if any([
        str(value) == '0',
        str(value) == 'off']):
        return 'off'


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
    tmode = _refine_mode(mode)
    if tmode == 'unknown':
        ret['comment'] = '{0} is not an accepted mode'.format(name)
        return ret
    mode = __salt__['selinux.getenforce']()
    if mode == tmode:
        ret['result'] = True
        ret['comment'] = 'Selinux is already in {0} mode'.format(tmode)
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
        ret['comment'] = 'Selinux has been set to {0} mode'.format(tmode)
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
    if not name in bools:
        ret['comment'] = 'Boolean {0} is not available'.format(name)
        ret['result'] = False
        return ret
    value = _refine_value(value)
    state = bools[name]['State'] == value
    default = bools[name]['Default'] == value
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
                name, value)
        return ret

    if __salt__['selinux.setsebool'](name, value, persist):
        ret['comment'] = 'Boolean {0} has been set to {1}'.format(name, value)
        return ret
    ret['comment'] = 'Failed to set the boolean {0} to {1}'.format(name, value)
    return ret
