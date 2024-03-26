"""
Management of keyboard layouts
==============================

The keyboard layout can be managed for the system:

.. code-block:: yaml

    us:
      keyboard.system

Or it can be managed for XOrg:

.. code-block:: yaml

    us:
      keyboard.xorg
"""


def __virtual__():
    """
    Only load if the keyboard module is available in __salt__
    """
    if "keyboard.get_sys" in __salt__:
        return True
    return (False, "keyboard module could not be loaded")


def system(name):
    """
    Set the keyboard layout for the system

    name
        The keyboard layout to use
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}
    if __salt__["keyboard.get_sys"]() == name:
        ret["result"] = True
        ret["comment"] = f"System layout {name} already set"
        return ret
    if __opts__["test"]:
        ret["comment"] = f"System layout {name} needs to be set"
        return ret
    if __salt__["keyboard.set_sys"](name):
        ret["changes"] = {"layout": name}
        ret["result"] = True
        ret["comment"] = f"Set system keyboard layout {name}"
        return ret
    else:
        ret["result"] = False
        ret["comment"] = "Failed to set system keyboard layout"
        return ret


def xorg(name):
    """
    Set the keyboard layout for XOrg

    layout
        The keyboard layout to use
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}
    if __salt__["keyboard.get_x"]() == name:
        ret["result"] = True
        ret["comment"] = f"XOrg layout {name} already set"
        return ret
    if __opts__["test"]:
        ret["comment"] = f"XOrg layout {name} needs to be set"
        return ret
    if __salt__["keyboard.set_x"](name):
        ret["changes"] = {"layout": name}
        ret["result"] = True
        ret["comment"] = f"Set XOrg keyboard layout {name}"
        return ret
    else:
        ret["result"] = False
        ret["comment"] = "Failed to set XOrg keyboard layout"
        return ret
