# -*- coding: utf-8 -*-
'''
Module for managing windows systems.

:depends:
    - pythoncom
    - pywintypes
    - win32api
    - win32con
    - win32net
    - wmi

Support for reboot, shutdown, etc
'''
from __future__ import absolute_import

# Import python libs
import logging
import time
import ctypes
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
import salt.ext.six as six

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'system'


def __virtual__():
    '''
    Only works on Windows Systems with Win32 Modules
    '''
    if not salt.utils.is_windows():
        return False, 'Module win_system: Requires Windows'

    if not HAS_WIN32NET_MODS:
        return False, 'Module win_system: Missing win32 modules'

    return __virtualname__


def _convert_minutes_seconds(timeout, in_seconds=False):
    '''
    convert timeout to seconds
    '''
    return timeout if in_seconds else timeout*60


def _convert_date_time_string(dt_string):
    '''
    convert string to date time object
    '''
    dt_string = dt_string.split('.')[0]
    dt_obj = datetime.strptime(dt_string, '%Y%m%d%H%M%S')
    return dt_obj.strftime('%Y-%m-%d %H:%M:%S')


def _to_unicode(instr):
    '''
    Converts from current users character encoding to unicode.
    When instr has a value of None, the return value of the function
    will also be None.
    '''
    if instr is None or isinstance(instr, six.text_type):
        return instr
    else:
        return six.text_type(instr, 'utf8')


def halt(timeout=5, in_seconds=False):
    '''
    Halt a running system.

    Args:
        timeout (int): Number of seconds before halting the system. Default is
        5 seconds.

        in_seconds (bool): Whether to treat timeout as seconds or minutes.

            .. versionadded:: 2015.8.0

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' system.halt 5
    '''
    return shutdown(timeout=timeout, in_seconds=in_seconds)


def init(runlevel):  # pylint: disable=unused-argument
    '''
    Change the system runlevel on sysV compatible systems

    CLI Example:

    .. code-block:: bash

        salt '*' system.init 3
    '''
    # cmd = ['init', runlevel]
    # ret = __salt__['cmd.run'](cmd, python_shell=False)
    # return ret

    # TODO: Create a mapping of runlevels to  # pylint: disable=fixme
    #       corresponding Windows actions

    return 'Not implemented on Windows at this time.'


def poweroff(timeout=5, in_seconds=False):
    '''
    Power off a running system.

    Args:
        timeout (int): Number of seconds before powering off the system. Default
            is 5 seconds.

        in_seconds (bool): Whether to treat timeout as seconds or minutes.
            .. versionadded:: 2015.8.0

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' system.poweroff 5
    '''
    return shutdown(timeout=timeout, in_seconds=in_seconds)


def reboot(timeout=5, in_seconds=False, wait_for_reboot=False,  # pylint: disable=redefined-outer-name
           only_on_pending_reboot=False):
    '''
    Reboot a running system.

    Args:
        timeout (int): Number of minutes/seconds before rebooting the system.
            Minutes vs seconds depends on the value of ``in_seconds``. Default
            is 5 minutes.

        in_seconds (bool): Whether to treat timeout as seconds or minutes.

            .. versionadded:: 2015.8.0

        wait_for_reboot (bool): Sleeps for timeout + 30 seconds after reboot has
            been initiated. This may be useful for use in a highstate if a
            reboot should be performed and the return data of the highstate is
            not required. If return data is required, consider using the reboot
            state instead of this module.

            .. versionadded:: 2015.8.0

        only_on_pending_reboot (bool): If this is set to True, then the reboot
            will only proceed if the system reports a pending reboot. To
            optionally reboot in a highstate, consider using the reboot state
            instead of this module.

    Returns:
        bool: True if successful (a reboot will occur), otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' system.reboot 5
        salt '*' system.reboot 5 True

    As example of invoking this function from within a final housekeeping state
    is as follows:

    Example:

    .. code-block:: yaml

        final housekeeping:
           module.run:
              - name: system.reboot
              - only_on_pending_reboot: True
              - order: last
    '''

    ret = shutdown(timeout=timeout, reboot=True, in_seconds=in_seconds,
                   only_on_pending_reboot=only_on_pending_reboot)

    if wait_for_reboot:
        seconds = _convert_minutes_seconds(timeout, in_seconds)
        time.sleep(seconds + 30)

    return ret


