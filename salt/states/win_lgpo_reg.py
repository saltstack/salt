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
import salt.utils.win_functions

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


def _get_domain_gpo_warning(key, name, policy_class):
    """
    Return a warning string if a Domain GPO manages the given key/value, else None.
    Only checked for Machine policy (User RSoP is not queryable from SYSTEM context).
    """
    if policy_class != "Machine":
        return None
    if "lgpo_reg.get_rsop_value" not in __salt__:
        return None
    rsop = __salt__["lgpo_reg.get_rsop_value"](key=key, v_name=name)
    if rsop.get("domain_managed"):
        gpo_label = rsop.get("gpo_name") or rsop.get("gpo_id", "unknown")
        return (
            f"Warning: '{key}\\{name}' is also managed by Domain GPO '{gpo_label}'. "
            "Changes may be overridden on the next Group Policy refresh."
        )
    return None


def _append_domain_warning(ret, key, name, policy_class):
    """
    Append a domain GPO warning to ret['comment'] if a Domain GPO manages the
    given key/value. Returns ret for use directly in return statements.
    """
    warning = _get_domain_gpo_warning(key=key, name=name, policy_class=policy_class)
    if warning:
        ret["comment"] = ret["comment"] + "\n" + warning if ret["comment"] else warning
    return ret


def _get_current(key, name, policy_class, write_registry=True):
    """
    Helper function to get the current state of the policy
    """
    pol = __salt__["lgpo_reg.get_value"](
        key=key, v_name=name, policy_class=policy_class
    )
    if pol:
        pol.update({"key": key, "name": name})
    # We only change registry on Machine policy, user will always be {}.
    # When write_registry=False the registry is not our concern, so skip the
    # read to keep the diff honest (changes will only reflect .pol changes).
    reg = {}
    if policy_class == "Machine" and write_registry:
        reg_raw = __utils__["reg.read_value"](hive="HKLM", key=key, vname=name)

        if reg_raw["vdata"] is not None:
            reg["data"] = reg_raw["vdata"]
        if reg_raw["vtype"] is not None:
            reg["type"] = reg_raw["vtype"]
        if reg:
            reg.update({"key": key, "name": name})

    return {"pol": pol, "reg": reg}


def value_present(
    name,
    key,
    v_data,
    v_type="REG_DWORD",
    policy_class="Machine",
    write_registry=None,
    refresh_policy=False,
):
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

        write_registry (bool, optional):
            Controls whether the value is also written to the live registry
            immediately after updating ``Registry.pol``.

            - ``None`` (default): auto-detect. Skips the registry write on
              Domain Controllers where ``HKLM\\SOFTWARE\\Policies\\`` is
              write-protected; writes directly on all other machine types.
            - ``True``: always write to the registry (non-DC behaviour).
            - ``False``: always skip the registry write; the Group Policy
              engine will commit the value on the next refresh.

        refresh_policy (bool, optional):
            When ``True``, trigger a native in-process Group Policy refresh
            via ``userenv.dll`` after successfully writing ``Registry.pol``.

            .. note::
                The refresh is **asynchronous**. This call signals the
                Group Policy service to begin processing; it returns before
                processing is complete. Registry values will reflect the
                updated policy only after the service finishes its refresh
                cycle. Use ``lgpo_reg.get_rsop_value`` to verify applied
                state.

            Default is ``False``.

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

    # Resolve auto-detect once so all correctness checks use the same value.
    if write_registry is None:
        write_registry = not salt.utils.win_functions.is_domain_controller()

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = _get_current(
        key=key, name=name, policy_class=policy_class, write_registry=write_registry
    )

    pol_correct = (
        str(old.get("pol", {}).get("name", "")) == str(name)
        and str(old.get("pol", {}).get("data", "")) == str(v_data)
        and str(old.get("pol", {}).get("type", "")) == v_type
    )
    if policy_class == "User" or not write_registry:
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
        if policy_class == "Machine" and write_registry:
            comment.append("Registry value already present")

    if __opts__["test"]:
        if not pol_correct:
            comment.append("Policy value will be set")
        if not reg_correct:
            if policy_class == "Machine" and write_registry:
                comment.append("Registry value will be set")
        ret["comment"] = "\n".join(comment)
        if pol_correct and reg_correct:
            ret["result"] = True
        else:
            ret["result"] = None
        return _append_domain_warning(
            ret, key=key, name=name, policy_class=policy_class
        )

    if pol_correct and reg_correct:
        ret["comment"] = "\n".join(comment)
        ret["result"] = True
        return _append_domain_warning(
            ret, key=key, name=name, policy_class=policy_class
        )

    __salt__["lgpo_reg.set_value"](
        key=key,
        v_name=name,
        v_data=v_data,
        v_type=v_type,
        policy_class=policy_class,
        write_registry=write_registry,
        refresh_policy=refresh_policy,
    )

    new = _get_current(
        key=key, name=name, policy_class=policy_class, write_registry=write_registry
    )
    ret["changes"] = salt.utils.data.recursive_diff(old, new)

    comment = []
    if ret["changes"]:
        pol_correct = (
            str(new.get("pol", {}).get("name", "")) == str(name)
            and str(new.get("pol", {}).get("data", "")) == str(v_data)
            and new.get("pol", {}).get("type", "") == v_type
        )
        if policy_class == "User" or not write_registry:
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
            if policy_class == "Machine" and write_registry:
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

    return _append_domain_warning(ret, key=key, name=name, policy_class=policy_class)


