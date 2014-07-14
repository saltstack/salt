# -*- coding: utf-8 -*-
'''
Mounting of filesystems
=======================

Mount any type of mountable filesystem with the mounted function:

.. code-block:: yaml

    /mnt/sdb:
      mount.mounted:
        - device: /dev/sdb1
        - fstype: ext4
        - mkmnt: True
        - opts:
          - defaults

    /srv/bigdata:
      mount.mounted:
        - device: UUID=066e0200-2867-4ebe-b9e6-f30026ca2314
        - fstype: xfs
        - opts: nobootwait,noatime,nodiratime,nobarrier,logbufs=8
        - dump: 0
        - pass_num: 2
        - persist: True
        - mkmnt: True
'''

# Import python libs
import os.path
import re

# Import salt libs
from salt._compat import string_types


def mounted(name,
            device,
            fstype,
            mkmnt=False,
            opts=None,
            dump=0,
            pass_num=0,
            config='/etc/fstab',
            persist=True,
            mount=True):
    '''
    Verify that a device is mounted

    name
        The path to the location where the device is to be mounted

    device
        The device name, typically the device node, such as ``/dev/sdb1``
        or ``UUID=066e0200-2867-4ebe-b9e6-f30026ca2314``

    fstype
        The filesystem type, this will be ``xfs``, ``ext2/3/4`` in the case of classic
        filesystems, and ``fuse`` in the case of fuse mounts

    mkmnt
        If the mount point is not present then the state will fail, set ``mkmnt: True``
        to create the mount point if it is otherwise not present

    opts
        A list object of options or a comma delimited list

    dump
        The dump value to be passed into the fstab, Default is ``0``

    pass_num
        The pass value to be passed into the fstab, Default is ``0``

    config
        Set an alternative location for the fstab, Default is ``/etc/fstab``

    persist
        Set if the mount should be saved in the fstab, Default is ``True``

    mount
        Set if the mount should be mounted immediately, Default is ``True``
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # Make sure that opts is correct, it can be a list or a comma delimited
    # string
    if isinstance(opts, string_types):
        opts = opts.split(',')
    elif opts is None:
        opts = ['defaults']

    # remove possible trailing slash
    if not name == '/':
        name = name.rstrip('/')

    # Get the active data
    active = __salt__['mount.active']()
    real_name = os.path.realpath(name)
    if device.startswith('/'):
        real_device = os.path.realpath(device)
    elif device.upper().startswith('UUID='):
        real_device = device.split('=')[1].strip('"').lower()
    else:
        real_device = device

    # LVS devices have 2 names under /dev:
    # /dev/mapper/vg--name-lv--name and /dev/vg-name/lv-name
    # No matter what name is used for mounting,
    # mount always displays the device as /dev/mapper/vg--name-lv--name
    # Note the double-dash escaping.
    # So, let's call that the canonical device name
    # We should normalize names of the /dev/vg-name/lv-name type to the canonical name
    lvs_match = re.match(r'^/dev/(?P<vg_name>[^/]+)/(?P<lv_name>[^/]+$)', device)
    if lvs_match:
        double_dash_escaped = dict((k, re.sub(r'-', '--', v)) for k, v in lvs_match.groupdict().iteritems())
        mapper_device = '/dev/mapper/{vg_name}-{lv_name}'.format(**double_dash_escaped)
        if os.path.exists(mapper_device):
            real_device = mapper_device

    device_list = []
    if real_name in active:
        if mount:
            device_list.append(active[real_name]['device'])
            device_list.append(os.path.realpath(device_list[0]))
            alt_device = active[real_name]['alt_device'] if 'alt_device' in active[real_name] else None
            uuid_device = active[real_name]['device_uuid'] if 'device_uuid' in active[real_name] else None
            if alt_device and alt_device not in device_list:
                device_list.append(alt_device)
            if uuid_device and uuid_device not in device_list:
                device_list.append(uuid_device)
            if opts:
                for opt in opts:
                    if opt not in active[real_name]['opts']:
                        if __opts__['test']:
                            ret['result'] = None
                            ret['comment'] = "Remount would be forced because options changed"
                            return ret
                        else:
                            ret['changes']['umount'] = "Forced remount because " \
                                                        + "options changed"
                            remount_result = __salt__['mount.remount'](real_name, device, mkmnt=mkmnt, fstype=fstype, opts=opts)
                            ret['result'] = remount_result
                            return ret
            if real_device not in device_list:
                # name matches but device doesn't - need to umount
                ret['changes']['umount'] = "Forced unmount because devices " \
                                           + "don't match. Wanted: " + device
                if real_device != device:
                    ret['changes']['umount'] += " (" + real_device + ")"
                ret['changes']['umount'] += ", current: " + ', '.join(device_list)
                out = __salt__['mount.umount'](real_name)
                active = __salt__['mount.active']()
                if real_name in active:
                    ret['comment'] = "Unable to unmount"
                    ret['result'] = None
                    return ret
            else:
                ret['comment'] = 'Target was already mounted'
    # using a duplicate check so I can catch the results of a umount
    if real_name not in active:
        if mount:
            # The mount is not present! Mount it
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = '{0} would be mounted'.format(name)
                return ret

            out = __salt__['mount.mount'](name, device, mkmnt, fstype, opts)
            active = __salt__['mount.active']()
            if isinstance(out, string_types):
                # Failed to (re)mount, the state has failed!
                ret['comment'] = out
                ret['result'] = False
                return ret
            elif real_name in active:
                # (Re)mount worked!
                ret['comment'] = 'Target was successfully mounted'
                ret['changes']['mount'] = True
        else:
            ret['comment'] = '{0} not mounted'.format(name)

    if persist:
        if __opts__['test']:
            out = __salt__['mount.set_fstab'](name,
                                              device,
                                              fstype,
                                              opts,
                                              dump,
                                              pass_num,
                                              config,
                                              test=True)
            if out != 'present':
                ret['result'] = None
                if out == 'new':
                    if mount:
                        ret['comment'] = ('{0} is mounted, but needs to be '
                                          'written to the fstab in order to be '
                                          'made persistent').format(name)
                    else:
                        ret['comment'] = ('{0} needs to be '
                                          'written to the fstab in order to be '
                                          'made persistent').format(name)
                elif out == 'change':
                    if mount:
                        ret['comment'] = ('{0} is mounted, but its fstab entry '
                                          'must be updated').format(name)
                    else:
                        ret['comment'] = ('The {0} fstab entry '
                                          'must be updated').format(name)
                else:
                    ret['result'] = False
                    ret['comment'] = ('Unable to detect fstab status for '
                                      'mount point {0} due to unexpected '
                                      'output \'{1}\' from call to '
                                      'mount.set_fstab. This is most likely '
                                      'a bug.').format(name, out)
                return ret

        else:
            out = __salt__['mount.set_fstab'](name,
                                              device,
                                              fstype,
                                              opts,
                                              dump,
                                              pass_num,
                                              config)

        if out == 'present':
            ret['comment'] += '. Entry already exists in the fstab.'
            return ret
        if out == 'new':
            ret['changes']['persist'] = 'new'
            ret['comment'] += '. Added new entry to the fstab.'
            return ret
        if out == 'change':
            ret['changes']['persist'] = 'update'
            ret['comment'] += '. Updated the entry in the fstab.'
            return ret
        if out == 'bad config':
            ret['result'] = False
            ret['comment'] += '. However, the fstab was not found.'
            return ret

    return ret


def swap(name, persist=True, config='/etc/fstab'):
    '''
    Activates a swap device

    .. code-block:: yaml

        /root/swapfile:
          mount.swap

    .. note::
        ``swap`` does not currently support LABEL
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    on_ = __salt__['mount.swaps']()

    if name in on_:
        ret['comment'] = 'Swap {0} already active'.format(name)
    elif __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Swap {0} is set to be activated'.format(name)
    else:
        __salt__['mount.swapon'](name)

        on_ = __salt__['mount.swaps']()

        if name in on_:
            ret['comment'] = 'Swap {0} activated'.format(name)
            ret['changes'] = on_[name]
        else:
            ret['comment'] = 'Swap {0} failed to activate'.format(name)
            ret['result'] = False

    if persist:
        fstab_data = __salt__['mount.fstab'](config)
        if __opts__['test']:
            if name not in fstab_data:
                ret['result'] = None
                if name in on_:
                    ret['comment'] = ('Swap {0} is set to be added to the '
                                      'fstab and to be activated').format(name)
            return ret

        if 'none' in fstab_data:
            if fstab_data['none']['device'] == name and \
               fstab_data['none']['fstype'] != 'swap':
                return ret

        # present, new, change, bad config
        # Make sure the entry is in the fstab
        out = __salt__['mount.set_fstab']('none',
                                          name,
                                          'swap',
                                          ['defaults'],
                                          0,
                                          0,
                                          config)
        if out == 'present':
            return ret
        if out == 'new':
            ret['changes']['persist'] = 'new'
            ret['comment'] += '. Added new entry to the fstab.'
            return ret
        if out == 'change':
            ret['changes']['persist'] = 'update'
            ret['comment'] += '. Updated the entry in the fstab.'
            return ret
        if out == 'bad config':
            ret['result'] = False
            ret['comment'] += '. However, the fstab was not found.'
            return ret
    return ret


