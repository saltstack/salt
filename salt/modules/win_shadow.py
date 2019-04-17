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

    :param str name: The name of the user account to show.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.info root
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


def verify_password(name, password):
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

    Returns:
        bool: ``True`` if password is valid, otherwise ``False``

    Raises:
        win32security.error: If an error is encountered

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
        user_handle = win32security.LogonUser(
            name,  # The name
            '.',  # The domain, '.' means localhost
            password,  # The password
            win32security.LOGON32_LOGON_NETWORK,  # Logon Type
            win32security.LOGON32_PROVIDER_DEFAULT)  # Logon Provider
    except win32security.error as exc:
        # A failed logon attempt will increment the number of failed logon
        # attempts. This could lock the account if the threshold is reached
        # before the lockout counter reset time occurs. In that case, we want to
        # unlock the account... unless the account was already locked.
        # If the lockout counter reset time occurs first, the logon attempt
        # counter will reset.
        if not pre_info['account_locked']:
            if __salt__['user.info'](name=name)['account_locked']:
                __salt__['user.update'](name, unlock_account=True)
        if exc.winerror == winerror.ERROR_PASSWORD_MUST_CHANGE:
            log.debug('shadow.verify_password: Password is valid')
            return True
        # This is the error code you get when the logon attempt fails
        if exc.winerror == winerror.ERROR_LOGON_FAILURE:
            log.debug('shadow.verify_password: Password is not valid')
            return False
        log.exception('shadow.verify_password: Unknown error')
        raise
    else:
        user_handle.close()
        log.debug('shadow.verify_password: Password is valid')
        return True
