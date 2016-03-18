# -*- coding: utf-8 -*-
'''
.. versionadded:: 2016.3.0

Manage Mac OSX local directory passwords and policies.

Note that it is usually better to apply password policies through the creation
of a configuration profile.
'''
# Authentication concepts reference:
# https://developer.apple.com/library/mac/documentation/Networking/Conceptual/Open_Directory/openDirectoryConcepts/openDirectoryConcepts.html#//apple_ref/doc/uid/TP40000917-CH3-CIFCAIBB

from __future__ import absolute_import
from datetime import datetime
import pwd

# Import salt libs
import salt.utils
import logging
import salt.utils.mac_utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)  # Start logging

__virtualname__ = 'shadow'


def __virtual__():
    # Is this os x?
    if not salt.utils.is_darwin():
        return False, 'Not Darwin'

    return __virtualname__


def _get_account_policy(name):
    '''
    Get the entire accountPolicy and return it as a dictionary
    For use by this module only

    Args:
        name: username

    Returns:
        a dictionary containing all values for the accountPolicy
    '''
    cmd = 'pwpolicy -u {0} -getpolicy'.format(name)
    ret = salt.utils.mac_utils.execute_return_result(cmd)

    try:
        policy_list = ret.split('\n')[1].split(' ')
        policy_dict = {}
        for policy in policy_list:
            if '=' in policy:
                key, value = policy.split('=')
                policy_dict[key] = value
        return policy_dict
    except IndexError:
        return 'Value not found'


