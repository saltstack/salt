# -*- coding: utf-8 -*-
'''
Manage and query udev info

.. versionadded:: 2015.8.0

'''
from __future__ import absolute_import

import logging
import salt.utils
import salt.modules.cmdmod
from salt.exceptions import CommandExecutionError

__salt__ = {
    'cmd.run_all': salt.modules.cmdmod.run_all,
}

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work when udevadm is installed.
    '''
    return salt.utils.which_bin(['udevadm']) is not None


def _parse_udevadm_info(udevadm_info):
    '''
    Parse the info returned by udevadm command.
    '''
    devices = list()
    udev_info = dict()

    for line in udevadm_info.splitlines():
        line = line.strip()
        if line:
            line = line.split(': ', 1)
            query = str(line[0])
            if query == 'E':
                if query not in udev_info:
                    udev_info[query] = {}
                val = line[1].split('=', 1)
                key = str(val[0])
                val = val[1]

                try:
                    val = int(val)
                except:  # pylint: disable=bare-except
                    try:
                        val = float(val)
                    except:  # pylint: disable=bare-except
                        pass

                udev_info[query][key] = val
            else:
                if query not in udev_info:
                    udev_info[query] = []
                udev_info[query].append(line[1])

        else:
            _normalize_info(udev_info)
            devices.append(udev_info)
            udev_info = dict()

    if udev_info:
        _normalize_info(udev_info)
        devices.append(udev_info)

    return devices


def _normalize_info(udev_info):
    '''
    Normalize the output dictionary
    '''
    for sect, val in udev_info.items():
        if len(val) == 1:
            udev_info[sect] = val[0]


def info(dev):
    '''
    Extract all info delivered by udevadm

    CLI Example:

    .. code-block:: bash

        salt '*' udev.info /dev/sda
        salt '*' udev.info /sys/class/net/eth0
    '''
    if 'sys' in dev:
        qtype = 'path'
    else:
        qtype = 'name'

    cmd = 'udevadm info --export --query=all --{0}={1}'.format(qtype, dev)
    udev_result = __salt__['cmd.run_all'](cmd, output_loglevel='quiet')

    if udev_result['retcode'] != 0:
        raise CommandExecutionError(udev_result['stderr'])

    return _parse_udevadm_info(udev_result['stdout'])[0]


def env(dev):
    '''
    Return all environment variables udev has for dev

    CLI Example:

    .. code-block:: bash

        salt '*' udev.env /dev/sda
        salt '*' udev.env /sys/class/net/eth0
    '''
    return info(dev).get('E', None)


def name(dev):
    '''
    Return the actual dev name(s?) according to udev for dev

    CLI Example:

    .. code-block:: bash

        salt '*' udev.dev /dev/sda
        salt '*' udev.dev /sys/class/net/eth0
    '''
    return info(dev).get('N', None)


def path(dev):
    '''
    Return the physical device path(s?) according to udev for dev

    CLI Example:

    .. code-block:: bash

        salt '*' udev.path /dev/sda
        salt '*' udev.path /sys/class/net/eth0
    '''
    return info(dev).get('P', None)


def links(dev):
    '''
    Return all udev-created device symlinks

    CLI Example:

    .. code-block:: bash

        salt '*' udev.links /dev/sda
        salt '*' udev.links /sys/class/net/eth0
    '''
    return info(dev).get('S', None)


def exportdb():
    '''
    Return all the udev database

    CLI Example:

    .. code-block:: bash
        salt '*' udev.exportdb
    '''

    cmd = 'udevadm info --export-db'
    udev_result = __salt__['cmd.run_all'](cmd, output_loglevel='quiet')

    if udev_result['retcode']:
        raise CommandExecutionError(udev_result['stderr'])

    return _parse_udevadm_info(udev_result['stdout'])
