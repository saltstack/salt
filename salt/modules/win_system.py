# -*- coding: utf-8 -*-
'''
Support for reboot, shutdown, etc
'''

# Import python libs
import logging
import re

# Import salt libs
import salt.utils

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'system'


def __virtual__():
    '''
    This only supports Windows
    '''
    if not salt.utils.is_windows():
        return False
    return __virtualname__


def halt(timeout=5):
    '''
    Halt a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.halt
    '''
    return shutdown(timeout)


def init(runlevel):
    '''
    Change the system runlevel on sysV compatible systems

    CLI Example:

    .. code-block:: bash

        salt '*' system.init 3
    '''
    #cmd = 'init {0}'.format(runlevel)
    #ret = __salt__['cmd.run'](cmd)
    #return ret

    # TODO: Create a mapping of runlevels to
    #       corresponding Windows actions

    return 'Not implemented on Windows at this time.'


def poweroff(timeout=5):
    '''
    Poweroff a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.poweroff
    '''
    return shutdown(timeout)


def reboot(timeout=5):
    '''
    Reboot the system

    CLI Example:

    .. code-block:: bash

        salt '*' system.reboot
    '''
    cmd = 'shutdown /r /t {0}'.format(timeout)
    ret = __salt__['cmd.run'](cmd)
    return ret


def shutdown(timeout=5):
    '''
    Shutdown a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown
    '''
    cmd = 'shutdown /s /t {0}'.format(timeout)
    ret = __salt__['cmd.run'](cmd)
    return ret


def shutdown_hard():
    '''
    Shutdown a running system with no timeout or warning

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown_hard
    '''
    cmd = 'shutdown /p /f'
    ret = __salt__['cmd.run'](cmd)
    return ret


def set_computer_name(name):
    '''
    Set the Windows computer name

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.set_computer_name 'DavesComputer'
    '''
    cmd = ('wmic computersystem where name="%COMPUTERNAME%"'
           ' call rename name="{0}"')
    log.debug('Attempting to change computer name. Cmd is: '.format(cmd))
    ret = __salt__['cmd.run'](cmd.format(name))
    if 'ReturnValue = 0;' in ret:
        ret = {'Computer Name': {'Current': get_computer_name()}}
        pending = get_pending_computer_name()
        if pending not in (None, False):
            ret['Computer Name']['Pending'] = pending
        return ret
    return False


def get_pending_computer_name():
    '''
    Get a pending computer name. If the computer name has been changed, and the
    change is pending a system reboot, this function will return the pending
    computer name. Otherwise, ``None`` will be returned. If there was an error
    retrieving the pending computer name, ``False`` will be returned, and an
    error message will be logged to the minion log.

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_pending_computer_name
    '''
    current = get_computer_name()
    cmd = ('reg query HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control'
           '\\ComputerName\\ComputerName /v ComputerName')
    output = __salt__['cmd.run'](cmd)
    pending = None
    for line in output.splitlines():
        try:
            pending = re.search(
                r'ComputerName\s+REG_SZ\s+(\S+)',
                line
            ).group(1)
            break
        except AttributeError:
            continue

    if pending is not None:
        return pending if pending != current else None

    log.error('Unable to retrieve pending computer name using the '
              'following command: {0}'.format(cmd))
    return False


def get_computer_name():
    '''
    Get the Windows computer name

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_computer_name
    '''
    cmd = 'net config server'
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        if 'Server Name' in line:
            _, srv_name = line.split('Server Name', 1)
            return srv_name.strip().lstrip('\\')
    return False


def set_computer_desc(desc):
    '''
    Set the Windows computer description

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.set_computer_desc 'This computer belongs to Dave!'
    '''
    cmd = 'net config server /srvcomment:"{0}"'.format(desc)
    __salt__['cmd.run'](cmd)
    return {'Computer Description': get_computer_desc()}

set_computer_description = set_computer_desc


def get_computer_desc():
    '''
    Get the Windows computer description

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_computer_desc
    '''
    cmd = 'net config server'
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        if 'Server Comment' in line:
            _, desc = line.split('Server Comment', 1)
            return desc.strip()
    return False

get_computer_description = get_computer_desc


def join_domain(domain, username, passwd, ou=None, acct_exists=False,):
    '''
    Join a computer the an Active Directory domain

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.join_domain 'mydomain.local' 'myusername' \
             'mysecretpasswd' 'OU=MyClients;OU=MyOrg;DC=myDom;DC=local'
    '''
    # remove any escape characters
    if isinstance(ou, str):
        ou = ou.split('\\')
        ou = ''.join(ou)

    FJoinOptions = 3
    if acct_exists:
        FJoinOptions = 1
    cmd = ('wmic /interactive:off ComputerSystem Where '
           'name="%computername%" call JoinDomainOrWorkgroup FJoinOptions={0} '
           'Name="{1}" UserName="{2}" Password="{3}" '
           ).format(FJoinOptions, domain, username, passwd)
    if ou:
        add_ou = 'AccountOU="{4}"'.format(ou)
        cmd = cmd + add_ou

    ret = __salt__['cmd.run'](cmd)
    if 'ReturnValue = 0;' in ret:
        return {'Domain': domain}
    return False


def get_system_time():
    '''
    Get the Windows system time

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_system_time
    '''
    cmd = 'time /T'
    return __salt__['cmd.run'](cmd)


def set_system_time(newtime):
    '''
    Set the Windows system time

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_system_time '11:31:15 AM'
    '''
    cmd = 'time {0}'.format(newtime)
    return not __salt__['cmd.retcode'](cmd)


def get_system_date():
    '''
    Get the Windows system date

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_system_date
    '''
    cmd = 'date /T'
    return __salt__['cmd.run'](cmd)


def set_system_date(newdate):
    '''
    Set the Windows system date. Use <mm-dd-yy> format for the date.

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_system_date '03-28-13'
    '''
    cmd = 'date {0}'.format(newdate)
    return not __salt__['cmd.retcode'](cmd)


def start_time_service():
    '''
    Start the Windows time service

    CLI Example:

    .. code-block:: bash

        salt '*' system.start_time_service
    '''
    return __salt__['service.start']('w32time')


def stop_time_service():
    '''
    Stop the Windows time service

    CLI Example:

    .. code-block:: bash

        salt '*' system.stop_time_service
    '''
    return __salt__['service.stop']('w32time')
