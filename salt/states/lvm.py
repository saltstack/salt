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


def pv_present(name, devices, **kwargs):
    '''
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    if __salt__['lvm.pvdisplay'](name):
        ret['comment'] = 'Physical Volume {0} already present'.format(name)
    elif __opts__['test']:
        ret['comment'] = 'Physical Volume {0} is set to be created'.format(name)
        ret['result'] = None
        return ret
    else:
        changes = __salt__['lvm.pvcreate'](name, devices, **kwargs)

        if __salt__['lvm.pvdisplay'](name):
            ret['comment'] = 'Created Physical Volume {0}'.format(name)
            ret['changes'] = changes
        else:
            ret['comment'] = 'Failed to create Physical Volume {0}'.format(name)
            ret['result'] = False
    return ret


def vg_present(name, devices, **kwargs):
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


def vg_absent(name):
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


def lv_present(name, vgname, size=None, extents=None, pv=''):
    '''
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    if __salt__['lvm.lvdisplay'](name):
        ret['comment'] = 'Logical Volume {0} already present'.format(name)
    elif __opts__['test']:
        ret['comment'] = 'Logical Volume {0} is set to be created'.format(name)
        ret['result'] = None
        return ret
    else:
        changes = __salt__['lvm.lvcreate'](name,
                                           vgname,
                                           size=size,
                                           extents=extents,
                                           pv=pv)

        if __salt__['lvm.lvdisplay'](name):
            ret['comment'] = 'Created Logical Volume {0}'.format(name)
            ret['changes'] = changes
        else:
            ret['comment'] = 'Failed to create Logical Volume {0}'.format(name)
            ret['result'] = False
    return ret


def lv_absent(name, vgname):
    '''
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    if not __salt__['lvm.lvdisplay'](name):
        ret['comment'] = 'Logical Volume {0} already absent'.format(name)
    elif __opts__['test']:
        ret['comment'] = 'Logical Volume {0} is set to be removed'.format(name)
        ret['result'] = None
        return ret
    else:
        changes = __salt__['lvm.lvremove'](name, vgname)

        if not __salt__['lvm.lvdisplay'](name):
            ret['comment'] = 'Removed Logical Volume {0}'.format(name)
            ret['changes'] = changes
        else:
            ret['comment'] = 'Failed to remove Logical Volume {0}'.format(name)
            ret['result'] = False
    return ret
