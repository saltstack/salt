# -*- coding: utf-8 -*-
'''
Manage list type grains on the minion
=======================================

This state allows for list type grains to be set. 
Grains set or altered this way are stored in the 'grains'
file on the minions, by default at: /etc/salt/grains

Note: This does NOT override any grains set in the minion file.
'''

def present(name, value):
    '''
    Ensure the value is present in the list type grain

    name
        The grain name
    
    value
       The value is present in the list type grain

    .. code-block:: yaml

      cheese:
        grains_list.present:
          - value: edam
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    grain = __grains__.get(name)

    if grain:
        # check whether grain is a list 
        if not isinstance(grain, list):
            ret['result'] = False
            ret['comment'] = 'Grain {0} is not a valid list'.format(name)
            return ret

        if value in grain:
            ret['comment'] = 'Value {1} is already in grain {0}'.format(name, value)
            return ret
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Value {1} is set to be appended to grain {0}'.format(name, value)
            return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Grain {0} is set to be added'.format(name)
        return ret
            
    __salt__['grains.append'](name, value)
    if value not in __grains__.get(name):
        ret['result'] = False
        ret['comment'] = 'Failed append value {1} to grain {0}'.format(name, value)
        return ret
    ret['comment'] = 'Append value {1} to grain {0}'.format(name, value)
    return ret

def absent(name, value):
    '''
    Ensure the value is absent in the list type grain

    name
        The grain name
    
    value
       The value is  absent in the list type grain

    .. code-block:: yaml

        cheese:
          grains_list.present:
            - value: edam
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    grain = __grains__.get(name)
    
    if grain:
        # check whether grain is a list
        if not isinstance(grain, list):
            ret['result'] = False
            ret['coment'] = 'Grain {0} is not a valid list'
            return ret
        
        if value not in grain:
            ret['comment'] = 'Value {1} is absent in grain {0}'.format(name, value)
            return ret
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Value {1} is set to be remove from grain {0}'.format(name, value)
            return ret
        __salt__['grains.remove'](name, value)
        
        if value in __grains__.get(name):
            ret['result'] = False
            ret['comment'] = 'Failed remove value {1} from grain {0}'.format(name, value)
            return ret
        ret['comment'] = 'Remove value {1} from grain {0}'.format(name, value)    
    else:
        ret['comment'] = 'Grain {0} is not exist or empty'.format(name)
    return ret
