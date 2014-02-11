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
      blockdev:
        - tuned:
        - name : /dev/vg/master-data
        - read-only: True
        - read-ahead: 1024


'''



# Import salt libs
import salt.utils

def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if salt.utils.is_windows():
        return False
    return 'blockdev'

def tuned(name,**kwargs):
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

    if not __salt__['file.is_blkdev']:
        ret['comment'] = 'Changes to {0} cannot be applied. Not a block device '.format(name)
    elif __opts__['test']:
        ret['comment'] = 'Changes to {0} will be applied '.format(name)
        ret['result'] = None
        return ret
    else:
        changes = __salt__['blockdev.tune'](name,**kwargs)
        if changes:
            ret['comment'] = 'Block device {0} successfully modified '.format(name)
            ret['changes'] = changes
        else:
            ret['comment'] = 'Failed to modify block device {0}'.format(name)
            ret['result'] = False
    return ret
