# -*- coding: utf-8 -*-
'''
virst compatibility module for managing VMs on SmartOS
'''
from __future__ import absolute_import

# Import Python libs
import logging
import json

# Import Salt libs
from salt.exceptions import CommandExecutionError
import salt.utils
import salt.utils.decorators as decorators

log = logging.getLogger(__name__)

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
    return __salt__['vmadm.create'](**kwargs)


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
    data = __salt__['vmadm.list'](keyed=True)
    vms = []
    vms.append("UUID                                  TYPE  RAM      STATE             ALIAS")
    for vm in data:
        vms.append("{vmuuid}{vmtype}{vmram}{vmstate}{vmalias}".format(
            vmuuid=vm.ljust(38),
            vmtype=data[vm]['type'].ljust(6),
            vmram=data[vm]['ram'].ljust(9),
            vmstate=data[vm]['state'].ljust(18),
            vmalias=data[vm]['alias'],
        ))
    return vms


def list_active_vms():
    '''
    Return a list of uuids for active virtual machine on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_active_vms
    '''
    return __salt__['vmadm.list'](search="state='running'", order='uuid')


def list_inactive_vms():
    '''
    Return a list of uuids for inactive virtual machine on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_inactive_vms
    '''
    return __salt__['vmadm.list'](search="state='stopped'", order='uuid')


def vm_info(uuid):
    '''
    Return a dict with information about the specified VM on this CN

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_info <uuid>
    '''
    return __salt__['vmadm.get'](uuid)


def start(uuid):
    '''
    Start a defined domain

    CLI Example:

    .. code-block:: bash

        salt '*' virt.start <uuid>
    '''
    if uuid in list_active_vms():
        raise CommandExecutionError('The specified vm is already running')

    __salt__['vmadm.start'](uuid)

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

    __salt__['vmadm.stop'](uuid)

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

    __salt__['vmadm.reboot'](uuid)

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

    return __salt__['vmadm.delete'](uuid)


def vm_virt_type(uuid):
    '''
    Return VM virtualization type : OS or KVM

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_virt_type <uuid>
    '''
    ret = __salt__['vmadm.lookup'](search="uuid={uuid}".format(uuid=uuid), order='type')
    if len(ret) < 1:
        raise CommandExecutionError("We can't determine the type of this VM")

    return ret[0]['type']


def setmem(uuid, memory):
    '''
    Change the amount of memory allocated to VM.
    <memory> is to be specified in MB.

    Note for KVM : this would require a restart of the VM.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.setmem <uuid> 512
    '''
    vmtype = vm_virt_type(uuid)
    if vmtype == 'OS':
        return __salt__['vmadm.update'](vm=uuid, max_physical_memory=memory)
    elif vmtype == 'LX':
        return __salt__['vmadm.update'](vm=uuid, max_physical_memory=memory)
    elif vmtype == 'KVM':
        log.warning('Changes will be applied after the VM restart.')
        return __salt__['vmadm.update'](vm=uuid, ram=memory)
    else:
        raise CommandExecutionError('Unknown VM type')

    return False


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
