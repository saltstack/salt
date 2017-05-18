# -*- coding: utf-8 -*-
'''
Opening of Encrypted Devices
=======================

Ensure that an encrypted device is mapped with the `mapped` function:

.. code-block:: yaml

    mappedname:
      cryptdev.mapped:
        - device: /dev/sdb1
        - password: /etc/keyfile.key
        - opts:
          - size=256

    swap:
      crypted.mapped:
        - device: /dev/sdx4
        - password: /dev/urandom
        - opts: swap,cipher=aes-cbc-essiv:sha256,size=256

    mappedbyuuid:
      crypted.mapped:
        - device: UUID=066e0200-2867-4ebe-b9e6-f30026ca2314
        - password: /etc/keyfile.key
        - config: /etc/alternate-crypttab
'''
from __future__ import absolute_import

# Import python libs
import os.path

# Import salt libs
from salt.ext.six import string_types

import logging
import salt.ext.six as six
log = logging.getLogger(__name__)

def mapped(name,
           device,
           password=None,
           opts=None,
           config='/etc/crypttab',
           persist=True,
           delay_mapping=True,
           match_on='name'):
    '''
    Verify that a device is mapped

    name
        The name under which the device is to be mapped

    device
        The device name, typically the device node, such as ``/dev/sdb1``
        or ``UUID=066e0200-2867-4ebe-b9e6-f30026ca2314``.

    password
        Either ``None`` if the password is to be entered manually on boot, or
        an absolute path to a key file. If it must be entered manually, it
        cannot be mapped immediately.

    opts
        A list object of options or a comma delimited list

    config
        Set an alternative location for the crypttab, if the map is persistent,
        Default is ``/etc/crypttab``

    persist
        Set if the map should be saved in the crypttab, Default is ``True``

    delay_mapping
        Set if the device mapping should not be executed until the next boot.
        Default is ``True``.

    match_on
        A name or list of crypttab properties on which this state should be applied.
        Default is ``name``, meaning that the line is matched only by the name
        parameter. If the desired configuration requires two devices mapped to
        the same name, supply a list of parameters to match on.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if not delay_mapping:
        # Get the active crypt mounts. If ours is listed already, no action is necessary.
        active = __salt__['cryptdev.active']()
        if name not in active.keys():
            # Open the map using cryptsetup. This does not pass any options.
            if opts:
                log.warn('passed cryptdev options are ignored when mapping immediately')

            if __opts__['test']:
                ret['result'] = None
                ret['commment'] = 'Device would be mapped immediately'
            else:
                cryptsetup_result = __salt__['cryptdev.open'](name, device, password)
                if cryptsetup_result:
                    ret['changes']['cryptsetup'] = 'Device mapped using cryptsetup'
                else:
                    ret['changes']['cryptsetup'] = 'Device failed to map using cryptsetup'
                    ret['result'] = False

    if persist and not __opts__['test']:
        crypttab_result = __salt__['cryptdev.set_crypttab'](name,
                                                            device,
                                                            password=password,
                                                            options=opts,
                                                            config=config,
                                                            match_on=match_on)
        if crypttab_result:
            if crypttab_result == 'new':
                ret['changes']['crypttab'] = 'Entry added in {0}'.format(config)

            if crypttab_result == 'change':
                ret['changes']['crypttab'] = 'Existing entry in {0} changed'.format(config)
        
        else:
            ret['changes']['crypttab'] = 'Unable to set entry in {0}'.format(config)
            ret['result'] = False

    return ret

def unmapped(name,
             config='/etc/crypttab',
             persist=True,
             immediate=False):
    '''
    Ensure that a device is unmapped

    name
        The name to ensure is not mapped

    config
        Set an alternative location for the crypttab, if the map is persistent,
        Default is ``/etc/crypttab``

    persist
        Set if the map should be removed from the crypttab. Default is ``True``

    immediate
        Set if the device should be unmapped immediately. Default is ``False``.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if immediate:
        # Get the active crypt mounts. If ours is not listed already, no action is necessary.
        active = __salt__['cryptdev.active']()
        if name in active.keys():
            # Close the map using cryptsetup.
            if __opts__['test']:
                ret['result'] = None
                ret['commment'] = 'Device would be unmapped immediately'
            else:
                cryptsetup_result = __salt__['cryptdev.close'](name)
                if cryptsetup_result:
                    ret['changes']['cryptsetup'] = 'Device unmapped using cryptsetup'
                else:
                    ret['changes']['cryptsetup'] = 'Device failed to unmap using cryptsetup'
                    ret['result'] = False

    if persist and not __opts__['test']:
        crypttab_result = __salt__['cryptdev.rm_crypttab'](name, config=config)
        if crypttab_result:
            if crypttab_result == 'change':
                ret['changes']['crypttab'] = 'Entry removed from {0}'.format(config)

        else:
            ret['changes']['crypttab'] = 'Unable to remove entry in {0}'.format(config)
            ret['result'] = False

    return ret
