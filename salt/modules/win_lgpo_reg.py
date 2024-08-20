"""
LGPO - Registry.pol
===================

.. versionadded:: 3006.0

A module for working with registry based policies in Windows Local Group Policy
(LGPO). This module contains functions for working with the ``Registry.pol``
file. The ``Registry.pol`` file is the source of truth for registry settings
and LGPO.

Group Policy is refreshed every 90 seconds by default. During that refresh the
contents of the ``Registry.pol`` file are applied to the Registry. If the
setting is changed outside of Group Policy to something other than what is
contained in the ``Registry.pol`` file, it will be changed back during the next
refresh.

In the Group Policy Editor (``gpedit.msc``) these policies can be set to three
states:

- Not Configured
- Enabled
- Disabled

A policy that is "Not Configured" does not have an entry in the ``Registry.pol``
file. A Group Policy refresh will not make any changes to key/value pairs in the
registry that are not specified in the ``Registry.pol`` file.

An "Enabled" policy will have an entry in the ``Registry.pol`` files that
contains its key path, value name, value type, value size, and value data. When
Group Policy is refreshed, existing values will be overwritten with those
contained in the ``Registry.pol`` file.

A "Disabled" policy will have an entry in the ``Registry.pol`` file with the key
path and the value name, but the value name will be prepended with ``**del.``.
When Group Policy is refreshed the key/value will be deleted from the registry.
If the key contains no values, it will also be deleted.

Working with LGPO Reg
---------------------

The easiest way to figure out the values needed for this module is to set the
policy using the Group Policy Editor (``gpedit.msc``) and then run the
``lgpo_reg.read_reg_pol`` function. This function will display a dictionary of
all registry-based policies in the ``Registry.pol`` file. From its return you
can get the ``key``, ``v_name``, ``v_type``, and ``v_data`` required to "enable"
that policy. Use those values to set/disable/delete policies using this module.
The same values can also be used to create states for setting these policies.

.. note::
    Not all policies in the Group Policy Editor (``gpedit.msc``) that write to
    the registry make that change in the ``Registry.pol`` file. Those policies
    could still be enforced via the ``Registry.pol`` file... theoretically. But
    you will have to find the values needed to set them with this module using a
    different method.
"""

import logging

import salt.utils.platform
import salt.utils.win_lgpo_reg
import salt.utils.win_reg
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)
__virtualname__ = "lgpo_reg"


def __virtual__():
    """
    Only works on Windows
    """
    if not salt.utils.platform.is_windows():
        return False, "LGPO_REG Module: Only available on Windows"

    return __virtualname__


def read_reg_pol(policy_class="Machine"):
    r"""
    Read the contents of the Registry.pol file. Display the contents as a
    human-readable dictionary.

    Args:
        policy_class (str): The registry class to retrieve. Can be one of the
            following:

            - Computer
            - Machine
            - User

            Default is ``Machine``

    Raises:
        SaltInvocationError: Invalid policy class

    Returns:
        dict: A dictionary representing the contents of the Registry.pol file

    CLI Example:

    .. code-block:: bash

        # Read the machine Registry.pol
        salt '*' lgpo_reg.read_reg_pol
    """
    # Verify policy_class
    if policy_class.lower() in ["computer", "machine"]:
        policy_class = "Machine"
    elif policy_class.lower() in ["user"]:
        policy_class = "User"
    else:
        raise SaltInvocationError("An invalid policy class was specified")
    pol_info = salt.utils.win_lgpo_reg.CLASS_INFO[policy_class]
    pol_file_data = salt.utils.win_lgpo_reg.read_reg_pol_file(
        reg_pol_path=pol_info["policy_path"]
    )

    return salt.utils.win_lgpo_reg.reg_pol_to_dict(pol_file_data)


