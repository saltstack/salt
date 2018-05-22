# -*- coding: utf-8 -*-
'''
SmartOS grain provider

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils, salt.ext.six, salt.module.cmdmod
:platform:      SmartOS

.. versionadded:: nitrogen

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import os
import re
import logging

# Import salt libs
import salt.utils.dictupdate
import salt.utils.json
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
from salt.ext.six.moves import zip

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmdmod

__virtualname__ = 'smartos'
__salt__ = {
    'cmd.run': salt.modules.cmdmod.run,
}

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load when we are on SmartOS
    '''
    if salt.utils.platform.is_smartos():
        return __virtualname__
    return False


def _smartos_computenode_data():
    '''
    Return useful information from a SmartOS compute node
    '''
    # Provides:
    #   vms_total
    #   vms_running
    #   vms_stopped
    #   vms_type
    #   sdc_version
    #   vm_capable
    #   vm_hw_virt

    grains = {}

    # collect vm data
    vms = {}
    for vm in __salt__['cmd.run']('vmadm list -p -o uuid,alias,state,type').split("\n"):
        vm = dict(list(zip(['uuid', 'alias', 'state', 'type'], vm.split(':'))))
        vms[vm['uuid']] = vm
        del vms[vm['uuid']]['uuid']

    # set vm grains
    grains['computenode_vms_total'] = len(vms)
    grains['computenode_vms_running'] = 0
    grains['computenode_vms_stopped'] = 0
    grains['computenode_vms_type'] = {'KVM': 0, 'LX': 0, 'OS': 0}
    for vm in vms:
        if vms[vm]['state'].lower() == 'running':
            grains['computenode_vms_running'] += 1
        elif vms[vm]['state'].lower() == 'stopped':
            grains['computenode_vms_stopped'] += 1

        if vms[vm]['type'] not in grains['computenode_vms_type']:
            # NOTE: be prepared for when bhyve gets its own type
            grains['computenode_vms_type'][vms[vm]['type']] = 0
        grains['computenode_vms_type'][vms[vm]['type']] += 1

    # sysinfo derived grains
    sysinfo = salt.utils.json.loads(__salt__['cmd.run']('sysinfo'))
    grains['computenode_sdc_version'] = sysinfo['SDC Version']
    grains['computenode_vm_capable'] = sysinfo['VM Capable']
    if sysinfo['VM Capable']:
        grains['computenode_vm_hw_virt'] = sysinfo['CPU Virtualization']

    # sysinfo derived smbios grains
    grains['manufacturer'] = sysinfo['Manufacturer']
    grains['productname'] = sysinfo['Product']
    grains['uuid'] = sysinfo['UUID']

    return grains


def _smartos_zone_data():
    '''
    Return useful information from a SmartOS zone
    '''
    # Provides:
    #   zoneid
    #   zonename
    #   imageversion

    grains = {
        'zoneid': __salt__['cmd.run']('zoneadm list -p | awk -F: \'{ print $1 }\'', python_shell=True),
        'zonename': __salt__['cmd.run']('zonename'),
        'imageversion': 'Unknown',
    }

    imageversion = re.compile('Image:\\s(.+)')
    if os.path.isfile('/etc/product'):
        with salt.utils.files.fopen('/etc/product', 'r') as fp_:
            for line in fp_:
                line = salt.utils.stringutils.to_unicode(line)
                match = imageversion.match(line)
                if match:
                    grains['imageversion'] = match.group(1)

    return grains


def _smartos_zone_pkgsrc_data():
    '''
    SmartOS zone pkgsrc information
    '''
    # Provides:
    #   pkgsrcversion
    #   pkgsrcpath

    grains = {
        'pkgsrcversion': 'Unknown',
        'pkgsrcpath': 'Unknown',
    }

    pkgsrcversion = re.compile('^release:\\s(.+)')
    if os.path.isfile('/etc/pkgsrc_version'):
        with salt.utils.files.fopen('/etc/pkgsrc_version', 'r') as fp_:
            for line in fp_:
                line = salt.utils.stringutils.to_unicode(line)
                match = pkgsrcversion.match(line)
                if match:
                    grains['pkgsrcversion'] = match.group(1)

    pkgsrcpath = re.compile('PKG_PATH=(.+)')
    if os.path.isfile('/opt/local/etc/pkg_install.conf'):
        with salt.utils.files.fopen('/opt/local/etc/pkg_install.conf', 'r') as fp_:
            for line in fp_:
                line = salt.utils.stringutils.to_unicode(line)
                match = pkgsrcpath.match(line)
                if match:
                    grains['pkgsrcpath'] = match.group(1)

    return grains


def _smartos_zone_pkgin_data():
    '''
    SmartOS zone pkgsrc information
    '''
    # Provides:
    #   pkgin_repositories

    grains = {
        'pkgin_repositories': [],
    }

    pkginrepo = re.compile('^(?:https|http|ftp|file)://.*$')
    if os.path.isfile('/opt/local/etc/pkgin/repositories.conf'):
        with salt.utils.files.fopen('/opt/local/etc/pkgin/repositories.conf', 'r') as fp_:
            for line in fp_:
                line = salt.utils.stringutils.to_unicode(line)
                if pkginrepo.match(line):
                    grains['pkgin_repositories'].append(line)

    return grains


def smartos():
    '''
    Provide grains for SmartOS
    '''
    grains = {}

    if salt.utils.platform.is_smartos_zone():
        grains = salt.utils.dictupdate.update(grains, _smartos_zone_data(), merge_lists=True)
        grains = salt.utils.dictupdate.update(grains, _smartos_zone_pkgsrc_data(), merge_lists=True)
        grains = salt.utils.dictupdate.update(grains, _smartos_zone_pkgin_data(), merge_lists=True)
    elif salt.utils.platform.is_smartos_globalzone():
        grains = salt.utils.dictupdate.update(grains, _smartos_computenode_data(), merge_lists=True)

    return grains


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
