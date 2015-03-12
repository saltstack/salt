# -*- coding: utf-8 -*-
'''
Management of Block Devices
===================================

A state module to manage blockdevices

.. code-block:: yaml


    /dev/sda:
      blockdev.tuned:
        - read-only: True

    master-data:
      blockdev.tuned::
        - name : /dev/vg/master-data
        - read-only: True
        - read-ahead: 1024


'''

# Import python libs
import os
import os.path

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if salt.utils.is_windows():
        return False
    return True


def tuned(name, **kwargs):
    '''
    Manage options of block device

    name
        The name of the block device

    opts:
      - read-ahead
          Read-ahead buffer size

      - filesystem-read-ahead
          Filesystem Read-ahead buffer size

      - read-only
          Set Read-Only

      - read-write
          Set Read-Write
    '''

    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    kwarg_map = {'read-ahead': 'getra',
                 'filesystem-read-ahead': 'getfra',
                 'read-only': 'getro',
                 'read-write': 'getro'}

    if not __salt__['file.is_blkdev']:
        ret['comment'] = ('Changes to {0} cannot be applied. '
                          'Not a block device. ').format(name)
    elif __opts__['test']:
        ret['comment'] = 'Changes to {0} will be applied '.format(name)
        ret['result'] = None
        return ret
    else:
        current = __salt__['blockdev.dump'](name)
        changes = __salt__['blockdev.tune'](name, **kwargs)
        changeset = {}
        for key in kwargs:
            if key in kwarg_map:
                switch = kwarg_map[key]
                if current[switch] != changes[switch]:
                    if isinstance(kwargs[key], bool):
                        old = (current[switch] == '1')
                        new = (changes[switch] == '1')
                    else:
                        old = current[switch]
                        new = changes[switch]
                    if key == 'read-write':
                        old = not old
                        new = not new
                    changeset[key] = 'Changed from {0} to {1}'.format(old, new)
        if changes:
            if changeset:
                ret['comment'] = ('Block device {0} '
                                  'successfully modified ').format(name)
                ret['changes'] = changeset
            else:
                ret['comment'] = 'Block device {0} already in correct state'.format(name)
        else:
            ret['comment'] = 'Failed to modify block device {0}'.format(name)
            ret['result'] = False
    return ret


def formatted(name, fs_type='ext4', **kwargs):
    '''
    Manage filesystems of partitions.

    name
        The name of the block device

    fs_type
        The filesystem it should be formatted as
    '''
    ret = {'changes': {},
           'comment': '{0} already formatted with {1}'.format(name, fs_type),
           'name': name,
           'result': False}

    if not os.path.exists(name):
        ret['comment'] = '{0} does not exist'.format(name)
        return ret

    blk = __salt__['cmd.run']('lsblk -o fstype {0}'.format(name)).splitlines()

    if len(blk) == 1:
        current_fs = ''
    else:
        current_fs = blk[1]

    if current_fs == fs_type:
        ret['result'] = True
        return ret
    elif not salt.utils.which('mkfs.{0}'.format(fs_type)):
        ret['comment'] = 'Invalid fs_type: {0}'.format(fs_type)
        ret['result'] = False
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Changes to {0} will be applied '.format(name)
        ret['result'] = None
        return ret

    cmd = 'mkfs -t {0} '.format(fs_type)
    if 'inode_size' in kwargs:
        if fs_type[:3] == 'ext':
            cmd += '-i {0}'.format(kwargs['inode_size'])
        elif fs_type == 'xfs':
            cmd += '-i size={0} '.format(kwargs['inode_size'])
    cmd += name
    __salt__['cmd.run'](cmd).splitlines()
    __salt__['cmd.run']('sync').splitlines()
    blk = __salt__['cmd.run']('lsblk -o fstype {0}'.format(name)).splitlines()

    if len(blk) == 1:
        current_fs = ''
    else:
        current_fs = blk[1]

    if current_fs == fs_type:
        ret['comment'] = ('{0} has been formatted '
                          'with {1}').format(name, fs_type)
        ret['changes'] = {'new': fs_type, 'old': current_fs}
        ret['result'] = True
    else:
        ret['comment'] = 'Failed to format {0}'.format(name)
        ret['result'] = False
    return ret
