# -*- coding: utf-8 -*-
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
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import 3rd party libs
from salt.ext import six


def __virtual__():
    """
    Only make this state available if the selinux module is available.
    """
    return "selinux" if "selinux.getenforce" in __salt__ else False


def _refine_mode(mode):
    """
    Return a mode value that is predictable
    """
    mode = six.text_type(mode).lower()
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
    value = six.text_type(value).lower()
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
    module_state = six.text_type(module_state).lower()
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
        ret["comment"] = "{0} is not an accepted mode".format(name)
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
        ret["comment"] = "SELinux is already in {0} mode".format(tmode)
        return ret
    # The mode needs to change...
    if __opts__["test"]:
        ret["comment"] = "SELinux mode is set to be changed to {0}".format(tmode)
        ret["result"] = None
        ret["changes"] = {"old": mode, "new": tmode}
        return ret

    oldmode, mode = mode, __salt__["selinux.setenforce"](tmode)
    if mode == tmode or (
        tmode == "Disabled" and __salt__["selinux.getconfig"]() == tmode
    ):
        ret["result"] = True
        ret["comment"] = "SELinux has been set to {0} mode".format(tmode)
        ret["changes"] = {"old": oldmode, "new": mode}
        return ret
    ret["comment"] = "Failed to set SELinux to {0} mode".format(tmode)
    return ret


def boolean(name, value, persist=False):
    """
    Set up an SELinux boolean

    name
        The name of the boolean to set

    value
        The value to set on the boolean

    persist
        Defaults to False, set persist to true to make the boolean apply on a
        reboot
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    bools = __salt__["selinux.list_sebool"]()
    if name not in bools:
        ret["comment"] = "Boolean {0} is not available".format(name)
        ret["result"] = False
        return ret
    rvalue = _refine_value(value)
    if rvalue is None:
        ret["comment"] = "{0} is not a valid value for the " "boolean".format(value)
        ret["result"] = False
        return ret
    state = bools[name]["State"] == rvalue
    default = bools[name]["Default"] == rvalue
    if persist:
        if state and default:
            ret["comment"] = "Boolean is in the correct state"
            return ret
    else:
        if state:
            ret["comment"] = "Boolean is in the correct state"
            return ret
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Boolean {0} is set to be changed to {1}".format(name, rvalue)
        return ret

    ret["result"] = __salt__["selinux.setsebool"](name, rvalue, persist)
    if ret["result"]:
        ret["comment"] = "Boolean {0} has been set to {1}".format(name, rvalue)
        ret["changes"].update({"State": {"old": bools[name]["State"], "new": rvalue}})
        if persist and not default:
            ret["changes"].update(
                {"Default": {"old": bools[name]["Default"], "new": rvalue}}
            )
        return ret
    ret["comment"] = "Failed to set the boolean {0} to {1}".format(name, rvalue)
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
        ret["comment"] = "Module {0} is not available".format(name)
        ret["result"] = False
        return ret
    rmodule_state = _refine_module_state(module_state)
    if rmodule_state == "unknown":
        ret["comment"] = "{0} is not a valid state for the " "{1} module.".format(
            module_state, module
        )
        ret["result"] = False
        return ret
    if version != "any":
        installed_version = modules[name]["Version"]
        if not installed_version == version:
            ret["comment"] = (
                "Module version is {0} and does not match "
                "the desired version of {1} or you are "
                "using semodule >= 2.4".format(installed_version, version)
            )
            ret["result"] = False
            return ret
    current_module_state = _refine_module_state(modules[name]["Enabled"])
    if rmodule_state == current_module_state:
        ret["comment"] = "Module {0} is in the desired state".format(name)
        return ret
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Module {0} is set to be toggled to {1}".format(
            name, module_state
        )
        return ret

    if __salt__["selinux.setsemod"](name, rmodule_state):
        ret["comment"] = "Module {0} has been set to {1}".format(name, module_state)
        return ret
    ret["result"] = False
    ret["comment"] = "Failed to set the Module {0} to {1}".format(name, module_state)
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
        ret["comment"] = "Module {0} has been installed".format(name)
        return ret
    ret["result"] = False
    ret["comment"] = "Failed to install module {0}".format(name)
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
        ret["comment"] = "Module {0} is not available".format(name)
        ret["result"] = False
        return ret
    if __salt__["selinux.remove_semod"](name):
        ret["comment"] = "Module {0} has been removed".format(name)
        return ret
    ret["result"] = False
    ret["comment"] = "Failed to remove module {0}".format(name)
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
                ret.update({"comment": "Error adding new rule: {0}".format(add_ret)})
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
                    "comment": 'SELinux policy for "{0}" already present '.format(name)
                    + 'with specified filetype "{0}" and sel_type "{1}".'.format(
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
                ret.update({"comment": "Error adding new rule: {0}".format(change_ret)})
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
                "comment": 'SELinux policy for "{0}" already absent '.format(name)
                + 'with specified filetype "{0}" and sel_type "{1}".'.format(
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
            ret.update({"comment": "Error removing policy: {0}".format(remove_ret)})
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
                "comment": 'SElinux policies are already applied for filespec "{0}"'.format(
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
        name=name, sel_type=sel_type, protocol=protocol, port=port,
    )
    if old_state:
        ret.update(
            {
                "result": True,
                "comment": 'SELinux policy for "{0}" already present '.format(name)
                + 'with specified sel_type "{0}", protocol "{1}" and port "{2}".'.format(
                    sel_type, protocol, port
                ),
            }
        )
        return ret
    if __opts__["test"]:
        ret.update({"result": None})
    else:
        add_ret = __salt__["selinux.port_add_policy"](
            name=name,
            sel_type=sel_type,
            protocol=protocol,
            port=port,
            sel_range=sel_range,
        )
        if add_ret["retcode"] != 0:
            ret.update({"comment": "Error adding new policy: {0}".format(add_ret)})
        else:
            ret.update({"result": True})
            new_state = __salt__["selinux.port_get_policy"](
                name=name, sel_type=sel_type, protocol=protocol, port=port,
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
        name=name, sel_type=sel_type, protocol=protocol, port=port,
    )
    if not old_state:
        ret.update(
            {
                "result": True,
                "comment": 'SELinux policy for "{0}" already absent '.format(name)
                + 'with specified sel_type "{0}", protocol "{1}" and port "{2}".'.format(
                    sel_type, protocol, port
                ),
            }
        )
        return ret
    if __opts__["test"]:
        ret.update({"result": None})
    else:
        delete_ret = __salt__["selinux.port_delete_policy"](
            name=name, protocol=protocol, port=port,
        )
        if delete_ret["retcode"] != 0:
            ret.update({"comment": "Error deleting policy: {0}".format(delete_ret)})
        else:
            ret.update({"result": True})
            new_state = __salt__["selinux.port_get_policy"](
                name=name, sel_type=sel_type, protocol=protocol, port=port,
            )
            ret["changes"].update({"old": old_state, "new": new_state})
    return ret
