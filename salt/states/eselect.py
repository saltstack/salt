# -*- coding: utf-8 -*-
'''
Management of Gentoo configuration using eselect
================================================

A state module to manage Gentoo configuration via eselect

.. code-block:: yaml

    profile:
        eselect.set:
            target: hardened/linux/amd64
'''

# Import Python libs
from __future__ import absolute_import

# Define a function alias in order not to shadow built-in's
__func_alias__ = {
    'set_': 'set'
}


def __virtual__():
    '''
    Only load if the eselect module is available in __salt__
    '''
    return 'eselect' if 'eselect.exec_action' in __salt__ else False


def set_(name, target, module_parameter=None, action_parameter=None):
    '''
    Verify that the given module is set to the given target

    name
        The name of the module

    target
        The target to be set for this module

    module_parameter
        additional params passed to the defined module

    action_parameter
        additional params passed to the defined action

    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    old_target = __salt__['eselect.get_current_target'](name, module_parameter=module_parameter, action_parameter=action_parameter)

    if target == old_target:
        ret['comment'] = 'Target {0!r} is already set on {1!r} module.'.format(
            target, name
        )
    elif target not in __salt__['eselect.get_target_list'](name):
        ret['comment'] = (
            'Target {0!r} is not available for {1!r} module.'.format(
                target, name
            )
        )
        ret['result'] = False
    elif __opts__['test']:
        ret['comment'] = 'Target {0!r} will be set on {1!r} module.'.format(
            target, name
        )
        ret['result'] = None
    else:
        result = __salt__['eselect.set_target'](name, target, module_parameter=module_parameter, action_parameter=action_parameter)
        if result:
            ret['changes'][name] = {'old': old_target, 'new': target}
            ret['comment'] = 'Target {0!r} set on {1!r} module.'.format(
                target, name
            )
        else:
            ret['comment'] = (
                'Target {0!r} failed to be set on {1!r} module.'.format(
                    target, name
                )
            )
            ret['result'] = False
    return ret