def shutdown(message=None, timeout=5, force_close=True, reboot=False,  # pylint: disable=redefined-outer-name
             in_seconds=False, only_on_pending_reboot=False):
    '''
    Shutdown a running system.

    Args:
        message (str): A message to display to the user before shutting down.

        timeout (int): The length of time that the shutdown dialog box should be
            displayed, in seconds. While this dialog box is displayed, the
            shutdown can be stopped by the shutdown_abort function.

            If timeout is not zero, InitiateSystemShutdown displays a dialog box
            on the specified computer. The dialog box displays the name of the
            user who called the function, displays the message specified by the
            lpMessage parameter, and prompts the user to log off. The dialog box
            beeps when it is created and remains on top of other windows in the
            system. The dialog box can be moved but not closed. A timer counts
            down the remaining time before a forced shutdown.

            If timeout is zero, the computer shuts down without displaying the
            dialog box, and the shutdown cannot be stopped by shutdown_abort.

            Default is 5 minutes

        in_seconds (bool): Whether to treat timeout as seconds or minutes.

            .. versionadded:: 2015.8.0

        force_close (bool): True to force close all open applications. False
            displays a dialog box instructing the user to close the
            applications.

        reboot (bool): True restarts the computer immediately after shutdown.
            False caches to disk and safely powers down the system.

        only_on_pending_reboot (bool): If this is set to True, then the shutdown
            will only proceed if the system reports a pending reboot. To
            optionally shutdown in a highstate, consider using the shutdown
            state instead of this module.

    Returns:
        bool: True if successful (a shutdown or reboot will occur), otherwise
            False

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown 5
    '''
    if six.PY2:
        message = _to_unicode(message)

    timeout = _convert_minutes_seconds(timeout, in_seconds)

    if only_on_pending_reboot and not get_pending_reboot():
        return False

    if message and not isinstance(message, str):
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

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown_hard
    '''
    return shutdown(timeout=0)


def shutdown_abort():
    '''
    Abort a shutdown. Only available while the dialog box is being
    displayed to the user. Once the shutdown has initiated, it cannot be
    aborted.

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.shutdown_abort
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

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.lock
    '''
    return windll.user32.LockWorkStation()


def set_computer_name(name):
    '''
    Set the Windows computer name

    Args:
        name (str): The new name to give the computer. Requires a reboot to take
            effect.

    Returns:
        dict: Returns a dictionary containing the old and new names if
            successful. False if not.

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.set_computer_name 'DavesComputer'
    '''
    if six.PY2:
        name = _to_unicode(name)

    if windll.kernel32.SetComputerNameExW(
            win32con.ComputerNamePhysicalDnsHostname, name):
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

    Returns:
        str: The pending name if restart is pending, otherwise returns None.

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_pending_computer_name
    '''
    current = get_computer_name()
    pending = __salt__['reg.read_value'](
                'HKLM',
                r'SYSTEM\CurrentControlSet\Services\Tcpip\Parameters',
                'NV Hostname')['vdata']
    if pending:
        return pending if pending != current else None
    return False


def get_computer_name():
    '''
    Get the Windows computer name

    Returns:
        str: Returns the computer name if found. Otherwise returns False

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_computer_name
    '''
    name = win32api.GetComputerNameEx(win32con.ComputerNamePhysicalDnsHostname)
    return name if name else False


def set_computer_desc(desc=None):
    '''
    Set the Windows computer description

    Args:
        desc (str): The computer description

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.set_computer_desc 'This computer belongs to Dave!'
    '''
    if six.PY2:
        desc = _to_unicode(desc)

    # Make sure the system exists
    # Return an object containing current information array for the computer
    system_info = win32net.NetServerGetInfo(None, 101)

    # If desc is passed, decode it for unicode
    if desc is None:
        return False

    system_info['comment'] = desc

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


set_computer_description = salt.utils.alias_function(set_computer_desc, 'set_computer_description')  # pylint: disable=invalid-name


