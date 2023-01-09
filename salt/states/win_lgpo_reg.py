"""
LGPO - Registry.pol
===================

.. versionadded:: 3006.0

A state module for working with registry based policies in Windows Local Group
Policy (LGPO). This module contains functions for working with the
``Registry.pol`` file. The ``Registry.pol`` file is the source of truth for
registry settings and LGPO.

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
can get the ``key``, ``v_name``, ``v_type``, and ``v_data`` required to
configure that policy.

.. note::
    Not all policies in the Group Policy Editor (``gpedit.msc``) that write to
    the registry make that change in the ``Registry.pol`` file. Those policies
    could still be enforced via the ``Registry.pol`` file... theoretically. But
    you will have to find the values needed to set them with this module using a
    different method.
"""
import salt.utils.data
import salt.utils.platform

__virtualname__ = "lgpo_reg"


def __virtual__():
    """
    Only works on Windows with the lgpo_reg module
    """
    if not salt.utils.platform.is_windows():
        return False, "LGPO_REG State: Only available on Windows"

    if "lgpo_reg.get_value" not in __salt__:
        return False, "LGPO_REG State: lgpo_reg module not available"

    return __virtualname__


def _format_changes(changes, key, v_name):
    """
    Reformat the changes dictionary to group new and old together.
    """
    new_changes = {"new": {}, "old": {}}
    for item in changes:
        if changes[item]["new"]:
            new_changes["new"][item] = changes[item]["new"]
            new_changes["new"]["key"] = key
            new_changes["new"]["name"] = v_name
        if changes[item]["old"]:
            new_changes["old"][item] = changes[item]["old"]
            new_changes["old"]["key"] = key
            new_changes["old"]["name"] = v_name
    return new_changes


def value_present(name, key, v_data, v_type="REG_DWORD", policy_class="Machine"):
    r"""
    Ensure a registry setting is present in the Registry.pol file.

    Args:

        name (str): The registry value name within the key

        key (str): The registry key path

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

    CLI Example:

    .. code-block:: yaml

        # Using the name parameter in the definition
        set_reg_pol_value:
          lgpo_reg.value_present:
            - key: SOFTWARE\MyKey
            - name: MyValue
            - v_type: REG_SZ
            - v_data: "some string data"
            - policy_class: Machine


        # Using the name as the parameter and modifying the User policy
        MyValue:
          lgpo_reg.value_present:
            - key: SOFTWARE\MyKey
            - v_type: REG_SZ
            - v_data: "some string data"
            - policy_class: User
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = __salt__["lgpo_reg.get_value"](
        key=key, v_name=name, policy_class=policy_class
    )
    if old.get("data", "") == v_data and old.get("type", "") == v_type:
        ret["comment"] = "Registry.pol value already present"
        ret["result"] = True
        return ret

    if __opts__["test"]:
        ret["comment"] = "Registry.pol value will be set"
        ret["result"] = None
        return ret

    __salt__["lgpo_reg.set_value"](
        key=key,
        v_name=name,
        v_data=v_data,
        v_type=v_type,
        policy_class=policy_class,
    )

    new = __salt__["lgpo_reg.get_value"](
        key=key, v_name=name, policy_class=policy_class
    )

    changes = salt.utils.data.compare_dicts(old, new)

    if changes:
        ret["comment"] = "Registry.pol value has been set"
        ret["changes"] = _format_changes(changes, key, name)
        ret["result"] = True

    return ret


def value_disabled(name, key, policy_class="Machine"):
    r"""
    Ensure a registry setting is disabled in the Registry.pol file.

    Args:

        key (str): The registry key path

        name (str): The registry value name within the key

        policy_class (str): The registry class to write to. Can be one of the
            following:

            - Computer
            - Machine
            - User

            Default is ``Machine``

    CLI Example:

    .. code-block:: yaml

        # Using the name parameter in the definition
        set_reg_pol_value:
          lgpo_reg.value_disabled:
            - key: SOFTWARE\MyKey
            - name: MyValue
            - policy_class: Machine


        # Using the name as the parameter and modifying the User policy
        MyValue:
          lgpo_reg.value_disabled:
            - key: SOFTWARE\MyKey
            - policy_class: User
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = __salt__["lgpo_reg.get_value"](
        key=key, v_name=name, policy_class=policy_class
    )
    if old.get("data", "") == "**del.{}".format(name):
        ret["comment"] = "Registry.pol value already disabled"
        ret["result"] = True
        return ret

    if __opts__["test"]:
        ret["comment"] = "Registry.pol value will be disabled"
        ret["result"] = None
        return ret

    __salt__["lgpo_reg.disable_value"](key=key, v_name=name, policy_class=policy_class)

    new = __salt__["lgpo_reg.get_value"](
        key=key, v_name=name, policy_class=policy_class
    )

    changes = salt.utils.data.compare_dicts(old, new)

    if changes:
        ret["comment"] = "Registry.pol value enabled"
        ret["changes"] = _format_changes(changes, key, name)
        ret["result"] = True

    return ret


def value_absent(name, key, policy_class="Machine"):
    r"""
    Ensure a registry setting is not present in the Registry.pol file.

    Args:

        key (str): The registry key path

        name (str): The registry value name within the key

        policy_class (str): The registry class to write to. Can be one of the
            following:

            - Computer
            - Machine
            - User

            Default is ``Machine``

    CLI Example:

    .. code-block:: yaml

        # Using the name parameter in the definition
        set_reg_pol_value:
          lgpo_reg.value_absent:
            - key: SOFTWARE\MyKey
            - name: MyValue
            - policy_class: Machine


        # Using the name as the parameter and modifying the User policy
        MyValue:
          lgpo_reg.value_absent:
            - key: SOFTWARE\MyKey
            - policy_class: User
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = __salt__["lgpo_reg.get_value"](
        key=key, v_name=name, policy_class=policy_class
    )
    if not old:
        ret["comment"] = "Registry.pol value already absent"
        ret["result"] = True
        return ret

    if __opts__["test"]:
        ret["comment"] = "Registry.pol value will be deleted"
        ret["result"] = None
        return ret

    __salt__["lgpo_reg.delete_value"](key=key, v_name=name, policy_class=policy_class)

    new = __salt__["lgpo_reg.get_value"](
        key=key, v_name=name, policy_class=policy_class
    )

    if new is None:
        new = {}

    changes = salt.utils.data.compare_dicts(old, new)

    if changes:
        ret["comment"] = "Registry.pol value deleted"
        ret["changes"] = _format_changes(changes, key, name)
        ret["result"] = True

    return ret
