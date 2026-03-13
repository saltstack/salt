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


def _get_current(key, name, policy_class):
    """
    Helper function to get the current state of the policy
    """
    pol = __salt__["lgpo_reg.get_value"](
        key=key, v_name=name, policy_class=policy_class
    )
    if pol:
        pol.update({"key": key, "name": name})
    # We only change registry on Machine policy, user will always be {}
    reg = {}
    if policy_class == "Machine":
        reg_raw = __utils__["reg.read_value"](hive="HKLM", key=key, vname=name)

        if reg_raw["vdata"] is not None:
            reg["data"] = reg_raw["vdata"]
        if reg_raw["vtype"] is not None:
            reg["type"] = reg_raw["vtype"]
        if reg:
            reg.update({"key": key, "name": name})

    return {"pol": pol, "reg": reg}


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
    if policy_class.lower() in ["computer", "machine"]:
        policy_class = "Machine"
    else:
        policy_class = "User"

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = _get_current(key=key, name=name, policy_class=policy_class)

    pol_correct = (
        str(old.get("pol", {}).get("name", "")) == str(name)
        and str(old.get("pol", {}).get("data", "")) == str(v_data)
        and str(old.get("pol", {}).get("type", "")) == v_type
    )
    if policy_class == "User":
        reg_correct = True
    else:
        reg_correct = (
            str(old.get("reg", {}).get("name", "")) == str(name)
            and str(old.get("reg", {}).get("data", "")) == str(v_data)
            and old.get("reg", {}).get("type", "") == v_type
        )

    comment = []
    if pol_correct:
        comment.append("Policy value already present")
    if reg_correct:
        if policy_class == "Machine":
            comment.append("Registry value already present")

    if __opts__["test"]:
        if not pol_correct:
            comment.append("Policy value will be set")
        if not reg_correct:
            if policy_class == "Machine":
                comment.append("Registry value will be set")
        ret["comment"] = "\n".join(comment)
        if pol_correct and reg_correct:
            ret["result"] = True
        else:
            ret["result"] = None
        return ret

    if pol_correct and reg_correct:
        ret["comment"] = "\n".join(comment)
        ret["result"] = True
        return ret

    __salt__["lgpo_reg.set_value"](
        key=key,
        v_name=name,
        v_data=v_data,
        v_type=v_type,
        policy_class=policy_class,
    )

    new = _get_current(key=key, name=name, policy_class=policy_class)
    ret["changes"] = salt.utils.data.recursive_diff(old, new)

    comment = []
    if ret["changes"]:
        pol_correct = (
            str(new.get("pol", {}).get("name", "")) == str(name)
            and str(new.get("pol", {}).get("data", "")) == str(v_data)
            and new.get("pol", {}).get("type", "") == v_type
        )
        if policy_class == "User":
            reg_correct = True
        else:
            reg_correct = (
                str(new.get("reg", {}).get("name", "")) == str(name)
                and str(new.get("reg", {}).get("data", "")) == str(v_data)
                and new.get("reg", {}).get("type", "") == v_type
            )

        if pol_correct:
            if "pol" in ret["changes"].get("new", {}):
                comment.append("Policy value set")
        else:
            comment.append("Failed to set policy value")

        if reg_correct:
            if policy_class == "Machine":
                if "reg" in ret["changes"].get("new", {}):
                    comment.append("Registry value set")
        else:
            comment.append("Failed to set registry value")

        if reg_correct and pol_correct:
            ret["result"] = True

    else:
        comment.append(f"Failed to set {policy_class} policy value")
        comment.append(f"- key: {key}")
        comment.append(f"- name: {name}")
        comment.append(f"- v_data: {v_data}")
        comment.append(f"- v_type: {v_type}")
        ret["result"] = False

    ret["comment"] = "\n".join(comment)

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
    if policy_class.lower() in ["computer", "machine"]:
        policy_class = "Machine"
    else:
        policy_class = "User"

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = _get_current(key=key, name=name, policy_class=policy_class)

    pol_correct = old["pol"].get("data", "") == f"**del.{name}"
    if policy_class == "User":
        reg_correct = True
    else:
        reg_correct = old["reg"] == {}

    comment = []
    if pol_correct:
        comment.append("Policy value already disabled")

    if reg_correct:
        if policy_class == "Machine":
            comment.append("Registry value already deleted")

    if __opts__["test"]:
        if not pol_correct:
            comment.append("Policy value will be disabled")
        if not reg_correct:
            if policy_class == "Machine":
                comment.append("Registry value will be deleted")
        ret["comment"] = "\n".join(comment)
        if pol_correct and reg_correct:
            ret["result"] = True
        else:
            ret["result"] = None
        return ret

    if pol_correct and reg_correct:
        ret["comment"] = "\n".join(comment)
        ret["result"] = True
        return ret

    __salt__["lgpo_reg.disable_value"](key=key, v_name=name, policy_class=policy_class)

    new = _get_current(key=key, name=name, policy_class=policy_class)
    ret["changes"] = salt.utils.data.recursive_diff(old, new)

    comment = []
    if ret["changes"]:
        pol_correct = new["pol"].get("data", "") == f"**del.{name}"
        if policy_class == "User":
            reg_correct = True
        else:
            reg_correct = new["reg"] == {}

        if pol_correct:
            if "pol" in ret["changes"].get("new", {}):
                comment.append("Policy value disabled")
        else:
            comment.append("Failed to disable policy value")

        if reg_correct:
            if policy_class == "Machine":
                if "reg" in ret["changes"].get("new", {}):
                    comment.append("Registry value deleted")
        else:
            comment.append("Failed to delete registry value")

        if pol_correct and reg_correct:
            ret["result"] = True
    else:
        comment.append(f"Failed to disable {policy_class} policy value")
        comment.append(f"- key: {key}")
        comment.append(f"- name: {name}")
        ret["result"] = False

    ret["comment"] = "\n".join(comment)

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
    if policy_class.lower() in ["computer", "machine"]:
        policy_class = "Machine"
    else:
        policy_class = "User"

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = _get_current(key=key, name=name, policy_class=policy_class)

    pol_correct = old["pol"] == {}
    if policy_class == "User":
        reg_correct = True
    else:
        reg_correct = old["reg"] == {}

    comment = []
    if pol_correct:
        comment.append("Policy value already deleted")
    if reg_correct:
        if policy_class == "Machine":
            comment.append("Registry value already deleted")

    if __opts__["test"]:
        if not pol_correct:
            comment.append("Policy value will be deleted")
        if not reg_correct:
            if policy_class == "Machine":
                comment.append("Registry value will be deleted")
        ret["comment"] = "\n".join(comment)
        if pol_correct and reg_correct:
            ret["result"] = True
        else:
            ret["result"] = None
        return ret

    if pol_correct and reg_correct:
        ret["comment"] = "\n".join(comment)
        ret["result"] = True
        return ret

    __salt__["lgpo_reg.delete_value"](key=key, v_name=name, policy_class=policy_class)

    new = _get_current(key=key, name=name, policy_class=policy_class)
    ret["changes"] = salt.utils.data.recursive_diff(old, new)

    comment = []
    if ret["changes"]:
        pol_correct = new["pol"] == {}
        if policy_class == "User":
            reg_correct = True
        else:
            reg_correct = new["reg"] == {}

        if pol_correct:
            if "pol" in ret["changes"].get("new", {}):
                comment.append("Policy value deleted")
        else:
            comment.append("Failed to delete policy value")

        if reg_correct:
            if policy_class == "Machine":
                if "reg" in ret["changes"].get("new", {}):
                    comment.append("Registry value deleted")
        else:
            comment.append("Failed to delete registry value")

        if reg_correct and pol_correct:
            ret["result"] = True

    else:
        comment.append(f"Failed to remove {policy_class} policy value")
        comment.append(f"- key: {key}")
        comment.append(f"- name: {name}")
        ret["result"] = False

    ret["comment"] = "\n".join(comment)

    return ret
