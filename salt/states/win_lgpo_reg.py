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
          lgpo_reg.present:
            - key: SOFTWARE\MyKey
            - name: MyValue
            - v_type: REG_SZ
            - v_data: "some string data"
            - policy_class: Machine


        # Using the name as the parameter and modifying the User policy
        MyValue:
          lgpo_reg.present:
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
        ret["changes"] = changes
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
          lgpo_reg.disabled:
            - key: SOFTWARE\MyKey
            - name: MyValue
            - policy_class: Machine


        # Using the name as the parameter and modifying the User policy
        MyValue:
          lgpo_reg.disabled:
            - key: SOFTWARE\MyKey
            - policy_class: User
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = __salt__["lgpo_reg.get_value"](
        key=key, v_name=name, policy_class=policy_class
    )
    if old.get("data", "") == "**del.{}".format(name):
        ret["comment"] = "Registry.pol value already disabled"
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
        ret["changes"] = changes
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
          lgpo_reg.absent:
            - key: SOFTWARE\MyKey
            - name: MyValue
            - policy_class: Machine


        # Using the name as the parameter and modifying the User policy
        MyValue:
          lgpo_reg.absent:
            - key: SOFTWARE\MyKey
            - policy_class: User
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    old = __salt__["lgpo_reg.get_value"](
        key=key, v_name=name, policy_class=policy_class
    )
    if not old:
        ret["comment"] = "Registry.pol value already absent"
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
        ret["changes"] = changes
        ret["result"] = True

    return ret
