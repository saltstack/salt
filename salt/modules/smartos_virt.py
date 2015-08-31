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
    ret.update((key, kwargs[key]) for key in check_args if key in kwargs and key not in nics_args)
    # NICs are defined in a subdict
    nics.update((key, kwargs[key]) for key in nics_args if key in kwargs)
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
    check_zone_args = ('image_uuid', 'alias', 'hostname', 'max_physical_memory',
                       'quota', 'nic_tag', 'ip', 'netmask', 'gateway')
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


def _call_vmadm(cmd):
    '''
    Call vmadm and return the result or raise an exception.

    :param cmd: command params for the vmadm on SmartOS.
    :return:
    '''
    res = __salt__['cmd.run_all']('{vmadm} {cmd}'.format(vmadm=_check_vmadm(), cmd=cmd))
    if res['retcode'] != 0:
        raise CommandExecutionError(_exit_status(res['retcode']))

    return res


def list_domains():
    '''
    Return a list of virtual machine names on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_domains
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


def vm_info(uuid):
    '''
    Return a dict with information about the specified VM on this CN

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_info <uuid>
    '''
    res = __salt__['cmd.run_all']('{0} get {1}'.format(_check_vmadm(), uuid))
    if res['retcode'] != 0:
        raise CommandExecutionError(_exit_status(res['retcode']))

    return res['stdout']


def start(uuid):
    '''
    Start a defined domain

    CLI Example:

    .. code-block:: bash

        salt '*' virt.start <uuid>
    '''
    if uuid in list_active_vms():
        raise CommandExecutionError('The specified vm is already running')

    _call_vmadm('start {0}'.format(uuid))

    return uuid in list_active_vms()


def shutdown(uuid):
    '''
    Send a soft shutdown signal to the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.shutdown <uuid>
    '''
    if uuid in list_inactive_vms():
        raise CommandExecutionError('The specified vm is already stopped')

    _call_vmadm('stop {0}'.format(uuid))

    return uuid in list_inactive_vms()


def reboot(uuid):
    '''
    Reboot a domain via ACPI request

    CLI Example:

    .. code-block:: bash

        salt '*' virt.reboot <uuid>
    '''
    if uuid in list_inactive_vms():
        raise CommandExecutionError('The specified vm is stopped')

    _call_vmadm('reboot {0}'.format(uuid))

    return uuid in list_active_vms()


def stop(uuid):
    '''
    Hard power down the virtual machine, this is equivalent to powering off the hardware.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.destroy <uuid>
    '''
    if uuid in list_inactive_vms():
        raise CommandExecutionError('The specified vm is stopped')

    _call_vmadm('delete {0}'.format(uuid))

    return uuid in list_inactive_vms()


def vm_virt_type(uuid):
    '''
    Return VM virtualization type : OS or KVM

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_virt_type <uuid>
    '''
    ret = _call_vmadm('list -p -o type uuid={0}'.format(uuid))['stdout']
    if not ret:
        raise CommandExecutionError('We can\'t determine the type of this VM')
    return ret


def setmem(uuid, memory):
    '''
    Change the amount of memory allocated to VM.
    <memory> is to be specified in MB.

    Note for KVM : this would require a restart of the VM.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.setmem <uuid> 512
    '''
    warning = None
    vmtype = vm_virt_type(uuid)
    if vmtype == 'OS':
        cmd = 'update {1} max_physical_memory={2}'.format(uuid, memory)
    elif vmtype == 'KVM':
        cmd = 'update {1} ram={2}'.format(uuid, memory)
        warning = 'Changes will be applied after the VM restart.'
    else:
        raise CommandExecutionError('Unknown VM type')

    retcode = _call_vmadm(cmd)['retcode']
    if retcode:
        raise CommandExecutionError(_exit_status(retcode))

    return warning or None


def get_macs(uuid):
    '''
    Return a list off MAC addresses from the named VM

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_macs <uuid>
    '''
    dladm = _check_dladm()
    cmd = '{0} show-vnic -o MACADDRESS -p -z {1}'.format(dladm, uuid)
    res = __salt__['cmd.run_all'](cmd)
    ret = res['stdout']
    if ret != '':
        return ret
    raise CommandExecutionError('We can\'t find the MAC address of this VM')


# Deprecated aliases
def create(domain):
    '''
    .. deprecated:: Boron
       Use :py:func:`~salt.modules.virt.start` instead.

    Start a defined domain

    CLI Example:

    .. code-block:: bash

        salt '*' virt.create <domain>
    '''
    salt.utils.warn_until('Nitrogen', 'Use "virt.start" instead.')
    return start(domain)


def destroy(domain):
    '''
    .. deprecated:: Boron
       Use :py:func:`~salt.modules.virt.stop` instead.

    Power off a defined domain

    CLI Example:

    .. code-block:: bash

        salt '*' virt.destroy <domain>
    '''
    salt.utils.warn_until('Nitrogen', 'Use "virt.stop" instead.')
    return stop(domain)


def list_vms():
    '''
    .. deprecated:: Boron
       Use :py:func:`~salt.modules.virt.list_domains` instead.

    List all virtual machines.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_vms <domain>
    '''
    salt.utils.warn_until('Nitrogen', 'Use "virt.list_domains" instead.')
    return list_domains()
