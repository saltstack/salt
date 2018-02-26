# -*- coding: utf-8 -*-
'''
Managing software RAID with mdadm
==================================

A state module for creating or destroying software RAID devices.

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

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six

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

    kwargs
        Optional arguments to be passed to mdadm.

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

    # Decide whether to create or assemble
    can_assemble = {}
    for dev in devices:
        # mdadm -E exits with 0 iff all devices given are part of an array
        cmd = 'mdadm -E {0}'.format(dev)
        can_assemble[dev] = __salt__['cmd.retcode'](cmd) == 0

    if True in six.itervalues(can_assemble) and False in six.itervalues(can_assemble):
        in_raid = sorted([x[0] for x in six.iteritems(can_assemble) if x[1]])
        not_in_raid = sorted([x[0] for x in six.iteritems(can_assemble) if not x[1]])
        ret['comment'] = 'Devices are a mix of RAID constituents ({0}) and '\
            'non-RAID-constituents({1}).'.format(in_raid, not_in_raid)
        ret['result'] = False
        return ret
    elif next(six.itervalues(can_assemble)):
        do_assemble = True
        verb = 'assembled'
    else:
        do_assemble = False
        verb = 'created'

    # If running with test use the test_mode with create or assemble
    if __opts__['test']:
        if do_assemble:
            res = __salt__['raid.assemble'](name,
                                            devices,
                                            test_mode=True,
                                            **kwargs)
        else:
            res = __salt__['raid.create'](name,
                                          level,
                                          devices,
                                          test_mode=True,
                                          **kwargs)
        ret['comment'] = 'Raid will be {0} with: {1}'.format(verb, res)
        ret['result'] = None
        return ret

    # Attempt to create or assemble the array
    if do_assemble:
        __salt__['raid.assemble'](name,
                                  devices,
                                  **kwargs)
    else:
        __salt__['raid.create'](name,
                                level,
                                devices,
                                **kwargs)

    raids = __salt__['raid.list']()
    changes = raids.get(name)
    if changes:
        ret['comment'] = 'Raid {0} {1}.'.format(name, verb)
        ret['changes'] = changes
        # Saving config
        __salt__['raid.save_config']()
    else:
        ret['comment'] = 'Raid {0} failed to be {1}.'.format(name, verb)
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
