# -*- coding: utf-8 -*-
'''
    Detect SSDs (Solid State Drives)
'''

# Import python libs
import glob
import salt.utils
import logging
import os

log = logging.getLogger(__name__)


def ssds():
    '''
    Return list of disk devices that are SSD (non-rotational)
    '''
    ssd_devices = {}
    for entry in glob.glob('/sys/block/*/queue/rotational'):
        with salt.utils.fopen(entry) as entry_fp:
            device = entry.split('/')[3]
            # check, whether the device belongs to a physical device to filter out non-physical devices
            # such as device-mapper, NBD, loopback, ...
            try:
                os.stat(os.path.join('/sys/block', device, 'device'))
            except OSError:
                log.trace('Device {0} is no physical device'.format(device))
                continue
            log.trace('Device {0} is a physical device'.format(device))

            flag = entry_fp.read(1)
            if flag == '0':
                ssd_devices[device] = {}
                log.trace('Device {0} reports itself as an SSD'.format(device))
            elif flag == '1':
                log.trace('Device {0} does not report itself as an SSD'.format(device))
                continue
            else:
                log.trace('Unable to identify device {0} as an SSD or not. It does not report 0 or 1'.format(device))
                continue

            model_file = os.path.join('/sys/block', device, 'device/model')
            try:
                with salt.utils.fopen(model_file) as model_fp:
                    model = model_fp.readline().rstrip()
                    if model:
                        ssd_devices[device]['model'] = model
            except IOError:
                log.trace('Model of device {0} can not be determined'.format(device))
                pass

            revision_file = os.path.join('/sys/block', device, 'device/rev')
            try:
                with salt.utils.fopen(revision_file) as revision_fp:
                    revision = revision_fp.readline().rstrip()
                    if revision:
                        ssd_devices[device]['revision'] = revision
            except IOError:
                log.trace('Revision of device {0} can not be determined'.format(device))
                pass

            size_file = os.path.join('/sys/block', device, 'size')
            try:
                with salt.utils.fopen(size_file) as size_fp:
                    size = int(size_fp.readline().rstrip())
                    if size:
                        blocksize_file = os.path.join('/sys/block', device, 'queue/physical_block_size')
                        with salt.utils.fopen(blocksize_file) as blocksize_fp:
                            blocksize = int(blocksize_fp.readline().rstrip())
                            if blocksize:
                                ssd_devices[device]['size'] = size * blocksize
            except IOError:
                log.trace('Size of device {0} can not be determined'.format(device))
                pass

    return {'ssds': ssd_devices}
