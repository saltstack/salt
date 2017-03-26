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

    nginx:
        selinux.module:
          - enabled: False

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
    if any([mode.startswith('d')]):
        return 'Disabled'
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


def _refine_module_state(module_state):
    '''
    Return a predictable value, or allow us to error out
    .. versionadded:: 2016.3.0
    '''
    module_state = str(module_state).lower()
    if module_state in ('1', 'on', 'yes', 'true', 'enabled'):
        return 'enabled'
    if module_state in ('0', 'off', 'no', 'false', 'disabled'):
        return 'disabled'
    return 'unknown'


def mode(name):
    '''
    Verifies the mode SELinux is running in, can be set to enforcing,
    permissive, or disabled
        Note: A change to or from disabled mode requires a system reboot.
            You will need to perform this yourself.

    name
        The mode to run SELinux in, permissive, enforcing, or disabled.
    '''
    ret = {'name': name,
           'result': False,
           'comment': '',
           'changes': {}}
    tmode = _refine_mode(name)
    if tmode == 'unknown':
        ret['comment'] = '{0} is not an accepted mode'.format(name)
        return ret
    # Either the current mode in memory or a non-matching config value
    # will trigger setenforce
    mode = __salt__['selinux.getenforce']()
    config = __salt__['selinux.getconfig']()
    # Just making sure the oldmode reflects the thing that didn't match tmode
    if mode == tmode and mode != config and tmode != config:
        mode = config

    if mode == tmode:
        ret['result'] = True
        ret['comment'] = 'SELinux is already in {0} mode'.format(tmode)
        return ret
    # The mode needs to change...
    if __opts__['test']:
        ret['comment'] = 'SELinux mode is set to be changed to {0}'.format(
                tmode)
        ret['result'] = None
        ret['changes'] = {'old': mode,
                          'new': tmode}
        return ret

    oldmode, mode = mode, __salt__['selinux.setenforce'](tmode)
    if mode == tmode or (tmode == 'Disabled' and __salt__['selinux.getconfig']() == tmode):
        ret['result'] = True
        ret['comment'] = 'SELinux has been set to {0} mode'.format(tmode)
        ret['changes'] = {'old': oldmode,
                          'new': mode}
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


def module(name, module_state='Enabled', version='any', **opts):
    '''
    Enable/Disable and optionally force a specific version for an SELinux module

    name
        The name of the module to control

    module_state
        Should the module be enabled or disabled?

    version
        Defaults to no preference, set to a specified value if required.
        Currently can only alert if the version is incorrect.

    install
        Setting to True installs module

    source
        Points to module source file, used only when install is True

    remove
        Setting to True removes module

    .. versionadded:: 2016.3.0
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}
    if opts.get('install', False) and opts.get('remove', False):
        ret['result'] = False
        ret['comment'] = 'Cannot install and remove at the same time'
        return ret
    if opts.get('install', False):
        module_path = opts.get('source', name)
        ret = module_install(module_path)
        if not ret['result']:
            return ret
    elif opts.get('remove', False):
        return module_remove(name)
    modules = __salt__['selinux.list_semod']()
    if name not in modules:
        ret['comment'] = 'Module {0} is not available'.format(name)
        ret['result'] = False
        return ret
    rmodule_state = _refine_module_state(module_state)
    if rmodule_state == 'unknown':
        ret['comment'] = '{0} is not a valid state for the ' \
                         '{1} module.'.format(module_state, module)
        ret['result'] = False
        return ret
    if version != 'any':
        installed_version = modules[name]['Version']
        if not installed_version == version:
            ret['comment'] = 'Module version is {0} and does not match ' \
                             'the desired version of {1} or you are ' \
                             'using semodule >= 2.4'.format(installed_version, version)
            ret['result'] = False
            return ret
    current_module_state = _refine_module_state(modules[name]['Enabled'])
    if rmodule_state == current_module_state:
        ret['comment'] = 'Module {0} is in the desired state'.format(name)
        return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Module {0} is set to be toggled to {1}'.format(
            name, module_state)
        return ret

    if __salt__['selinux.setsemod'](name, rmodule_state):
        ret['comment'] = 'Module {0} has been set to {1}'.format(name, module_state)
        return ret
    ret['result'] = False
    ret['comment'] = 'Failed to set the Module {0} to {1}'.format(name, module_state)
    return ret


def module_install(name):
    '''
    Installs custom SELinux module from given file

    name
        Path to file with module to install

    .. versionadded:: develop
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}
    if __salt__['selinux.install_semod'](name):
        ret['comment'] = 'Module {0} has been installed'.format(name)
        return ret
    ret['result'] = False
    ret['comment'] = 'Failed to install module {0}'.format(name)
    return ret


def module_remove(name):
    '''
    Removes SELinux module

    name
        The name of the module to remove

    .. versionadded:: develop
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}
    modules = __salt__['selinux.list_semod']()
    if name not in modules:
        ret['comment'] = 'Module {0} is not available'.format(name)
        ret['result'] = False
        return ret
    if __salt__['selinux.remove_semod'](name):
        ret['comment'] = 'Module {0} has been removed'.format(name)
        return ret
    ret['result'] = False
    ret['comment'] = 'Failed to remove module {0}'.format(name)
    return ret