def get_system_info():
    '''
    Get system information.

    Returns:
        dict: Returns a Dictionary containing information about the system to
            include name, description, version, etc...

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_info
    '''
    os_type = {1: 'Work Station',
               2: 'Domain Controller',
               3: 'Server'}
    pythoncom.CoInitialize()
    conn = wmi.WMI()
    system = conn.Win32_OperatingSystem()[0]
    ret = {'name': get_computer_name(),
           'description': system.Description,
           'install_date': system.InstallDate,
           'last_boot': system.LastBootUpTime,
           'os_manufacturer': system.Manufacturer,
           'os_name': system.Caption,
           'users': system.NumberOfUsers,
           'organization': system.Organization,
           'os_architecture': system.OSArchitecture,
           'primary': system.Primary,
           'os_type': os_type[system.ProductType],
           'registered_user': system.RegisteredUser,
           'system_directory': system.SystemDirectory,
           'system_drive': system.SystemDrive,
           'os_version': system.Version,
           'windows_directory': system.WindowsDirectory}
    system = conn.Win32_ComputerSystem()[0]
    ret.update({'hardware_manufacturer': system.Manufacturer,
                'hardware_model': system.Model,
                'processors': system.NumberOfProcessors,
                'processors_logical': system.NumberOfLogicalProcessors,
                'system_type': system.SystemType})
    system = conn.Win32_BIOS()[0]
    ret.update({'hardware_serial': system.SerialNumber,
                'bios_manufacturer': system.Manufacturer,
                'bios_version': system.Version,
                'bios_details': system.BIOSVersion,
                'bios_caption': system.Caption,
                'bios_description': system.Description})
    ret['install_date'] = _convert_date_time_string(ret['install_date'])
    ret['last_boot'] = _convert_date_time_string(ret['last_boot'])
    return ret


def get_computer_desc():
    '''
    Get the Windows computer description

    Returns:
        str: The computer description if found, otherwise False

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_computer_desc
    '''
    desc = get_system_info()['description']
    return False if desc is None else desc


get_computer_description = salt.utils.alias_function(get_computer_desc, 'get_computer_description')  # pylint: disable=invalid-name


def get_hostname():
    '''
    .. versionadded:: 2016.3.0

    Get the hostname of the windows minion

    Returns:
        str: The hostname of the windows minion

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_hostname
    '''
    cmd = 'hostname'
    ret = __salt__['cmd.run'](cmd=cmd)
    return ret


def set_hostname(hostname):
    '''
    .. versionadded:: 2016.3.0

    Set the hostname of the windows minion, requires a restart before this
    will be updated.

    Args:
        hostname (str): The hostname to set

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.set_hostname newhostname
    '''
    curr_hostname = get_hostname()
    cmd = "wmic computersystem where name='{0}' call rename name='{1}'".format(curr_hostname, hostname)
    ret = __salt__['cmd.run'](cmd=cmd)

    return "successful" in ret


def join_domain(domain,
                username=None,
                password=None,
                account_ou=None,
                account_exists=False,
                restart=False):
    '''
    Join a computer to an Active Directory domain. Requires reboot.

    Args:
        domain (str): The domain to which the computer should be joined, e.g.
            ``example.com``

        username (str): Username of an account which is authorized to join
            computers to the specified domain. Need to be either fully qualified
            like ``user@domain.tld`` or simply ``user``

        password (str): Password of the specified user

        account_ou (str): The DN of the OU below which the account for this
            computer should be created when joining the domain, e.g.
            ``ou=computers,ou=departm_432,dc=my-company,dc=com``

        account_exists (bool): If set to ``True`` the computer will only join
            the domain if the account already exists. If set to ``False`` the
            computer account will be created if it does not exist, otherwise it
            will use the existing account. Default is False.

        restart (bool): Restarts the computer after a successful join

            .. versionadded:: 2015.8.2/2015.5.7

    Returns:
        dict: Dictionary if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.join_domain domain='domain.tld' \\
                         username='joinuser' password='joinpassword' \\
                         account_ou='ou=clients,ou=org,dc=domain,dc=tld' \\
                         account_exists=False, restart=True
    '''
    if six.PY2:
        domain = _to_unicode(domain)
        username = _to_unicode(username)
        password = _to_unicode(password)
        account_ou = _to_unicode(account_ou)

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

    NETSETUP_JOIN_DOMAIN = 0x1  # pylint: disable=invalid-name
    NETSETUP_ACCOUNT_CREATE = 0x2  # pylint: disable=invalid-name
    NETSETUP_DOMAIN_JOIN_IF_JOINED = 0x20  # pylint: disable=invalid-name
    NETSETUP_JOIN_WITH_NEW_NAME = 0x400  # pylint: disable=invalid-name

    join_options = 0x0
    join_options |= NETSETUP_JOIN_DOMAIN
    join_options |= NETSETUP_DOMAIN_JOIN_IF_JOINED
    join_options |= NETSETUP_JOIN_WITH_NEW_NAME
    if not account_exists:
        join_options |= NETSETUP_ACCOUNT_CREATE

    pythoncom.CoInitialize()
    conn = wmi.WMI()
    comp = conn.Win32_ComputerSystem()[0]
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

    log.error(win32api.FormatMessage(err[0]).rstrip())
    return False


