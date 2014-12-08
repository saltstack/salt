# -*- coding: utf-8 -*-
'''
Support for eselect, Gentoo's configuration and management tool.
'''

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only work on Gentoo systems with eselect installed
    '''
    if __grains__['os'] == 'Gentoo' and salt.utils.which('eselect'):
        return 'eselect'
    return False


def exec_action(module, action, module_parameter=None, action_parameter=None, parameter=None, state_only=False):
    '''
    Execute an arbitrary action on a module.

    CLI Example:

    .. code-block:: bash

        salt '*' eselect.exec_action <module name> [module_parameter] <action> [action_parameter]
    '''
    if parameter:
        salt.utils.warn_until(
            'Lithium',
            'The \'parameter\' option is deprecated and will be removed in the '
            '\'Lithium\' Salt release. Please use either \'module_parameter\' or '
            '\'action_parameter\' instead.'
        )
        action_parameter=parameter
    out = __salt__['cmd.run'](
        'eselect --brief --colour=no {0} {1} {2} {3}'.format(
            module, module_parameter or '', action, action_parameter or ''
        )
    )
    out = out.strip().split('\n')

    if out[0].startswith('!!! Error'):
        return False

    if state_only:
        return True

    return out


def get_modules():
    '''
    Get available modules list.

    CLI Example:

    .. code-block:: bash

        salt '*' eselect.get_modules
    '''
    modules = []
    try:
        module_list = exec_action('modules', 'list', action_parameter='--only-names')
    except:
        return None

    for module in module_list:
        if module not in ['help', 'usage', 'version']:
            modules.append(module)
    return modules

def get_target_list(module):
    '''
    Get available target for the given module.

    CLI Example:

    .. code-block:: bash

        salt '*' eselect.get_target_list <module name>
    '''
    target_list = []
    try:
        exec_output = exec_action(module, 'list')
    except:
        return None

    for item in exec_output:
        target_list.append(item.split(None, 1)[0])

    return target_list


def get_current_target(module, module_parameter=None, action_parameter=None):
    '''
    Get the currently selected target for the given module.

    CLI Example:

    .. code-block:: bash

        salt '*' eselect.get_current_target <module name> module_parameter='optional module params' action_parameter='optional action params'
    '''
    try:
        return exec_action(module, 'show', module_parameter=module_parameter, action_parameter=action_parameter)[0]
    except:
        return None


def set_target(module, target, module_parameter=None, action_parameter=None):
    '''
    Set the target for the given module.
    Target can be specified by index or name.

    CLI Example:

    .. code-block:: bash

        salt '*' eselect.set_target <module name> <target> module_parameter='optional module params' action_parameter='optional action params'
    '''
    if action_parameter:
        action_parameter = '{0} {1}'.format(action_parameter, target)
    else:
        action_parameter = target
    try:
        return exec_action(module, 'set', module_parameter=module_parameter, action_parameter=action_parameter, state_only=True)
    except:
        return False
