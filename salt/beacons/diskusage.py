# -*- coding: utf-8 -*-
'''
Beacon to monitor disk usage.

.. versionadded:: 2015.5.0

:depends: python-psutil
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals
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
    if not isinstance(config, list):
        return False, ('Configuration for diskusage beacon '
                       'must be a list.')
    return True, 'Valid beacon configuration'


def beacon(config):
    r'''
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

    Regular expressions can be used as mount points.

    .. code-block:: yaml

        beacons:
          diskusage:
            - '^\/(?!home).*$': 90%
            - '^[a-zA-Z]:\$': 50%

    The first one will match all mounted disks beginning with "/", except /home
    The second one will match disks from A:\ to Z:\ on a Windows system

    Note that if a regular expression are evaluated after static mount points,
    which means that if a regular expression matches an other defined mount point,
    it will override the previously defined threshold.

    '''
    parts = psutil.disk_partitions(all=False)
    ret = []
    for mounts in config:
        mount = next(iter(mounts))

        for part in parts:
            if re.match(mount, part.mountpoint):
                _mount = part.mountpoint

                try:
                    _current_usage = psutil.disk_usage(mount)
                except OSError:
                    log.warning('%s is not a valid mount point.', mount)
                    continue

                current_usage = _current_usage.percent
                monitor_usage = mounts[mount]
                log.info('current_usage %s', current_usage)
                if '%' in monitor_usage:
                    monitor_usage = re.sub('%', '', monitor_usage)
                monitor_usage = float(monitor_usage)
                if current_usage >= monitor_usage:
                    ret.append({'diskusage': current_usage, 'mount': _mount})
    return ret