def value_disabled(
    name,
    key,
    policy_class="Machine",
    write_registry=None,
    refresh_policy=False,
):
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

        write_registry (bool, optional):
            Controls whether the registry value is also deleted immediately
            after updating ``Registry.pol``.

            - ``None`` (default): auto-detect. Skips the registry delete on
              Domain Controllers; deletes directly on all other machine types.
            - ``True``: always delete from the registry (non-DC behaviour).
            - ``False``: always skip the registry delete; the Group Policy
              engine will remove the value on the next refresh.

        refresh_policy (bool, optional):
            When ``True``, trigger a native in-process Group Policy refresh
            via ``userenv.dll`` after successfully writing ``Registry.pol``.

            .. note::
                The refresh is **asynchronous**. This call signals the
                Group Policy service to begin processing; it returns before
                processing is complete. Registry values will reflect the
                updated policy only after the service finishes its refresh
                cycle. Use ``lgpo_reg.get_rsop_value`` to verify applied
                state.

            Default is ``False``.

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

    # Resolve auto-detect once so all correctness checks use the same value.
    if write_registry is None:
        write_registry = not salt.utils.win_functions.is_domain_controller()

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = _get_current(
        key=key, name=name, policy_class=policy_class, write_registry=write_registry
    )

    pol_correct = old["pol"].get("data", "") == f"**del.{name}"
    if policy_class == "User" or not write_registry:
        reg_correct = True
    else:
        reg_correct = old["reg"] == {}

    comment = []
    if pol_correct:
        comment.append("Policy value already disabled")

    if reg_correct:
        if policy_class == "Machine" and write_registry:
            comment.append("Registry value already deleted")

    if __opts__["test"]:
        if not pol_correct:
            comment.append("Policy value will be disabled")
        if not reg_correct:
            if policy_class == "Machine" and write_registry:
                comment.append("Registry value will be deleted")
        ret["comment"] = "\n".join(comment)
        if pol_correct and reg_correct:
            ret["result"] = True
        else:
            ret["result"] = None
        return _append_domain_warning(
            ret, key=key, name=name, policy_class=policy_class
        )

    if pol_correct and reg_correct:
        ret["comment"] = "\n".join(comment)
        ret["result"] = True
        return _append_domain_warning(
            ret, key=key, name=name, policy_class=policy_class
        )

    __salt__["lgpo_reg.disable_value"](
        key=key,
        v_name=name,
        policy_class=policy_class,
        write_registry=write_registry,
        refresh_policy=refresh_policy,
    )

    new = _get_current(
        key=key, name=name, policy_class=policy_class, write_registry=write_registry
    )
    ret["changes"] = salt.utils.data.recursive_diff(old, new)

    comment = []
    if ret["changes"]:
        pol_correct = new["pol"].get("data", "") == f"**del.{name}"
        if policy_class == "User" or not write_registry:
            reg_correct = True
        else:
            reg_correct = new["reg"] == {}

        if pol_correct:
            if "pol" in ret["changes"].get("new", {}):
                comment.append("Policy value disabled")
        else:
            comment.append("Failed to disable policy value")

        if reg_correct:
            if policy_class == "Machine" and write_registry:
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

    return _append_domain_warning(ret, key=key, name=name, policy_class=policy_class)