def _convert_to_datetime(unix_timestamp):
    try:
        unix_timestamp = float(unix_timestamp)
        return datetime.fromtimestamp(unix_timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return 'Invalid Timestamp'


def info(name):
    '''
    Return information for the specified user

    :param str name: the username

    :return: A dictionary containing the user's shadow information
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.info admin
    '''
    try:
        data = pwd.getpwnam(name)
        return {'name': data.pw_name,
                'passwd': data.pw_passwd,
                'account_created': get_account_created(name),
                'login_failed_count': get_login_failed_count(name),
                'login_failed_last': get_login_failed_last(name),
                'lstchg': get_last_change(name),
                'max': get_maxdays(name),
                'expire': get_expire(name),
                'change': get_change(name),
                'min': 'Unavailable',
                'warn': 'Unavailable',
                'inact': 'Unavailable'}

    except KeyError:
        log.debug('User not found: {0}'.format(name))
        return {'name': '',
                'passwd': '',
                'account_created': '',
                'login_failed_count': '',
                'login_failed_last': '',
                'lstchg': '',
                'max': '',
                'expire': '',
                'change': '',
                'min': '',
                'warn': '',
                'inact': ''}


def get_account_created(name):
    '''
    Get the date/time the account was created

    :param str name: the username of the account

    :return: the date/time the account was created (yyyy-mm-dd hh:mm:ss)
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_account_created admin
    '''
    try:
        pwd.getpwnam(name)
    except KeyError:
        log.debug('User not found: {0}'.format(name))
        raise CommandExecutionError('User not found: {0}'.format(name))

    cmd = 'dscl . -readpl /Users/{0} ' \
          'accountPolicyData {1}'.format(name, 'creationTime')
    ret = salt.utils.mac_utils.execute_return_result(cmd)

    unix_timestamp = salt.utils.mac_utils.parse_return(ret)

    date_text = _convert_to_datetime(unix_timestamp)

    return date_text


def get_last_change(name):
    '''
    Get the date/time the account was changed

    :param str name: the username of the account

    :return: the date/time the account was modified (yyyy-mm-dd hh:mm:ss)
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_last_change admin
    '''
    try:
        pwd.getpwnam(name)
    except KeyError:
        log.debug('User not found: {0}'.format(name))
        raise CommandExecutionError('User not found: {0}'.format(name))

    cmd = 'dscl . -readpl /Users/{0} ' \
          'accountPolicyData {1}'.format(name, 'passwordLastSetTime')
    ret = salt.utils.mac_utils.execute_return_result(cmd)

    unix_timestamp = salt.utils.mac_utils.parse_return(ret)

    date_text = _convert_to_datetime(unix_timestamp)

    return date_text


def get_login_failed_count(name):
    '''
    Get the the number of failed login attempts

    :param str name: the username of the account

    :return: The number of failed login attempts
    :rtype: int

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_login_failed_count admin
    '''
    try:
        pwd.getpwnam(name)
    except KeyError:
        log.debug('User not found: {0}'.format(name))
        raise CommandExecutionError('User not found: {0}'.format(name))

    cmd = 'dscl . -readpl /Users/{0} ' \
          'accountPolicyData {1}'.format(name, 'failedLoginCount')
    ret = salt.utils.mac_utils.execute_return_result(cmd)

    return salt.utils.mac_utils.parse_return(ret)


def get_login_failed_last(name):
    '''
    Get the date/time of the last failed login attempt

    :param str name: the username of the account

    :return: the date/time of the last failed login attempt on this account
    (yyyy-mm-dd hh:mm:ss)
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_login_failed_last admin
    '''
    try:
        pwd.getpwnam(name)
    except KeyError:
        log.debug('User not found: {0}'.format(name))
        raise CommandExecutionError('User not found: {0}'.format(name))

    cmd = 'dscl . -readpl /Users/{0} ' \
          'accountPolicyData {1}'.format(name, 'failedLoginTimestamp')
    ret = salt.utils.mac_utils.execute_return_result(cmd)

    unix_timestamp = salt.utils.mac_utils.parse_return(ret)

    date_text = _convert_to_datetime(unix_timestamp)

    return date_text


def set_maxdays(name, days):
    '''
    Set the maximum age of the password in days

    :param str name: the username of the account

    :param int days: the maximum age of the account in days

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_maxdays admin 90
    '''
    try:
        pwd.getpwnam(name)
    except KeyError:
        log.debug('User not found: {0}'.format(name))
        raise CommandExecutionError('User not found: {0}'.format(name))

    minutes = days * 24 * 60

    cmd = 'pwpolicy -u {0} -setpolicy ' \
          'maxMinutesUntilChangePassword={1}'.format(name, minutes)
    ret = salt.utils.mac_utils.execute_return_result(cmd)

    return get_maxdays(name) == days


def get_maxdays(name):
    '''
    Get the maximum age of the password

    :param str name: the username of the account

    :return: the maximum age of the password in days
    :rtype: int

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_maxdays admin 90
    '''
    try:
        pwd.getpwnam(name)
    except KeyError:
        log.debug('User not found: {0}'.format(name))
        raise CommandExecutionError('User not found: {0}'.format(name))

    policies = _get_account_policy(name)

    if 'maxMinutesUntilChangePassword' in policies:
        max_minutes = policies['maxMinutesUntilChangePassword']
        return int(max_minutes) / 24 / 60

    return 0


def set_mindays(name, days):
    '''
    Set the minimum password age in days. Not available in OS X.
    '''
    return False


def set_inactdays(name, days):
    '''
    Set the number if inactive days before the account is locked. Not available
    in OS X.
    '''
    return False


def set_warndays(name, days):
    '''
    Set the number of days before the password expires that the user will start
    to see a warning. Not available in OS X.
    '''
    return False


def set_change(name, date):
    '''
    Sets the date on which the password expires. The user will be required to
    change their password. Format is mm/dd/yyyy

    :param str name: the name of the user account

    :param date date: the date the password will expire. Must be in mm/dd/yyyy
    format.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_change username 09/21/2016
    '''
    try:
        pwd.getpwnam(name)
    except KeyError:
        log.debug('User not found: {0}'.format(name))
        raise CommandExecutionError('User not found: {0}'.format(name))

    cmd = 'pwpolicy -u {0} -setpolicy "usingExpirationDate=1 ' \
          'expirationDateGMT={1}"'.format(name, date)
    salt.utils.mac_utils.execute_return_result(cmd)

    return get_change(name) == date


def get_change(name):
    '''
    Gets the date on which the password expires.

    :param str name: the name of the user account

    :return: The date the password will expire
    :rtype: str
    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_change username
    '''
    try:
        pwd.getpwnam(name)
    except KeyError:
        log.debug('User not found: {0}'.format(name))
        raise CommandExecutionError('User not found: {0}'.format(name))

    policies = _get_account_policy(name)

    if 'expirationDateGMT' in policies:
        return policies['expirationDateGMT']

    return 'Value not set'


def set_expire(name, date):
    '''
    Sets the date on which the account expires. The user will not be able to
    login after this date. Date format is mm/dd/yyyy

    :param str name: the name of the user account

    :param datetime date: the date the account will expire. Format must be
    mm/dd/yyyy

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_expire username 07/23/2015
    '''
    try:
        pwd.getpwnam(name)
    except KeyError:
        log.debug('User not found: {0}'.format(name))
        raise CommandExecutionError('User not found: {0}'.format(name))

    cmd = 'pwpolicy -u {0} -setpolicy "usingHardExpirationDate=1 ' \
          'hardExpireDateGMT={1}"'.format(name, date)

    salt.utils.mac_utils.execute_return_result(cmd)

    return get_expire(name) == date


def get_expire(name):
    '''
    Gets the date on which the account expires.

    :param str name: the name of the user account

    :return: the date the account expires
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_expire username
    '''
    try:
        pwd.getpwnam(name)
    except KeyError:
        log.debug('User not found: {0}'.format(name))
        raise CommandExecutionError('User not found: {0}'.format(name))

    policies = _get_account_policy(name)

    if 'hardExpireDateGMT' in policies:
        return policies['hardExpireDateGMT']

    return 'Value not set'


def del_password(name):
    '''
    Deletes the account password

    :param str name: The user name of the account

    :return: True if successful, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.del_password username
    '''
    try:
        pwd.getpwnam(name)
    except KeyError:
        log.debug('User not found: {0}'.format(name))
        raise CommandExecutionError('User not found: {0}'.format(name))

    # This removes the password
    cmd = "dscl . -passwd /Users/{0} ''".format(name)

    salt.utils.mac_utils.execute_return_result(cmd)

    # This is so it looks right in shadow.info
    cmd = "dscl . -create /Users/{0} Password '*'".format(name)
    salt.utils.mac_utils.execute_return_success(cmd)

    return info(name)['passwd'] == '*'


def set_password(name, password):
    '''
    Set the password for a named user (insecure, the password will be in the
    process list while the command is running).

    :param str name: The name of the local user, which is assumed to be in the
    local directory service.

    :param str password: The plaintext password to set

    :return: True if successful, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' mac_shadow.set_password macuser macpassword
    '''
    try:
        pwd.getpwnam(name)
    except KeyError:
        log.debug('User not found: {0}'.format(name))
        raise CommandExecutionError('User not found: {0}'.format(name))

    cmd = "dscl . -passwd /Users/{0} '{1}'".format(name, password)
    salt.utils.mac_utils.execute_return_success(cmd)

    return True
