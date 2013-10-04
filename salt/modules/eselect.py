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


def exec_action(module, action, parameter='', state_only=False):
    '''
    Execute an arbitrary action on a module.

    CLI Example:

    .. code-block:: bash

        salt '*' eselect.exec_action <module name> <action> [parameter]
    '''
    out = __salt__['cmd.run'](
        'eselect --brief --colour=no {0} {1} {2}'.format(
            module, action, parameter
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
    return exec_action('modules', 'list')


def get_target_list(module):
    '''
    Get available target for the given module.

    CLI Example:

    .. code-block:: bash

        salt '*' eselect.get_target_list <module name>
    '''
    return exec_action(module, 'list')


def get_current_target(module):
    '''
    Get the currently selected target for the given module.

    CLI Example:

    .. code-block:: bash

        salt '*' eselect.get_current_target <module name>
    '''
    return exec_action(module, 'show')[0]


def set_target(module, target):
    '''
    Set the target for the given module.
    Target can be specified by index or name.

    CLI Example:

    .. code-block:: bash

        salt '*' eselect.set_target <module name> <target>
    '''
    return exec_action(module, 'set', target, state_only=True)
