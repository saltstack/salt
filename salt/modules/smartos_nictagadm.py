# -*- coding: utf-8 -*-
'''
Module for running nictagadm command on SmartOS
:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       nictagadm binary, dladm binary
:platform:      smartos

..versionadded: Boron

'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
import salt.utils
import salt.utils.decorators as decorators

log = logging.getLogger(__name__)

# Function aliases
__func_alias__ = {
    'list_nictags': 'list'
}

# Define the module's virtual name
__virtualname__ = 'nictagadm'


@decorators.memoize
def _check_nictagadm():
    '''
    Looks to see if nictagadm is present on the system
    '''
    return salt.utils.which('nictagadm')


def _check_dladm():
    '''
    Looks to see if dladm is present on the system
    '''
    return salt.utils.which('dladm')


def __virtual__():
    '''
    Provides nictagadm on SmartOS
    '''
    if salt.utils.is_smartos_globalzone() and _check_nictagadm() and _check_dladm():
        return __virtualname__
    return (
        False,
        '{0} module can only be loaded on SmartOS computed nodes'.format(
            __virtualname__
        )
    )


def list_nictags(include_etherstubs=True):
    '''
    List all nictags

    include_etherstubs : boolean
        toggle include of etherstubs

    CLI Example:

    .. code-block:: bash

        salt '*' nictagadm.list
    '''
    ret = {}
    nictagadm = _check_nictagadm()
    cmd = '{nictagadm} list -d "|" -p{estubs}'.format(
        nictagadm=nictagadm,
        estubs=' -L' if not include_etherstubs else ''
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else 'Failed to get list of nictags.'
    else:
        header = ['name', 'macaddress', 'link', 'type']
        for nictag in res['stdout'].splitlines():
            nictag = nictag.split('|')
            nictag_data = {}
            for field in header:
                nictag_data[field] = nictag[header.index(field)]
            ret[nictag_data['name']] = nictag_data
            del ret[nictag_data['name']]['name']
    return ret


def vms(nictag):
    '''
    List all vms connect to nictag

    nictag : string
        name of nictag

    CLI Example:

    .. code-block:: bash

        salt '*' nictagadm.vms admin
    '''
    ret = {}
    nictagadm = _check_nictagadm()
    cmd = '{nictagadm} vms {nictag}'.format(
        nictagadm=nictagadm,
        nictag=nictag
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else 'Failed to get list of vms.'
    else:
        ret = res['stdout'].splitlines()
    return ret


def exists(*nictag, **kwargs):
    '''
    Check if nictags exists

    nictag : string
        one or more nictags to check
    verbose : boolean
        return list of nictags

    CLI Example:

    .. code-block:: bash

        salt '*' nictagadm.exists admin
    '''
    ret = {}
    nictagadm = _check_nictagadm()
    if len(nictag) == 0:
        return {'Error': 'Please provide at least one nictag to check.'}

    cmd = '{nictagadm} exists -l {nictags}'.format(
        nictagadm=nictagadm,
        nictags=' '.join(nictag)
    )
    res = __salt__['cmd.run_all'](cmd)

    if not kwargs.get('verbose', False):
        ret = res['retcode'] == 0
    else:
        missing = res['stderr'].splitlines()
        for nt in nictag:
            ret[nt] = nt not in missing

    return ret


def add(name, mac, mtu=1500):
    '''
    Add a new nictag

    name : string
        name of new nictag
    mac : string
        mac of parent interface or 'etherstub' to create a ether stub
    mtu : int
        MTU

    CLI Example:

    .. code-block:: bash

        salt '*' nictagadm.add storage etherstub
        salt '*' nictagadm.add trunk 'DE:AD:OO:OO:BE:EF' 9000
    '''
    ret = {}
    nictagadm = _check_nictagadm()
    dladm = _check_dladm()

    if mtu > 9000 or mtu < 1500:
        return {'Error': 'mtu must be a value between 1500 and 9000.'}
    if mac != 'etherstub':
        cmd = '{dladm} show-phys -m -p -o address'.format(
            dladm=dladm
        )
        res = __salt__['cmd.run_all'](cmd)
        if mac not in res['stdout'].splitlines():
            return {'Error': '{0} is not present on this system.'.format(mac)}

    if mac == 'etherstub':
        cmd = '{nictagadm} add -l -p mtu={mtu} {name}'.format(
            nictagadm=nictagadm,
            mtu=mtu,
            name=name
        )
        res = __salt__['cmd.run_all'](cmd)
    else:
        cmd = '{nictagadm} add -p mtu={mtu},mac={mac} {name}'.format(
            nictagadm=nictagadm,
            mtu=mtu,
            mac=mac,
            name=name
        )
        res = __salt__['cmd.run_all'](cmd)

    if res['retcode'] == 0:
        return True
    else:
        return {'Error': 'failed to create nictag.' if 'stderr' not in res and res['stderr'] == '' else res['stderr']}


def update(name, mac=None, mtu=None):
    '''
    Update a nictag

    name : string
        name of nictag
    mac : string
        optional new mac for nictag
    mtu : int
        optional new MTU for nictag

    CLI Example:

    .. code-block:: bash

        salt '*' nictagadm.update trunk mtu=9000
    '''
    ret = {}
    nictagadm = _check_nictagadm()
    dladm = _check_dladm()

    if name not in list_nictags():
        return {'Error': 'nictag {0} does not exists.'.format(name)}
    if not mtu and not mac:
        return {'Error': 'please provide either mac or/and mtu.'}
    if mtu:
        if mtu > 9000 or mtu < 1500:
            return {'Error': 'mtu must be a value between 1500 and 9000.'}
    if mac:
        if mac == 'etherstub':
            return {'Error': 'cannot update a nic with "etherstub".'}
        else:
            cmd = '{dladm} show-phys -m -p -o address'.format(
                dladm=dladm
            )
            res = __salt__['cmd.run_all'](cmd)
            if mac not in res['stdout'].splitlines():
                return {'Error': '{0} is not present on this system.'.format(mac)}

    if mac and mtu:
        properties = "mtu={0},mac={1}".format(mtu, mac)
    elif mac:
        properties = "mac={0}".format(mac) if mac else ""
    elif mtu:
        properties = "mtu={0}".format(mtu) if mtu else ""

    cmd = '{nictagadm} update -p {properties} {name}'.format(
        nictagadm=nictagadm,
        properties=properties,
        name=name
    )
    res = __salt__['cmd.run_all'](cmd)

    if res['retcode'] == 0:
        return True
    else:
        return {'Error': 'failed to update nictag.' if 'stderr' not in res and res['stderr'] == '' else res['stderr']}


def delete(name, force=False):
    '''
    Delete nictag

    name : string
        nictag to delete
    force : boolean
        force delete even if vms attached

    CLI Example:

    .. code-block:: bash

        salt '*' nictagadm.exists admin
    '''
    ret = {}
    nictagadm = _check_nictagadm()

    if name not in list_nictags():
        return True

    cmd = '{nictagadm} delete {force}{name}'.format(
        nictagadm=nictagadm,
        force="-f " if force else "",
        name=name
    )
    res = __salt__['cmd.run_all'](cmd)

    if res['retcode'] == 0:
        return True
    else:
        return {'Error': 'failed to delete nictag.' if 'stderr' not in res and res['stderr'] == '' else res['stderr']}

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
