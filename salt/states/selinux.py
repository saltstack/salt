"""
Management of SELinux rules
===========================

If SELinux is available for the running system, the mode can be managed and
booleans can be set.

.. code-block:: yaml

    enforcing:
        selinux.mode

    samba_create_home_dirs:
        selinux.boolean:
          - value: True
          - persist: True

    nginx:
        selinux.module:
          - enabled: False

.. note::
    Use of these states require that the :mod:`selinux <salt.modules.selinux>`
    execution module is available.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import salt.utils.data
import salt.utils.state
from salt.modules.selinux import SeBool

LowChunk = dict[str, Any]


def __virtual__():
    """
    Only make this state available if the selinux module is available.
    """
    if "selinux.getenforce" in __salt__:
        return "selinux"
    return (False, "selinux module could not be loaded")


def _refine_mode(mode):
    """
    Return a mode value that is predictable
    """
    mode = str(mode).lower()
    if any([mode.startswith("e"), mode == "1", mode == "on"]):
        return "Enforcing"
    if any([mode.startswith("p"), mode == "0", mode == "off"]):
        return "Permissive"
    if any([mode.startswith("d")]):
        return "Disabled"
    return "unknown"


def _refine_value(value):
    """
    Return a yes/no value, or None if the input is invalid
    """
    value = str(value).lower()
    if value in ("1", "on", "yes", "true"):
        return "on"
    if value in ("0", "off", "no", "false"):
        return "off"
    return None


def _refine_module_state(module_state):
    """
    Return a predictable value, or allow us to error out
    .. versionadded:: 2016.3.0
    """
    module_state = str(module_state).lower()
    if module_state in ("1", "on", "yes", "true", "enabled"):
        return "enabled"
    if module_state in ("0", "off", "no", "false", "disabled"):
        return "disabled"
    return "unknown"


def mode(name):
    """
    Verifies the mode SELinux is running in, can be set to enforcing,
    permissive, or disabled

    .. note::
        A change to or from disabled mode requires a system reboot. You will
        need to perform this yourself.

    name
        The mode to run SELinux in, permissive, enforcing, or disabled.
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    tmode = _refine_mode(name)
    if tmode == "unknown":
        ret["comment"] = f"{name} is not an accepted mode"
        return ret
    # Either the current mode in memory or a non-matching config value
    # will trigger setenforce
    mode = __salt__["selinux.getenforce"]()
    config = __salt__["selinux.getconfig"]()
    # Just making sure the oldmode reflects the thing that didn't match tmode
    if mode == tmode and mode != config and tmode != config:
        mode = config

    if mode == tmode:
        ret["result"] = True
        ret["comment"] = f"SELinux is already in {tmode} mode"
        return ret
    # The mode needs to change...
    if __opts__["test"]:
        ret["comment"] = f"SELinux mode is set to be changed to {tmode}"
        ret["result"] = None
        ret["changes"] = {"old": mode, "new": tmode}
        return ret

    oldmode, mode = mode, __salt__["selinux.setenforce"](tmode)
    if mode == tmode or (
        tmode == "Disabled" and __salt__["selinux.getconfig"]() == tmode
    ):
        ret["result"] = True
        ret["comment"] = f"SELinux has been set to {tmode} mode"
        ret["changes"] = {"old": oldmode, "new": mode}
        return ret
    ret["comment"] = f"Failed to set SELinux to {tmode} mode"
    return ret


