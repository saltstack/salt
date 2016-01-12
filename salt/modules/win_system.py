# -*- coding: utf-8 -*-
'''
Module for managing windows systems.

:depends:
    - win32net

Support for reboot, shutdown, etc
'''
from __future__ import absolute_import

# Import python libs
import logging
from datetime import datetime

# Import 3rd Party Libs
try:
    import pythoncom
    import wmi
    import win32net
    import win32api
    import win32con
    import pywintypes
    from ctypes import windll
    HAS_WIN32NET_MODS = True
except ImportError:
    HAS_WIN32NET_MODS = False

# Import salt libs
import salt.utils
import salt.utils.locales
from salt.modules.reg import read_value

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'system'


def __virtual__():
    '''
    Set the system module of the kernel is Windows
    '''
    if HAS_WIN32NET_MODS and salt.utils.is_windows():
        return __virtualname__
    return False


def _convert_minutes_seconds(timeout, in_seconds=False):
    '''
    convert timeout to seconds
    '''
    return timeout if in_seconds else timeout*60


def halt(timeout=5, in_seconds=False):
    '''
    Halt a running system.

    :param int timeout:
        Number of seconds before halting the system.
        Default is 5 seconds.

    :return: True is successful.
    :rtype: bool

    timeout
        The wait time before the system will be shutdown.

    in_seconds
        Whether to treat timeout as seconds or minutes.

        .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' system.halt 5
    '''
    return shutdown(timeout=timeout, in_seconds=in_seconds)


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


def poweroff(timeout=5, in_seconds=False):
    '''
    Power off a running system.

    :param int timeout:
        Number of seconds before powering off the system.
        Default is 5 seconds.

    :return: True if successful
    :rtype: bool

    timeout
        The wait time before the system will be shutdown.

    in_seconds
        Whether to treat timeout as seconds or minutes.

        .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' system.poweroff 5
    '''
    return shutdown(timeout=timeout, in_seconds=in_seconds)


def reboot(timeout=5, in_seconds=False):
    '''
    Reboot a running system.

    :param int timeout:
        Number of seconds before rebooting the system.
        Default is 5 minutes.

    :param bool in_seconds:
        Whether to treat timeout as seconds or minutes.

        .. versionadded:: 2015.8.0

    :return: True if successful
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.reboot 5
    '''
    return shutdown(timeout=timeout, reboot=True, in_seconds=in_seconds)


def shutdown(message=None, timeout=5, force_close=True, reboot=False, in_seconds=False):
    '''
    Shutdown a running system.

    :param str message:
        A message to display to the user before shutting down.

    :param int timeout:
        The length of time that the shutdown dialog box should be displayed, in
        seconds. While this dialog box is displayed, the shutdown can be stopped
        by the shutdown_abort function.

        If timeout is not zero, InitiateSystemShutdown displays a dialog box on
        the specified computer. The dialog box displays the name of the user
        who called the function, displays the message specified by the
        lpMessage parameter, and prompts the user to log off. The dialog box
        beeps when it is created and remains on top of other windows in the
        system. The dialog box can be moved but not closed. A timer counts down
        the remaining time before a forced shutdown.

        If timeout is zero, the computer shuts down without displaying the
        dialog box, and the shutdown cannot be stopped by shutdown_abort.

        Default is 5 minutes

    :param bool in_seconds:
        Whether to treat timeout as seconds or minutes.

        .. versionadded:: 2015.8.0

    :param bool force_close:
        True to force close all open applications. False displays a dialog box
        instructing the user to close the applications.

    :param bool reboot:
        True restarts the computer immediately after shutdown.
        False caches to disk and safely powers down the system.

    :return: True if successful
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown 5
    '''
    seconds = _convert_minutes_seconds(timeout, in_seconds)

    if message:
        message = message.decode('utf-8')
    try:
        win32api.InitiateSystemShutdown('127.0.0.1', message, timeout,
                                        force_close, reboot)
        return True
    except pywintypes.error as exc:
        (number, context, message) = exc
        log.error('Failed to shutdown the system')
        log.error('nbr: {0}'.format(number))
        log.error('ctx: {0}'.format(context))
        log.error('msg: {0}'.format(message))
        return False


