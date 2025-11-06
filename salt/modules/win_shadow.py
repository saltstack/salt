"""
Manage the shadow file

.. important::
    If you feel that Salt should be using this module to manage passwords on a
    minion, and it is using a different module (or gives an error similar to
    *'shadow.info' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import salt.utils.platform

# Define the module's virtual name
__virtualname__ = "shadow"


def __virtual__():
    """
    Only works on Windows systems
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return (False, "Module win_shadow: module only works on Windows systems.")


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
