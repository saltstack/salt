# -*- coding: utf-8 -*-
'''
Module for managing VMs on SmartOS
'''
from __future__ import absolute_import

# Import Python libs
import json

# Import Salt libs
from salt.exceptions import CommandExecutionError
import salt.utils
import salt.utils.decorators as decorators
import salt.ext.six as six
try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote


# Define the module's virtual name
__virtualname__ = 'virt'


@decorators.memoize
def _check_vmadm():
    '''
    Looks to see if vmadm is present on the system
    '''
    return salt.utils.which('vmadm')


def _check_dladm():
    '''
    Looks to see if dladm is present on the system
    '''
    return salt.utils.which('dladm')


def __virtual__():
    '''
    Provides virt on SmartOS
    '''
    if __grains__['os'] == "SmartOS" and _check_vmadm():
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


def _gen_zone_json(**kwargs):
    '''
    Generate the JSON for OS virtualization creation

    Example layout (all keys are mandatory) :

       {"brand": "joyent",
        "image_uuid": "9eac5c0c-a941-11e2-a7dc-57a6b041988f",
        "alias": "myname",
        "hostname": "www.domain.com",
        "max_physical_memory": 2048,
        "quota": 10,
        "nics": [
            {
                "nic_tag": "admin",
                "ip": "192.168.0.1",
                "netmask": "255.255.255.0",
                "gateway": "192.168.0.254"
            }
        ]}
    '''
    ret = {}
    nics = {}
    check_args = (
        'image_uuid', 'alias', 'hostname',
        'max_physical_memory', 'quota', 'nic_tag',
        'ip', 'netmask', 'gateway')
    nics_args = ('nic_tag', 'ip', 'netmask', 'gateway')
    # Lazy check of arguments
    if not all(key in kwargs for key in check_args):
        raise CommandExecutionError('Missing arguments for JSON generation')
    # This one is mandatory for OS virt
    ret.update(brand='joyent')
    # Populate JSON without NIC information
    ret.update((key, kwargs[key])
        for key in check_args
        if key in kwargs and key not in nics_args)
    # NICs are defined in a subdict
    nics.update((key, kwargs[key])
        for key in nics_args
        if key in kwargs)
    ret.update(nics=[nics])

    return json.dumps(ret)


def init(**kwargs):
    '''
    Initialize a new VM

    CLI Example:

    .. code-block:: bash

        salt '*' virt.init image_uuid='...' alias='...' [...]
    '''
    ret = {}
    vmadm = _check_vmadm()
    check_zone_args = (
        'image_uuid', 'alias', 'hostname',
        'max_physical_memory', 'quota', 'nic_tag',
        'ip', 'netmask', 'gateway')
    check_kvm_args = ('to_be_implemented')
    # check routines for mandatory arguments
    # Zones
    if all(key in kwargs for key in check_zone_args):
        ret = _gen_zone_json(**kwargs)
        # validation first
        cmd = 'echo {0} | {1} validate create'.format(_cmd_quote(ret), _cmd_quote(vmadm))
        res = __salt__['cmd.run_all'](cmd, python_shell=True)
        retcode = res['retcode']
        if retcode != 0:
            return CommandExecutionError(_exit_status(retcode))
        # if succedeed, proceed to the VM creation
        cmd = 'echo {0} | {1} create'.format(_cmd_quote(ret), _cmd_quote(vmadm))
        res = __salt__['cmd.run_all'](cmd, python_shell=True)
        retcode = res['retcode']
        if retcode != 0:
            return CommandExecutionError(_exit_status(retcode))
        return True
    # KVM
    elif all(key in kwargs for key in check_kvm_args):
        raise CommandExecutionError('KVM is not yet implemented')
    else:
        raise CommandExecutionError('Missing mandatory arguments')


def list_vms():
    '''
    Return a list of virtual machine names on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_vms
    '''
    vmadm = _check_vmadm()
    cmd = '{0} list'.format(vmadm)
    vms = []
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        raise CommandExecutionError(_exit_status(retcode))
    for key, uuid in six.iteritems(res):
        if key == "stdout":
            vms.append(uuid)
    return vms


def list_active_vms():
    '''
    Return a list of uuids for active virtual machine on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_active_vms
    '''
    vmadm = _check_vmadm()
    cmd = '{0} lookup state=running'.format(vmadm)
    vms = []
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        raise CommandExecutionError(_exit_status(retcode))
    for key, uuid in six.iteritems(res):
        if key == "stdout":
            vms.append(uuid)
    return vms


def list_inactive_vms():
    '''
    Return a list of uuids for inactive virtual machine on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_inactive_vms
    '''
    vmadm = _check_vmadm()
    cmd = '{0} lookup state=stopped'.format(vmadm)
    vms = []
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        raise CommandExecutionError(_exit_status(retcode))
    for key, uuid in six.iteritems(res):
        if key == "stdout":
            vms.append(uuid)
    return vms