def value_absent(
    name,
    key,
    policy_class="Machine",
    write_registry=None,
    refresh_policy=False,
):
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

        write_registry (bool, optional):
            Controls whether the registry value is also deleted immediately
            after updating ``Registry.pol``.

            - ``None`` (default): auto-detect. Skips the registry delete on
              Domain Controllers; deletes directly on all other machine types.
            - ``True``: always delete from the registry (non-DC behaviour).
            - ``False``: always skip the registry delete; the Group Policy
              engine will remove the value on the next refresh.

        refresh_policy (bool, optional):
            When ``True``, trigger a native in-process Group Policy refresh
            via ``userenv.dll`` after successfully writing ``Registry.pol``.

            .. note::
                The refresh is **asynchronous**. This call signals the
                Group Policy service to begin processing; it returns before
                processing is complete. Registry values will reflect the
                updated policy only after the service finishes its refresh
                cycle. Use ``lgpo_reg.get_rsop_value`` to verify applied
                state.

            Default is ``False``.

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

    # Resolve auto-detect once so all correctness checks use the same value.
    if write_registry is None:
        write_registry = not salt.utils.win_functions.is_domain_controller()

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = _get_current(
        key=key, name=name, policy_class=policy_class, write_registry=write_registry
    )

    pol_correct = old["pol"] == {}
    if policy_class == "User" or not write_registry:
        reg_correct = True
    else:
        reg_correct = old["reg"] == {}

    comment = []
    if pol_correct:
        comment.append("Policy value already deleted")
    if reg_correct:
        if policy_class == "Machine" and write_registry:
            comment.append("Registry value already deleted")

    if __opts__["test"]:
        if not pol_correct:
            comment.append("Policy value will be deleted")
        if not reg_correct:
            if policy_class == "Machine" and write_registry:
                comment.append("Registry value will be deleted")
        ret["comment"] = "\n".join(comment)
        if pol_correct and reg_correct:
            ret["result"] = True
        else:
            ret["result"] = None
        return _append_domain_warning(
            ret, key=key, name=name, policy_class=policy_class
        )

    if pol_correct and reg_correct:
        ret["comment"] = "\n".join(comment)
        ret["result"] = True
        return _append_domain_warning(
            ret, key=key, name=name, policy_class=policy_class
        )

    __salt__["lgpo_reg.delete_value"](
        key=key,
        v_name=name,
        policy_class=policy_class,
        write_registry=write_registry,
        refresh_policy=refresh_policy,
    )

    new = _get_current(
        key=key, name=name, policy_class=policy_class, write_registry=write_registry
    )
    ret["changes"] = salt.utils.data.recursive_diff(old, new)

    comment = []
    if ret["changes"]:
        pol_correct = new["pol"] == {}
        if policy_class == "User" or not write_registry:
            reg_correct = True
        else:
            reg_correct = new["reg"] == {}

        if pol_correct:
            if "pol" in ret["changes"].get("new", {}):
                comment.append("Policy value deleted")
        else:
            comment.append("Failed to delete policy value")

        if reg_correct:
            if policy_class == "Machine" and write_registry:
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

    return _append_domain_warning(ret, key=key, name=name, policy_class=policy_class)


def refresh_policy(name):
    r"""
    Trigger a Machine Group Policy refresh.

    This is an imperative state — it fires a refresh signal every run.
    Use it at the end of a block of ``value_present`` / ``value_disabled``
    states that were applied with ``refresh_policy: False`` to commit all
    policy changes in a single GP refresh pass.

    .. note::
        This state does not assert a persistent desired configuration. It
        signals the Group Policy service to process the current
        ``Registry.pol`` file. Registry values will be updated
        **asynchronously** after the service completes its refresh cycle.
        To verify the applied state, run ``lgpo_reg.get_rsop_value`` after
        allowing the refresh to complete.

    The recommended pattern on Domain Controllers is to write all policy
    values with ``refresh_policy: False``, then seal the batch with a
    single ``lgpo_reg.refresh_policy`` state using ``require``:

    .. code-block:: yaml

        set_appx_policy:
          lgpo_reg.value_present:
            - key: SOFTWARE\\Policies\\Microsoft\\Windows\\Appx
            - name: AllowAllTrustedApps
            - v_type: REG_DWORD
            - v_data: 0
            - refresh_policy: False

        set_smartscreen_policy:
          lgpo_reg.value_present:
            - key: SOFTWARE\\Policies\\Microsoft\\Windows\\System
            - name: EnableSmartScreen
            - v_type: REG_DWORD
            - v_data: 1
            - refresh_policy: False

        apply_local_policy:
          lgpo_reg.refresh_policy:
            - name: apply_local_policy
            - require:
              - lgpo_reg: set_appx_policy
              - lgpo_reg: set_smartscreen_policy

    Args:
        name (str): Arbitrary identifier for the state (not used functionally).

    Returns:
        dict: Standard state return with ``result`` indicating whether the
        refresh signal was accepted.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Group Policy refresh would be triggered"
        return ret
    if __salt__["lgpo_reg.refresh_policy"]():
        ret["result"] = True
        ret["comment"] = "Group Policy refresh triggered successfully"
    else:
        ret["comment"] = "Group Policy refresh failed"
    return ret
