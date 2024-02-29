"""
Manage macOS local directory passwords and policies

.. versionadded:: 2016.3.0

Note that it is usually better to apply password policies through the creation
of a configuration profile.
"""
# Authentication concepts reference:
# https://developer.apple.com/library/mac/documentation/Networking/Conceptual/Open_Directory/openDirectoryConcepts/openDirectoryConcepts.html#//apple_ref/doc/uid/TP40000917-CH3-CIFCAIBB

import logging
from datetime import datetime

import salt.utils.mac_utils
import salt.utils.platform
from salt.exceptions import CommandExecutionError

try:
    import pwd

    HAS_PWD = True
except ImportError:
    HAS_PWD = False


log = logging.getLogger(__name__)  # Start logging

__virtualname__ = "shadow"


def __virtual__():
    # Is this macOS?
    if not salt.utils.platform.is_darwin():
        return False, "Not macOS"

    if HAS_PWD:
        return __virtualname__
    else:
        return (False, "The pwd module failed to load.")


def _get_account_policy(name):
    """
    Get the entire accountPolicy and return it as a dictionary. For use by this
    module only

    :param str name: The user name

    :return: a dictionary containing all values for the accountPolicy
    :rtype: dict

    :raises: CommandExecutionError on user not found or any other unknown error
    """

    cmd = f"pwpolicy -u {name} -getpolicy"
    try:
        ret = salt.utils.mac_utils.execute_return_result(cmd)
    except CommandExecutionError as exc:
        if f"Error: user <{name}> not found" in exc.strerror:
            raise CommandExecutionError(f"User not found: {name}")
        raise CommandExecutionError(f"Unknown error: {exc.strerror}")

    try:
        policy_list = ret.split("\n")[1].split(" ")
        policy_dict = {}
        for policy in policy_list:
            if "=" in policy:
                key, value = policy.split("=")
                policy_dict[key] = value
        return policy_dict
    except IndexError:
        return {}


def _set_account_policy(name, policy):
    """
    Set a value in the user accountPolicy. For use by this module only

    :param str name: The user name
    :param str policy: The policy to apply

    :return: True if success, otherwise False
    :rtype: bool

    :raises: CommandExecutionError on user not found or any other unknown error
    """
    cmd = f'pwpolicy -u {name} -setpolicy "{policy}"'

    try:
        return salt.utils.mac_utils.execute_return_success(cmd)
    except CommandExecutionError as exc:
        if f"Error: user <{name}> not found" in exc.strerror:
            raise CommandExecutionError(f"User not found: {name}")
        raise CommandExecutionError(f"Unknown error: {exc.strerror}")


def _get_account_policy_data_value(name, key):
    """
    Return the value for a key in the accountPolicy section of the user's plist
    file. For use by this module only

    :param str name: The username
    :param str key: The accountPolicy key

    :return: The value contained within the key
    :rtype: str

    :raises: CommandExecutionError on user not found or any other unknown error
    """
    cmd = f"dscl . -readpl /Users/{name} accountPolicyData {key}"
    try:
        ret = salt.utils.mac_utils.execute_return_result(cmd)
    except CommandExecutionError as exc:
        if "eDSUnknownNodeName" in exc.strerror:
            raise CommandExecutionError(f"User not found: {name}")
        if "eDSUnknownMatchType" in exc.strerror:
            raise CommandExecutionError(f"Value not found: {key}")
        raise CommandExecutionError(f"Unknown error: {exc.strerror}")

    return ret


