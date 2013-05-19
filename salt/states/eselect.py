'''
Management of Gentoo configuration using eselect
================================================

A state module to manage Gentoo configuration via eselect

.. code-block:: yaml

    profile:
        eselect.set:
            target: hardened/linux/amd64
'''

def __virtual__():
    '''
    Only load if the eselect module is available in __salt__
    '''
    return 'eselect' if 'eselect.exec_action' in __salt__ else False

def set(name, target):
    '''
    Verify that the given module is set to the given target

    name
        The name of the module
    '''
    ret = {'changes': {},
             'comment': '',
             'name': name,
             'result': True}
    
    old_target = __salt__['eselect.get_current_target'](name)
    
    if target == old_target:
        ret['comment'] = 'Target "{0}" is already set on "{1}" module.'.format(target,name)
    elif target not in __salt__['eselect.get_target_list'](name):
        ret['comment'] = 'Target "{0}" is not available for "{1}" module.'.format(target,name)
        ret['result'] = False
    elif __opts__['test']:
        ret['comment'] = 'Target "{0}" will be set on "{1}" module.'.format(target,name)
        ret['result'] = None
        return ret
    else:
        result = __salt__['eselect.set_target'](name,target)
        if result:
            ret['comment'] = 'Target "{0}" failed to be set on "{1}" module.'.format(target,name)
            ret['result'] = False
        else:
            ret['changes'][name] = {'old':old_target,'new':target}
            ret['comment'] = 'Target "{0}" set on "{1}" module.'.format(target,name)
    
    return ret