def write_reg_pol(data, policy_class="Machine"):
    r"""
    Write data to the Registry.pol file. The data is a dictionary that is then
    converted to the appropriate bytes format expected by Registry.pol

    Args:
        data (dict): A dictionary containing Registry.pol data

        policy_class (str): The registry class to write to. Can be one of the
            following:

            - Computer
            - Machine
            - User

            Default is ``Machine``

    Raises:
        SaltInvocationError: Invalid policy class
        CommandExecutionError: On failure

    Returns:
        bool: True if successful

    CLI Example:

    .. code-block:: bash

        # Write to Machine Registry.pol
        salt '*' lgpo_reg.write_reg_pol "{'SOFTWARE\MyKey': {'MyValue': 'data': 1, 'type': 'REG_DWORD'}}"
    """
    # Maybe have this data passed instead of opening it here
    # Verify policy_class
    if policy_class.lower() in ["computer", "machine"]:
        policy_class = "Machine"
    elif policy_class.lower() in ["user"]:
        policy_class = "User"
    else:
        raise SaltInvocationError("An invalid policy class was specified")

    policy_class_info = salt.utils.win_lgpo_reg.CLASS_INFO[policy_class]

    policy_file_data = salt.utils.win_lgpo_reg.dict_to_reg_pol(data)

    return salt.utils.win_lgpo_reg.write_reg_pol_data(
        policy_file_data,
        policy_class_info["policy_path"],
        policy_class_info["gpt_extension_location"],
        policy_class_info["gpt_extension_guid"],
    )


def get_value(key, v_name, policy_class="Machine"):
    r"""
    Get the value of a single value pair as set in the ``Registry.pol``
    file.

    Args:
        key (str): The registry key where the value name resides

        v_name (str): The value name to retrieve

        policy_class (str): The registry class to read from. Can be one of the
            following:

    Raises:
        SaltInvocationError: Invalid policy class

    Returns:
        dict: A dictionary containing the value data and the value type found

    CLI Example:

    .. code-block:: bash

        # Get a value
        salt '*' lgpo_reg.get_value "SOFTWARE\MyKey" "MyValue"
    """
    # Verify input
    if policy_class.lower() in ["computer", "machine"]:
        policy_class = "Machine"
    elif policy_class.lower() in ["user"]:
        policy_class = "User"
    else:
        raise SaltInvocationError("An invalid policy class was specified")
    pol_data = read_reg_pol(policy_class=policy_class)

    found_key = ""
    found_name = ""
    for p_key in pol_data:
        if key.lower() == p_key.lower():
            found_key = p_key
            for p_name in pol_data[p_key]:
                if v_name.lower() in p_name.lower():
                    found_name = p_name

    if found_key:
        if found_name:
            if "**del." in found_name:
                pol_data[found_key][found_name]["data"] = found_name
            return pol_data[found_key][found_name]

    return {}


def get_key(key, policy_class="Machine"):
    r"""
    Get all the values set in a key in the ``Registry.pol`` file.

    Args:
        key (str): The registry key where the values reside

        policy_class (str): The registry class to read from. Can be one of the
            following:

    Raises:
        SaltInvocationError: Invalid policy class

    Returns:
        dict: A dictionary containing the value data and the value type

    CLI Example:

    .. code-block:: bash

        # Get all values from a key
        salt '*' lgpo_reg.get_key "SOFTWARE\MyKey"
    """
    # Verify input
    if policy_class.lower() in ["computer", "machine"]:
        policy_class = "Machine"
    elif policy_class.lower() in ["user"]:
        policy_class = "User"
    else:
        raise SaltInvocationError("An invalid policy class was specified")
    pol_data = read_reg_pol(policy_class=policy_class)
    found_key = ""
    for p_key in pol_data:
        if key.lower() == p_key.lower():
            found_key = p_key

    if found_key:
        return pol_data[found_key]

    return {}