def boolean(
    name: str,
    value: SeBool | None = None,
    booleans: Iterable[str | dict[str, SeBool]] | dict[str, SeBool] | None = None,
    persist=False,
):
    """
    Set up an SELinux boolean

    name
        The name of the boolean to set.
        Note that this parameter is ignored if either "booleans" is passed.

    value
        The value to set on the boolean
        You can install a different value for each boolean with the ``booleans``
        argument by including the version after the boolean name:

        .. code-block:: yaml

            "my selinux booleans":
              selinux.boolean:
                - value: true
                - booleans:
                  - foo
                  - bar
                  - baz: false

    booleans
        A list of boolean to set. All booleans
        listed under ``booleans`` will be installed via a single command.

        .. code-block:: yaml

            mybooleans:
              selinux.boolean:
                - value: true
                - booleans:
                  - foo
                  - bar
                  - baz

        value can be specified
        in the ``booleans`` argument. For example:

        .. code-block:: yaml

            mybooleans:
              selinux.boolean:
                - value: true
                - booleans:
                  - foo
                  - bar: false
                  - baz

        .. code-block:: yaml

            mybooleans:
              selinux.boolean:
                - booleans:
                    foo: true
                    bar: true
                    baz: false

    persist
        Defaults to False, set persist to true to make the boolean apply on a
        reboot
    """
    desired_bools = {}
    if not booleans:
        desired_bools[name] = value
    elif isinstance(booleans, dict):
        desired_bools.update(booleans)
    else:
        for sebool in booleans:
            if isinstance(sebool, dict):
                desired_bools.update(sebool)
            else:
                desired_bools[sebool] = value
    ret = {"name": name, "result": False, "comment": "", "changes": {}}
    existing_bools = __salt__["selinux.list_sebool"]()
    to_change = {}
    correct = []
    old = {}
    for sebool_name, sebool_value in desired_bools.items():
        if sebool_name not in existing_bools:
            ret["comment"] = f"Boolean {sebool_name} is not available"
            return ret
        rvalue = _refine_value(sebool_value)
        if rvalue is None:
            ret["comment"] = (
                f"{sebool_value} is not a valid value for the boolean {sebool_name}"
            )
            return ret
        state_same = existing_bools[sebool_name]["State"] == rvalue
        default_same = existing_bools[sebool_name]["Default"] == rvalue
        if state_same and (default_same or not persist):
            correct.append(sebool_name)
        else:
            old[sebool_name] = (
                (
                    existing_bools[sebool_name]["State"],
                    existing_bools[sebool_name]["Default"],
                )
                if persist
                else existing_bools[sebool_name]["State"]
            )
            to_change[sebool_name] = rvalue

    comments = []
    if correct:
        comments.append(
            "The following booleans were in the correct state: "
            + ", ".join(sorted(correct))
        )
    if not to_change:
        ret["comment"] = "\n".join(comments)
        ret["result"] = True
        return ret

    if persist:
        new = {key: (value, value) for key, value in to_change.items()}
    else:
        new = to_change
    diffs = salt.utils.data.compare_dicts(old, new)
    if __opts__.get("test"):
        comments.append(
            "The following booleans would be changed: "
            + ", ".join(sorted(to_change.keys()))
        )
        ret["comment"] = "\n".join(comments)
        ret["changes"] = diffs
        ret["result"] = None
        return ret

    mod_ret = __salt__["selinux.setsebools"](to_change, persist)
    if mod_ret:
        comments.append(
            "The following booleans have been changed: "
            + ", ".join(sorted(to_change.keys()))
        )
        ret["comment"] = "\n".join(comments)
        ret["changes"] = diffs
        ret["result"] = True
        return ret
    ret["comment"] = f"Failed to set the following booleans: {desired_bools}"
    return ret