def unjoin_domain(username=None,
                  password=None,
                  domain=None,
                  workgroup='WORKGROUP',
                  disable=False,
                  restart=False):
    r'''
    Unjoin a computer from an Active Directory Domain. Requires restart.

    Args:
        username (str): Username of an account which is authorized to manage
            computer accounts on the domain. Need to be fully qualified like
            ``user@domain.tld`` or ``domain.tld\user``. If domain not specified,
            the passed domain will be used. If computer account doesn't need to
            be disabled, can be None.

        password (str): Password of the specified user

        domain (str): The domain from which to unjoin the computer. Can be None.

        workgroup (str): The workgroup to join the computer to. Default is
            ``WORKGROUP``

            .. versionadded:: 2015.8.2/2015.5.7

        disable (bool): Disable the computer account in Active Directory. True
            to disable. Default is False

        restart (bool): Restart the computer after successful unjoin

            .. versionadded:: 2015.8.2/2015.5.7

    Returns:
        dict: Dictionary if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.unjoin_domain restart=True

        salt 'minion-id' system.unjoin_domain username='unjoinuser' \\
                         password='unjoinpassword' disable=True \\
                         restart=True
    '''
    if six.PY2:
        username = _to_unicode(username)
        password = _to_unicode(password)
        domain = _to_unicode(domain)

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

    NETSETUP_ACCT_DELETE = 0x4  # pylint: disable=invalid-name

    unjoin_options = 0x0
    if disable:
        unjoin_options |= NETSETUP_ACCT_DELETE

    pythoncom.CoInitialize()
    conn = wmi.WMI()
    comp = conn.Win32_ComputerSystem()[0]
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
            log.error(win32api.FormatMessage(err[0]).rstrip())
            log.error('Failed to join the computer to {0}'.format(workgroup))
            return False
    else:
        log.error(win32api.FormatMessage(err[0]).rstrip())
        log.error('Failed to unjoin computer from {0}'.format(status['Domain']))
        return False


def get_domain_workgroup():
    '''
    Get the domain or workgroup the computer belongs to.

    .. versionadded:: 2015.5.7
    .. versionadded:: 2015.8.2

    Returns:
        str: The name of the domain or workgroup

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_domain_workgroup
    '''
    pythoncom.CoInitialize()
    conn = wmi.WMI()
    for computer in conn.Win32_ComputerSystem():
        if computer.PartOfDomain:
            return {'Domain': computer.Domain}
        else:
            return {'Workgroup': computer.Domain}


def _try_parse_datetime(time_str, fmts):
    '''
    Attempts to parse the input time_str as a date.

    Args:
        time_str (str): A string representing the time

        fmts (list): A list of date format strings

    Returns:
        datetime: A datetime object if parsed properly, otherwise None
    '''
    result = None
    for fmt in fmts:
        try:
            result = datetime.strptime(time_str, fmt)
            break
        except ValueError:
            pass
    return result


def get_system_time():
    '''
    Get the system time.

    Returns:
        str: Returns the system time in HH:MM:SS AM/PM format.

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_system_time
    '''
    now = win32api.GetLocalTime()
    meridian = 'AM'
    hours = int(now[4])
    if hours == 12:
        meridian = 'PM'
    elif hours == 0:
        hours = 12
    elif hours > 12:
        hours = hours - 12
        meridian = 'PM'
    return '{0:02d}:{1:02d}:{2:02d} {3}'.format(hours, now[5], now[6], meridian)


