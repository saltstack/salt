'''
Mangement of linux logical volumes
==================================

A state module to manage lvms
'''

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only load the module if lvm is installed
    '''
    if salt.utils.which('lvm'):
        return 'lvm'
    return False


def vgpresent(name, devices, **kwargs):
    '''
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    if __salt__['lvm.vgdisplay'](name):
        ret['comment'] = 'Volume Group {0} already present'.format(name)
    elif __opts__['test']:
        ret['comment'] = 'Volume Group {0} is set to be created'.format(name)
        ret['result'] = None
        return ret
    else:
        changes = __salt__['lvm.vgcreate'](name, devices, **kwargs)

        if __salt__['lvm.vgdisplay'](name):
            ret['comment'] = 'Created Volume Group {0}'.format(name)
            ret['changes'] = changes
        else:
            ret['comment'] = 'Failed to create Volume Group {0}'.format(name)
            ret['result'] = False
    return ret


def vgabsent(name):
    '''
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    if not __salt__['lvm.vgdisplay'](name):
        ret['comment'] = 'Volume Group {0} already absent'.format(name)
    elif __opts__['test']:
        ret['comment'] = 'Volume Group {0} is set to be removed'.format(name)
        ret['result'] = None
        return ret
    else:
        changes = __salt__['lvm.vgremove'](name)

        if not __salt__['lvm.vgdisplay'](name):
            ret['comment'] = 'Removed Volume Group {0}'.format(name)
            ret['changes'] = changes
        else:
            ret['comment'] = 'Failed to remove Volume Group {0}'.format(name)
            ret['result'] = False
    return ret