def module(name, module_state="Enabled", version="any", **opts):
    """
    Enable/Disable and optionally force a specific version for an SELinux module

    name
        The name of the module to control

    module_state
        Should the module be enabled or disabled?

    version
        Defaults to no preference, set to a specified value if required.
        Currently can only alert if the version is incorrect.

    install
        Setting to True installs module

    source
        Points to module source file, used only when install is True

    remove
        Setting to True removes module

    .. versionadded:: 2016.3.0
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    if opts.get("install", False) and opts.get("remove", False):
        ret["result"] = False
        ret["comment"] = "Cannot install and remove at the same time"
        return ret
    if opts.get("install", False):
        module_path = opts.get("source", name)
        ret = module_install(module_path)
        if not ret["result"]:
            return ret
    elif opts.get("remove", False):
        return module_remove(name)
    modules = __salt__["selinux.list_semod"]()
    if name not in modules:
        ret["comment"] = f"Module {name} is not available"
        ret["result"] = False
        return ret
    rmodule_state = _refine_module_state(module_state)
    if rmodule_state == "unknown":
        ret["comment"] = "{} is not a valid state for the {} module.".format(
            module_state, module
        )
        ret["result"] = False
        return ret
    if version != "any":
        installed_version = modules[name]["Version"]
        if not installed_version == version:
            ret["comment"] = (
                f"Module version is {installed_version} and does not match "
                f"the desired version of {version} or you are "
                "using semodule >= 2.4"
            )
            ret["result"] = False
            return ret
    current_module_state = _refine_module_state(modules[name]["Enabled"])
    if rmodule_state == current_module_state:
        ret["comment"] = f"Module {name} is in the desired state"
        return ret
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Module {} is set to be toggled to {}".format(
            name, module_state
        )
        return ret

    if __salt__["selinux.setsemod"](name, rmodule_state):
        ret["comment"] = f"Module {name} has been set to {module_state}"
        return ret
    ret["result"] = False
    ret["comment"] = f"Failed to set the Module {name} to {module_state}"
    return ret


def module_install(name):
    """
    Installs custom SELinux module from given file

    name
        Path to file with module to install

    .. versionadded:: 2016.11.6
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    if __salt__["selinux.install_semod"](name):
        ret["comment"] = f"Module {name} has been installed"
        return ret
    ret["result"] = False
    ret["comment"] = f"Failed to install module {name}"
    return ret


def module_remove(name):
    """
    Removes SELinux module

    name
        The name of the module to remove

    .. versionadded:: 2016.11.6
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    modules = __salt__["selinux.list_semod"]()
    if name not in modules:
        ret["comment"] = f"Module {name} is not available"
        ret["result"] = False
        return ret
    if __salt__["selinux.remove_semod"](name):
        ret["comment"] = f"Module {name} has been removed"
        return ret
    ret["result"] = False
    ret["comment"] = f"Failed to remove module {name}"
    return ret


def fcontext_policy_present(
    name, sel_type, filetype="a", sel_user=None, sel_level=None
):
    """
    .. versionadded:: 2017.7.0

    Makes sure a SELinux policy for a given filespec (name), filetype
    and SELinux context type is present.

    name
        filespec of the file or directory. Regex syntax is allowed.

    sel_type
        SELinux context type. There are many.

    filetype
        The SELinux filetype specification. Use one of [a, f, d, c, b,
        s, l, p]. See also `man semanage-fcontext`. Defaults to 'a'
        (all files).

    sel_user
        The SELinux user.

    sel_level
        The SELinux MLS range.
    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    new_state = {}
    old_state = {}
    filetype_str = __salt__["selinux.filetype_id_to_string"](filetype)
    current_state = __salt__["selinux.fcontext_get_policy"](
        name=name,
        filetype=filetype,
        sel_type=sel_type,
        sel_user=sel_user,
        sel_level=sel_level,
    )
    if not current_state:
        new_state = {name: {"filetype": filetype_str, "sel_type": sel_type}}
        if __opts__["test"]:
            ret.update({"result": None})
        else:
            add_ret = __salt__["selinux.fcontext_add_policy"](
                name=name,
                filetype=filetype,
                sel_type=sel_type,
                sel_user=sel_user,
                sel_level=sel_level,
            )
            if add_ret["retcode"] != 0:
                ret.update({"comment": f"Error adding new rule: {add_ret}"})
            else:
                ret.update({"result": True})
    else:
        if current_state["sel_type"] != sel_type:
            old_state.update({name: {"sel_type": current_state["sel_type"]}})
            new_state.update({name: {"sel_type": sel_type}})
        else:
            ret.update(
                {
                    "result": True,
                    "comment": f'SELinux policy for "{name}" already present '
                    + 'with specified filetype "{}" and sel_type "{}".'.format(
                        filetype_str, sel_type
                    ),
                }
            )
            return ret

        # Removal of current rule is not neccesary, since adding a new rule for the same
        # filespec and the same filetype automatically overwrites
        if __opts__["test"]:
            ret.update({"result": None})
        else:
            change_ret = __salt__["selinux.fcontext_add_policy"](
                name=name,
                filetype=filetype,
                sel_type=sel_type,
                sel_user=sel_user,
                sel_level=sel_level,
            )
            if change_ret["retcode"] != 0:
                ret.update({"comment": f"Error adding new rule: {change_ret}"})
            else:
                ret.update({"result": True})
    if ret["result"] and (new_state or old_state):
        ret["changes"].update({"old": old_state, "new": new_state})
    return ret


