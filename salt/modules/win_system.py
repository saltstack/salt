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
import time
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
    return (False, "Module win_system: module only works on Windows systems")


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
    # cmd = ['init', runlevel]
    # ret = __salt__['cmd.run'](cmd, python_shell=False)
    # return ret

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


def reboot(timeout=5, in_seconds=False, wait_for_reboot=False):
    '''
    Reboot a running system.

    :param int timeout:
        Number of minutes/seconds before rebooting the system. Minutes vs
        seconds depends on the value of ``in_seconds``.
        Default is 5 minutes.

    :param bool in_seconds:
        Whether to treat timeout as seconds or minutes.

        .. versionadded:: 2015.8.0

    :param bool wait_for_reboot:

        Sleeps for timeout + 30 seconds after reboot has been initiated.
        This is useful for use in a highstate for example where
        you have many states that could be ran after this one. Which you don't want
        to start until after the restart i.e You could end up with a half finished state.

        .. versionadded:: 2015.8.0

    :return: True if successful
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.reboot 5
        salt '*' system.reboot 5 True
    '''

    ret = shutdown(timeout=timeout, reboot=True, in_seconds=in_seconds)

    if wait_for_reboot:
        seconds = _convert_minutes_seconds(timeout, in_seconds)
        time.sleep(seconds + 30)

    return ret


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

    :return:
        Returns the pending name if pending restart. Returns none if not pending
        restart.

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_pending_computer_name
    '''
    current = get_computer_name()
    pending = read_value('HKLM',
                         r'SYSTEM\CurrentControlSet\Services\Tcpip\Parameters',
                         'NV Hostname')['vdata']
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
    name = win32api.GetComputerNameEx(win32con.ComputerNamePhysicalDnsHostname)
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
    os_type = {1: 'Work Station',
               2: 'Domain Controller',
               3: 'Server'}
    pythoncom.CoInitialize()
    c = wmi.WMI()
    system = c.Win32_OperatingSystem()[0]
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
    system = c.Win32_ComputerSystem()[0]
    ret.update({'hardware_manufacturer': system.Manufacturer,
                'hardware_model': system.Model,
                'processors': system.NumberOfProcessors,
                'processors_logical': system.NumberOfLogicalProcessors,
                'system_type': system.SystemType})
    system = c.Win32_BIOS()[0]
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
    :return:
        Returns the computer description if found. Otherwise returns False

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_computer_desc
    '''
    desc = get_system_info()['description']
    return desc if desc else False


get_computer_description = salt.utils.alias_function(get_computer_desc, 'get_computer_description')


def get_hostname():
    '''
    .. versionadded:: 2016.3.0

    Get the hostname of the windows minion

    :return:
        Returns the hostname of the windows minion

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.get_hostname
    '''
    cmd = 'wmic computersystem get name'
    ret = __salt__['cmd.run'](cmd=cmd)
    _, hostname = ret.split("\n")
    return hostname


def set_hostname(hostname):
    '''
    .. versionadded:: 2016.3.0

    Set the hostname of the windows minion, requires a restart before this
    will be updated.

    :param str hostname:
        The hostname to set

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' system.set_hostname newhostname
    '''
    curr_hostname = get_hostname()
    cmd = "wmic computersystem where name='{0}' call rename name='{1}'".format(curr_hostname, hostname)
    ret = __salt__['cmd.run'](cmd=cmd)

    return "successful" in ret


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

        .. versionadded:: 2015.8.2/2015.5.7

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
    NETSETUP_JOIN_WITH_NEW_NAME = 0x400

    join_options = 0x0
    join_options |= NETSETUP_JOIN_DOMAIN
    join_options |= NETSETUP_DOMAIN_JOIN_IF_JOINED
    join_options |= NETSETUP_JOIN_WITH_NEW_NAME
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

        .. versionadded:: 2015.8.2/2015.5.7

    :param bool disable:
        Disable the user account in Active Directory. True to disable.

    :param bool restart: Restart the computer after successful unjoin

        .. versionadded:: 2015.8.2/2015.5.7

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
    # Get date/time object from newtime
    dt_obj = salt.utils.date_cast(newtime)

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
    # Get date/time object from newdate
    dt_obj = salt.utils.date_cast(newdate)

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


def get_pending_component_servicing():
    '''
    Determine whether there are pending Component Based Servicing tasks that require a reboot.

    :return: A boolean representing whether there are pending Component Based Servicing tasks.
    :rtype: bool

    .. versionadded:: Carbon

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_pending_component_servicing
    '''
    vname = '(Default)'
    key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'

    reg_ret = read_value('HKLM', key, vname)

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

    :return: A boolean representing whether there is a pending domain join action.
    :rtype: bool

    .. versionadded:: Carbon

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

    avoid_reg_ret = read_value('HKLM', avoid_key, vname)

    if avoid_reg_ret['success']:
        log.debug('Found key: %s', avoid_key)
        return True
    else:
        log.debug('Unable to access key: %s', avoid_key)

    join_reg_ret = read_value('HKLM', join_key, vname)

    if join_reg_ret['success']:
        log.debug('Found key: %s', join_key)
        return True
    else:
        log.debug('Unable to access key: %s', join_key)
    return False


def get_pending_file_rename():
    '''
    Determine whether there are pending file rename operations that require a reboot.

    :return: A boolean representing whether there are pending file rename operations.
    :rtype: bool

    .. versionadded:: Carbon

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_pending_file_rename
    '''
    vnames = ('PendingFileRenameOperations', 'PendingFileRenameOperations2')
    key = r'SYSTEM\CurrentControlSet\Control\Session Manager'

    # If any of the value names exist and have value data set,
    # then a reboot is pending.

    for vname in vnames:
        reg_ret = read_value('HKLM', key, vname)

        if reg_ret['success']:
            log.debug('Found key: %s', key)

            if reg_ret['vdata'] and (reg_ret['vdata'] != '(value not set)'):
                return True
        else:
            log.debug('Unable to access key: %s', key)
    return False


def get_pending_servermanager():
    '''
    Determine whether there are pending Server Manager tasks that require a reboot.

    :return: A boolean representing whether there are pending Server Manager tasks.
    :rtype: bool

    .. versionadded:: Carbon

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_pending_servermanager
    '''
    vname = 'CurrentRebootAttempts'
    key = r'SOFTWARE\Microsoft\ServerManager'

    # There are situations where it's possible to have '(value not set)' as
    # the value data, and since an actual reboot wont be pending in that
    # instance, just catch instances where we try unsuccessfully to cast as int.

    reg_ret = read_value('HKLM', key, vname)

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

    :return: A boolean representing whether there are pending updates.
    :rtype: bool

    .. versionadded:: Carbon

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_pending_update
    '''
    vname = '(Default)'
    key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'

    reg_ret = read_value('HKLM', key, vname)

    # So long as the registry key exists, a reboot is pending.
    if reg_ret['success']:
        log.debug('Found key: %s', key)
        return True
    else:
        log.debug('Unable to access key: %s', key)
    return False


def get_pending_reboot():
    '''
    Determine whether there is a reboot pending.

    :return: A boolean representing whether reboots are pending.
    :rtype: bool

    .. versionadded:: Carbon

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_pending_reboot
    '''

    # Order the checks for reboot pending in most to least likely.
    checks = (get_pending_update, get_pending_file_rename, get_pending_servermanager,
              get_pending_component_servicing, get_pending_computer_name,
              get_pending_domain_join)

    for check in checks:
        if check():
            return True

    return False
