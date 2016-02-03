# -*- coding: utf-8 -*-
'''
Module for running nictagadm command on SmartOS
'''
from __future__ import absolute_import

# Import Python libs
import logging
import json
import os
try:
    from shlex import quote as _quote_args  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _quote_args

# Import Salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.utils.odict import OrderedDict

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


def __virtual__():
    '''
    Provides nictagadm on SmartOS
    '''
    if salt.utils.is_smartos_globalzone() and _check_nictagadm():
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

    if mtu > 9000 or mtu < 1500:
        return {'Error': 'mtu must be a value between 1500 and 9000.'}
    if mac != 'etherstub':
        ## we do not check for dladm, we always have it if we have nictagadm
        cmd = '{dladm} show-phys -m -p -o address'.format(
            dladm=salt.utils.which('dladm')
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
        cmd = '{nictagadm} add -p mtu={mtu} -p mac={mac} {name}'.format(
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

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