def set_value(
    key,
    v_name,
    v_data,
    v_type="REG_DWORD",
    policy_class="Machine",
):
    r"""
    Add a key/value pair to the registry.pol file. This bypasses the admx/adml
    style policies. This is the equivalent of setting a policy to ``Enabled``

    Args:
        key (str): The registry key path

        v_name (str): The registry value name within the key

        v_data(str): The registry value

        v_type (str): The registry value type. Must be one of the following:

            - REG_BINARY
            - REG_DWORD
            - REG_EXPAND_SZ
            - REG_MULTI_SZ
            - REG_QWORD
            - REG_SZ

            Default is REG_DWORD

        policy_class (str): The registry class to write to. Can be one of the
            following:

            - Computer
            - Machine
            - User

            Default is ``Machine``

    Raises:
        SaltInvocationError: Invalid policy_class
        SaltInvocationError: Invalid v_type
        SaltInvocationError: v_data doesn't match v_type

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        # Set REG_DWORD value (default)
        salt '*' lgpo_reg.set_value "SOFTWARE\MyKey" "MyValue" 1

        # Set REG_SZ value
        salt '*' lgpo_reg.set_value "SOFTWARE\MyKey" "MyValue" "string value" "REG_SZ"
    """
    # Verify input
    if policy_class.lower() in ["computer", "machine"]:
        policy_class = "Machine"
        hive = "HKLM"
    elif policy_class.lower() in ["user"]:
        policy_class = "User"
        hive = "HKCU"
    else:
        raise SaltInvocationError("An invalid policy class was specified")

    v_type = v_type.upper()
    valid_types = [
        "REG_BINARY",
        "REG_DWORD",
        "REG_EXPAND_SZ",
        "REG_MULTI_SZ",
        "REG_QWORD",
        "REG_SZ",
    ]
    if v_type not in valid_types:
        msg = f"Invalid type: {v_type}"
        raise SaltInvocationError(msg)

    if v_type in ["REG_SZ", "REG_EXPAND_SZ"]:
        if not isinstance(v_data, str):
            msg = f"{v_type} data must be a string"
            raise SaltInvocationError(msg)
    elif v_type == "REG_MULTI_SZ":
        if not isinstance(v_data, list):
            msg = f"{v_type} data must be a list"
            raise SaltInvocationError(msg)
    elif v_type in ["REG_DWORD", "REG_QWORD"]:
        try:
            int(v_data)
        except (TypeError, ValueError):
            msg = f"{v_type} data must be an integer"
            raise SaltInvocationError(msg)

    pol_data = read_reg_pol(policy_class=policy_class)

    found_key = ""
    found_name = ""
    for p_key in pol_data:
        if key.lower() == p_key.lower():
            found_key = p_key
            for p_name in pol_data[p_key]:
                if v_name.lower() == p_name.lower().lstrip("**del."):
                    found_name = p_name

    if found_key:
        if found_name:
            if "**del." in found_name:
                log.debug("LGPO_REG Mod: Found disabled name: %s", found_name)
                pol_data[found_key][v_name] = pol_data[found_key].pop(found_name)
                found_name = v_name
            log.debug("LGPO_REG Mod: Updating value: %s", found_name)
            pol_data[found_key][found_name] = {"data": v_data, "type": v_type}
        else:
            log.debug("LGPO_REG Mod: Setting new value: %s", found_name)
            pol_data[found_key][v_name] = {"data": v_data, "type": v_type}
    else:
        log.debug("LGPO_REG Mod: Adding new key and value: %s", found_name)
        pol_data[key] = {v_name: {"data": v_data, "type": v_type}}

    success = True
    if not write_reg_pol(pol_data, policy_class=policy_class):
        log.error("LGPO_REG Mod: Failed to write registry.pol file")
        success = False

    if not salt.utils.win_reg.set_value(
        hive=hive,
        key=key,
        vname=v_name,
        vdata=v_data,
        vtype=v_type,
    ):
        log.error("LGPO_REG Mod: Failed to set registry entry")
        success = False

    return success


def disable_value(key, v_name, policy_class="machine"):
    r"""
    Mark a registry value for deletion in the registry.pol file. This bypasses
    the admx/adml style policies. This is the equivalent of setting the policy
    to ``Disabled`` in the Group Policy editor (``gpedit.msc``)

    Args:
        key (str): The registry key path

        v_name (str): The registry value name within the key

        policy_class (str): The registry class to write to. Can be one of the
            following:

            - Computer
            - Machine
            - User

            Default is ``Machine``

    Raises:
        SaltInvocationError: Invalid policy_class
        CommandExecutionError: On failure

    Returns:
        bool: ``True`` if successful, otherwise ``False``
        None: If already disabled

    CLI Example:

    .. code-block:: bash

        # Delete a value
        salt '*' lgpo_reg.delete_value "SOFTWARE\MyKey" "MyValue"
    """
    # Verify input
    if policy_class.lower() in ["computer", "machine"]:
        policy_class = "Machine"
        hive = "HKLM"
    elif policy_class.lower() in ["user"]:
        policy_class = "User"
        hive = "HKCU"
    else:
        raise SaltInvocationError("An invalid policy class was specified")

    pol_data = read_reg_pol(policy_class=policy_class)

    found_key = ""
    found_name = ""
    for p_key in pol_data:
        if key.lower() == p_key.lower():
            found_key = p_key
            for p_name in pol_data[p_key]:
                if v_name.lower() == p_name.lower().lstrip("**del."):
                    found_name = p_name

    if found_key:
        if found_name:
            if "**del." in found_name:
                log.debug("LGPO_REG Mod: Already disabled: %s", v_name)
                return None
            log.debug("LGPO_REG Mod: Disabling value name: %s", v_name)
            pol_data[found_key].pop(found_name)
            found_name = f"**del.{found_name}"
            pol_data[found_key][found_name] = {"data": " ", "type": "REG_SZ"}
        else:
            log.debug("LGPO_REG Mod: Setting new disabled value name: %s", v_name)
            pol_data[found_key][f"**del.{v_name}"] = {
                "data": " ",
                "type": "REG_SZ",
            }
    else:
        log.debug(
            "LGPO_REG Mod: Adding new key and disabled value name: %s", found_name
        )
        pol_data[key] = {f"**del.{v_name}": {"data": " ", "type": "REG_SZ"}}

    success = True
    if not write_reg_pol(pol_data, policy_class=policy_class):
        log.error("LGPO_REG Mod: Failed to write registry.pol file")
        success = False

    ret = salt.utils.win_reg.delete_value(hive=hive, key=key, vname=v_name)
    if not ret:
        if ret is None:
            log.debug("LGPO_REG Mod: Registry key/value already missing")
        else:
            log.error("LGPO_REG Mod: Failed to remove registry entry")
            success = False

    return success


