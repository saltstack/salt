# -*- coding: utf-8 -*-
'''
Management of Linux logical volumes
===================================

A state module to manage LVMs

.. code-block:: yaml

    /dev/sda:
      lvm.pv_present

    my_vg:
      lvm.vg_present:
        - devices: /dev/sda

    lvroot:
      lvm.lv_present:
        - vgname: my_vg
        - size: 10G
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


def pv_present(name, **kwargs):
    '''
    Set a physical device to be used as an LVM physical volume

    name
        The device name to initialize.

    kwargs
        Any supported options to pvcreate. See
        :mod:`linux_lvm <salt.modules.linux_lvm>` for more details.
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
        changes = __salt__['lvm.pvcreate'](name, **kwargs)

        if __salt__['lvm.pvdisplay'](name):
            ret['comment'] = 'Created Physical Volume {0}'.format(name)
            ret['changes'] = changes
        else:
            ret['comment'] = 'Failed to create Physical Volume {0}'.format(name)
            ret['result'] = False
    return ret


def vg_present(name, devices=None, **kwargs):
    '''
    Create an LVM volume group

    name
        The volume group name to create

    devices
        A list of devices that will be added to the volume group

    kwargs
        Any supported options to vgcreate. See
        :mod:`linux_lvm <salt.modules.linux_lvm>` for more details.
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
    Remove an LVM volume group

    name
        The volume group to remove
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


def lv_present(name, vgname=None, size=None, extents=None, pv=''):
    '''
    Create a new logical volume

    name
        The name of the logical volume

    vgname
        The volume group name for this logical volume

    size
        The initial size of the logical volume

    extents
        The number of logical extents to allocate

    pv
        The physical volume to use
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    lvpath = '/dev/{0}/{1}'.format(vgname, name)
    if __salt__['lvm.lvdisplay'](lvpath):
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

        if __salt__['lvm.lvdisplay'](lvpath):
            ret['comment'] = 'Created Logical Volume {0}'.format(name)
            ret['changes'] = changes
        else:
            ret['comment'] = 'Failed to create Logical Volume {0}'.format(name)
            ret['result'] = False
    return ret


def lv_absent(name, vgname=None):
    '''
    Remove a given existing logical volume from a named existing volume group

    name
        The logical volume to remove

    vgname
        The volume group name
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    lvpath = '/dev/{0}/{1}'.format(vgname, name)
    if not __salt__['lvm.lvdisplay'](lvpath):
        ret['comment'] = 'Logical Volume {0} already absent'.format(name)
    elif __opts__['test']:
        ret['comment'] = 'Logical Volume {0} is set to be removed'.format(name)
        ret['result'] = None
        return ret
    else:
        changes = __salt__['lvm.lvremove'](name, vgname)

        if not __salt__['lvm.lvdisplay'](lvpath):
            ret['comment'] = 'Removed Logical Volume {0}'.format(name)
            ret['changes'] = changes
        else:
            ret['comment'] = 'Failed to remove Logical Volume {0}'.format(name)
            ret['result'] = False
    return ret
