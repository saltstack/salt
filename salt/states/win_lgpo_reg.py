import logging

import salt.utils.data
import salt.utils.platform
__virtualname__ = "lgpo"


def __virtual__():
    """
    Only works on Windows with the lgpo_reg module
    """
    if not salt.utils.platform.is_windows():
        return False, "LGPO_REG State: Only available on Windows"

    if "lgpo_reg.get_value" not in __salt__:
        return False, "LGPO_REG State: lgpo_reg module not available"

    return __virtualname__


def value_present(
    key,
    v_name,
    v_data,
    v_type="REG_DWORD",
    policy_class="Machine"
):
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = __salt__["lgpo_reg.get_value"](
        key=key,
        v_name=v_name,
        policy_class=policy_class
    )
    if old["data"] == v_data and old["type"] == v_type:
        ret["comment"] = "Registry.pol value already present"
        return ret

    if __opts__["test"]:
        ret["changes"] = "Registry.pol value will be set"
        ret["result"] = None
        return ret

    __salt__["lgpo_reg.set_value"](
        key=key,
        v_name=v_name,
        v_data=v_data,
        v_type=v_type,
        policy_class=policy_class,
    )

    new = __salt__["lgpo_reg.get_value"](
        key=key,
        v_name=v_name,
        policy_class=policy_class
    )

    changes = salt.utils.data.compare_dicts(old, new)

    if changes:
        ret["comment"] = "Registry.pol value has been set"
        ret["changes"] = changes

    return ret


def value_disabled(key, v_name, policy_class="Machine"):

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = __salt__["lgpo_reg.get_value"](
        key=key,
        v_name=v_name,
        policy_class=policy_class
    )
    if old["data"] == "**del.{}".format(v_name):
        ret["comment"] = "Registry.pol value already disabled"
        return ret

    if __opts__["test"]:
        ret["changes"] = "Registry.pol value will be disabled"
        ret["result"] = None
        return ret

    __salt__["lgpo_reg.disable_value"](
        key=key,
        v_name=v_name,
        policy_class=policy_class,
    )

    new = __salt__["lgpo_reg.get_value"](
        key=key,
        v_name=v_name,
        policy_class=policy_class
    )

    changes = salt.utils.data.compare_dicts(old, new)

    if changes:
        ret["comment"] = "Registry.pol value enabled"
        ret["changes"] = changes

    return ret


def value_absent(key, v_name, policy_class="Machine"):

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = __salt__["lgpo_reg.get_value"](
        key=key,
        v_name=v_name,
        policy_class=policy_class
    )
    if old is None:
        ret["comment"] = "Registry.pol value already absent"
        return ret

    if __opts__["test"]:
        ret["changes"] = "Registry.pol value will be deleted"
        ret["result"] = None
        return ret

    __salt__["lgpo_reg.delete_value"](
        key=key,
        v_name=v_name,
        policy_class=policy_class,
    )

    new = __salt__["lgpo_reg.get_value"](
        key=key,
        v_name=v_name,
        policy_class=policy_class
    )

    if new is None:
        new = {}

    changes = salt.utils.data.compare_dicts(old, new)

    if changes:
        ret["comment"] = "Registry.pol value deleted"
        ret["changes"] = changes

    return ret
