# -*- coding: utf-8 -*-
'''
Manage NX-OS System Image Upgrades.

.. versionadded: xxxx.xx.x

For documentation on setting up the nxos proxy minion look in the documentation
for :mod:`salt.proxy.nxos<salt.proxy.nxos>`.
'''
from __future__ import absolute_import, print_function, unicode_literals
import salt.utils.platform
import re
import logging
import time


__virtualname__ = 'nxos'
__virtual_aliases__ = ('nxos_upgrade',)

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def image_running(name, system_image, kickstart_image=None, issu=True, **kwargs):
    '''
    Ensure the NX-OS system image is running on the device.

    name
        Name of the salt state task

    system_image
        Name of the system image file on bootflash:

    kickstart_image
        Name of the kickstart image file on bootflash:
        This is not needed if the system_image is a combined system and
        kickstart image
        Default: None

    issu
        Ensure the correct system is running on the device using an in service
        software upgrade, or force a disruptive upgrade by setting the option
        to False.
        Default: False

    timeout
        Timeout in seconds for long running 'install all' upgrade command.
        Default: 900
    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    if kickstart_image is None:
        upgrade = __salt__['nxos.upgrade'](system_image=system_image,
                                           issu=issu, **kwargs)
    else:
        upgrade = __salt__['nxos.upgrade'](system_image=system_image,
                                           kickstart_image=kickstart_image,
                                           issu=issu, **kwargs)

    if upgrade['upgrade_in_progress']:
        ret['result'] = upgrade['upgrade_in_progress']
        ret['changes'] = upgrade['module_data']
        ret['comment'] = 'NX-OS Device Now Being Upgraded - See Change Details Below'
    elif upgrade['succeeded']:
        ret['result'] = upgrade['succeeded']
        ret['comment'] = 'NX-OS Device Running Image: {}'.format(_version_info())
    else:
        ret['comment'] = 'Upgrade Failed: {}.'.format(upgrade['error_data'])

    return ret


def _version_info():
    '''
    Helper method to return running image version
    '''
    if 'NXOS' in __grains__['nxos']['software']:
        return __grains__['nxos']['software']['NXOS']
    elif 'kickstart' in __grains__['nxos']['software']:
        return __grains__['nxos']['software']['kickstart']
    else:
        return 'Unable to detect sofware version'
