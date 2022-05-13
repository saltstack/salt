"""
A salt module for modifying the audit policies on the machine

Though this module does not set group policy for auditing, it displays how all
auditing configuration is applied on the machine, either set directly or via
local or domain group policy.

.. versionadded:: 2018.3.4
.. versionadded:: 2019.2.1

This module allows you to view and modify the audit settings as they are applied
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

CLI Example:

.. code-block:: bash

    # Get current state of all audit settings
    salt * auditpol.get_settings

    # Get the current state of all audit settings in the "Account Logon"
    # category
    salt * auditpol.get_settings category="Account Logon"

    # Get current state of the "Credential Validation" setting
    salt * auditpol.get_setting name="Credential Validation"

    # Set the state of the "Credential Validation" setting to Success and
    # Failure
    salt * auditpol.set_setting name="Credential Validation" value="Success and Failure"

    # Set the state of the "Credential Validation" setting to No Auditing
    salt * auditpol.set_setting name="Credential Validation" value="No Auditing"
"""

import salt.utils.platform

# Define the module's virtual name
__virtualname__ = "auditpol"


def __virtual__():
    """
    Only works on Windows systems
    """
    if not salt.utils.platform.is_windows():
        return False, "Module win_auditpol: module only available on Windows"

    return __virtualname__


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

    CLI Example:

    .. code-block:: bash

        # Get current state of all audit settings
        salt * auditipol.get_settings

        # Get the current state of all audit settings in the "Account Logon"
        # category
        salt * auditpol.get_settings "Account Logon"
    """
    return __utils__["auditpol.get_settings"](category=category)


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

    CLI Example:

    .. code-block:: bash

        # Get current state of the "Credential Validation" setting
        salt * auditpol.get_setting "Credential Validation"
    """
    return __utils__["auditpol.get_setting"](name=name)


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

    CLI Example:

    .. code-block:: bash

        # Set the state of the "Credential Validation" setting to Success and
        # Failure
        salt * auditpol.set_setting "Credential Validation" "Success and Failure"

        # Set the state of the "Credential Validation" setting to No Auditing
        salt * auditpol.set_setting "Credential Validation" "No Auditing"
    """
    return __utils__["auditpol.set_setting"](name=name, value=value)
