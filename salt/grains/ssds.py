# -*- coding: utf-8 -*-
'''
    Detect SSDs
'''
from __future__ import absolute_import

# Import python libs
import glob
import salt.utils
import logging

# Import salt libs
import salt.utils

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmdmod

__salt__ = {
    'cmd.run': salt.modules.cmdmod._run_quiet
}

log = logging.getLogger(__name__)


def ssds():
    '''
    Return list of disk devices that are SSD (non-rotational)
    '''
    ssds = []

    if salt.utils.is_linux():
        ssds = _linux_ssds()
    elif salt.utils.is_freebsd():
        ssds = _freebsd_ssds()
    else:
        log.trace('SSD grain does not support OS')

    return {'SSDs': ssds}


def _freebsd_ssds():
    '''
    Return a list of disk devices that ATA identify as SSDs (non-rotating)
    '''
    ssd_devices = []

    SSD_TOKEN = 'non-rotating'
    sysctl = salt.utils.which('sysctl')
    camcontrol = salt.utils.which('camcontrol')

    devices = __salt__['cmd.run']('{0} kern.disks'.format(sysctl))
    for device in devices.split(' ')[1:]:
        identify = __salt__['cmd.run']('{0} identify {1}'.format(camcontrol,
                                       device))
        if SSD_TOKEN in identify:
            log.trace('Device {0} reports itself as an SSD'.format(device))
            ssd_devices.append(device)
        else:
            log.trace('Device {0} does not report itself as an SSD'.format(
                      device))

    return ssd_devices


def _linux_ssds():
    '''
    Return list of disk devices that are SSD (non-rotational)
    '''
    ssd_devices = []

    for entry in glob.glob('/sys/block/*/queue/rotational'):
        with salt.utils.fopen(entry) as entry_fp:
            device = entry.split('/')[3]
            flag = entry_fp.read(1)
            if flag == '0':
                ssd_devices.append(device)
                log.trace('Device {0} reports itself as an SSD'.format(device))
            elif flag == '1':
                log.trace('Device {0} does not report itself as an SSD'
                          .format(device))
            else:
                log.trace('Unable to identify device {0} as an SSD or not.'
                          ' It does not report 0 or 1'.format(device))
    return ssd_devices
