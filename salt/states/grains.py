'''
Manage grains on the minion. This state allows for grains to be set and unset
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
        if not name in __grains__:
            ret['comment'] = 'Grain {0} is set to be added'.format(name)
        else:
            ret['comment'] = 'Grain {0} is set to be changed'.format(name)
        return ret
    grain = __salt__['grains.setval'](name, value)
    if not grain == {name: value}:
        ret['result'] = False
        ret['comment'] = 'Failed to set grain {0}'.format(name)
        return ret
    ret['result'] = True
    ret['changes'] = grain
    ret['comment'] = 'Set grain {0} to {1}'.format(name, value)
    return ret
