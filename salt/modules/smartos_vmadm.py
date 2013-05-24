'''
Module for managing VMs on SmartOS
'''

# Import Python libs
import logging

# Import Salt libs
from salt.exceptions import CommandExecutionError
import salt.utils

@salt.utils.memoize
def _check_vmadm():
    '''
    Looks to see if vmadm is present on the system
    '''
    return salt.utils.which('vmadm')


def __virtual__():
    '''
    Provides virt on SmartOS
    '''
    if __grains__['os'] == "SmartOS" and _check_vmadm():
        return 'virt'
    return False


def _exit_status(retcode):
    '''
    Translate exit status of vmadm
    '''
    ret = { 0 : 'Successful completion.',
            1 : 'An error occurred.',
            2 : 'Usage error.'
          }[retcode]
    return ret


def list_vms():
    '''
    Return a list of virtual machine names on the minion

    CLI Example::
        
        salt '*' virt.list_vms
    ''' 
    vmadm = _check_vmadm()
    cmd = '{0} list'.format(vmadm)
    vms = []
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        raise CommandExecutionError(_exit_status(retcode))
    for key, uuid in res.iteritems():
        if key == "stdout":
            vms.append(uuid)
    return vms


def list_active_vms():
    '''
    Return a list of uuids for active virtual machine on the minion

    CLI Example::

        salt '*' virt.list_active_vms
    '''
    vmadm = _check_vmadm()
    cmd = '{0} lookup state=running'.format(vmadm)
    vms = []
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        raise CommandExecutionError(_exit_status(retcode))
    for key, uuid in res.iteritems():
        if key == "stdout":
            vms.append(uuid)
    return vms

    
def list_inactive_vms():
    '''
    Return a list of uuids for inactive virtual machine on the minion

    CLI Example::

        salt '*' virt.list_inactive_vms
    '''
    vmadm = _check_vmadm()
    cmd = '{0} lookup state=stopped'.format(vmadm)
    vms = []
    res = __salt__['cmd.run_all'](cmd)
    retcode = res['retcode']
    if retcode != 0:
        raise CommandExecutionError(_exit_status(retcode))
    for key, uuid in res.iteritems():
        if key == "stdout":
            vms.append(uuid)
    return vms


def start(uuid=None):
    '''
    Start a defined domain

    CLI Example::
    
        salt '*' virt.start <uuid>
    '''
    if not uuid :
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

    CLI Example::

        salt '*' virt.shutdown <uuid>
    '''
    if not uuid :
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

    CLI Example::
    
        salt '*' virt.reboot <uuid>
    '''
    if not uuid :
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


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