def fcontext_policy_absent(
    name, filetype="a", sel_type=None, sel_user=None, sel_level=None
):
    """
    .. versionadded:: 2017.7.0

    Makes sure an SELinux file context policy for a given filespec
    (name), filetype and SELinux context type is absent.

    name
        filespec of the file or directory. Regex syntax is allowed.

    filetype
        The SELinux filetype specification. Use one of [a, f, d, c, b,
        s, l, p]. See also `man semanage-fcontext`. Defaults to 'a'
        (all files).

    sel_type
        The SELinux context type. There are many.

    sel_user
        The SELinux user.

    sel_level
        The SELinux MLS range.
    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    new_state = {}
    old_state = {}
    current_state = __salt__["selinux.fcontext_get_policy"](
        name=name,
        filetype=filetype,
        sel_type=sel_type,
        sel_user=sel_user,
        sel_level=sel_level,
    )
    if not current_state:
        ret.update(
            {
                "result": True,
                "comment": f'SELinux policy for "{name}" already absent '
                + 'with specified filetype "{}" and sel_type "{}".'.format(
                    filetype, sel_type
                ),
            }
        )
        return ret
    else:
        old_state.update({name: current_state})
    ret["changes"].update({"old": old_state, "new": new_state})
    if __opts__["test"]:
        ret.update({"result": None})
    else:
        remove_ret = __salt__["selinux.fcontext_delete_policy"](
            name=name,
            filetype=filetype,
            sel_type=sel_type or current_state["sel_type"],
            sel_user=sel_user,
            sel_level=sel_level,
        )
        if remove_ret["retcode"] != 0:
            ret.update({"comment": f"Error removing policy: {remove_ret}"})
        else:
            ret.update({"result": True})
    return ret


def fcontext_policy_applied(name, recursive=False):
    """
    .. versionadded:: 2017.7.0

    Checks and makes sure the SELinux policies for a given filespec are
    applied.
    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    changes_text = __salt__["selinux.fcontext_policy_is_applied"](name, recursive)
    if changes_text == "":
        ret.update(
            {
                "result": True,
                "comment": 'SElinux policies are already applied for filespec "{}"'.format(
                    name
                ),
            }
        )
        return ret
    if __opts__["test"]:
        ret.update({"result": None})
    else:
        apply_ret = __salt__["selinux.fcontext_apply_policy"](name, recursive)
        if apply_ret["retcode"] != 0:
            ret.update({"comment": apply_ret})
        else:
            ret.update({"result": True})
            ret.update({"changes": apply_ret.get("changes")})
    return ret


