# -*- coding: utf-8 -*-
'''
Support for reboot, shutdown, etc
'''
from __future__ import absolute_import

# Import python libs
import logging
import re
import datetime
try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote

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
    #cmd = ['init', runlevel]
    #ret = __salt__['cmd.run'](cmd, python_shell=False)
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
    cmd = ['shutdown', '/r', '/t', '{0}'.format(timeout)]
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    return ret


def shutdown(timeout=5):
    '''
    Shutdown a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown
    '''
    cmd = ['shutdown', '/s', '/t', '{0}'.format(timeout)]
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    return ret


def shutdown_hard():
    '''
    Shutdown a running system with no timeout or warning

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown_hard
    '''
    cmd = ['shutdown', '/p', '/f']
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    return ret


def set_computer_name(name):
    '''
    Set the Windows computer name

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.set_computer_name 'DavesComputer'
    '''
    cmd = ('wmic computersystem where name="%COMPUTERNAME%"'
           ' call rename name="{0}"'.format(name))
    log.debug('Attempting to change computer name. Cmd is: {0}'.format(cmd))
    ret = __salt__['cmd.run'](cmd, python_shell=True)
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
    cmd = ['reg', 'query',
           'HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\ComputerName\\ComputerName',
           '/v', 'ComputerName']
    output = __salt__['cmd.run'](cmd, python_shell=False)
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
    cmd = ['net', 'config', 'server']
    lines = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
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
    cmd = ['net', 'config', 'server', u'/srvcomment:{0}'.format(salt.utils.sdecode(desc))]
    __salt__['cmd.run'](cmd, python_shell=False)
    return {'Computer Description': get_computer_desc()}

set_computer_description = set_computer_desc


def get_computer_desc():
    '''
    Get the Windows computer description

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_computer_desc
    '''
    cmd = ['net', 'config', 'server']
    lines = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    for line in lines:
        if 'Server Comment' in line:
            _, desc = line.split('Server Comment', 1)
            return desc.strip()
    return False

get_computer_description = get_computer_desc


def join_domain(
        domain=None,
        username=None,
        password=None,
        account_ou=None,
        account_exists=False
    ):
    '''
    Join a computer to an Active Directory domain

    domain
        The domain to which the computer should be joined, e.g.
        ``my-company.com``

    username
        Username of an account which is authorized to join computers to the
        specified domain. Need to be either fully qualified like
        ``user@domain.tld`` or simply ``user``

    password
        Password of the specified user

    account_ou : None
        The DN of the OU below which the account for this computer should be
        created when joining the domain, e.g.
        ``ou=computers,ou=departm_432,dc=my-company,dc=com``

    account_exists : False
        Needs to be set to ``True`` to allow re-using an existing account

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.join_domain domain='domain.tld' \\
                         username='joinuser' password='joinpassword' \\
                         account_ou='ou=clients,ou=org,dc=domain,dc=tld' \\
                         account_exists=False
    '''

    if '@' not in username:
        username = '{0}@{1}'.format(username, domain)

    # remove any escape characters
    if isinstance(account_ou, str):
        account_ou = account_ou.split('\\')
        account_ou = ''.join(account_ou)

    join_options = 3
    if account_exists:
        join_options = 1
    cmd = ('wmic /interactive:off ComputerSystem Where '
           'name="%computername%" call JoinDomainOrWorkgroup FJoinOptions={0} '
           'Name={1} UserName={2} Password="{3}"'
           ).format(
               join_options,
               _cmd_quote(domain),
               _cmd_quote(username),
               password)
    if account_ou:
        # contrary to RFC#2253, 2.1, 'wmic' requires a ; as a RDN separator
        # for the DN
        account_ou = account_ou.replace(',', ';')
        add_ou = ' AccountOU="{0}"'.format(account_ou)
        cmd = cmd + add_ou

    ret = __salt__['cmd.run'](cmd, python_shell=True)
    if 'ReturnValue = 0;' in ret:
        return {'Domain': domain}
    return_values = {
        2:    'Invalid OU or specifying OU is not supported',
        5:    'Access is denied',
        87:   'The parameter is incorrect',
        110:  'The system cannot open the specified object',
        1323: 'Unable to update the password',
        1326: 'Logon failure: unknown username or bad password',
        1355: 'The specified domain either does not exist or could not be contacted',
        2224: 'The account already exists',
        2691: 'The machine is already joined to the domain',
        2692: 'The machine is not currently joined to a domain',
    }
    for value in return_values:
        if 'ReturnValue = {0};'.format(value) in ret:
            log.error(return_values[value])
    return False


def _validate_datetime(newdatetime, valid_formats):
    '''
    Validate `newdatetime` against list of date/time formats understood by
    windows.
    '''
    for dt_format in valid_formats:
        try:
            datetime.datetime.strptime(newdatetime, dt_format)
            return True
        except ValueError:
            continue
    return False


def _validate_time(newtime):
    '''
    Validate `newtime` against list of time formats understood by windows.
    '''
    valid_time_formats = [
        '%I:%M:%S %p',
        '%I:%M %p',
        '%H:%M:%S',
        '%H:%M'
    ]
    return _validate_datetime(newtime, valid_time_formats)


def _validate_date(newdate):
    '''
    Validate `newdate` against list of date formats understood by windows.
    '''
    valid_date_formats = [
        '%Y-%m-%d',
        '%m/%d/%y',
        '%y/%m/%d'
    ]
    return _validate_datetime(newdate, valid_date_formats)


def get_system_time():
    '''
    Get the Windows system time

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_system_time
    '''
    cmd = 'time /T'
    return __salt__['cmd.run'](cmd, python_shell=True)


def set_system_time(newtime):
    '''
    Set the Windows system time

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_system_time '11:31:15 AM'
    '''
    if not _validate_time(newtime):
        return False
    cmd = 'time {0}'.format(newtime)
    return not __salt__['cmd.retcode'](cmd, python_shell=True)


def get_system_date():
    '''
    Get the Windows system date

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_system_date
    '''
    cmd = 'date /T'
    return __salt__['cmd.run'](cmd, python_shell=True)


def set_system_date(newdate):
    '''
    Set the Windows system date. Use <mm-dd-yy> format for the date.

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_system_date '03-28-13'
    '''
    if not _validate_date(newdate):
        return False
    cmd = 'date {0}'.format(newdate)
    return not __salt__['cmd.retcode'](cmd, python_shell=True)


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
