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
import csv
import logging
import os
import pathlib
import re
import shutil
import tempfile
from functools import lru_cache

import salt.modules.cmdmod
import salt.utils.files
import salt.utils.platform
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

CATEGORIES = (
    "Account Logon",
    "Account Management",
    "Detailed Tracking",
    "DS Access",
    "Logon/Logoff",
    "Object Access",
    "Policy Change",
    "Privilege Use",
    "System",
)
CATEGORIES_LC_KEYS = tuple(k.lower() for k in CATEGORIES)

SETTINGS = {
    "No Auditing": "/success:disable /failure:disable",
    "Success": "/success:enable /failure:disable",
    "Failure": "/success:disable /failure:enable",
    "Success and Failure": "/success:enable /failure:enable",
}


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


@lru_cache
def _get_valid_names():
    return [k.lower() for k in get_settings()]


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
    elif category.lower() not in CATEGORIES_LC_KEYS:
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
    for setting in SETTINGS:
        if value.lower() == setting.lower():
            cmd = f'/set /subcategory:"{name}" {SETTINGS[setting]}'
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


@lru_cache
def _get_advaudit_values():
    system_root = os.environ.get("SystemRoot", "C:\\Windows")
    f_audit = os.path.join(system_root, "security", "audit", "audit.csv")

    # Make sure the csv file exists before trying to open it
    advaudit_check_csv()

    audit_settings = {}
    with salt.utils.files.fopen(f_audit, mode="r") as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            audit_settings.update({row["Subcategory"]: row["Setting Value"]})
    return audit_settings


def get_advaudit_value(option, refresh=False):
    """
    Get the Advanced Auditing policy as configured in
    ``C:\\Windows\\Security\\Audit\\audit.csv``

    Args:

        option (str):
            The name of the setting as it appears in audit.csv

        refresh (bool):
            Refresh secedit data stored in __context__. This is needed for
            testing where the state is setting the value, but the module that
            is checking the value has its own __context__.

    Returns:
        bool: ``True`` if successful, otherwise ``False``
    """
    if refresh is True:
        _get_advaudit_values.cache_clear()
    return _get_advaudit_values().get(option, None)


def advaudit_check_csv():
    """
    This function checks for the existence of the `audit.csv` file here:
    `C:\\Windows\\security\\audit`

    If the file does not exist, then it copies the `audit.csv` file from the
    Group Policy location:
    `C:\\Windows\\System32\\GroupPolicy\\Machine\\Microsoft\\Windows NT\\Audit`

    If there is no `audit.csv` in either location, then a default `audit.csv`
    file is created.
    """
    system_root = os.environ.get("SystemRoot", "C:\\Windows")
    f_audit = pathlib.Path(system_root, "security", "audit", "audit.csv")
    f_audit_gpo = pathlib.Path(
        system_root,
        "System32",
        "GroupPolicy",
        "Machine",
        "Microsoft",
        "Windows NT",
        "Audit",
        "audit.csv",
    )
    # Make sure there is an existing audit.csv file on the machine
    if not f_audit.exists():
        if f_audit_gpo.exists():
            # If the GPO audit.csv exists, we'll use that one
            shutil.copyfile(str(f_audit_gpo), str(f_audit))
        else:
            field_names = get_advaudit_defaults("fieldnames")
            # If the file doesn't exist anywhere, create it with default
            # fieldnames
            f_audit.parent.mkdir(parents=True, exist_ok=True)
            f_audit.write_text(",".join(field_names))


@lru_cache
def _get_advaudit_defaults():
    # Get available setting names and GUIDs
    # This is used to get the fieldnames and GUIDs for individual policies
    log.debug("Loading auditpol defaults into __context__")
    dump = salt.utils.win_lgpo_auditpol.get_auditpol_dump()
    reader = csv.DictReader(dump)
    audit_defaults = {"fieldnames": reader.fieldnames}
    for row in reader:
        row["Machine Name"] = ""
        row["Auditpol Name"] = row["Subcategory"]
        # Special handling for snowflake scenarios where the audit.csv names
        # don't match the auditpol names
        if row["Subcategory"] == "Central Policy Staging":
            row["Subcategory"] = "Audit Central Access Policy Staging"
        elif row["Subcategory"] == "Plug and Play Events":
            row["Subcategory"] = "Audit PNP Activity"
        elif row["Subcategory"] == "Token Right Adjusted Events":
            row["Subcategory"] = "Audit Token Right Adjusted"
        else:
            row["Subcategory"] = "Audit {}".format(row["Subcategory"])
        audit_defaults[row["Subcategory"]] = row
    return audit_defaults


def get_advaudit_defaults(option=None):
    """
    Loads audit.csv defaults into a dict.
    The dictionary includes fieldnames and all configurable policies as keys.
    The values are used to create/modify the ``audit.csv`` file. The first
    entry is `fieldnames` used to create the header for the csv file. The rest
    of the entries are the audit policy names.
    Sample data follows:

    .. code-block:: python



        {
            'fieldnames': ['Machine Name',
                           'Policy Target',
                           'Subcategory',
                           'Subcategory GUID',
                           'Inclusion Setting',
                           'Exclusion Setting',
                           'Setting Value'],
            'Audit Sensitive Privilege Use': {'Auditpol Name': 'Sensitive Privilege Use',
                                              'Exclusion Setting': '',
                                              'Inclusion Setting': 'No Auditing',
                                              'Machine Name': 'WIN-8FGT3E045SE',
                                              'Policy Target': 'System',
                                              'Setting Value': '0',
                                              'Subcategory': u'Audit Sensitive Privilege Use',
                                              'Subcategory GUID': '{0CCE9228-69AE-11D9-BED3-505054503030}'},
            'Audit Special Logon': {'Auditpol Name': 'Special Logon',
                                    'Exclusion Setting': '',
                                    'Inclusion Setting': 'No Auditing',
                                    'Machine Name': 'WIN-8FGT3E045SE',
                                    'Policy Target': 'System',
                                    'Setting Value': '0',
                                    'Subcategory': u'Audit Special Logon',
                                    'Subcategory GUID': '{0CCE921B-69AE-11D9-BED3-505054503030}'},
            'Audit System Integrity': {'Auditpol Name': 'System Integrity',
                                       'Exclusion Setting': '',
                                       'Inclusion Setting': 'No Auditing',
                                       'Machine Name': 'WIN-8FGT3E045SE',
                                       'Policy Target': 'System',
                                       'Setting Value': '0',
                                       'Subcategory': u'Audit System Integrity',
                                       'Subcategory GUID': '{0CCE9212-69AE-11D9-BED3-505054503030}'},
            ...
        }

    .. note::
        `Auditpol Name` designates the value to use when setting the value with
        the auditpol command

    Args:
        option (str): The item from the dictionary to return. If ``None`` the
            entire dictionary is returned. Default is ``None``

    Returns:
        dict: If ``None`` or one of the audit settings is passed
        list: If ``fieldnames`` is passed
    """
    audit_defaults = _get_advaudit_defaults()
    if option:
        return audit_defaults[option]
    return audit_defaults
