"""
Manage RDP Service on Windows servers
"""


def __virtual__():
    """
    Load only if network_win is loaded
    """
    if "rdp.enable" in __salt__:
        return "rdp"
    return (False, "rdp module could not be loaded")


def enabled(name):
    """
    Enable the RDP service and make sure access to the RDP
    port is allowed in the firewall configuration
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    stat = __salt__["rdp.status"]()

    if not stat:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "RDP will be enabled"
            return ret

        ret["result"] = __salt__["rdp.enable"]()
        ret["changes"] = {"RDP was enabled": True}
        return ret

    ret["comment"] = "RDP is enabled"
    return ret


def disabled(name):
    """
    Disable the RDP service
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    stat = __salt__["rdp.status"]()

    if stat:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "RDP will be disabled"
            return ret

        ret["result"] = __salt__["rdp.disable"]()
        ret["changes"] = {"RDP was disabled": True}
        return ret

    ret["comment"] = "RDP is disabled"
    return ret
