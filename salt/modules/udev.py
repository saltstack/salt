# -*- coding: utf-8 -*-
'''
Manage and query udev info
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


def info(dev):
    '''
    Extract all info delivered by udevadm
    Get it all into a semi-nice dict
    '''
    if 'sys' in dev:
        qtype = 'path'
    else:
        qtype = 'name'

    cmd = 'udevadm info --export --query=all --{0}={1}'.format(qtype, dev)
    udev_result = __salt__['cmd.run_all'](cmd, output_loglevel='quiet')

    if udev_result['retcode'] != 0:
        raise CommandExecutionError(udev_result['stderr'])

    udev_info = {}

    for line in udev_result['stdout'].splitlines():
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

    for sect, val in udev_info.items():
        if len(val) == 1:
            udev_info[sect] = val[0]

    return udev_info


def env(dev):
    '''
    Return the environment variables available to udev for dev
    '''
    return info(dev).get('E', None)


def name(dev):
    '''
    Return the name(s?) according to udev for dev
    '''
    return info(dev).get('N', None)


def path(dev):
    '''
    Return the physical path(s?) according to udev for dev
    '''
    return info(dev).get('P', None)


def links(dev):
    '''
    Return all udev-created symlinks
    '''
    return info(dev).get('S', None)
