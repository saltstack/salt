# -*- coding: utf-8 -*-
'''
Beacon to monitor memory usage.

.. versionadded:: 2016.3.0

:depends: python-psutil
'''

# Import Python libs
from __future__ import absolute_import
import logging
import re

# Import Salt libs
import salt.utils

# Import Third Party Libs
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

log = logging.getLogger(__name__)

__virtualname__ = 'memusage'


def __virtual__():
    if salt.utils.is_windows():
        return False
    elif HAS_PSUTIL is False:
        return False
    else:
        return __virtualname__


def validate(config):
    '''
    Validate the beacon configuration
    '''
    # Configuration for diskusage beacon should be a list of dicts
    if not isinstance(config, dict):
        log.info('Configuration for diskusage beacon must be a dictionary.')
        return False
    return True


def beacon(config):
    '''
    Monitor the memory usage of the minion

    Specify thresholds for percent used and only emit a beacon if it is exceeded.

    .. code-block:: yaml

        beacons:
          memusage:
            - percent: 63%
    '''
    ret = []
    for memusage in config:
        mount = memusage.keys()[0]
        _current_usage = psutil.virtual_memory()

        current_usage = _current_usage.percent
        monitor_usage = memusage[mount]
        if '%' in monitor_usage:
            monitor_usage = re.sub('%', '', monitor_usage)
        monitor_usage = float(monitor_usage)
        if current_usage >= monitor_usage:
            ret.append({'memusage': current_usage})
    return ret
