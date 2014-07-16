# -*- coding: utf-8 -*-
'''
Managing software RAID with mdadm
==================================

A state module for creating or destroying software RAID devices.

.. code-block:: yaml

    /dev/md0:
      raid.present:
        - opts: level=1 chunk=256 raid-devices=2 /dev/xvdd /dev/xvde
'''

# Import python libs
import logging

# Import salt libs
import salt.utils

# Set up logger
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'raid'


def __virtual__():
    '''
    mdadm provides raid functions for Linux
    '''
    if __grains__['kernel'] != 'Linux':
        return False
    if not salt.utils.which('mdadm'):
        return False
    return __virtualname__


def present(name,
            level,
            devices,
            raid_devices=None,
            **kwargs):
    '''
    Verify that the raid is present

    .. versionchanged:: 2014.7.0

    name
        The name of raid device to be created

    level
                The RAID level to use when creating the raid.

    devices
        A list of devices used to build the array.

    raid_devices
        The number of devices in the array.  If not specified, the number of devices will be counted.

    Example:

    .. code-block:: yaml

        /dev/md0:
          raid.present:
            - level: 5
            - devices:
              - /dev/xvdd
              - /dev/xvde
              - /dev/xvdf
            - chunk: 256
            - run: True
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    # Device exists
    raids = __salt__['raid.list']()
    if raids.get(name):
        ret['comment'] = 'Raid {0} already present'.format(name)
        return ret

    # If running with test use the test_mode with create
    if __opts__['test']:
        res = __salt__['raid.create'](name,
                                      level,
                                      devices,
                                      raid_devices,
                                      test_mode=True,
                                      **kwargs)
        ret['comment'] = 'Raid will be created with: {0}'.format(res)
        ret['result'] = None
        return ret

    # Attempt to create the array
    __salt__['raid.create'](name,
                            level,
                            devices,
                            raid_devices,
                            **kwargs)

    raids = __salt__['raid.list']()
    changes = raids.get(name)
    if changes:
        ret['comment'] = 'Raid {0} created.'.format(name)
        ret['changes'] = changes
        # Saving config
        __salt__['raid.save_config']()
    else:
        ret['comment'] = 'Raid {0} failed to be created.'.format(name)
        ret['result'] = False

    return ret


def absent(name):
    '''
    Verify that the raid is absent

    name
        The name of raid device to be destroyed

    .. code-block:: yaml

        /dev/md0:
          raid:
            - absent
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    # Raid does not exist
    if name not in __salt__['raid.list']():
        ret['comment'] = 'Raid {0} already absent'.format(name)
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Raid {0} is set to be destroyed'.format(name)
        ret['result'] = None
        return ret
    else:
        # Attempt to destroy raid
        ret['result'] = __salt__['raid.destroy'](name)

        if ret['result']:
            ret['comment'] = 'Raid {0} has been destroyed'.format(name)
        else:
            ret['comment'] = 'Raid {0} failed to be destroyed'.format(name)
        return ret
