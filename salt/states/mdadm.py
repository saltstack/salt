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


def present(name, opts=None):
    '''
    Verify that the raid is present

    name
        The name of raid device to be created

    opts
        The mdadm options to use to create the raid. See
        :mod:`mdadm <salt.modules.mdadm>` for more information.
        Opts can be expressed as a single string of options.

        .. code-block:: yaml

            /dev/md0:
              raid.present:
                - opts: level=1 chunk=256 raid-devices=2 /dev/xvdd /dev/xvde

        Or as a list of options.

        .. code-block:: yaml

            /dev/md0:
              raid.present:
                - opts:
                  - level=1
                  - chunk=256
                  - raid-devices=2
                  - /dev/xvdd
                  - /dev/xvde
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    args = [name]
    if isinstance(opts, str):
        opts = opts.split()

    args.extend(opts)

    # Device exists
    raids = __salt__['raid.list']()
    if raids.get(name):
        ret['comment'] = 'Raid {0} already present'.format(name)
        return ret

    # If running with test use the test_mode with create
    if __opts__['test']:
        args.extend(['test_mode=True'])
        res = __salt__['raid.create'](*args)
        ret['comment'] = 'Raid will be created with: {0}'.format(res)
        ret['result'] = None
        return ret

    # Attempt to create the array
    __salt__['raid.create'](*args)

    raids = __salt__['raid.list']()
    changes = raids.get(name)
    if changes:
        ret['comment'] = 'Raid {0} created.'.format(name)
        ret['changes'] = changes
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
