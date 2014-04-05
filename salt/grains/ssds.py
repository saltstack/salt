# -*- coding: utf-8 -*-
'''
    Detect SSDs
'''

# Import python libs
import glob
import salt.utils
import logging

log = logging.getLogger(__name__)


def ssds():
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
                log.trace('Device {0} does not report itself as an SSD'.format(device))
            else:
                log.trace('Unable to identify device {0} as an SSD or not. It does not report 0 or 1'.format(device))
    return {'SSDs': ssd_devices}
