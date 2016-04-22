# -*- coding: utf-8 -*-
'''
virst compatibility module for managing VMs on SmartOS
'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
from salt.exceptions import CommandExecutionError
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'virt'


def __virtual__():
    '''
    Provides virt on SmartOS
    '''
    if salt.utils.is_smartos_globalzone() and salt.utils.which('vmadm'):
        return __virtualname__
    return (
        False,
        '{0} module can only be loaded on SmartOS computed nodes'.format(
            __virtualname__
        )
    )


def init(**kwargs):
    '''
    Initialize a new VM

    CLI Example:

    .. code-block:: bash

        salt '*' virt.init image_uuid='...' alias='...' [...]
    '''
    return __salt__['vmadm.create'](**kwargs)


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


def vm_info(domain):
    '''
    Return a dict with information about the specified VM on this CN

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_info <domain>
    '''
    return __salt__['vmadm.get'](domain)


def start(domain):
    '''
    Start a defined domain

    CLI Example:

    .. code-block:: bash

        salt '*' virt.start <domain>
    '''
    if domain in list_active_vms():
        raise CommandExecutionError('The specified vm is already running')

    __salt__['vmadm.start'](domain)

    return domain in list_active_vms()


def shutdown(domain):
    '''
    Send a soft shutdown signal to the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.shutdown <domain>
    '''
    if domain in list_inactive_vms():
        raise CommandExecutionError('The specified vm is already stopped')

    __salt__['vmadm.stop'](domain)

    return domain in list_inactive_vms()


def reboot(domain):
    '''
    Reboot a domain via ACPI request

    CLI Example:

    .. code-block:: bash

        salt '*' virt.reboot <domain>
    '''
    if domain in list_inactive_vms():
        raise CommandExecutionError('The specified vm is stopped')

    __salt__['vmadm.reboot'](domain)

    return domain in list_active_vms()


def stop(domain):
    '''
    Hard power down the virtual machine, this is equivalent to powering off the hardware.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.destroy <domain>
    '''
    if domain in list_inactive_vms():
        raise CommandExecutionError('The specified vm is stopped')

    return __salt__['vmadm.delete'](domain)


def vm_virt_type(domain):
    '''
    Return VM virtualization type : OS or KVM

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_virt_type <domain>
    '''
    ret = __salt__['vmadm.lookup'](search="uuid={uuid}".format(uuid=domain), order='type')
    if len(ret) < 1:
        raise CommandExecutionError("We can't determine the type of this VM")

    return ret[0]['type']


def setmem(domain, memory):
    '''
    Change the amount of memory allocated to VM.
    <memory> is to be specified in MB.

    Note for KVM : this would require a restart of the VM.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.setmem <domain> 512
    '''
    vmtype = vm_virt_type(domain)
    if vmtype == 'OS':
        return __salt__['vmadm.update'](vm=domain, max_physical_memory=memory)
    elif vmtype == 'LX':
        return __salt__['vmadm.update'](vm=domain, max_physical_memory=memory)
    elif vmtype == 'KVM':
        log.warning('Changes will be applied after the VM restart.')
        return __salt__['vmadm.update'](vm=domain, ram=memory)
    else:
        raise CommandExecutionError('Unknown VM type')

    return False


def get_macs(domain):
    '''
    Return a list off MAC addresses from the named VM

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_macs <domain>
    '''
    macs = []
    ret = __salt__['vmadm.lookup'](search="uuid={uuid}".format(uuid=domain), order='nics')
    if len(ret) < 1:
        raise CommandExecutionError('We can\'t find the MAC address of this VM')
    else:
        for nic in ret[0]['nics']:
            macs.append(nic['mac'])
        return macs


# Deprecated aliases
def create(domain):
    '''
    .. deprecated:: Nitrogen
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
    .. deprecated:: Nitrogen
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
    .. deprecated:: Nitrogen
       Use :py:func:`~salt.modules.virt.list_domains` instead.

    List all virtual machines.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_vms <domain>
    '''
    salt.utils.warn_until('Nitrogen', 'Use "virt.list_domains" instead.')
    return list_domains()