def vm_info(uuid=None):
    '''
    Return a dict with information about the specified VM on this CN

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_info <uuid>
    '''
    info = {}
    if not uuid:
        raise CommandExecutionError('UUID parameter is mandatory')
    vmadm = _check_vmadm()
    cmd = '{0} get {1}'.format(vmadm, uuid)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        raise CommandExecutionError(_exit_status(retcode))
    info = res['stdout']
    return info


def start(uuid=None):
    '''
    Start a defined domain

    CLI Example:

    .. code-block:: bash

        salt '*' virt.start <uuid>
    '''
    if not uuid:
        raise CommandExecutionError('UUID parameter is mandatory')
    if uuid in list_active_vms():
        raise CommandExecutionError('The specified vm is already running')
    vmadm = _check_vmadm()
    cmd = '{0} start {1}'.format(vmadm, uuid)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        raise CommandExecutionError(_exit_status(retcode))
    if uuid in list_active_vms():
        return True
    else:
        return False


def shutdown(uuid=None):
    '''
    Send a soft shutdown signal to the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.shutdown <uuid>
    '''
    if not uuid:
        raise CommandExecutionError('UUID parameter is mandatory')
    if uuid in list_inactive_vms():
        raise CommandExecutionError('The specified vm is already stopped')
    vmadm = _check_vmadm()
    cmd = '{0} stop {1}'.format(vmadm, uuid)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        raise CommandExecutionError(_exit_status(retcode))
    if uuid in list_inactive_vms():
        return True
    else:
        return False


def reboot(uuid=None):
    '''
    Reboot a domain via ACPI request

    CLI Example:

    .. code-block:: bash

        salt '*' virt.reboot <uuid>
    '''
    if not uuid:
        raise CommandExecutionError('UUID parameter is mandatory')
    if uuid in list_inactive_vms():
        raise CommandExecutionError('The specified vm is stopped')
    vmadm = _check_vmadm()
    cmd = '{0} reboot {1}'.format(vmadm, uuid)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        raise CommandExecutionError(_exit_status(retcode))
    if uuid in list_active_vms():
        return True
    else:
        return False


def destroy(uuid=None):
    '''
    Hard power down the virtual machine, this is equivalent to pulling the power

    CLI Example:

    .. code-block:: bash

        salt '*' virt.destroy <uuid>
    '''
    if not uuid:
        raise CommandExecutionError('UUID parameter is mandatory')
    vmadm = _check_vmadm()
    cmd = '{0} delete {1}'.format(vmadm, uuid)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        raise CommandExecutionError(_exit_status(retcode))
    return True


def vm_virt_type(uuid=None):
    '''
    Return VM virtualization type : OS or KVM

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_virt_type <uuid>
    '''
    if not uuid:
        raise CommandExecutionError('UUID parameter is mandatory')
    vmadm = _check_vmadm()
    cmd = '{0} list -p -o type uuid={1}'.format(vmadm, uuid)
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        raise CommandExecutionError(_exit_status(retcode))
    ret = res['stdout']
    if ret != '':
        return ret
    raise CommandExecutionError('We can\'t determine the type of this VM')


def setmem(uuid, memory):
    '''
    Change the amount of memory allocated to VM.
    <memory> is to be specified in MB.

    Note for KVM : this would require a restart of the VM.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.setmem <uuid> 512
    '''
    if not uuid:
        raise CommandExecutionError('UUID parameter is mandatory')
    # We want to determine the nature of the VM
    vmtype = vm_virt_type(uuid)
    vmadm = _check_vmadm()
    warning = []
    if vmtype == 'OS':
        cmd = '{0} update {1} max_physical_memory={2}'.format(vmadm, uuid, memory)
    elif vmtype == 'KVM':
        cmd = '{0} update {1} ram={2}'.format(vmadm, uuid, memory)
        warning = 'Done, but please note this will require a restart of the VM'
    retcode = __salt__['cmd.retcode'](cmd)
    if retcode != 0:
        raise CommandExecutionError(_exit_status(retcode))
    if not warning:
        return True
    return warning


def get_macs(uuid=None):
    '''
    Return a list off MAC addresses from the named VM

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_macs <uuid>
    '''
    if not uuid:
        raise CommandExecutionError('UUID parameter is mandatory')
    dladm = _check_dladm()
    cmd = '{0} show-vnic -o MACADDRESS -p -z {1}'.format(dladm, uuid)
    res = __salt__['cmd.run_all'](cmd)
    ret = res['stdout']
    if ret != '':
        return ret
    raise CommandExecutionError('We can\'t find the MAC address of this VM')


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
