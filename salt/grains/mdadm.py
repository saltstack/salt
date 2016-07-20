# -*- coding: utf-8 -*-
'''
Detect MDADM RAIDs
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def mdadm():
    '''
    Return list of mdadm devices
    '''
    devices = set()
    try:
        with salt.utils.fopen('/proc/mdstat', 'r') as mdstat:
            for line in mdstat:
                if line.startswith('Personalities : '):
                    continue
                if line.startswith('unused devices:'):
                    continue
                if ' : ' in line:
                    devices.add(line.split(' : ')[0])
    except IOError:
        return {}

    devices = sorted(devices)
    if devices:
        log.trace(
            'mdadm devices detected: {0}'.format(', '.join(devices))
        )

    return {'mdadm': devices}
