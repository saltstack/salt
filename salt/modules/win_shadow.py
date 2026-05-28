"""
Manage the shadow file

.. important::
    If you feel that Salt should be using this module to manage passwords on a
    minion, and it is using a different module (or gives an error similar to
    *'shadow.info' is not available*), see :ref:`here
    <module-provider-override>`.

:depends:
    - pywintypes
    - win32security
    - winerror
"""

import logging

import salt.utils.platform
import salt.utils.win_runas
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

try:
    import pywintypes
    import win32security
    import winerror

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# Define the module's virtual name
__virtualname__ = "shadow"


def __virtual__():
    """
    Only works on Windows systems
    """
    if not salt.utils.platform.is_windows():
        return (False, "Module win_shadow: module only works on Windows systems.")
    if not HAS_WIN32:
        return (False, "Module win_shadow: Missing Win32 modules")
    return __virtualname__


def info(name):
    """
    Return information for the specified user.

    .. note::
        This just returns dummy data so that salt states can work.

    Args:

        name (str): The name of the user account to show.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.info root
    """
    info = __salt__["user.info"](name=name)

    ret = {
        "name": name,
        "passwd": "",
        "lstchg": "",
        "min": "",
        "max": "",
        "warn": "",
        "inact": "",
        "expire": "",
    }

    if info:
        ret = {
            "name": info["name"],
            "passwd": "Unavailable",
            "lstchg": info["password_changed"],
            "min": "",
            "max": "",
            "warn": "",
            "inact": "",
            "expire": info["expiration_date"],
        }

    return ret


def set_expire(name, expire):
    """
    Set the expiration date for a user account.

    Args:

        name (str): The name of the user account to edit.

        expire (str): The date the account will expire.

    Returns:
        bool: ``True`` if successful, otherwise ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_expire <username> 2016/7/1
    """
    return __salt__["user.update"](name, expiration_date=expire)


def require_password_change(name):
    """
    Require the user to change their password the next time they log in.

    Args:

        name (str): The name of the user account to require a password change.

    Returns:
        bool: ``True`` if successful, otherwise ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.require_password_change <username>
    """
    return __salt__["user.update"](name, expired=True)


def unlock_account(name):
    """
    Unlocks a user account.

    Args:

        name (str): The name of the user account to unlock.

    Returns:
        bool: ``True`` if successful, otherwise ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.unlock_account <username>
    """
    return __salt__["user.update"](name, unlock_account=True)


def set_password(name, password):
    """
    Set the password for a named user.

    Args:

        name (str): The name of the user account.

        password (str): The new password.

    Returns:
        bool: ``True`` if successful, otherwise ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_password root mysecretpassword
    """
    return __salt__["user.update"](name=name, password=password)


def verify_password(name, password):
    """
    Verify the password for a Windows user account by attempting a network
    logon. This uses ``LOGON32_LOGON_NETWORK`` which does not create an
    interactive session and typically does not generate audit log events.

    .. note::
        This is Microsoft's documented recommended method for validating
        credentials on Windows. There is no equivalent of ``/etc/shadow`` on
        Windows — the NT hash stored in the SAM database is inaccessible even
        to SYSTEM at runtime. ``LogonUser`` with ``LOGON32_LOGON_NETWORK`` is
        the only supported approach.

        See `How to validate user credentials on Microsoft operating systems
        <https://support.microsoft.com/en-us/help/180548/how-to-validate-user-credentials-on-microsoft-operating-systems>`_

    .. warning::
        A wrong password will increment the account's bad-logon counter. If
        the counter reaches the lockout threshold, the account will be locked.
        This function detects that situation and automatically unlocks the
        account if the lockout was caused by this call (i.e. the account was
        not already locked beforehand). If the account was already locked,
        a ``CommandExecutionError`` is raised because the password cannot be
        verified in that state.

    If the logon attempt causes the account to become locked (i.e. the bad
    password pushed the counter over the threshold), the account is
    automatically unlocked — but only if it was not already locked before
    this call.

    Args:

        name (str): The username to verify. Accepts plain names (local
            accounts), UPN format (``user@domain``), or down-level format
            (``DOMAIN\\user``).

        password (str): The password to verify.

    Returns:
        bool: ``True`` if the password is correct (or correct but the account
        has some other restriction such as being disabled or expired).
        ``False`` if the password is wrong.

    Raises:
        CommandExecutionError: If the account is locked (cannot verify) or an
            unexpected error occurs.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.verify_password <username> <password>
    """
    user_name, domain = salt.utils.win_runas.split_username(name)

    pre_info = __salt__["user.info"](name)
    pre_locked = pre_info.get("account_locked", False) if pre_info else False

    try:
        handle = win32security.LogonUser(
            user_name,
            domain,
            password,
            win32security.LOGON32_LOGON_NETWORK,
            win32security.LOGON32_PROVIDER_DEFAULT,
        )
    except pywintypes.error as exc:
        if exc.winerror in (
            winerror.ERROR_LOGON_FAILURE,
            winerror.ERROR_WRONG_PASSWORD,
        ):
            # Wrong password. If our attempt pushed the account into lockout,
            # undo it — but only if the account was not already locked.
            if not pre_locked:
                post_info = __salt__["user.info"](name)
                if post_info and post_info.get("account_locked", False):
                    log.debug(
                        "shadow.verify_password: password check locked account %s, "
                        "unlocking",
                        name,
                    )
                    __salt__["user.update"](name, unlock_account=True)
            log.debug("shadow.verify_password: password is not valid: %s", exc.strerror)
            return False

        # These errors occur after a successful credential check — the password
        # is correct but some other account restriction prevents logon.
        if exc.winerror in (
            winerror.ERROR_ACCOUNT_DISABLED,
            winerror.ERROR_ACCOUNT_EXPIRED,
            winerror.ERROR_PASSWORD_EXPIRED,
            winerror.ERROR_PASSWORD_MUST_CHANGE,
            winerror.ERROR_ACCOUNT_RESTRICTION,
            winerror.ERROR_INVALID_LOGON_HOURS,
            winerror.ERROR_INVALID_WORKSTATION,
            winerror.ERROR_LOGON_NOT_GRANTED,
            winerror.ERROR_LOGON_TYPE_NOT_GRANTED,
        ):
            log.debug(
                "shadow.verify_password: password is valid (restricted: %s)",
                exc.strerror,
            )
            return True

        if exc.winerror == winerror.ERROR_ACCOUNT_LOCKED_OUT:
            msg = f"shadow.verify_password: account '{name}' is locked, cannot verify password"
            log.debug(msg)
            raise CommandExecutionError(msg)

        msg = f"shadow.verify_password: unexpected error {exc.winerror}: {exc.strerror}"
        log.debug(msg)
        raise CommandExecutionError(msg)
    else:
        handle.Close()
        log.debug("shadow.verify_password: password is valid")
        return True
