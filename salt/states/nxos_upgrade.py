# -*- coding: utf-8 -*-
'''
Manage NX-OS System Image Upgrades.

.. versionadded: xxxx.xx.x

For documentation on setting up the nxos proxy minion look in the documentation
for :mod:`salt.proxy.nxos<salt.proxy.nxos>`.
'''
from __future__ import absolute_import, print_function, unicode_literals
import re
import logging


import sys
import pdb


class ForkedPdb(pdb.Pdb):
    """A Pdb subclass that may be used from a forked multiprocessing child
    Use this subclass to set a pdb tracepoint for debugging purposes.
    Usage:
        ForkedPdb().set_trace()
    """
    def interaction(self, *args, **kwargs):
        _stdin = sys.stdin
        try:
            sys.stdin = open('/dev/stdin')
            pdb.Pdb.interaction(self, *args, **kwargs)
        finally:
            sys.stdin = _stdin


__virtualname__ = 'nxos'
__virtual_aliases__ = ('nxos_upgrade',)

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def _parse_upgrade_data(data):
    '''
    Helper method to parse upgrade data returned by __salt__['nxos']('upgrade')
    function.
    '''
    upgrade_result = {}
    upgrade_result['succeeded'] = False
    upgrade_result['upgrade_required'] = False
    upgrade_result['installing'] = False
    upgrade_result['running_version'] = None
    upgrade_result['new_version'] = None
    upgrade_result['module_data'] = {}
    upgrade_result['error_data'] = ''

    # ForkedPdb().set_trace()
    if 'code' in data and data['code'] == '400':
        upgrade_result['error_data'] = data['cli_error']
        return upgrade_result

    if isinstance(data, list) and len(data) == 2:
        data = data[1]

    log.info('Parsing NX-OS upgrade data')
    for line in data.split('\n'):

        log.info('Processing line: ({})'.format(line))

        # Example:
        # Module  Image  Running-Version(pri:alt)  New-Version  Upg-Required
        # 1       nxos   7.0(3)I7(5a)              7.0(3)I7(5a)        no
        # 1       bios   v07.65(09/04/2018)        v07.64(05/16/2018)  no
        mo = re.search(r'(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(yes|no)', line)
        if mo:
            log.info('Matched Module Running/New Version Upg-Req Line')
            bk = 'module_data'  # base key
            g1 = mo.group(1)
            g2 = mo.group(2)
            g3 = mo.group(3)
            g4 = mo.group(4)
            g5 = mo.group(5)
            mk = 'module {0}:image {1}'.format(g1, g2)  # module key
            upgrade_result[bk][mk] = {}
            upgrade_result[bk][mk]['running_version'] = g3
            upgrade_result[bk][mk]['new_version'] = g4
            if g5 == 'yes':
                upgrade_result['upgrade_required'] = True
                upgrade_result[bk][mk]['upgrade_required'] = True
            continue

        # The following lines indicate a successfull upgrade.
        if re.search(r'Install has been successful', line):
            log.info('Install successful line')
            upgrade_result['succeeded'] = True
            continue

        if re.search(r'Finishing the upgrade, switch will reboot in', line):
            log.info('Finishing upgrade line')
            upgrade_result['succeeded'] = True
            continue

        if re.search(r'Switch will be reloaded for disruptive upgrade', line):
            log.info('Switch will be reloaded line')
            upgrade_result['succeeded'] = True
            continue

    return upgrade_result


def image_running(name, system_image, kickstart_image=None, issu=True, **kwargs):
    '''
    Ensure the NX-OS system image is running on the device.

    name
        Name of the salt state task

    system_image
        Name of the system image file on bootflash:

    kickstart_image
        Name of the kickstart image file on bootflash:
        This is not needed if the system_image is a combined system and
        kickstart image
        Default: None

    issu
        Ensure the correct system is running on the device using an in service
        software upgrade, or force a disruptive upgrade by setting the option
        to False.
        Default: False
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    if kickstart_image is None:
        upgrade_data = __salt__['nxos.upgrade'](system_image=system_image,
                                                issu=issu, **kwargs)
    else:
        upgrade_data = __salt__['nxos.upgrade'](system_image=system_image,
                                                kickstart_image=kickstart_image,
                                                issu=issu, **kwargs)
    # upgrade_data = _mock_data()

    upgrade_result = _parse_upgrade_data(upgrade_data)

    ret['result'] = upgrade_result['succeeded']
    if upgrade_result['succeeded']:
        if upgrade_result['upgrade_required']:
            ret['changes'] = upgrade_result['module_data']
            ret['comment'] = 'NX-OS Device Now Being Upgraded - See Change Details Below'
        else:
            ret['comment'] = 'NX-OS Device Running Image: {}'.format(_version_info())
    else:
        ret['comment'] = 'Upgrade Failed: {}.'.format(upgrade_result['error_data'])

    return ret


def _version_info():
    '''
    Helper method to return running image version
    '''
    return __grains__['nxos']['software']['NXOS']


def _mock_data():
    data = u'''
    Installer will perform compatibility check first. Please wait.
    Installer is forced disruptive

    Verifying image bootflash:/nxos.7.0.3.I7.5a.bin for boot variable "nxos".
    [####################] 100% -- SUCCESS

    Verifying image type.
    [####################] 100% -- SUCCESS

    Preparing "nxos" version info using image bootflash:/nxos.7.0.3.I7.5a.bin.
    [####################] 100% -- SUCCESS

    Preparing "bios" version info using image bootflash:/nxos.7.0.3.I7.5a.bin.
    [####################] 100% -- SUCCESS

    Performing module support checks.
    [####################] 100% -- SUCCESS

    Notifying services about system upgrade.
    [####################] 100% -- SUCCESS



    Compatibility check is done:
    Module  bootable          Impact  Install-type  Reason
    ------  --------  --------------  ------------  ------
         1       yes  non-disruptive          none



    Images will be upgraded according to following table:
    Module       Image                  Running-Version(pri:alt)           New-Version  Upg-Required
    ------  ----------  ----------------------------------------  --------------------  ------------
         1        nxos                              7.0(3)I7(5a)          7.0(3)I7(5a)            no
         1        bios     v07.65(09/04/2018):v07.06(03/02/2014)    v07.64(05/16/2018)            no


    Do you want to continue with the installation (y/n)?  [n] y


    Install is in progress, please wait.

    Performing runtime checks.
    [####################] 100% -- SUCCESS

    Setting boot variables.
    [####################] 100% -- SUCCESS

    Performing configuration copy.
    [####################] 100% -- SUCCESS

    Module 1: Refreshing compact flash and upgrading bios/loader/bootrom.
    Warning: please do not remove or power off the module at this time.
    [####################] 100% -- SUCCESS


    Install has been successful.
'''
    return data
