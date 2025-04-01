r"""
A salt util for modifying the audit policies on the machine. This util is used
by the ``win_auditpol`` and ``win_lgpo`` modules.

Though this utility does not set group policy for auditing, it displays how all
auditing configuration is applied on the machine, either set directly or via
local or domain group policy.

.. versionadded:: 2018.3.4
.. versionadded:: 2019.2.1

This util allows you to view and modify the audit settings as they are applied
on the machine. The audit settings are broken down into nine categories:

- Account Logon
- Account Management
- Detailed Tracking
- DS Access
- Logon/Logoff
- Object Access
- Policy Change
- Privilege Use
- System

The ``get_settings`` function will return the subcategories for all nine of
the above categories in one dictionary along with their auditing status.

To modify a setting you only need to specify the subcategory name and the value
you wish to set. Valid settings are:

- No Auditing
- Success
- Failure
- Success and Failure

Usage:

.. code-block:: python

    import salt.utils.win_lgpo_auditpol

    # Get current state of all audit settings
    salt.utils.win_lgpo_auditpol.get_settings()

    # Get the current state of all audit settings in the "Account Logon"
    # category
    salt.utils.win_lgpo_auditpol.get_settings(category="Account Logon")

    # Get current state of the "Credential Validation" setting
    salt.utils.win_lgpo_auditpol.get_setting(name='Credential Validation')

    # Set the state of the "Credential Validation" setting to Success and
    # Failure
    salt.utils.win_lgpo_auditpol.set_setting(name='Credential Validation',
                                             value='Success and Failure')

    # Set the state of the "Credential Validation" setting to No Auditing
    salt.utils.win_lgpo_auditpol.set_setting(name='Credential Validation',
                                             value='No Auditing')
"""

import logging
import re
import tempfile

import salt.modules.cmdmod
import salt.utils.files
import salt.utils.platform
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)
__virtualname__ = "auditpol"

categories = [
    "Account Logon",
    "Account Management",
    "Detailed Tracking",
    "DS Access",
    "Logon/Logoff",
    "Object Access",
    "Policy Change",
    "Privilege Use",
    "System",
]

settings = {
    "No Auditing": "/success:disable /failure:disable",
    "Success": "/success:enable /failure:disable",
    "Failure": "/success:disable /failure:enable",
    "Success and Failure": "/success:enable /failure:enable",
}


# Although utils are often directly imported, it is also possible to use the
# loader.
def __virtual__():
    """
    Only load if on a Windows system
    """
    if not salt.utils.platform.is_windows():
        return False, "This utility only available on Windows"

    return __virtualname__


def _auditpol_cmd(cmd):
    """
    Helper function for running the auditpol command

    Args:
        cmd (str): the auditpol command to run

    Returns:
        list: A list containing each line of the return (splitlines)

    Raises:
        CommandExecutionError: If the command encounters an error
    """
    ret = salt.modules.cmdmod.run_all(cmd=f"auditpol {cmd}", python_shell=True)
    if ret["retcode"] == 0:
        return ret["stdout"].splitlines()

    msg = f"Error executing auditpol command: {cmd}\n"
    msg += "\n".join(ret["stdout"])
    raise CommandExecutionError(msg)


def get_settings(category="All"):
    """
    Get the current configuration for all audit settings specified in the
    category

    Args:
        category (str):
            One of the nine categories to return. Can also be ``All`` to return
            the settings for all categories. Valid options are:

            - Account Logon
            - Account Management
            - Detailed Tracking
            - DS Access
            - Logon/Logoff
            - Object Access
            - Policy Change
            - Privilege Use
            - System
            - All

            Default value is ``All``

    Returns:
        dict: A dictionary containing all subcategories for the specified
            category along with their current configuration

    Raises:
        KeyError: On invalid category
        CommandExecutionError: If an error is encountered retrieving the settings

    Usage:

    .. code-block:: python

        import salt.utils.win_lgpo_auditpol

        # Get current state of all audit settings
        salt.utils.win_lgpo_auditpol.get_settings()

        # Get the current state of all audit settings in the "Account Logon"
        # category
        salt.utils.win_lgpo_auditpol.get_settings(category="Account Logon")
    """
    # Parameter validation
    if category.lower() in ["all", "*"]:
        category = "*"
    elif category.lower() not in [x.lower() for x in categories]:
        raise KeyError(f'Invalid category: "{category}"')

    cmd = f'/get /category:"{category}"'
    results = _auditpol_cmd(cmd)

    ret = {}
    # Skip the first 2 lines
    for line in results[3:]:
        if "  " in line.strip():
            ret.update(dict(list(zip(*[iter(re.split(r"\s{2,}", line.strip()))] * 2))))
    return ret


def get_setting(name):
    """
    Get the current configuration for the named audit setting

    Args:
        name (str): The name of the setting to retrieve

    Returns:
        str: The current configuration for the named setting

    Raises:
        KeyError: On invalid setting name
        CommandExecutionError: If an error is encountered retrieving the settings

    Usage:

    .. code-block:: python

        import salt.utils.win_lgpo_auditpol

        # Get current state of the "Credential Validation" setting
        salt.utils.win_lgpo_auditpol.get_setting(name='Credential Validation')
    """
    current_settings = get_settings(category="All")
    for setting in current_settings:
        if name.lower() == setting.lower():
            return current_settings[setting]
    raise KeyError(f"Invalid name: {name}")


def _get_valid_names():
    if "auditpol.valid_names" not in __context__:
        settings = get_settings(category="All")
        __context__["auditpol.valid_names"] = [k.lower() for k in settings]
    return __context__["auditpol.valid_names"]


def set_setting(name, value):
    """
    Set the configuration for the named audit setting

    Args:

        name (str):
            The name of the setting to configure

        value (str):
            The configuration for the named value. Valid options are:

            - No Auditing
            - Success
            - Failure
            - Success and Failure

    Returns:
        bool: True if successful

    Raises:
        KeyError: On invalid ``name`` or ``value``
        CommandExecutionError: If an error is encountered modifying the setting

    Usage:

    .. code-block:: python

        import salt.utils.win_lgpo_auditpol

        # Set the state of the "Credential Validation" setting to Success and
        # Failure
        salt.utils.win_lgpo_auditpol.set_setting(name='Credential Validation',
                                                 value='Success and Failure')

        # Set the state of the "Credential Validation" setting to No Auditing
        salt.utils.win_lgpo_auditpol.set_setting(name='Credential Validation',
                                                 value='No Auditing')
    """
    # Input validation
    if name.lower() not in _get_valid_names():
        raise KeyError(f"Invalid name: {name}")
    for setting in settings:
        if value.lower() == setting.lower():
            cmd = f'/set /subcategory:"{name}" {settings[setting]}'
            break
    else:
        raise KeyError(f"Invalid setting value: {value}")

    _auditpol_cmd(cmd)

    return True


def get_auditpol_dump():
    """
    Gets the contents of an auditpol /backup. Used by the LGPO module to get
    fieldnames and GUIDs for Advanced Audit policies.

    Returns:
        list: A list of lines form the backup file

    Usage:

    .. code-block:: python

        import salt.utils.win_lgpo_auditpol

        dump = salt.utils.win_lgpo_auditpol.get_auditpol_dump()
    """
    # Just get a temporary file name
    # NamedTemporaryFile will delete the file it creates by default on Windows
    with tempfile.NamedTemporaryFile(suffix=".csv") as tmp_file:
        csv_file = tmp_file.name

    cmd = f"/backup /file:{csv_file}"
    _auditpol_cmd(cmd)

    with salt.utils.files.fopen(csv_file) as fp:
        return fp.readlines()