def set_system_time(newtime):
    '''
    Set the system time.

    Args:
        newtime (str): The time to set. Can be any of the following formats.

            - HH:MM:SS AM/PM
            - HH:MM AM/PM
            - HH:MM:SS (24 hour)
            - HH:MM (24 hour)

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.set_system_time 12:01
    '''
    # Get date/time object from newtime
    fmts = ['%I:%M:%S %p', '%I:%M %p', '%H:%M:%S', '%H:%M']
    dt_obj = _try_parse_datetime(newtime, fmts)
    if dt_obj is None:
        return False

    # Set time using set_system_date_time()
    return set_system_date_time(hours=dt_obj.hour,
                                minutes=dt_obj.minute,
                                seconds=dt_obj.second)


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

    Args:
        years (int): Years digit, ie: 2015

        months (int): Months digit: 1 - 12

        days (int): Days digit: 1 - 31

        hours (int): Hours digit: 0 - 23

        minutes (int): Minutes digit: 0 - 59

        seconds (int): Seconds digit: 0 - 59

    Returns:
        bool: True if successful, otherwise False.

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
    if years is None:
        years = date_time[0]
    if months is None:
        months = date_time[1]
    if days is None:
        days = date_time[3]
    if hours is None:
        hours = date_time[4]
    if minutes is None:
        minutes = date_time[5]
    if seconds is None:
        seconds = date_time[6]

    try:
        class SYSTEMTIME(ctypes.Structure):
            _fields_ = [
                ('wYear', ctypes.c_int16),
                ('wMonth', ctypes.c_int16),
                ('wDayOfWeek', ctypes.c_int16),
                ('wDay', ctypes.c_int16),
                ('wHour', ctypes.c_int16),
                ('wMinute', ctypes.c_int16),
                ('wSecond', ctypes.c_int16),
                ('wMilliseconds', ctypes.c_int16)]
        system_time = SYSTEMTIME()
        system_time.wYear = int(years)
        system_time.wMonth = int(months)
        system_time.wDay = int(days)
        system_time.wHour = int(hours)
        system_time.wMinute = int(minutes)
        system_time.wSecond = int(seconds)
        system_time_ptr = ctypes.pointer(system_time)
        succeeded = ctypes.windll.kernel32.SetLocalTime(system_time_ptr)
        return succeeded is not 0
    except OSError:
        log.error('Failed to set local time')
        return False

    return True


def get_system_date():
    '''
    Get the Windows system date

    Returns:
        str: The system date

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_system_date
    '''
    now = win32api.GetLocalTime()
    return '{0:02d}/{1:02d}/{2:04d}'.format(now[1], now[3], now[0])


