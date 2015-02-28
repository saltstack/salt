# -*- coding: utf-8 -*-
'''
Support for eselect, Gentoo's configuration and management tool.
'''

import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


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

    module
        name of the module to be executed

    action
        name of the module's action to be run

    module_parameter
        additional params passed to the defined module

    action_parameter
        additional params passed to the defined action

    parameter
        additional params passed to the defined action
        .. deprecated:: Lithium

    state_only
        don't return any output but only the success/failure of the operation

    CLI Example (updating the ``php`` implementation used for ``apache2``):

    .. code-block:: bash

        salt '*' eselect.exec_action php update action_parameter='apache2'
    '''
    if parameter:
        salt.utils.warn_until(
            'Lithium',
            'The \'parameter\' option is deprecated and will be removed in the '
            '\'Lithium\' Salt release. Please use either \'module_parameter\' or '
            '\'action_parameter\' instead.'
        )
        action_parameter = parameter
    out = __salt__['cmd.run'](
        'eselect --brief --colour=no {0} {1} {2} {3}'.format(
            module, module_parameter or '', action, action_parameter or ''),
        python_shell=False
    )
    out = out.strip().split('\n')

    if out[0].startswith('!!! Error'):
        return False

    if state_only:
        return True

    if len(out) < 1:
        return False

    if len(out) == 1 and not out[0].strip():
        return False

    return out


def get_modules():
    '''
    List available ``eselect`` modules.

    CLI Example:

    .. code-block:: bash

        salt '*' eselect.get_modules
    '''
    modules = []
    module_list = exec_action('modules', 'list', action_parameter='--only-names')
    if not module_list:
        return None

    for module in module_list:
        if module not in ['help', 'usage', 'version']:
            modules.append(module)
    return modules


def get_target_list(module):
    '''
    List available targets for the given module.

    module
        name of the module to be queried for its targets

    CLI Example:

    .. code-block:: bash

        salt '*' eselect.get_target_list kernel
    '''
    exec_output = exec_action(module, 'list')
    if not exec_output:
        return None

    target_list = []
    if isinstance(exec_output, list):
        for item in exec_output:
            target_list.append(item.split(None, 1)[0])
        return target_list

    return None


def get_current_target(module, module_parameter=None, action_parameter=None):
    '''
    Get the currently selected target for the given module.

    module
        name of the module to be queried for its current target

    module_parameter
        additional params passed to the defined module

    action_parameter
        additional params passed to the 'show' action

    CLI Example (current target of system-wide ``java-vm``):

    .. code-block:: bash

        salt '*' eselect.get_current_target java-vm action_parameter='system'

    CLI Example (current target of ``kernel`` symlink):

    .. code-block:: bash

        salt '*' eselect.get_current_target kernel
    '''
    result = exec_action(module, 'show', module_parameter=module_parameter, action_parameter=action_parameter)[0]
    if not result:
        return None

    if result == '(unset)':
        return None

    return result


def set_target(module, target, module_parameter=None, action_parameter=None):
    '''
    Set the target for the given module.
    Target can be specified by index or name.

    module
        name of the module for which a target should be set

    target
        name of the target to be set for this module

    module_parameter
        additional params passed to the defined module

    action_parameter
        additional params passed to the defined action

    CLI Example (setting target of system-wide ``java-vm``):

    .. code-block:: bash

        salt '*' eselect.set_target java-vm icedtea-bin-7 action_parameter='system'

    CLI Example (setting target of ``kernel`` symlink):

    .. code-block:: bash

        salt '*' eselect.set_target kernel linux-3.17.5-gentoo
    '''
    if action_parameter:
        action_parameter = '{0} {1}'.format(action_parameter, target)
    else:
        action_parameter = target

    # get list of available modules
    if module not in get_modules():
        log.error('Module {0} not available'.format(module))
        return False

    exec_result = exec_action(module, 'set', module_parameter=module_parameter, action_parameter=action_parameter, state_only=True)
    if exec_result:
        return exec_result
    return False
