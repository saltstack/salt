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
#info <uuid> [type,...]
#receive [-f <filename>]
#reprovision [-f <filename>]
#rollback-snapshot <uuid> <snapname>
#send <uuid> [target]
#update <uuid> [-f <filename>]
# -or- update <uuid> property=value [property=value ...]
#validate create [-f <filename>]
#validate update <brand> [-f <filename>]


def start(vm=None, options=None, key='uuid'):
    '''
    Start a vm

    vm : string
        Specifies the vm to be started
    options : string
        Specifies additional options
    key : string
        Specifies if 'vm' is a uuid, alias or hostname.

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.start 186da9ab-7392-4f55-91a5-b8f1fe770543
        salt '*' vmadm.start 186da9ab-7392-4f55-91a5-b8f1fe770543 'order=c,once=d cdrom=/path/to/image.iso,ide'
        salt '*' vmadm.start vm=nacl key=alias
        salt '*' vmadm.start vm=nina.example.org key=hostname
    '''
    ret = {}
    vmadm = _check_vmadm()
    if vm is None:
        ret['Error'] = 'uuid, alias or hostname must be provided'
        return ret
    if key not in ['uuid', 'alias', 'hostname']:
        ret['Error'] = 'Key must be either uuid, alias or hostname'
        return ret
    vm = lookup('{0}={1}'.format(key, vm), one=True)
    if 'Error' in vm:
        return vm
    # vmadm start <uuid> [option=value ...]
    cmd = '{vmadm} start {uuid} {options}'.format(
        vmadm=vmadm,
        uuid=vm,
        options=options if options else ''
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else _exit_status(retcode)
        return ret
    return True


def stop(vm=None, force=False, key='uuid'):
    '''
    Stop a vm

    vm : string
        Specifies the vm to be stopped
    force : boolean
        Specifies if the vm should be force stopped
    key : string
        Specifies if 'vm' is a uuid, alias or hostname.

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.stop 186da9ab-7392-4f55-91a5-b8f1fe770543
        salt '*' vmadm.stop 186da9ab-7392-4f55-91a5-b8f1fe770543 True
        salt '*' vmadm.stop vm=nacl key=alias
        salt '*' vmadm.stop vm=nina.example.org key=hostname
    '''
    ret = {}
    vmadm = _check_vmadm()
    if vm is None:
        ret['Error'] = 'uuid, alias or hostname must be provided'
        return ret
    if key not in ['uuid', 'alias', 'hostname']:
        ret['Error'] = 'Key must be either uuid, alias or hostname'
        return ret
    vm = lookup('{0}={1}'.format(key, vm), one=True)
    if 'Error' in vm:
        return vm
    # vmadm stop <uuid> [-F]
    cmd = '{vmadm} stop {force} {uuid}'.format(
        vmadm=vmadm,
        force='-F' if force else '',
        uuid=vm
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = _exit_status(retcode)
        return ret
    return True


def reboot(vm=None, force=False, key='uuid'):
    '''
    Reboot a vm

    vm : string
        Specifies the vm to be rebooted
    force : boolean
        Specifies if the vm should be force rebooted
    key : string
        Specifies if 'vm' is a uuid, alias or hostname.

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.reboot 186da9ab-7392-4f55-91a5-b8f1fe770543
        salt '*' vmadm.reboot 186da9ab-7392-4f55-91a5-b8f1fe770543 True
        salt '*' vmadm.reboot vm=nacl key=alias
        salt '*' vmadm.reboot vm=nina.example.org key=hostname
    '''
    ret = {}
    vmadm = _check_vmadm()
    if vm is None:
        ret['Error'] = 'uuid, alias or hostname must be provided'
        return ret
    if key not in ['uuid', 'alias', 'hostname']:
        ret['Error'] = 'Key must be either uuid, alias or hostname'
        return ret
    vm = lookup('{0}={1}'.format(key, vm), one=True)
    if 'Error' in vm:
        return vm
    # vmadm reboot <uuid> [-F]
    cmd = '{vmadm} reboot {force} {uuid}'.format(
        vmadm=vmadm,
        force='-F' if force else '',
        uuid=vm
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else _exit_status(retcode)
        return ret
    return True


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
        ret['Error'] = res['stderr'] if 'stderr' in res else _exit_status(retcode)
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
        Specifies if you to one result only (-1)

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.lookup search='state=running'
        salt '*' vmadm.lookup search='state=running' order=uuid,alias,hostname
        salt '*' vmadm.lookup search='alias=nacl' one=True
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
        ret['Error'] = res['stderr'] if 'stderr' in res else _exit_status(retcode)
        return ret

    if one:
        result = res['stdout']
    else:
        for vm in json.loads(res['stdout']):
            result.append(vm)

    return result


def sysrq(vm=None, action='nmi', key='uuid'):
    '''
    Send non-maskable interupt to vm or capture a screenshot

    vm : string
        Specifies the vm
    action : string
        Specifies the action nmi or screenshot
    key : string
        Specifies what 'vm' is. Value = uuid|alias|hostname

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.sysrq 186da9ab-7392-4f55-91a5-b8f1fe770543 nmi
        salt '*' vmadm.sysrq 186da9ab-7392-4f55-91a5-b8f1fe770543 screenshot
        salt '*' vmadm.sysrq nacl nmi key=alias
    '''
    ret = {}
    vmadm = _check_vmadm()
    if vm is None:
        ret['Error'] = 'uuid, alias or hostname must be provided'
        return ret
    if key not in ['uuid', 'alias', 'hostname']:
        ret['Error'] = 'Key must be either uuid, alias or hostname'
        return ret
    if action not in ['nmi', 'screenshot']:
        ret['Error'] = 'Action must be either nmi or screenshot'
        return ret
    vm = lookup('{0}={1}'.format(key, vm), one=True)
    if 'Error' in vm:
        return vm
    # vmadm sysrq <uuid> <nmi|screenshot>
    cmd = '{vmadm} sysrq {uuid} {action}'.format(
        vmadm=vmadm,
        uuid=vm,
        action=action
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else _exit_status(retcode)
        return ret
    return True


def delete(vm=None, key='uuid'):
    '''
    Delete a vm

    vm : string
        Specifies the vm
    key : string
        Specifies what 'vm' is. Value = uuid|alias|hostname

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.delete 186da9ab-7392-4f55-91a5-b8f1fe770543
        salt '*' vmadm.delete nacl key=alias
    '''
    ret = {}
    vmadm = _check_vmadm()
    if vm is None:
        ret['Error'] = 'uuid, alias or hostname must be provided'
        return ret
    if key not in ['uuid', 'alias', 'hostname']:
        ret['Error'] = 'Key must be either uuid, alias or hostname'
        return ret
    vm = lookup('{0}={1}'.format(key, vm), one=True)
    if 'Error' in vm:
        return vm
    # vmadm delete <uuid>
    cmd = '{vmadm} delete {uuid}'.format(
        vmadm=vmadm,
        uuid=vm
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else _exit_status(retcode)
        return ret
    return True


def get(vm=None, key='uuid'):
    '''
    Output the JSON object describing a VM

    vm : string
        Specifies the vm
    key : string
        Specifies what 'vm' is. Value = uuid|alias|hostname

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.get 186da9ab-7392-4f55-91a5-b8f1fe770543
        salt '*' vmadm.get nacl key=alias
    '''
    ret = {}
    vmadm = _check_vmadm()
    if vm is None:
        ret['Error'] = 'uuid, alias or hostname must be provided'
        return ret
    if key not in ['uuid', 'alias', 'hostname']:
        ret['Error'] = 'Key must be either uuid, alias or hostname'
        return ret
    vm = lookup('{0}={1}'.format(key, vm), one=True)
    if 'Error' in vm:
        return vm
    # vmadm get <uuid>
    cmd = '{vmadm} get {uuid}'.format(
        vmadm=vmadm,
        uuid=vm
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else _exit_status(retcode)
        return ret
    return json.loads(res['stdout'])


def create_snapshot(vm=None, name=None, key='uuid'):
    '''
    Create snapshot of a vm

    vm : string
        Specifies the vm
    name : string
        Name of snapshot.
        The snapname must be 64 characters or less
        and must only contain alphanumeric characters and
        characters in the set [-_.:%] to comply with ZFS restrictions.

    key : string
        Specifies what 'vm' is. Value = uuid|alias|hostname

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.create_snapshot 186da9ab-7392-4f55-91a5-b8f1fe770543 baseline
        salt '*' vmadm.create_snapshot nacl baseline key=alias
    '''
    ret = {}
    vmadm = _check_vmadm()
    if vm is None:
        ret['Error'] = 'uuid, alias or hostname must be provided'
        return ret
    if name is None:
        ret['Error'] = 'Snapshot name most be specified'
        return ret
    if key not in ['uuid', 'alias', 'hostname']:
        ret['Error'] = 'Key must be either uuid, alias or hostname'
        return ret
    vm = lookup('{0}={1}'.format(key, vm), one=True)
    if 'Error' in vm:
        return vm
    vmobj = get(vm)
    if 'datasets' in vmobj:
        ret['Error'] = 'VM cannot have datasets'
        return ret
    if vmobj['brand'] in ['kvm']:
        ret['Error'] = 'VM must be of type OS'
        return ret
    if vmobj['zone_state'] not in ['running']: # work around a vmadm bug
        ret['Error'] = 'VM must be running to take a snapshot'
        return ret
    # vmadm create-snapshot <uuid> <snapname>
    cmd = '{vmadm} create-snapshot {uuid} {snapshot}'.format(
        vmadm=vmadm,
        snapshot=name,
        uuid=vm
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else _exit_status(retcode)
        return ret
    return True


def delete_snapshot(vm=None, name=None, key='uuid'):
    '''
    Delete snapshot of a vm

    vm : string
        Specifies the vm
    name : string
        Name of snapshot.
        The snapname must be 64 characters or less
        and must only contain alphanumeric characters and
        characters in the set [-_.:%] to comply with ZFS restrictions.

    key : string
        Specifies what 'vm' is. Value = uuid|alias|hostname

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.delete_snapshot 186da9ab-7392-4f55-91a5-b8f1fe770543 baseline
        salt '*' vmadm.delete_snapshot nacl baseline key=alias
    '''
    ret = {}
    vmadm = _check_vmadm()
    if vm is None:
        ret['Error'] = 'uuid, alias or hostname must be provided'
        return ret
    if name is None:
        ret['Error'] = 'Snapshot name most be specified'
        return ret
    if key not in ['uuid', 'alias', 'hostname']:
        ret['Error'] = 'Key must be either uuid, alias or hostname'
        return ret
    vm = lookup('{0}={1}'.format(key, vm), one=True)
    if 'Error' in vm:
        return vm
    vmobj = get(vm)
    if 'datasets' in vmobj:
        ret['Error'] = 'VM cannot have datasets'
        return ret
    if vmobj['brand'] in ['kvm']:
        ret['Error'] = 'VM must be of type OS'
        return ret
    if vmobj[''] in ['zone_state']:
        ret['Error'] = 'VM must be of type OS'
        return ret
    # vmadm delete-snapshot <uuid> <snapname>
    cmd = '{vmadm} delete-snapshot {uuid} {snapshot}'.format(
        vmadm=vmadm,
        snapshot=name,
        uuid=vm
    )
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        ret['Error'] = res['stderr'] if 'stderr' in res else _exit_status(retcode)
        return ret
    return True

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
