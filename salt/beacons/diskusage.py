# -*- coding: utf-8 -*-
'''
Beacon to monitor disk usage.

.. versionadded:: 2015.5.0

:depends: python-psutil
'''

# Import Python libs
from __future__ import absolute_import
import logging
import re

# Import Third Party Libs
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

log = logging.getLogger(__name__)

__virtualname__ = 'diskusage'


def __virtual__():
    if HAS_PSUTIL is False:
        return False
    else:
        return __virtualname__


def validate(config):
    '''
    Validate the beacon configuration
    '''
    # Configuration for diskusage beacon should be a list of dicts
    if not isinstance(config, dict):
        return False, ('Configuration for diskusage beacon '
                       'must be a dictionary.')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Monitor the disk usage of the minion

    Specify thresholds for each disk and only emit a beacon if any of them are
    exceeded.

    .. code-block:: yaml

        beacons:
          diskusage:
            - /: 63%
            - /mnt/nfs: 50%

    Windows drives must be quoted to avoid yaml syntax errors

    .. code-block:: yaml

        beacons:
          diskusage:
            -  interval: 120
            - 'c:\': 90%
            - 'd:\': 50%

    '''
    ret = []
    for diskusage in config:
        mount = diskusage.keys()[0]

        try:
            _current_usage = psutil.disk_usage(mount)
        except OSError:
            # Ensure a valid mount point
            log.error('{0} is not a valid mount point, skipping.'.format(mount))
            continue

        current_usage = _current_usage.percent
        monitor_usage = diskusage[mount]
        if '%' in monitor_usage:
            monitor_usage = re.sub('%', '', monitor_usage)
        monitor_usage = float(monitor_usage)
        if current_usage >= monitor_usage:
            ret.append({'diskusage': current_usage, 'mount': mount})
    return ret
