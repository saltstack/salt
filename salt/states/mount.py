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
from __future__ import absolute_import

# Import python libs
import os.path
import re

# Import salt libs
from salt.ext.six import string_types

import logging
import salt.ext.six as six
log = logging.getLogger(__name__)
from salt._compat import string_types


def mounted(name,
            device,
            fstype,
            mkmnt=False,
            opts='defaults',
            dump=0,
            pass_num=0,
            config='/etc/fstab',
            persist=True,
            mount=True,
            user=None,
            match_on='auto'):
    '''
    Verify that a device is mounted

    name
        The path to the location where the device is to be mounted

    device
        The device name, typically the device node, such as ``/dev/sdb1``
        or ``UUID=066e0200-2867-4ebe-b9e6-f30026ca2314`` or ``LABEL=DATA``

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

    user
        The user to own the mount; this defaults to the user salt is
        running as on the minion

    match_on
        A name or list of fstab properties on which this state should be applied.
        Default is ``auto``, a special value indicating to guess based on fstype.
        In general, ``auto`` matches on name for recognized special devices and
        device otherwise.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # Defaults is not a valid option on Mac OS
    if __grains__['os'] in ['MacOS', 'Darwin'] and opts == 'defaults':
        opts = 'noowners'

    # Make sure that opts is correct, it can be a list or a comma delimited
    # string
    if isinstance(opts, string_types):
        opts = opts.split(',')

    # remove possible trailing slash
    if not name == '/':
        name = name.rstrip('/')

    # Get the active data
    active = __salt__['mount.active'](extended=True)
    real_name = os.path.realpath(name)
    if device.startswith('/'):
        if 'bind' in opts and real_name in active:
            _device = device
            if active[real_name]['device'].startswith('/'):
                # Find the device that the bind really points at.
                while True:
                    if _device in active:
                        _real_device = active[_device]['device']
                        opts = list(set(opts + active[_device]['opts'] + active[_device]['superopts']))
                        active[real_name]['opts'].append('bind')
                        break
                    _device = os.path.dirname(_device)
                real_device = _real_device
            else:
                # Remote file systems act differently.
                if _device in active:
                    opts = list(set(opts + active[_device]['opts'] + active[_device]['superopts']))
                    active[real_name]['opts'].append('bind')
                real_device = active[real_name]['device']
        else:
            real_device = os.path.realpath(device)
    elif device.upper().startswith('UUID='):
        real_device = device.split('=')[1].strip('"').lower()
    elif device.upper().startswith('LABEL='):
        _label = device.split('=')[1]
        cmd = 'blkid -L {0}'.format(_label)
        res = __salt__['cmd.run_all']('{0}'.format(cmd))
        if res['retcode'] > 0:
            ret['comment'] = 'Unable to find device with label {0}.'.format(_label)
            ret['result'] = False
            return ret
        else:
            real_device = res['stdout']
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
        double_dash_escaped = dict((k, re.sub(r'-', '--', v)) for k, v in six.iteritems(lvs_match.groupdict()))
        mapper_device = '/dev/mapper/{vg_name}-{lv_name}'.format(**double_dash_escaped)
        if os.path.exists(mapper_device):
            real_device = mapper_device

    # When included in a Salt state file, FUSE
    # devices are prefaced by the filesystem type
    # and a hash, e.g. sshfs#.  In the mount list
    # only the hostname is included.  So if we detect
    # that the device is a FUSE device then we
    # remove the prefaced string so that the device in
    # state matches the device in the mount list.
    fuse_match = re.match(r'^\w+\#(?P<device_name>.+)', device)
    if fuse_match:
        if 'device_name' in fuse_match.groupdict():
            real_device = fuse_match.group('device_name')

    device_list = []
    if real_name in active:
        if 'superopts' not in active[real_name]:
            active[real_name]['superopts'] = []
        if mount:
            device_list.append(active[real_name]['device'])
            device_list.append(os.path.realpath(device_list[0]))
            alt_device = active[real_name]['alt_device'] if 'alt_device' in active[real_name] else None
            uuid_device = active[real_name]['device_uuid'] if 'device_uuid' in active[real_name] else None
            label_device = active[real_name]['device_label'] if 'device_label' in active[real_name] else None
            if alt_device and alt_device not in device_list:
                device_list.append(alt_device)
            if uuid_device and uuid_device not in device_list:
                device_list.append(uuid_device)
            if label_device and label_device not in device_list:
                device_list.append(label_device)
            if opts:
                mount_invisible_options = [
                    '_netdev',
                    'actimeo',
                    'bg',
                    'comment',
                    'defaults',
                    'delay_connect',
                    'intr',
                    'loop',
                    'nointr',
                    'nobootwait',
                    'nofail',
                    'password',
                    'reconnect',
                    'retry',
                    'soft',
                    'auto',
                    'users',
                    'bind',
                    'nonempty',
                    'transform_symlinks',
                    'port',
                ]
                # options which are provided as key=value (e.g. password=Zohp5ohb)
                mount_invisible_keys = [
                    'actimeo',
                    'comment',
                    'password',
                    'retry',
                    'port',
                ]
                # Some filesystems have options which should not force a remount.
                mount_ignore_fs_keys = {
                        'ramfs': ['size']
                        }

                for opt in opts:
                    keyval_option = opt.split('=')[0]
                    if keyval_option in mount_invisible_keys:
                        opt = keyval_option

                    size_match = re.match(r'size=(?P<size_value>[0-9]+)(?P<size_unit>k|m|g)', opt)
                    if size_match:
                        converted_size = int(size_match.group('size_value'))
                        if size_match.group('size_unit') == 'm':
                            converted_size = int(size_match.group('size_value')) * 1024
                        if size_match.group('size_unit') == 'g':
                            converted_size = int(size_match.group('size_value')) * 1024 * 1024
                        opt = "size={0}k".format(converted_size)
                    # make cifs option user synonym for option username which is reported by /proc/mounts
                    if fstype in ['cifs'] and opt.split('=')[0] == 'user':
                        opt = "username={0}".format(opt.split('=')[1])

                    if opt not in active[real_name]['opts'] \
                        and opt not in active[real_name]['superopts'] \
                        and opt not in mount_invisible_options:
                        if __opts__['test']:
                            ret['result'] = None
                            ret['comment'] = "Remount would be forced because options ({0}) changed".format(opt)
                            return ret
                        else:
                            # Some file systems require umounting and mounting if options change
                            # add others to list that require similiar functionality
                            if fstype in ['nfs', 'cvfs'] or fstype.startswith('fuse'):
                                ret['changes']['umount'] = "Forced unmount and mount because " \
                                                            + "options ({0}) changed".format(opt)
                                unmount_result = __salt__['mount.umount'](real_name)
                                if unmount_result is True:
                                    mount_result = __salt__['mount.mount'](real_name, device, mkmnt=mkmnt, fstype=fstype, opts=opts)
                                    ret['result'] = mount_result
                                else:
                                    ret['result'] = False
                                    ret['comment'] = 'Unable to unmount {0}: {1}.'.format(real_name, unmount_result)
                                    return ret
                            else:
                                ret['changes']['umount'] = "Forced remount because " \
                                                            + "options ({0}) changed".format(opt)
                                remount_result = __salt__['mount.remount'](real_name, device, mkmnt=mkmnt, fstype=fstype, opts=opts)
                                ret['result'] = remount_result
                                # Cleanup after the remount, so we
                                # don't write remount into fstab
                                if 'remount' in opts:
                                    opts.remove('remount')
            if real_device not in device_list:
                # name matches but device doesn't - need to umount
                if __opts__['test']:
                    ret['result'] = None
                    ret['comment'] = "An umount would have been forced " \
                                     + "because devices do not match.  Watched: " \
                                     + device
                else:
                    ret['changes']['umount'] = "Forced unmount because devices " \
                                               + "don't match. Wanted: " + device
                    if real_device != device:
                        ret['changes']['umount'] += " (" + real_device + ")"
                    ret['changes']['umount'] += ", current: " + ', '.join(device_list)
                    out = __salt__['mount.umount'](real_name, user=user)
                    active = __salt__['mount.active'](extended=True)
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
                if os.path.exists(name):
                    ret['comment'] = '{0} would be mounted'.format(name)
                else:
                    ret['comment'] = '{0} will be created and mounted'.format(name)
                return ret

            if not os.path.exists(name):
                if mkmnt:
                    __salt__['file.mkdir'](name, user=user)
                else:
                    ret['result'] = False
                    ret['comment'] = 'Mount directory is not present'
                    return ret

            out = __salt__['mount.mount'](name, device, mkmnt, fstype, opts, user=user)
            active = __salt__['mount.active'](extended=True)
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
        # Override default for Mac OS
        if __grains__['os'] in ['MacOS', 'Darwin'] and config == '/etc/fstab':
            config = "/etc/auto_salt"

        if __opts__['test']:
            if __grains__['os'] in ['MacOS', 'Darwin']:
                out = __salt__['mount.set_automaster'](name,
                                              device,
                                              fstype,
                                              opts,
                                              config,
                                              test=True)
            else:
                out = __salt__['mount.set_fstab'](name,
                                                  device,
                                                  fstype,
                                                  opts,
                                                  dump,
                                                  pass_num,
                                                  config,
                                                  test=True,
                                                  match_on=match_on)
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
            if __grains__['os'] in ['MacOS', 'Darwin']:
                out = __salt__['mount.set_automaster'](name,
                                              device,
                                              fstype,
                                              opts,
                                              config)
            else:
                out = __salt__['mount.set_fstab'](name,
                                                  device,
                                                  fstype,
                                                  opts,
                                                  dump,
                                                  pass_num,
                                                  config,
                                                  match_on=match_on)

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

    if __salt__['file.is_link'](name):
        real_swap_device = __salt__['file.readlink'](name)
        if not real_swap_device.startswith('/'):
            real_swap_device = '/dev/{0}'.format(os.path.basename(real_swap_device))
        else:
            real_swap_device = real_swap_device
    else:
        real_swap_device = name

    if real_swap_device in on_:
        ret['comment'] = 'Swap {0} already active'.format(name)
    elif __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Swap {0} is set to be activated'.format(name)
    else:
        __salt__['mount.swapon'](real_swap_device)

        on_ = __salt__['mount.swaps']()

        if real_swap_device in on_:
            ret['comment'] = 'Swap {0} activated'.format(name)
            ret['changes'] = on_[real_swap_device]
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
              device,
              config='/etc/fstab',
              persist=False,
              user=None):
    '''
    .. versionadded:: 0.17.0

    Verify that a device is not mounted

    name
        The path to the location where the device is to be unmounted from

    .. versionadded:: 2015.5.0

    device
        The device to be unmounted.

    config
        Set an alternative location for the fstab, Default is ``/etc/fstab``

    persist
        Set if the mount should be purged from the fstab, Default is ``False``

    user
        The user to own the mount; this defaults to the user salt is
        running as on the minion
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # Get the active data
    active = __salt__['mount.active'](extended=True)
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
        if device:
            out = __salt__['mount.umount'](name, device, user=user)
        else:
            out = __salt__['mount.umount'](name, user=user)
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
        # Override default for Mac OS
        if __grains__['os'] in ['MacOS', 'Darwin'] and config == '/etc/fstab':
            config = "/etc/auto_salt"
            fstab_data = __salt__['mount.automaster'](config)
        else:
            fstab_data = __salt__['mount.fstab'](config)

        if name not in fstab_data:
            ret['comment'] += '. fstab entry not found'
        else:
            if device:
                if fstab_data[name]['device'] != device:
                    ret['comment'] += '. fstab entry for device {0} not found'.format(device)
                    return ret
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = ('Mount point {0} is unmounted but needs to '
                                  'be purged from {1} to be made '
                                  'persistent').format(name, config)
                return ret
            else:
                if __grains__['os'] in ['MacOS', 'Darwin']:
                    out = __salt__['mount.rm_automaster'](name, device, config)
                else:
                    out = __salt__['mount.rm_fstab'](name, device, config)
                if out is not True:
                    ret['result'] = False
                    ret['comment'] += '. Failed to persist purge'
                else:
                    ret['comment'] += '. Removed target from fstab'
                    ret['changes']['persist'] = 'purged'

    return ret


def mod_watch(name, user=None, **kwargs):
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
        out = __salt__['mount.remount'](name, kwargs['device'], False, kwargs['fstype'], kwargs['opts'], user=user)
        if out:
            ret['comment'] = '{0} remounted'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = '{0} failed to remount: {1}'.format(name, out)
    else:
        ret['comment'] = 'Watch not supported in {0} at this time'.format(kwargs['sfun'])
    return ret