def shutdown_hard():
    '''
    Shutdown a running system with no timeout or warning.

    :return: True if successful
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown_hard
    '''
    return shutdown(timeout=0)


def shutdown_abort():
    '''
    Abort a shutdown. Only available while the dialog box is being
    displayed to the user. Once the shutdown has initiated, it cannot be aborted

    :return: True if successful
    :rtype: bool
    '''
    try:
        win32api.AbortSystemShutdown('127.0.0.1')
        return True
    except pywintypes.error as exc:
        (number, context, message) = exc
        log.error('Failed to abort system shutdown')
        log.error('nbr: {0}'.format(number))
        log.error('ctx: {0}'.format(context))
        log.error('msg: {0}'.format(message))
        return False


def lock():
    '''
    Lock the workstation.

    :return: True if successful
    :rtype: bool
    '''
    return windll.user32.LockWorkStation()


def set_computer_name(name):
    '''
    Set the Windows computer name

    :param str name:
        The new name to give the computer. Requires a reboot to take effect.

    :return:
        Returns a dictionary containing the old and new names if successful.
        False if not.

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.set_computer_name 'DavesComputer'
    '''
    if name:
        name = name.decode('utf-8')

    if windll.kernel32.SetComputerNameExW(win32con.ComputerNamePhysicalDnsHostname,
                                          name):
        ret = {'Computer Name': {'Current': get_system_info()['name']}}
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

    :return:
        Returns the pending name if pending restart. Returns none if not pending
        restart.

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_pending_computer_name
    '''
    current = get_computer_name()
    pending = read_value('HKLM',
                         r'SYSTEM\CurrentControlSet\Control\ComputerName\ComputerName',
                         'ComputerName')['vdata']
    if pending:
        return pending if pending != current else None
    return False


def get_computer_name():
    '''
    Get the Windows computer name

    :return:
        Returns the computer name if found. Otherwise returns False

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_computer_name
    '''
    name = get_system_info()['name']
    return name if name else False


def set_computer_desc(desc=None):
    '''
    Set the Windows computer description

    :param str desc:
        The computer description

    :return: False if it fails. Description if successful.

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.set_computer_desc 'This computer belongs to Dave!'
    '''
    # Make sure the system exists
    # Return an object containing current information array for the computer
    system_info = win32net.NetServerGetInfo(None, 101)

    # If desc is passed, decode it for unicode
    if desc:
        system_info['comment'] = desc.decode('utf-8')
    else:
        return False

    # Apply new settings
    try:
        win32net.NetServerSetInfo(None, 101, system_info)
    except win32net.error as exc:
        (number, context, message) = exc
        log.error('Failed to update system')
        log.error('nbr: {0}'.format(number))
        log.error('ctx: {0}'.format(context))
        log.error('msg: {0}'.format(message))
        return False

    return {'Computer Description': get_computer_desc()}


set_computer_description = salt.utils.alias_function(set_computer_desc, 'set_computer_description')


def get_system_info():
    '''
    Get system information.

    :return:
        Returns a Dictionary containing information about the system to include
        name, description, version, etc...
    :rtype: dict
    '''
    system_info = win32net.NetServerGetInfo(None, 101)
    return system_info


def get_computer_desc():
    '''
    Get the Windows computer description

    :return:
        Returns the computer description if found. Otherwise returns False

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_computer_desc
    '''
    desc = get_system_info()['comment']
    return desc if desc else False


get_computer_description = salt.utils.alias_function(get_computer_desc, 'get_computer_description')


def _lookup_error(number):
    '''
    Lookup the error based on the passed number
    .. versionadded:: 2015.5.7
    .. versionadded:: 2015.8.2

    :param int number: Number code to lookup

    :return: The text that corresponds to the error number
    :rtype: str
    '''
    return_values = {
        2:    'Invalid OU or specifying OU is not supported',
        5:    'Access is denied',
        53:   'The network path was not found',
        87:   'The parameter is incorrect',
        110:  'The system cannot open the specified object',
        1323: 'Unable to update the password',
        1326: 'Logon failure: unknown username or bad password',
        1355: 'The specified domain either does not exist or could not be contacted',
        2224: 'The account already exists',
        2691: 'The machine is already joined to the domain',
        2692: 'The machine is not currently joined to a domain',
    }
    return return_values[number]


def join_domain(domain,
                username=None,
                password=None,
                account_ou=None,
                account_exists=False,
                restart=False):
    '''
    Join a computer to an Active Directory domain. Requires reboot.

    :param str domain:
        The domain to which the computer should be joined, e.g.
        ``example.com``

    :param str username:
        Username of an account which is authorized to join computers to the
        specified domain. Need to be either fully qualified like
        ``user@domain.tld`` or simply ``user``

    :param str password:
        Password of the specified user

    :param str account_ou:
        The DN of the OU below which the account for this computer should be
        created when joining the domain, e.g.
        ``ou=computers,ou=departm_432,dc=my-company,dc=com``

    :param bool account_exists:
        Needs to be set to ``True`` to allow re-using an existing account

    :param bool restart: Restarts the computer after a successful join
    .. versionadded:: 2015.5.7
    .. versionadded:: 2015.8.2

    :returns: Returns a dictionary if successful. False if unsuccessful.
    :rtype: dict, bool

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.join_domain domain='domain.tld' \\
                         username='joinuser' password='joinpassword' \\
                         account_ou='ou=clients,ou=org,dc=domain,dc=tld' \\
                         account_exists=False, restart=True
    '''
    status = get_domain_workgroup()
    if 'Domain' in status:
        if status['Domain'] == domain:
            return 'Already joined to {0}'.format(domain)

    if username and '\\' not in username and '@' not in username:
        username = '{0}@{1}'.format(username, domain)

    if username and password is None:
        return 'Must specify a password if you pass a username'

    # remove any escape characters
    if isinstance(account_ou, str):
        account_ou = account_ou.split('\\')
        account_ou = ''.join(account_ou)

    NETSETUP_JOIN_DOMAIN = 0x1
    NETSETUP_ACCOUNT_CREATE = 0x2
    NETSETUP_DOMAIN_JOIN_IF_JOINED = 0x20

    join_options = 0x0
    join_options |= NETSETUP_JOIN_DOMAIN
    join_options |= NETSETUP_DOMAIN_JOIN_IF_JOINED
    if not account_exists:
        join_options |= NETSETUP_ACCOUNT_CREATE

    pythoncom.CoInitialize()
    c = wmi.WMI()
    comp = c.Win32_ComputerSystem()[0]
    err = comp.JoinDomainOrWorkgroup(Name=domain,
                                     Password=password,
                                     UserName=username,
                                     AccountOU=account_ou,
                                     FJoinOptions=join_options)

    # you have to do this because JoinDomainOrWorkgroup returns a strangely
    # formatted value that looks like (0,)
    if not err[0]:
        ret = {'Domain': domain,
               'Restart': False}
        if restart:
            ret['Restart'] = reboot()
        return ret

    log.error(_lookup_error(err[0]))
    return False


def unjoin_domain(username=None,
                  password=None,
                  domain=None,
                  workgroup='WORKGROUP',
                  disable=False,
                  restart=False):
    r'''
    Unjoin a computer from an Active Directory Domain. Requires restart.

    :param username:
        Username of an account which is authorized to manage computer accounts
        on the domain. Need to be fully qualified like ``user@domain.tld`` or
        ``domain.tld\user``. If domain not specified, the passed domain will be
        used. If computer account doesn't need to be disabled, can be None.

    :param str password:
        Password of the specified user

    :param str domain: The domain from which to unjoin the computer. Can be None

    :param str workgroup: The workgroup to join the computer to. Default is
    ``WORKGROUP``

    .. versionadded:: 2015.5.7
    .. versionadded:: 2015.8.2

    :param bool disable:
        Disable the user account in Active Directory. True to disable.

    :param bool restart: Restart the computer after successful unjoin

    .. versionadded:: 2015.5.7
    .. versionadded:: 2015.8.2

    :returns: Returns a dictionary if successful. False if unsuccessful.
    :rtype: dict, bool

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.unjoin_domain restart=True

        salt 'minion-id' system.unjoin_domain username='unjoinuser' \\
                         password='unjoinpassword' disable=True \\
                         restart=True
    '''
    status = get_domain_workgroup()
    if 'Workgroup' in status:
        if status['Workgroup'] == workgroup:
            return 'Already joined to {0}'.format(workgroup)

    if username and '\\' not in username and '@' not in username:
        if domain:
            username = '{0}@{1}'.format(username, domain)
        else:
            return 'Must specify domain if not supplied in username'

    if username and password is None:
        return 'Must specify a password if you pass a username'

    NETSETUP_ACCT_DELETE = 0x2

    unjoin_options = 0x0
    if disable:
        unjoin_options |= NETSETUP_ACCT_DELETE

    pythoncom.CoInitialize()
    c = wmi.WMI()
    comp = c.Win32_ComputerSystem()[0]
    err = comp.UnjoinDomainOrWorkgroup(Password=password,
                                       UserName=username,
                                       FUnjoinOptions=unjoin_options)

    # you have to do this because UnjoinDomainOrWorkgroup returns a
    # strangely formatted value that looks like (0,)
    if not err[0]:
        err = comp.JoinDomainOrWorkgroup(Name=workgroup)
        if not err[0]:
            ret = {'Workgroup': workgroup,
                   'Restart': False}
            if restart:
                ret['Restart'] = reboot()

            return ret
        else:
            log.error(_lookup_error(err[0]))
            log.error('Failed to join the computer to {0}'.format(workgroup))
            return False
    else:
        log.error(_lookup_error(err[0]))
        log.error('Failed to unjoin computer from {0}'.format(status['Domain']))
        return False


def get_domain_workgroup():
    '''
    Get the domain or workgroup the computer belongs to.

    .. versionadded:: 2015.5.7
    .. versionadded:: 2015.8.2

    :return: The name of the domain or workgroup
    :rtype: str

    '''
    pythoncom.CoInitialize()
    c = wmi.WMI()
    for computer in c.Win32_ComputerSystem():
        if computer.PartOfDomain:
            return {'Domain': computer.Domain}
        else:
            return {'Workgroup': computer.Domain}


def _get_date_time_format(dt_string):
    '''
    Function that detects the date/time format for the string passed.

    :param str dt_string:
        A date/time string

    :return: The format of the passed dt_string
    :rtype: str
    '''
    valid_formats = [
        '%I:%M:%S %p',
        '%I:%M %p',
        '%H:%M:%S',
        '%H:%M',
        '%Y-%m-%d',
        '%m-%d-%y',
        '%m-%d-%Y',
        '%m/%d/%y',
        '%m/%d/%Y',
        '%Y/%m/%d'
    ]
    for dt_format in valid_formats:
        try:
            datetime.strptime(dt_string, dt_format)
            return dt_format
        except ValueError:
            continue
    return False


def get_system_time():
    '''
    Get the system time.

    :return: Returns the system time in HH:MM AM/PM format.
    :rtype: str
    '''
    return datetime.strftime(datetime.now(), "%I:%M %p")


def set_system_time(newtime):
    '''
    Set the system time.

    :param str newtime:
        The time to set. Can be any of the following formats.
        - HH:MM:SS AM/PM
        - HH:MM AM/PM
        - HH:MM:SS (24 hour)
        - HH:MM (24 hour)

    :return: Returns True if successful. Otherwise False.
    :rtype: bool
    '''
    # Parse time values from new time
    time_format = _get_date_time_format(newtime)
    dt_obj = datetime.strptime(newtime, time_format)

    # Set time using set_system_date_time()
    return set_system_date_time(hours=int(dt_obj.strftime('%H')),
                                minutes=int(dt_obj.strftime('%M')),
                                seconds=int(dt_obj.strftime('%S')))


def set_system_date_time(years=None,
                         months=None,
                         days=None,
                         hours=None,
                         minutes=None,
                         seconds=None):
    '''
    Set the system date and time. Each argument is an element of the date, but
    not required. If an element is not passed, the current system value for that
    element will be used. For example, if you don't pass the year, the current
    system year will be used. (Used by set_system_date and set_system_time)

    :param int years: Years digit, ie: 2015
    :param int months: Months digit: 1 - 12
    :param int days: Days digit: 1 - 31
    :param int hours: Hours digit: 0 - 23
    :param int minutes: Minutes digit: 0 - 59
    :param int seconds: Seconds digit: 0 - 59

    :return: True if successful. Otherwise False.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_system_date_ time 2015 5 12 11 37 53
    '''
    # Get the current date/time
    try:
        date_time = win32api.GetLocalTime()
    except win32api.error as exc:
        (number, context, message) = exc
        log.error('Failed to get local time')
        log.error('nbr: {0}'.format(number))
        log.error('ctx: {0}'.format(context))
        log.error('msg: {0}'.format(message))
        return False

    # Check for passed values. If not passed, use current values
    if not years:
        years = date_time[0]
    if not months:
        months = date_time[1]
    if not days:
        days = date_time[3]
    if not hours:
        hours = date_time[4]
    if not minutes:
        minutes = date_time[5]
    if not seconds:
        seconds = date_time[6]

    # Create the time tuple to be passed to SetLocalTime, including day_of_week
    time_tuple = (years, months, days, hours, minutes, seconds, 0)

    try:
        win32api.SetLocalTime(time_tuple)
    except win32api.error as exc:
        (number, context, message) = exc
        log.error('Failed to set local time')
        log.error('nbr: {0}'.format(number))
        log.error('ctx: {0}'.format(context))
        log.error('msg: {0}'.format(message))
        return False

    return True


def get_system_date():
    '''
    Get the Windows system date

    :return: Returns the system date.
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_system_date
    '''
    return datetime.strftime(datetime.now(), "%a %m/%d/%Y")


def set_system_date(newdate):
    '''
    Set the Windows system date. Use <mm-dd-yy> format for the date.

    :param str newdate:
        The date to set. Can be any of the following formats
        - YYYY-MM-DD
        - MM-DD-YYYY
        - MM-DD-YY
        - MM/DD/YYYY
        - MM/DD/YY
        - YYYY/MM/DD

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_system_date '03-28-13'
    '''
    # Parse time values from new time
    date_format = _get_date_time_format(newdate)
    dt_obj = datetime.strptime(newdate, date_format)

    # Set time using set_system_date_time()
    return set_system_date_time(years=int(dt_obj.strftime('%Y')),
                                months=int(dt_obj.strftime('%m')),
                                days=int(dt_obj.strftime('%d')))


def start_time_service():
    '''
    Start the Windows time service

    :return: True if successful. Otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.start_time_service
    '''
    return __salt__['service.start']('w32time')


def stop_time_service():
    '''
    Stop the Windows time service

    :return: True if successful. Otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.stop_time_service
    '''
    return __salt__['service.stop']('w32time')
