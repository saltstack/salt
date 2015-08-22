# -*- coding: utf-8 -*-
'''
Module for running vmadm command on SmartOS
'''
from __future__ import absolute_import

# Import Python libs
import logging
import json

# Import Salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

# Function aliases
__func_alias__ = {
    'list_vms': 'list'
}

# Define the module's virtual name
__virtualname__ = 'vmadm'


@decorators.memoize
def _check_vmadm():
    '''
    Looks to see if vmadm is present on the system
    '''
    return salt.utils.which('vmadm')


def __virtual__():
    '''
    Provides vmadm on SmartOS
    '''
    if salt.utils.is_smartos_globalzone() and _check_vmadm():
        return __virtualname__
    return False


def _exit_status(retcode):
    '''
    Translate exit status of vmadm
    '''
    ret = {0: 'Successful completion.',
           1: 'An error occurred.',
           2: 'Usage error.'}[retcode]
    return ret

## TODO
#create [-f <filename>]
#create-snapshot <uuid> <snapname>
#console <uuid>
#delete <uuid>
#delete-snapshot <uuid> <snapname>
#get <uuid>
#info <uuid> [type,...]
#install <uuid>
#kill [-s SIGNAL|-SIGNAL] <uuid>
#reboot <uuid> [-F]
#receive [-f <filename>]
#reprovision [-f <filename>]
#rollback-snapshot <uuid> <snapname>
#send <uuid> [target]
#start <uuid> [option=value ...]
#sysrq <uuid> <nmi|screenshot>
#update <uuid> [-f <filename>]
# -or- update <uuid> property=value [property=value ...]
#validate create [-f <filename>]
#validate update <brand> [-f <filename>]

# vmadm stop <uuid> [-F]


def list_vms(search=None, sort=None, order='uuid,type,ram,state,alias', keyed=False):
    '''
    Return a list of VMs

    search : string
        Specifies the vmadm filter property
    sort : string
        Specifies the vmadm sort (-s) property
    order : string
        Specifies the vmadm order (-o) property
        Default: uuid,type,ram,state,alias
    keyed : boolean
        Specified if the output should be an array (False) or dict (True)
          Dict key is first field from order parameter
          Note: if key is not unique last vm wins.

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.list
        salt '*' vmadm.list order=alias,ram,cpu_cap sort=-ram,-cpu_cap
        salt '*' vmadm.list search='type=KVM'
    '''
    ret = {}
    vmadm = _check_vmadm()
    # vmadm list [-p] [-H] [-o field,...] [-s field,...] [field=value ...]
    cmd = '{vmadm} list -p -H {order} {sort} {search}'.format(
        vmadm=vmadm,
        order='-o {0}'.format(order) if order else '',
        sort='-s {0}'.format(sort) if sort else '',
        search=search if search else ''
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    result = OrderedDict() if keyed else []
    if retcode != 0:
        if 'stderr' not in res:
            ret['Error'] = _exit_status(retcode)
        else:
            ret['Error'] = res['stderr']
        return ret

    fields = order.split(',')

    for vm in res['stdout'].splitlines():
        vm_data = OrderedDict()
        vm = vm.split(':')
        if keyed:
            for field in fields:
                if fields.index(field) == 0:
                    continue
                vm_data[field.strip()] = vm[fields.index(field)].strip()
            result[vm[0]] = vm_data
        else:
            if len(vm) > 1:
                for field in fields:
                    vm_data[field.strip()] = vm[fields.index(field)].strip()
            else:
                vm_data = vm[0]
            result.append(vm_data)
    return result


def lookup(search=None, order=None, one=False):
    '''
    Return a list of VMs using lookup

    search : string
        Specifies the vmadm filter property
    order : string
        Specifies the vmadm order (-o) property
        Default: uuid,type,ram,state,alias
    one : boolean
        Specifies if you to one result only (-j)

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.lookup search='state=running'
        salt '*' vmadm.lookup search='state=running' orde=uuid,alias,hostname
    '''
    ret = {}
    vmadm = _check_vmadm()
    # vmadm lookup [-j|-1] [-o field,...] [field=value ...]
    cmd = '{vmadm} lookup {one} {order} {search}'.format(
        vmadm=vmadm,
        one='-1' if one else '-j',
        order='-o {0}'.format(order) if order else '',
        search=search if search else ''
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    result = []
    if retcode != 0:
        if 'stderr' not in res:
            ret['Error'] = _exit_status(retcode)
        else:
            ret['Error'] = res['stderr']
        return ret

    if one:
        result = res['stdout']
    else:
        for vm in json.loads(res['stdout']):
            result.append(vm)

    return result

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