def set_system_date(newdate):
    '''
    Set the Windows system date. Use <mm-dd-yy> format for the date.

    Args:
        newdate (str): The date to set. Can be any of the following formats:

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
    fmts = ['%Y-%m-%d', '%m-%d-%Y', '%m-%d-%y',
            '%m/%d/%Y', '%m/%d/%y', '%Y/%m/%d']
    # Get date/time object from newdate
    dt_obj = _try_parse_datetime(newdate, fmts)
    if dt_obj is None:
        return False

    # Set time using set_system_date_time()
    return set_system_date_time(years=dt_obj.year,
                                months=dt_obj.month,
                                days=dt_obj.day)


def start_time_service():
    '''
    Start the Windows time service

    Returns:
        bool: True if successful, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt '*' system.start_time_service
    '''
    return __salt__['service.start']('w32time')


def stop_time_service():
    '''
    Stop the Windows time service

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' system.stop_time_service
    '''
    return __salt__['service.stop']('w32time')


def get_pending_component_servicing():
    '''
    Determine whether there are pending Component Based Servicing tasks that
    require a reboot.

    .. versionadded:: 2016.11.0

    Returns:
        bool: True if a reboot is pending, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_pending_component_servicing
    '''
    vname = '(Default)'
    key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'

    reg_ret = __salt__['reg.read_value']('HKLM', key, vname)

    # So long as the registry key exists, a reboot is pending.
    if reg_ret['success']:
        log.debug('Found key: %s', key)
        return True
    else:
        log.debug('Unable to access key: %s', key)
    return False


def get_pending_domain_join():
    '''
    Determine whether there is a pending domain join action that requires a reboot.

    .. versionadded:: 2016.11.0

    Returns:
        bool: True if a reboot is pending, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_pending_domain_join
    '''
    vname = '(Default)'
    base_key = r'SYSTEM\CurrentControlSet\Services\Netlogon'
    avoid_key = r'{0}\AvoidSpnSet'.format(base_key)
    join_key = r'{0}\JoinDomain'.format(base_key)

    # If either the avoid_key or join_key is present,
    # then there is a reboot pending.

    avoid_reg_ret = __salt__['reg.read_value']('HKLM', avoid_key, vname)

    if avoid_reg_ret['success']:
        log.debug('Found key: %s', avoid_key)
        return True
    else:
        log.debug('Unable to access key: %s', avoid_key)

    join_reg_ret = __salt__['reg.read_value']('HKLM', join_key, vname)

    if join_reg_ret['success']:
        log.debug('Found key: %s', join_key)
        return True
    else:
        log.debug('Unable to access key: %s', join_key)
    return False


def get_pending_file_rename():
    '''
    Determine whether there are pending file rename operations that require a
    reboot.

    .. versionadded:: 2016.11.0

    Returns:
        bool: True if a reboot is pending, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_pending_file_rename
    '''
    vnames = ('PendingFileRenameOperations', 'PendingFileRenameOperations2')
    key = r'SYSTEM\CurrentControlSet\Control\Session Manager'

    # If any of the value names exist and have value data set,
    # then a reboot is pending.

    for vname in vnames:
        reg_ret = __salt__['reg.read_value']('HKLM', key, vname)

        if reg_ret['success']:
            log.debug('Found key: %s', key)

            if reg_ret['vdata'] and (reg_ret['vdata'] != '(value not set)'):
                return True
        else:
            log.debug('Unable to access key: %s', key)
    return False


def get_pending_servermanager():
    '''
    Determine whether there are pending Server Manager tasks that require a
    reboot.

    .. versionadded:: 2016.11.0

    Returns:
        bool: True if a reboot is pending, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_pending_servermanager
    '''
    vname = 'CurrentRebootAttempts'
    key = r'SOFTWARE\Microsoft\ServerManager'

    # There are situations where it's possible to have '(value not set)' as
    # the value data, and since an actual reboot wont be pending in that
    # instance, just catch instances where we try unsuccessfully to cast as int.

    reg_ret = __salt__['reg.read_value']('HKLM', key, vname)

    if reg_ret['success']:
        log.debug('Found key: %s', key)

        try:
            if int(reg_ret['vdata']) > 0:
                return True
        except ValueError:
            pass
    else:
        log.debug('Unable to access key: %s', key)
    return False


def get_pending_update():
    '''
    Determine whether there are pending updates that require a reboot.

    .. versionadded:: 2016.11.0

    Returns:
        bool: True if a reboot is pending, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_pending_update
    '''
    vname = '(Default)'
    key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'

    reg_ret = __salt__['reg.read_value']('HKLM', key, vname)

    # So long as the registry key exists, a reboot is pending.
    if reg_ret['success']:
        log.debug('Found key: %s', key)
        return True
    else:
        log.debug('Unable to access key: %s', key)
    return False


MINION_VOLATILE_KEY = r'SYSTEM\CurrentControlSet\Services\salt-minion\Volatile-Data'


REBOOT_REQUIRED_NAME = 'Reboot required'


def set_reboot_required_witnessed():
    r'''
    This function is used to remember that an event indicating that a reboot is
    required was witnessed. This function relies on the salt-minion's ability to
    create the following volatile registry key in the *HKLM* hive:

       *SYSTEM\\CurrentControlSet\\Services\\salt-minion\\Volatile-Data*

    Because this registry key is volatile, it will not persist beyond the
    current boot session. Also, in the scope of this key, the name *'Reboot
    required'* will be assigned the value of *1*.

    (For the time being, this this function is being used whenever an install
    completes with exit code 3010 and this usage can be extended where
    appropriate in the future.)

    .. versionadded:: 2016.11.0

    Returns:
        bool: True if registry entry set successfuly, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_reboot_required_witnessed
    '''
    return __salt__['reg.set_value'](hive='HKLM',
                                     key=MINION_VOLATILE_KEY,
                                     volatile=True,
                                     vname=REBOOT_REQUIRED_NAME,
                                     vdata=1,
                                     vtype='REG_DWORD')


def get_reboot_required_witnessed():
    '''
    This tells us if, at any time during the current boot session the salt
    minion witnessed an event indicating that a reboot is required. (For the
    time being, this function will return True if an install completed with exit
    code 3010 during the current boot session and this usage can be extended
    where appropriate in the future)

    .. versionadded:: 2016.11.0

    Returns:
        bool: True if reboot required, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_reboot_required_witnessed

    '''
    value_dict = __salt__['reg.read_value'](hive='HKLM',
                                            key=MINION_VOLATILE_KEY,
                                            vname=REBOOT_REQUIRED_NAME)
    return value_dict['vdata'] == 1


def get_pending_reboot():
    '''
    Determine whether there is a reboot pending.

    .. versionadded:: 2016.11.0

    Returns:
        bool: True if pending reboot, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_pending_reboot
    '''

    # Order the checks for reboot pending in most to least likely.
    checks = (get_pending_update, get_pending_file_rename, get_pending_servermanager,
              get_pending_component_servicing,
              get_reboot_required_witnessed,
              get_pending_computer_name,
              get_pending_domain_join)

    for check in checks:
        if check():
            return True

    return False
