# -*- coding: utf-8 -*-
'''
Configuration of email aliases.
===============================

The mail aliases file can be managed to contain definitions for specific email
aliases:

.. code-block:: yaml

    username:
      alias.present:
        - target: user@example.com
'''


def present(name, target):
    '''
    Ensures that the named alias is present with the given target

    name
        The local user/address to assign an alias to

    target
        The forwarding address
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    if __salt__['aliases.has_target'](name, target):
        ret['result'] = True
        ret['comment'] = 'Alias {0} already present'.format(name)
        return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Alias {0} -> {1} is set to be added'.format(
                name, target
                )
        return ret
    if __salt__['aliases.set_target'](name, target):
        ret['changes'] = {'alias': name}
        ret['result'] = True
        ret['comment'] = 'Set email alias {0} -> {1}'.format(name, target)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to set alias'
        return ret


def absent(name):
    '''
    Ensure that the named alias is absent

    name
        The alias to remove
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    if not __salt__['aliases.get_target'](name):
        ret['result'] = True
        ret['comment'] = 'Alias {0} already absent'.format(name)
        return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Alias {0} is set to be removed'.format(name)
        return ret
    if __salt__['aliases.rm_alias'](name):
        ret['changes'] = {'alias': name}
        ret['result'] = True
        ret['comment'] = 'Removed alias {0}'.format(name)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to remove alias'
        return ret