def delete_value(key, v_name, policy_class="Machine"):
    r"""
    Delete a key/value pair from the Registry.pol file. This bypasses the
    admx/adml style policies. This is the equivalent of setting the policy to
    ``Not Configured``.

    Args:
        key (str): The registry key path

        v_name (str): The registry value name within the key

        policy_class (str): The registry class to write to. Can be one of the
            following:

            - Computer
            - Machine
            - User

            Default is ``Machine``

    Raises:
        SaltInvocationError: Invalid policy_class
        CommandExecutionError: On failure

    Returns:
        bool: ``True`` if successful, otherwise ``False``
        None: Key/value not present

    CLI Example:

    .. code-block:: bash

        # Delete all values under a key
        salt '*' lgpo_reg.delete_value "SOFTWARE\MyKey" "MyValue"
    """

    # Verify input
    if policy_class.lower() in ["computer", "machine"]:
        policy_class = "Machine"
        hive = "HKLM"
    elif policy_class.lower() in ["user"]:
        policy_class = "User"
        hive = "HKCU"
    else:
        raise SaltInvocationError("An invalid policy class was specified")

    pol_data = read_reg_pol(policy_class=policy_class)

    found_key = ""
    found_name = ""
    for p_key in pol_data:
        if key.lower() == p_key.lower():
            found_key = p_key
            for p_name in pol_data[p_key]:
                if v_name.lower() == p_name.lower().lstrip("**del."):
                    found_name = p_name

    if found_key:
        if found_name:
            log.debug("LGPO_REG Mod: Removing value name: %s", found_name)
            pol_data[found_key].pop(found_name)
        else:
            log.debug("LGPO_REG Mod: Value name not found: %s", v_name)
            return None
        if len(pol_data[found_key]) == 0:
            log.debug("LGPO_REG Mod: Removing empty key: %s", found_key)
            pol_data.pop(found_key)
    else:
        log.debug("LGPO_REG Mod: Key not found: %s", key)
        return None

    success = True
    if not write_reg_pol(pol_data, policy_class=policy_class):
        log.error("LGPO_REG Mod: Failed to write registry.pol file")
        success = False

    ret = salt.utils.win_reg.delete_value(hive=hive, key=key, vname=v_name)
    if not ret:
        if ret is None:
            log.debug("LGPO_REG Mod: Registry key/value already missing")
        else:
            log.error("LGPO_REG Mod: Failed to remove registry entry")
            success = False

    return success


# This is for testing different settings and verifying that we are writing the
# values correctly
# def test():
#     pol_info = salt.utils.win_lgpo_reg.CLASS_INFO["Machine"]
#     reg_data = salt.utils.win_lgpo_reg.read_reg_pol_file(reg_pol_path=pol_info["policy_path"])
#     print(reg_data)
#     dict_data = salt.utils.win_lgpo_reg.reg_pol_to_dict(reg_data)
#     print(salt.utils.win_lgpo_reg.dict_to_reg_pol(dict_data))