def unmounted(name,
              config='/etc/fstab',
              persist=False):
    '''
    .. versionadded:: 0.17.0

    Verify that a device is not mounted

    name
        The path to the location where the device is to be unmounted from

    config
        Set an alternative location for the fstab, Default is ``/etc/fstab``

    persist
        Set if the mount should be purged from the fstab, Default is ``False``
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # Get the active data
    active = __salt__['mount.active']()
    if name not in active:
        # Nothing to unmount
        ret['comment'] = 'Target was already unmounted'
    if name in active:
        # The mount is present! Unmount it
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('Mount point {0} is mounted but should not '
                              'be').format(name)
            return ret
        out = __salt__['mount.umount'](name)
        if isinstance(out, string_types):
            # Failed to umount, the state has failed!
            ret['comment'] = out
            ret['result'] = False
        elif out is True:
            # umount worked!
            ret['comment'] = 'Target was successfully unmounted'
            ret['changes']['umount'] = True
        else:
            ret['comment'] = 'Execute set to False, Target was not unmounted'
            ret['result'] = True

    if persist:
        fstab_data = __salt__['mount.fstab'](config)
        if name not in fstab_data:
            ret['comment'] += '. fstab entry not found'
        else:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = ('Mount point {0} is unmounted but needs to '
                                  'be purged from {1} to be made '
                                  'persistent').format(name, config)
                return ret
            else:
                out = __salt__['mount.rm_fstab'](name, config)
                if out is not True:
                    ret['result'] = False
                    ret['comment'] += '. Failed to persist purge'
                else:
                    ret['comment'] += '. Removed target from fstab'
                    ret['changes']['persist'] = 'purged'

    return ret


def mod_watch(name, **kwargs):
    '''
    The mounted watcher, called to invoke the watch command.

    name
        The name of the mount point

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if kwargs['sfun'] == 'mounted':
        out = __salt__['mount.remount'](name, kwargs['device'], False, kwargs['fstype'], kwargs['opts'])
        if out:
            ret['comment'] = '{0} remounted'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = '{0} failed to remount: {1}'.format(name, out)
    else:
        ret['comment'] = 'Watch not supported in {1} at this time'.format(kwargs['sfun'])
    return ret
