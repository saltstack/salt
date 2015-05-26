# -*- coding: utf-8 -*-
'''
Beacon to monitor disk usage.

.. versionadded:: 2015.5.0
'''

# Import Python libs
from __future__ import absolute_import
import logging
import psutil
import re

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)

__virtualname__ = 'diskusage'


def __virtual__():
    if salt.utils.is_windows():
        return False
    else:
        return __virtualname__


def beacon(config):
    '''
    Monitor the disk usage of the minion

    Specify thresholds for each disk and only emit a beacon if any of them are
    exceeded.

    code_block:: yaml

        beacons:
          diskusage:
            - /: 63%
            - /mnt/nfs: 50%
    '''
    ret = []
    for diskusage in config:
        mount = diskusage.keys()[0]

        try:
            _current_usage = psutil.disk_usage(mount)
        except OSError:
            # Ensure a valid mount point
            log.error('{0} is not a valid mount point, skipping.'.format(mount))

        current_usage = _current_usage.percent
        monitor_usage = diskusage[mount]
        if '%' in monitor_usage:
            monitor_usage = re.sub('%', '', monitor_usage)
        monitor_usage = float(monitor_usage)
        if current_usage >= monitor_usage:
            ret.append({'diskusage': current_usage, 'mount': mount})
    return ret
