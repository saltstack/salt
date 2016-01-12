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

# Import salt libs
import salt.utils
import logging

log = logging.getLogger(__name__)  # Start logging

__virtualname__ = 'shadow'


def __virtual__():
    # Is this os x?
    if not salt.utils.is_darwin():
        return False, 'Not Darwin'

    return __virtualname__


def _run_parse_return_value(cmd):
    '''
    Execute the command, parse the return, return the value
    For use by this module only

    Args:
        cmd: a dscl command to run

    Returns:
        the value found in the command

    '''
    ret = __salt__['cmd.run'](cmd)
    if ': ' in ret:
        value = ret.split(': ')[1]
        return value
    if ':\n' in ret:
        value = ret.split(':\n')[1]
        return value
    return ret


def _get_dscl_data_value(name, key):
    '''
    Return the value for a key in the user's plist file
    For use by this module only

    Args:
        name: username
        key: plist key

    Returns:
        the value contained within the key
    '''
    cmd = 'dscl . -read /Users/{0} {1}'.format(name, key)
    return _run_parse_return_value(cmd)


def _get_account_policy_data_value(name, key):
    '''
    Return the value for a key in the accountPolicy section of the user's plist
    file
    For use by this module only

    Args:
        name: username
        key: accountPolicy key

    Returns:
        the value contained within the key
    '''
    cmd = 'dscl . -readpl /Users/{0} accountPolicyData {1}'.format(name, key)
    return _run_parse_return_value(cmd)


def _get_account_policy(name):
    '''
    Get the entire accountPolicy
    For use by this module only

    Args:
        name: username

    Returns:
        a dictionary containing all values for the accountPolicy
    '''
    cmd = 'pwpolicy -u {0} -getpolicy'.format(name)
    ret = __salt__['cmd.run'](cmd)
    if ret and 'Error:' not in ret:
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
    else:
        return 'Value not found'


def _convert_to_datetime(unix_timestamp):
    try:
        unix_timestamp = float(unix_timestamp)
        return datetime.fromtimestamp(unix_timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return 'Value not set'


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
    ret = {}
    ret['name'] = _get_dscl_data_value(name, 'name')
    ret['passwd'] = _get_dscl_data_value(name, 'passwd')

    ret['account_created'] = get_account_created(name)
    ret['login_failed_count'] = _get_account_policy_data_value(name, 'failedLoginCount')
    ret['login_failed_last'] = get_login_failed_last(name)
    ret['lstchg'] = get_last_change(name)

    ret['max'] = get_maxdays(name)
    ret['expire'] = get_expire(name)
    ret['change'] = get_change(name)
    ret['min'] = 'Unavailable'
    ret['warn'] = 'Unavailable'
    ret['inact'] = 'Unavailable'

    return ret


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
    unix_timestamp = _get_account_policy_data_value(name, 'creationTime')
    return _convert_to_datetime(unix_timestamp)


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
    unix_timestamp = _get_account_policy_data_value(name, 'passwordLastSetTime')
    return _convert_to_datetime(unix_timestamp)


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
    unix_timestamp = _get_account_policy_data_value(name, 'failedLoginTimestamp')
    return _convert_to_datetime(unix_timestamp)


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
    minutes = days * 24 * 60
    cmd = 'pwpolicy -u {0} -setpolicy ' \
          'maxMinutesUntilChangePassword={1}'.format(name, minutes)
    __salt__['cmd.run'](cmd)

    new = get_maxdays(name)

    return new == days


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
    policies = _get_account_policy(name)

    if 'maxMinutesUntilChangePassword' in policies:
        max_minutes = policies['maxMinutesUntilChangePassword']
        return int(max_minutes) / 24 / 60
    else:
        return 'Value not set'


def set_mindays(name, days):
    '''
    Set the minimum password age in days. Not available in OS X.
    '''
    return False, 'not available on OS X'


def set_inactdays(name, days):
    '''
    Set the number if inactive days before the account is locked. Not available
    in OS X.
    '''
    return False, 'not available on OS X'


def set_warndays(name, days):
    '''
    Set the number of days before the password expires that the user will start
    to see a warning. Not available in OS X.
    '''
    return False, 'not available on OS X'


def set_change(name, date):
    '''
    Sets the date on which the password expires. The user will be required to
    change their password. Format is mm/dd/yy

    :param str name: the name of the user account

    :param date date: the date the password will expire. Must be in mm/dd/yy
    format.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_change username 09/21/16
    '''
    cmd = 'pwpolicy -u {0} -setpolicy "usingExpirationDate=1 ' \
          'expirationDateGMT={1}"'.format(name, date)
    __salt__['cmd.run'](cmd)

    new = get_change(name)

    return new == date


def get_change(name):
    '''
    Gets the date on which the password expires.

    :param str name: the name of the user account

    :return: The date the password will expire
    :rtype: datetime
    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_change username
    '''
    policies = _get_account_policy(name)
    if 'expirationDateGMT' in policies:
        return policies['expirationDateGMT']
    else:
        return 'Value not set'


def set_expire(name, date):
    '''
    Sets the date on which the account expires. The user will not be able to
    login after this date. Date format is mm/dd/yy

    :param str name: the name of the user account

    :param datetime date: the date the account will expire. Format must be
    mm/dd/yy

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_expire username 07/23/15
    '''
    cmd = 'pwpolicy -u {0} -setpolicy "usingHardExpirationDate=1 ' \
          'hardExpireDateGMT={1}"'.format(name, date)
    __salt__['cmd.run'](cmd)

    new = get_expire(name)

    return new == date


def get_expire(name):
    '''
    Gets the date on which the account expires.

    :param str name: the name of the user account

    :return: the date the account expires

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_expire username
    '''
    policies = _get_account_policy(name)
    if 'hardExpireDateGMT' in policies:
        return policies['hardExpireDateGMT']
    else:
        return 'Value not set'


def del_password(name):
    '''
    Deletes the account password

    :param str name: The user name of the account

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.del_password username
    '''
    # This removes the password
    cmd = "dscl . -passwd /Users/{0} ''".format(name)
    success = __salt__['cmd.retcode'](cmd)
    if success:
        return False, 'Delete password failed'

    # This is so it looks right in shadow.info
    cmd = "dscl . -create /Users/{0} Password '*'".format(name)
    __salt__['cmd.retcode'](cmd)

    new = _get_dscl_data_value(name, 'passwd')

    return new == '*'


def set_password(name, password):
    '''
    Set the password for a named user (insecure, the password will be in the
    process list while the command is running).

    :param str name: The name of the local user, which is assumed to be in the
    local directory service.

    :param str password: The plaintext password to set

    CLI Example:

    .. code-block:: bash

        salt '*' mac_shadow.set_password macuser macpassword
    '''

    cmd = "dscl . -passwd /Users/{0} '{1}'".format(name, password)
    ret = __salt__['cmd.retcode'](cmd)
    if ret:
        return False
    else:
        return True
