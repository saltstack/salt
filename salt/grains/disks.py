# -*- coding: utf-8 -*-
'''
    Detect disks
'''
from __future__ import absolute_import

# Import python libs
import glob
import logging
import re

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmdmod

__salt__ = {
    'cmd.run': salt.modules.cmdmod._run_quiet
}

log = logging.getLogger(__name__)


def disks():
    '''
    Return list of disk devices
    '''
    if salt.utils.is_freebsd():
        return _freebsd_disks()
    elif salt.utils.is_linux():
        return _linux_disks()
    else:
        log.trace('Disk grain does not support OS')


def _clean_keys(key):
    key = key.replace(' ', '_')
    key = key.replace('(', '')
    key = key.replace(')', '')
    return key


class _camconsts(object):
    PROTOCOL = 'protocol'
    DEVICE_MODEL = 'device model'
    FIRMWARE_REVISION = 'firmware revision'
    SERIAL_NUMBER = 'serial number'
    WWN = 'WWN'
    SECTOR_SIZE = 'sector size'
    MEDIA_RPM = 'media RPM'

_identify_attribs = [_camconsts.__dict__[key] for key in
                     _camconsts.__dict__ if not key.startswith('__')]


@decorators.memoize
def _freebsd_vbox():
    # Don't tickle VirtualBox storage emulation bugs
    camcontrol = salt.utils.which('camcontrol')
    devlist = __salt__['cmd.run']('{0} devlist'.format(camcontrol))
    if 'VBOX' in devlist:
        return True
    return False


def _freebsd_disks():
    ret = {'disks': {}, 'SSDs': []}
    sysctl = salt.utils.which('sysctl')
    devices = __salt__['cmd.run']('{0} -n kern.disks'.format(sysctl))
    SSD_TOKEN = 'non-rotating'

    for device in devices.split(' '):
        if device.startswith('cd'):
            log.debug('Disk grain skipping cd')
        elif _freebsd_vbox():
            log.debug('Disk grain skipping CAM identify/inquirty on VBOX')
            ret['disks'][device] = {}
        else:
            cam = _freebsd_camcontrol(device)
            ret['disks'][device] = cam
            if cam.get(_clean_keys(_camconsts.MEDIA_RPM)) == SSD_TOKEN:
                ret['SSDs'].append(device)

    return ret


def _freebsd_camcontrol(device):
    camcontrol = salt.utils.which('camcontrol')
    ret = {}

    def parse_identify_attribs(line):
        for attrib in _identify_attribs:
            search = re.search(r'^{0}\s+(.*)'.format(attrib), line)
            if search:
                ret[_clean_keys(attrib)] = search.group(1)

    identify = __salt__['cmd.run']('{0} identify {1}'.format(camcontrol,
                                                             device))
    for line in identify.splitlines():
        parse_identify_attribs(line)

    def parse_inquiry(inquiry):
        if not ret.get(_clean_keys(_camconsts.DEVICE_MODEL)):
            model = re.search(r'\s<(.+?)>', inquiry)
            if model:
                ret[_clean_keys(_camconsts.DEVICE_MODEL)] = model.group(1)
        if not ret.get(_clean_keys(_camconsts.SERIAL_NUMBER)):
            sn = re.search(r'\sSerial Number\s+(\w+)\s', inquiry)
            if sn:
                ret[_clean_keys(_camconsts.SERIAL_NUMBER)] = sn.group(1)

    inquiry = __salt__['cmd.run']('{0} inquiry {1}'.format(camcontrol, device))
    parse_inquiry(inquiry)

    return ret


def _linux_disks():
    '''
    Return list of disk devices and work out if they are SSD or HDD.
    '''
    ret = {'disks': [], 'SSDs': []}

    for entry in glob.glob('/sys/block/*/queue/rotational'):
        with salt.utils.fopen(entry) as entry_fp:
            device = entry.split('/')[3]
            flag = entry_fp.read(1)
            if flag == '0':
                ret['SSDs'].append(device)
                log.trace('Device {0} reports itself as an SSD'.format(device))
            elif flag == '1':
                ret['disks'].append(device)
                log.trace('Device {0} reports itself as an HDD'.format(device))
            else:
                log.trace('Unable to identify device {0} as an SSD or HDD.'
                          ' It does not report 0 or 1'.format(device))
    return ret