def _convert_to_datetime(unix_timestamp):
    """
    Converts a unix timestamp to a human readable date/time

    :param float unix_timestamp: A unix timestamp

    :return: A date/time in the format YYYY-mm-dd HH:MM:SS
    :rtype: str
    """
    try:
        unix_timestamp = float(unix_timestamp)
        return datetime.fromtimestamp(unix_timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return "Invalid Timestamp"


def info(name):
    """
    Return information for the specified user

    :param str name: The username

    :return: A dictionary containing the user's shadow information
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.info admin
    """
    try:
        data = pwd.getpwnam(name)
        return {
            "name": data.pw_name,
            "passwd": data.pw_passwd,
            "account_created": get_account_created(name),
            "login_failed_count": get_login_failed_count(name),
            "login_failed_last": get_login_failed_last(name),
            "lstchg": get_last_change(name),
            "max": get_maxdays(name),
            "expire": get_expire(name),
            "change": get_change(name),
            "min": "Unavailable",
            "warn": "Unavailable",
            "inact": "Unavailable",
        }

    except KeyError:
        log.debug("User not found: %s", name)
        return {
            "name": "",
            "passwd": "",
            "account_created": "",
            "login_failed_count": "",
            "login_failed_last": "",
            "lstchg": "",
            "max": "",
            "expire": "",
            "change": "",
            "min": "",
            "warn": "",
            "inact": "",
        }


def get_account_created(name):
    """
    Get the date/time the account was created

    :param str name: The username of the account

    :return: The date/time the account was created (yyyy-mm-dd hh:mm:ss) or 0 if
        the value is not defined
    :rtype: str

    :raises: CommandExecutionError on user not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_account_created admin
    """
    try:
        ret = _get_account_policy_data_value(name, "creationTime")
    except CommandExecutionError as exc:
        if "Value not found" in exc.message:
            return "0"
        else:
            raise

    unix_timestamp = salt.utils.mac_utils.parse_return(ret)
    return _convert_to_datetime(unix_timestamp)


def get_last_change(name):
    """
    Get the date/time the account was changed

    :param str name: The username of the account

    :return: The date/time the account was modified (yyyy-mm-dd hh:mm:ss) or 0
        if the value is not defined
    :rtype: str

    :raises: CommandExecutionError on user not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_last_change admin
    """
    try:
        ret = _get_account_policy_data_value(name, "passwordLastSetTime")
    except CommandExecutionError as exc:
        if "Value not found" in exc.message:
            return "0"
        else:
            raise

    unix_timestamp = salt.utils.mac_utils.parse_return(ret)
    return _convert_to_datetime(unix_timestamp)


def get_login_failed_count(name):
    """
    Get the number of failed login attempts

    :param str name: The username of the account

    :return: The number of failed login attempts. 0 may mean there are no failed
        login attempts or the value is not defined
    :rtype: str

    :raises: CommandExecutionError on user not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_login_failed_count admin
    """
    try:
        ret = _get_account_policy_data_value(name, "failedLoginCount")
    except CommandExecutionError as exc:
        if "Value not found" in exc.message:
            return "0"
        else:
            raise
    return salt.utils.mac_utils.parse_return(ret)


def get_login_failed_last(name):
    """
    Get the date/time of the last failed login attempt

    :param str name: The username of the account

    :return: The date/time of the last failed login attempt on this account
        (yyyy-mm-dd hh:mm:ss) or 0 if the value is not defined
    :rtype: str

    :raises: CommandExecutionError on user not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_login_failed_last admin
    """
    try:
        ret = _get_account_policy_data_value(name, "failedLoginTimestamp")
    except CommandExecutionError as exc:
        if "Value not found" in exc.message:
            return "0"
        else:
            raise

    unix_timestamp = salt.utils.mac_utils.parse_return(ret)
    return _convert_to_datetime(unix_timestamp)


def set_maxdays(name, days):
    """
    Set the maximum age of the password in days

    :param str name: The username of the account

    :param int days: The maximum age of the account in days

    :return: True if successful, False if not
    :rtype: bool

    :raises: CommandExecutionError on user not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_maxdays admin 90
    """
    minutes = days * 24 * 60

    _set_account_policy(name, f"maxMinutesUntilChangePassword={minutes}")

    return get_maxdays(name) == days


def get_maxdays(name):
    """
    Get the maximum age of the password

    :param str name: The username of the account

    :return: The maximum age of the password in days
    :rtype: int

    :raises: CommandExecutionError on user not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_maxdays admin 90
    """
    policies = _get_account_policy(name)

    if "maxMinutesUntilChangePassword" in policies:
        max_minutes = policies["maxMinutesUntilChangePassword"]
        return int(max_minutes) / 24 / 60

    return 0


def set_mindays(name, days):
    """
    Set the minimum password age in days. Not available in macOS.

    :param str name: The user name

    :param int days: The number of days

    :return: Will always return False until macOS supports this feature.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_mindays admin 90
    """
    return False


def set_inactdays(name, days):
    """
    Set the number if inactive days before the account is locked. Not available
    in macOS

    :param str name: The user name

    :param int days: The number of days

    :return: Will always return False until macOS supports this feature.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_inactdays admin 90
    """
    return False


def set_warndays(name, days):
    """
    Set the number of days before the password expires that the user will start
    to see a warning. Not available in macOS

    :param str name: The user name

    :param int days: The number of days

    :return: Will always return False until macOS supports this feature.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_warndays admin 90
    """
    return False


def set_change(name, date):
    """
    Sets the date on which the password expires. The user will be required to
    change their password. Format is mm/dd/yyyy

    :param str name: The name of the user account

    :param date date: The date the password will expire. Must be in mm/dd/yyyy
        format.

    :return: True if successful, otherwise False
    :rtype: bool

    :raises: CommandExecutionError on user not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_change username 09/21/2016
    """
    _set_account_policy(name, f"usingExpirationDate=1 expirationDateGMT={date}")

    return get_change(name) == date


def get_change(name):
    """
    Gets the date on which the password expires

    :param str name: The name of the user account

    :return: The date the password will expire
    :rtype: str

    :raises: CommandExecutionError on user not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_change username
    """
    policies = _get_account_policy(name)

    if "expirationDateGMT" in policies:
        return policies["expirationDateGMT"]

    return "Value not set"


def set_expire(name, date):
    """
    Sets the date on which the account expires. The user will not be able to
    login after this date. Date format is mm/dd/yyyy

    :param str name: The name of the user account

    :param datetime date: The date the account will expire. Format must be
        mm/dd/yyyy.

    :return: True if successful, False if not
    :rtype: bool

    :raises: CommandExecutionError on user not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_expire username 07/23/2015
    """
    _set_account_policy(name, f"usingHardExpirationDate=1 hardExpireDateGMT={date}")

    return get_expire(name) == date


def get_expire(name):
    """
    Gets the date on which the account expires

    :param str name: The name of the user account

    :return: The date the account expires
    :rtype: str

    :raises: CommandExecutionError on user not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.get_expire username
    """
    policies = _get_account_policy(name)

    if "hardExpireDateGMT" in policies:
        return policies["hardExpireDateGMT"]

    return "Value not set"


def del_password(name):
    """
    Deletes the account password

    :param str name: The user name of the account

    :return: True if successful, otherwise False
    :rtype: bool

    :raises: CommandExecutionError on user not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.del_password username
    """
    # This removes the password
    cmd = f"dscl . -passwd /Users/{name} ''"
    try:
        salt.utils.mac_utils.execute_return_success(cmd)
    except CommandExecutionError as exc:
        if "eDSUnknownNodeName" in exc.strerror:
            raise CommandExecutionError(f"User not found: {name}")
        raise CommandExecutionError(f"Unknown error: {exc.strerror}")

    # This is so it looks right in shadow.info
    cmd = f"dscl . -create /Users/{name} Password '*'"
    salt.utils.mac_utils.execute_return_success(cmd)

    return info(name)["passwd"] == "*"


def set_password(name, password):
    """
    Set the password for a named user (insecure, the password will be in the
    process list while the command is running)

    :param str name: The name of the local user, which is assumed to be in the
        local directory service

    :param str password: The plaintext password to set

    :return: True if successful, otherwise False
    :rtype: bool

    :raises: CommandExecutionError on user not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' mac_shadow.set_password macuser macpassword
    """
    cmd = f"dscl . -passwd /Users/{name} '{password}'"
    try:
        salt.utils.mac_utils.execute_return_success(cmd)
    except CommandExecutionError as exc:
        if "eDSUnknownNodeName" in exc.strerror:
            raise CommandExecutionError(f"User not found: {name}")
        raise CommandExecutionError(f"Unknown error: {exc.strerror}")

    return True
