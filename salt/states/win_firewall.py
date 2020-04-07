# -*- coding: utf-8 -*-
"""
State for configuring Windows Firewall
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError


def __virtual__():
    """
    Load if the module firewall is loaded
    """
    return "win_firewall" if "firewall.get_config" in __salt__ else False


def disabled(name="allprofiles"):
    """
    Disable all the firewall profiles (Windows only)

    Args:
        profile (Optional[str]): The name of the profile to disable. Default is
            ``allprofiles``. Valid options are:

            - allprofiles
            - domainprofile
            - privateprofile
            - publicprofile

    Example:

    .. code-block:: yaml

        # To disable the domain profile
        disable_domain:
          win_firewall.disabled:
            - name: domainprofile

        # To disable all profiles
        disable_all:
          win_firewall.disabled:
            - name: allprofiles
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    profile_map = {
        "domainprofile": "Domain",
        "privateprofile": "Private",
        "publicprofile": "Public",
        "allprofiles": "All",
    }

    # Make sure the profile name is valid
    if name not in profile_map:
        raise SaltInvocationError("Invalid profile name: {0}".format(name))

    current_config = __salt__["firewall.get_config"]()
    if name != "allprofiles" and profile_map[name] not in current_config:
        ret["result"] = False
        ret["comment"] = "Profile {0} does not exist in firewall.get_config" "".format(
            name
        )
        return ret

    for key in current_config:
        if current_config[key]:
            if name == "allprofiles" or key == profile_map[name]:
                ret["changes"][key] = "disabled"

    if __opts__["test"]:
        ret["result"] = not ret["changes"] or None
        ret["comment"] = ret["changes"]
        ret["changes"] = {}
        return ret

    # Disable it
    if ret["changes"]:
        try:
            ret["result"] = __salt__["firewall.disable"](name)
        except CommandExecutionError:
            ret["comment"] = "Firewall Profile {0} could not be disabled" "".format(
                profile_map[name]
            )
    else:
        if name == "allprofiles":
            msg = "All the firewall profiles are disabled"
        else:
            msg = "Firewall profile {0} is disabled".format(name)
        ret["comment"] = msg

    return ret


def add_rule(name, localport, protocol="tcp", action="allow", dir="in", remoteip="any"):
    """
    Add a new inbound or outbound rule to the firewall policy

    Args:

        name (str): The name of the rule. Must be unique and cannot be "all".
            Required.

        localport (int): The port the rule applies to. Must be a number between
            0 and 65535. Can be a range. Can specify multiple ports separated by
            commas. Required.

        protocol (Optional[str]): The protocol. Can be any of the following:

            - A number between 0 and 255
            - icmpv4
            - icmpv6
            - tcp
            - udp
            - any

        action (Optional[str]): The action the rule performs. Can be any of the
            following:

            - allow
            - block
            - bypass

        dir (Optional[str]): The direction. Can be ``in`` or ``out``.

        remoteip (Optional [str]): The remote IP. Can be any of the following:

            - any
            - localsubnet
            - dns
            - dhcp
            - wins
            - defaultgateway
            - Any valid IPv4 address (192.168.0.12)
            - Any valid IPv6 address (2002:9b3b:1a31:4:208:74ff:fe39:6c43)
            - Any valid subnet (192.168.1.0/24)
            - Any valid range of IP addresses (192.168.0.1-192.168.0.12)
            - A list of valid IP addresses

            Can be combinations of the above separated by commas.

            .. versionadded:: 2016.11.6

    Example:

    .. code-block:: yaml

        open_smb_port:
          win_firewall.add_rule:
            - name: SMB (445)
            - localport: 445
            - protocol: tcp
            - action: allow
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    # Check if rule exists
    if not __salt__["firewall.rule_exists"](name):
        ret["changes"] = {"new rule": name}
    else:
        ret["comment"] = "A rule with that name already exists"
        return ret

    if __opts__["test"]:
        ret["result"] = not ret["changes"] or None
        ret["comment"] = ret["changes"]
        ret["changes"] = {}
        return ret

    # Add rule
    try:
        __salt__["firewall.add_rule"](name, localport, protocol, action, dir, remoteip)
    except CommandExecutionError:
        ret["comment"] = "Could not add rule"

    return ret


def enabled(name="allprofiles"):
    """
    Enable all the firewall profiles (Windows only)

    Args:
        profile (Optional[str]): The name of the profile to enable. Default is
            ``allprofiles``. Valid options are:

            - allprofiles
            - domainprofile
            - privateprofile
            - publicprofile

    Example:

    .. code-block:: yaml

        # To enable the domain profile
        enable_domain:
          win_firewall.enabled:
            - name: domainprofile

        # To enable all profiles
        enable_all:
          win_firewall.enabled:
            - name: allprofiles
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    profile_map = {
        "domainprofile": "Domain",
        "privateprofile": "Private",
        "publicprofile": "Public",
        "allprofiles": "All",
    }

    # Make sure the profile name is valid
    if name not in profile_map:
        raise SaltInvocationError("Invalid profile name: {0}".format(name))

    current_config = __salt__["firewall.get_config"]()
    if name != "allprofiles" and profile_map[name] not in current_config:
        ret["result"] = False
        ret["comment"] = "Profile {0} does not exist in firewall.get_config" "".format(
            name
        )
        return ret

    for key in current_config:
        if not current_config[key]:
            if name == "allprofiles" or key == profile_map[name]:
                ret["changes"][key] = "enabled"

    if __opts__["test"]:
        ret["result"] = not ret["changes"] or None
        ret["comment"] = ret["changes"]
        ret["changes"] = {}
        return ret

    # Enable it
    if ret["changes"]:
        try:
            ret["result"] = __salt__["firewall.enable"](name)
        except CommandExecutionError:
            ret["comment"] = "Firewall Profile {0} could not be enabled" "".format(
                profile_map[name]
            )
    else:
        if name == "allprofiles":
            msg = "All the firewall profiles are enabled"
        else:
            msg = "Firewall profile {0} is enabled".format(name)
        ret["comment"] = msg

    return ret
