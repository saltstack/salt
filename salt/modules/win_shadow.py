# -*- coding: utf-8 -*-
'''
Manage the shadow file

.. important::
    If you feel that Salt should be using this module to manage passwords on a
    minion, and it is using a different module (or gives an error similar to
    *'shadow.info' is not available*), see :ref:`here
    <module-provider-override>`.
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import logging

# Import Salt libs
import salt.utils.platform
from salt.exceptions import CommandExecutionError

# Import 3rd Party Libs
try:
    import win32security
    import winerror
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'shadow'


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if not HAS_WIN32:
        return False, 'win_shadow: Module requires pywin32 libraries.'
    if not salt.utils.platform.is_windows():
        return False, 'win_shadow: Module only works on Windows systems.'

    return __virtualname__


def info(name, password=None, **kwargs):
    '''
    Return information for the specified user
    This is just returns dummy data so that salt states can work.

    Args:

        name (str): The name of the user account to show.

        password (str): The password to verify. Default is ``None``

            .. note::

                There is no way to compare hashes on a Windows password. The
                way to check passwords it to attempt a logon. If Salt can logon
                with ``password`` then that value will be returned as
                ``passwd``.

    Returns:
        dict: A dictionary of information about the Windows password status

    Raises:
        CommandExecutionError: If the user account is locked and you passed a
            password to check.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.info Administrator
    '''
    info = __salt__['user.info'](name=name)

    passwd = 'Unavailable'
    if password is not None:
        if verify_password(name=name, password=password):
            passwd = password

    ret = {'name': name,
           'passwd': '',
           'lstchg': '',
           'min': '',
           'max': '',
           'warn': '',
           'inact': '',
           'expire': ''}

    if info:
        ret = {'name': info['name'],
               'passwd': passwd,
               'lstchg': info['password_changed'],
               'min': '',
               'max': '',
               'warn': '',
               'inact': '',
               'expire': info['expiration_date']}

    return ret


def set_expire(name, expire):
    '''
    Set the expiration date for a user account.

    :param name: The name of the user account to edit.

    :param expire: The date the account will expire.

    :return: True if successful. False if unsuccessful.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_expire <username> 2016/7/1
    '''
    return __salt__['user.update'](name, expiration_date=expire)


def require_password_change(name):
    '''
    Require the user to change their password the next time they log in.

    :param name: The name of the user account to require a password change.

    :return: True if successful. False if unsuccessful.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.require_password_change <username>
    '''
    return __salt__['user.update'](name, expired=True)


def unlock_account(name):
    '''
    Unlocks a user account.

    :param name: The name of the user account to unlock.

    :return: True if successful. False if unsuccessful.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.unlock_account <username>
    '''
    return __salt__['user.update'](name, unlock_account=True)


def set_password(name, password):
    '''
    Set the password for a named user.

    :param str name: The name of the user account

    :param str password: The new password

    :return: True if successful. False if unsuccessful.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_password root mysecretpassword
    '''
    return __salt__['user.update'](name=name, password=password)


def verify_password(name, password, domain='.'):
    '''
    Checks a username/password combination. For use with the state system to
    verify the user password.

    .. note::

        An invalid password will generate a Logon Audit Failure event in the
        security log. A valid password will generate a Logon Audit Success
        event.

    .. warning::

        This essentially attempts to logon with the passed credentials and will
        therefore lock the account if it reaches the failed logon attempt
        threshold. If that happens, this function attempts to unlock the
        account. This has the side-effect of resetting the number of failed
        logon attempts to 0.

    Args:

        name (str): The username to check

        password (str): The password to check

        domain (str): The name of the domain for the user. Default is '.'

    Returns:
        bool: ``True`` if password is valid, otherwise ``False``

    Raises:
        CommandExecution: If the user account is locked or an unknown error
            occurs

    Example:

    .. code-block:: python

        salt * shadow.verify_password spongebob P@ssW0rd
    '''
    # Get current account status
    pre_info = __salt__['user.info'](name=name)
    # If nothing is returned, the account does not exist
    if not pre_info:
        return False
    try:
        # We'll use LOGON_NETWORK as we really don't need a handle
        # https://support.microsoft.com/en-us/help/180548/how-to-validate-user-credentials-on-microsoft-operating-systems
        user_handle = win32security.LogonUser(
            name,  # The name
            domain,  # The domain, '.' means localhost
            password,  # The password
            win32security.LOGON32_LOGON_NETWORK,  # Logon Type
            win32security.LOGON32_PROVIDER_DEFAULT)  # Logon Provider
    except win32security.error as exc:
        # These are error codes you may get when the logon attempt fails
        # Return False
        if exc.winerror in (winerror.ERROR_LOGON_FAILURE,
                            winerror.ERROR_WRONG_PASSWORD):
            # A failed logon attempt will increment the number of failed logon
            # attempts. This could lock the account if the threshold is reached
            # before the lockout counter reset time occurs. In that case, we
            # want to unlock the account... unless the account was already
            # locked. If the lockout counter reset time occurs first, the logon
            # attempt counter will automatically reset.
            if not pre_info['account_locked']:
                if __salt__['user.info'](name=name)['account_locked']:
                    log.debug('shadow.verify_password: Account locked due to '
                              'password check. Unlocking...')
                    __salt__['user.update'](name, unlock_account=True)
            log.debug('shadow.verify_password: Password is not valid: {0}'
                      ''.format(exc.strerror))
            return False
        # These are all errors that occur after successful logon attempt. The
        # password is correct, but there is some other restriction. Return True
        if exc.winerror in [winerror.ERROR_ACCOUNT_DISABLED,
                            winerror.ERROR_ACCOUNT_EXPIRED,
                            winerror.ERROR_PASSWORD_EXPIRED,
                            # Password must be changed before logging in the
                            # first time
                            winerror.ERROR_PASSWORD_MUST_CHANGE,
                            # Some account restriction prevented logon
                            winerror.ERROR_ACCOUNT_RESTRICTION,
                            # User not permitted to logon at this time
                            winerror.ERROR_INVALID_LOGON_HOURS,
                            winerror.ERROR_LOGIN_TIME_RESTRICTION,
                            # User not allowed to logon to this computer
                            winerror.ERROR_INVALID_WORKSTATION,
                            # Logon type not granted
                            winerror.ERROR_LOGON_NOT_GRANTED,
                            winerror.ERROR_LOGON_TYPE_NOT_GRANTED]:
            log.debug('shadow.verify_password: Password is valid: {0}'
                      ''.format(exc.strerror))
            return True
        if exc.winerror == winerror.ERROR_ACCOUNT_LOCKED_OUT:
            # If the account is locked it will always return
            # ERROR_ACCOUNT_LOCKED_OUT regardless of the password being correct.
            # There's no way to verify the password in that case
            msg = 'shadow.verify_password: Account locked. Unable to verify ' \
                  'password'
        else:
            # If we get this far we have encountered an unknown error
            msg = 'shadow.verify_password: Unknown error {0}: {1}' \
                  ''.format(exc.winerror, exc.strerror)
        log.debug(msg)
        raise CommandExecutionError(msg)
    else:
        # Logon was successful
        user_handle.close()
        log.debug('shadow.verify_password: Password is valid')
        return True
