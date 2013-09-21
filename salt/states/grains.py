# -*- coding: utf-8 -*-
'''
Manage grains on the minion.
============================

This state allows for grains to be set. If a grain with the
given name exists, its value is updated to the new value. If
a grain does not yet exist, a new grain is set to the given
value. Grains set or altered this way are stored in the 'grains'
file on the minions, by default at: /etc/salt/grains

Note: This does NOT override any grains set in the minion file.

.. code-block:: yaml

    cheese:
      grains.present:
        - value: edam
'''


def present(name, value):
    '''
    Ensure that a grain is set

    name
        The grain name

    value
        The value to set on the grain
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if isinstance(value, dict):
        ret['result'] = False
        ret['comment'] = 'Grain value cannot be dict'
        return ret
    if __grains__.get(name) == value:
        ret['comment'] = 'Grain is already set'
        return ret
    if __opts__['test']:
        ret['result'] = None
        if name not in __grains__:
            ret['comment'] = 'Grain {0} is set to be added'.format(name)
        else:
            ret['comment'] = 'Grain {0} is set to be changed'.format(name)
        return ret
    grain = __salt__['grains.setval'](name, value)
    if grain != {name: value}:
        ret['result'] = False
        ret['comment'] = 'Failed to set grain {0}'.format(name)
        return ret
    ret['result'] = True
    ret['changes'] = grain
    ret['comment'] = 'Set grain {0} to {1}'.format(name, value)
    return ret