def port_policy_present(name, sel_type, protocol=None, port=None, sel_range=None):
    """
    .. versionadded:: 2019.2.0

    Makes sure an SELinux port policy for a given port, protocol and SELinux context type is present.

    name
        The protocol and port spec. Can be formatted as ``(tcp|udp)/(port|port-range)``.

    sel_type
        The SELinux Type.

    protocol
        The protocol for the port, ``tcp`` or ``udp``. Required if name is not formatted.

    port
        The port or port range. Required if name is not formatted.

    sel_range
        The SELinux MLS/MCS Security Range.
    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    old_state = __salt__["selinux.port_get_policy"](
        name=name,
        sel_type=sel_type,
        protocol=protocol,
        port=port,
    )
    if old_state:
        ret.update(
            {
                "result": True,
                "comment": f'SELinux policy for "{name}" already present '
                + f'with specified sel_type "{sel_type}", protocol "{protocol}" and port "{port}".',
            }
        )
        return ret
    if __opts__["test"]:
        ret.update({"result": None})
    else:
        old_state = __salt__["selinux.port_get_policy"](
            name=name,
            protocol=protocol,
            port=port,
        )
        if old_state:
            module_method = "selinux.port_modify_policy"
        else:
            module_method = "selinux.port_add_policy"
        add_modify_ret = __salt__[module_method](
            name=name,
            sel_type=sel_type,
            protocol=protocol,
            port=port,
            sel_range=sel_range,
        )
        if add_modify_ret["retcode"] != 0:
            ret.update({"comment": f"Error adding new policy: {add_modify_ret}"})
        else:
            ret.update({"result": True})
            new_state = __salt__["selinux.port_get_policy"](
                name=name,
                sel_type=sel_type,
                protocol=protocol,
                port=port,
            )
            ret["changes"].update({"old": old_state, "new": new_state})
    return ret


def port_policy_absent(name, sel_type=None, protocol=None, port=None):
    """
    .. versionadded:: 2019.2.0

    Makes sure an SELinux port policy for a given port, protocol and SELinux context type is absent.

    name
        The protocol and port spec. Can be formatted as ``(tcp|udp)/(port|port-range)``.

    sel_type
        The SELinux Type. Optional; can be used in determining if policy is present,
        ignored by ``semanage port --delete``.

    protocol
        The protocol for the port, ``tcp`` or ``udp``. Required if name is not formatted.

    port
        The port or port range. Required if name is not formatted.
    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    old_state = __salt__["selinux.port_get_policy"](
        name=name,
        sel_type=sel_type,
        protocol=protocol,
        port=port,
    )
    if not old_state:
        ret.update(
            {
                "result": True,
                "comment": f'SELinux policy for "{name}" already absent '
                + f'with specified sel_type "{sel_type}", protocol "{protocol}" and port "{port}".',
            }
        )
        return ret
    if __opts__["test"]:
        ret.update({"result": None})
    else:
        delete_ret = __salt__["selinux.port_delete_policy"](
            name=name,
            protocol=protocol,
            port=port,
        )
        if delete_ret["retcode"] != 0:
            ret.update({"comment": f"Error deleting policy: {delete_ret}"})
        else:
            ret.update({"result": True})
            new_state = __salt__["selinux.port_get_policy"](
                name=name,
                sel_type=sel_type,
                protocol=protocol,
                port=port,
            )
            ret["changes"].update({"old": old_state, "new": new_state})
    return ret


def mod_aggregate(low: LowChunk, chunks: Iterable[LowChunk], running: dict):
    """
    The mod_aggregate function which looks up all selinux boolean in the available
    low chunks and merges them into a single boolean ref in the present low data
    """
    agg_enabled = [
        "boolean",
    ]
    if low.get("fun") not in agg_enabled:
        return low

    booleans = {}
    for chunk in chunks:
        tag = salt.utils.state.gen_tag(chunk)
        if tag in running:
            # Already ran the boolean state, skip aggregation
            continue
        if chunk.get("state") == "selinux":
            if "__agg__" in chunk:
                continue
            # Check for the same function
            if chunk.get("fun") != low.get("fun"):
                continue
            # Check for the persist value
            if chunk.get("persist") != low.get("persist"):
                continue
            if "booleans" in chunk:
                _combine_booleans(chunk.get("value"), booleans, chunk["booleans"])
                chunk["__agg__"] = True
            elif "name" in chunk:
                booleans[chunk["name"]] = chunk.get("value")
                chunk["__agg__"] = True
    if booleans:
        low_booleans = {}
        if "booleans" in low:
            _combine_booleans(low.get("value"), low_booleans, low["booleans"])
        else:
            low_booleans[low["name"]] = low.get("value")
        low_booleans.update(booleans)
        low["booleans"] = low_booleans
    return low


def _combine_booleans(
    value: SeBool | None,
    bools_dict: dict[str, SeBool],
    additional_bools: dict[str, SeBool] | list[str | dict[str, SeBool]],
):
    if isinstance(additional_bools, dict):
        bools_dict.update(additional_bools)
        return
    for item in additional_bools:
        if isinstance(item, dict):
            bools_dict.update(item)
        elif value is not None:
            bools_dict[item] = value
