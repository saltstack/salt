# -*- coding: utf-8 -*-
'''
Module for running vmadm command on SmartOS
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
#list [-p] [-H] [-o field,...] [-s field,...] [field=value ...]
#lookup [-j|-1] [-o field,...] [field=value ...]
#reboot <uuid> [-F]
#receive [-f <filename>]
#reprovision [-f <filename>]
#rollback-snapshot <uuid> <snapname>
#send <uuid> [target]
#start <uuid> [option=value ...]
#stop <uuid> [-F]
#sysrq <uuid> <nmi|screenshot>
#update <uuid> [-f <filename>]
# -or- update <uuid> property=value [property=value ...]
#validate create [-f <filename>]
#validate update <brand> [-f <filename>]

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
