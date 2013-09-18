# -*- coding: utf-8 -*-
'''
Management of keyboard layouts
==============================

The keyboard layout can be managed for the system:

.. code-block:: yaml

    us:
      keyboard.system

Or it can be managed for XOrg:

.. code-block:: yaml

    us:
      keyboard.xorg
'''


def __virtual__():
    '''
    Only load if the keyboard module is available in __salt__
    '''
    return 'keyboard' if 'keyboard.get_sys' in __salt__ else False


def system(name):
    '''
    Set the keyboard layout for the system

    name
        The keyboard layout to use
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    if __salt__['keyboard.get_sys']() == name:
        ret['result'] = True
        ret['comment'] = 'System layout {0} already set'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = 'System layout {0} needs to be set'.format(name)
        return ret
    if __salt__['keyboard.set_sys'](name):
        ret['changes'] = {'layout': name}
        ret['result'] = True
        ret['comment'] = 'Set system keyboard layout {0}'.format(name)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to set system keyboard layout'
        return ret


def xorg(name):
    '''
    Set the keyboard layout for XOrg

    layout
        The keyboard layout to use
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    if __salt__['keyboard.get_x']() == name:
        ret['result'] = True
        ret['comment'] = 'XOrg layout {0} already set'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = 'XOrg layout {0} needs to be set'.format(name)
        return ret
    if __salt__['keyboard.set_x'](name):
        ret['changes'] = {'layout': name}
        ret['result'] = True
        ret['comment'] = 'Set XOrg keyboard layout {0}'.format(name)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to set XOrg keyboard layout'
        return ret
