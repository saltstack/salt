# -*- coding: utf-8 -*-
"""
Module for managing SNMP service settings on Windows servers.

"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import 3rd party libs
from salt.ext import six


def __virtual__():
    """
    Load only on minions that have the win_snmp module.
    """
    if "win_snmp.get_agent_settings" in __salt__:
        return True
    return False


def agent_settings(name, contact, location, services=None):
    """
    Manage the SNMP sysContact, sysLocation, and sysServices settings.

    :param str contact: The SNMP contact.
    :param str location: The SNMP location.
    :param str services: A list of selected services.

    Example of usage:

    .. code-block:: yaml

        snmp-agent-settings:
            win_snmp.agent_settings:
                - contact: Test Contact
                - location: Test Location
                - services:
                    - Physical
                    - Internet
    """
    ret = {"name": name, "changes": {}, "comment": six.text_type(), "result": None}

    ret_settings = {"changes": dict(), "failures": dict()}

    if not services:
        services = ["None"]

    # Filter services for unique items, and sort them for comparison purposes.
    services = sorted(set(services))

    settings = {"contact": contact, "location": location, "services": services}

    current_settings = __salt__["win_snmp.get_agent_settings"]()

    for setting in settings:
        if six.text_type(settings[setting]) != six.text_type(current_settings[setting]):
            ret_settings["changes"][setting] = {
                "old": current_settings[setting],
                "new": settings[setting],
            }
    if not ret_settings["changes"]:
        ret["comment"] = "Agent settings already contain the provided values."
        ret["result"] = True
        return ret
    elif __opts__["test"]:
        ret["comment"] = "Agent settings will be changed."
        ret["changes"] = ret_settings
        return ret

    __salt__["win_snmp.set_agent_settings"](**settings)
    new_settings = __salt__["win_snmp.get_agent_settings"]()

    for setting in settings:
        if settings[setting] != new_settings[setting]:
            ret_settings["failures"][setting] = {
                "old": current_settings[setting],
                "new": new_settings[setting],
            }
            ret_settings["changes"].pop(setting, None)

    if ret_settings["failures"]:
        ret["comment"] = "Some agent settings failed to change."
        ret["changes"] = ret_settings
        ret["result"] = False
    else:
        ret["comment"] = "Set agent settings to contain the provided values."
        ret["changes"] = ret_settings["changes"]
        ret["result"] = True
    return ret


def auth_traps_enabled(name, status=True):
    """
    Manage the sending of authentication traps.

    :param bool status: The enabled status.

    Example of usage:

    .. code-block:: yaml

        snmp-auth-traps:
            win_snmp.auth_traps_enabled:
                - status: True
    """
    ret = {"name": name, "changes": {}, "comment": six.text_type(), "result": None}

    vname = "EnableAuthenticationTraps"
    current_status = __salt__["win_snmp.get_auth_traps_enabled"]()

    if status == current_status:
        ret["comment"] = "{0} already contains the provided value.".format(vname)
        ret["result"] = True
    elif __opts__["test"]:
        ret["comment"] = "{0} will be changed.".format(vname)
        ret["changes"] = {"old": current_status, "new": status}
    else:
        ret["comment"] = "Set {0} to contain the provided value.".format(vname)
        ret["changes"] = {"old": current_status, "new": status}
        ret["result"] = __salt__["win_snmp.set_auth_traps_enabled"](status=status)

    return ret


def community_names(name, communities=None):
    """
    Manage the SNMP accepted community names and their permissions.

    :param str communities: A dictionary of SNMP communities and permissions.

    Example of usage:

    .. code-block:: yaml

        snmp-community-names:
            win_snmp.community_names:
                - communities:
                    TestCommunity: Read Only
                    OtherCommunity: Read Write
    """
    ret = {"name": name, "changes": dict(), "comment": six.text_type(), "result": None}

    ret_communities = {"changes": dict(), "failures": dict()}

    if not communities:
        communities = dict()

    current_communities = __salt__["win_snmp.get_community_names"]()

    # Note any existing communities that should be removed.
    for current_vname in current_communities:
        if current_vname not in communities:
            ret_communities["changes"][current_vname] = {
                "old": current_communities[current_vname],
                "new": None,
            }

    # Note any new communities or existing communities that should be changed.
    for vname in communities:
        current_vdata = None
        if vname in current_communities:
            current_vdata = current_communities[vname]
        if communities[vname] != current_vdata:
            ret_communities["changes"][vname] = {
                "old": current_vdata,
                "new": communities[vname],
            }

    if not ret_communities["changes"]:
        ret["comment"] = "Communities already contain the provided values."
        ret["result"] = True
        return ret
    elif __opts__["test"]:
        ret["comment"] = "Communities will be changed."
        ret["changes"] = ret_communities
        return ret

    __salt__["win_snmp.set_community_names"](communities=communities)
    new_communities = __salt__["win_snmp.get_community_names"]()

    # Verify that any communities that needed to be removed were removed.
    for new_vname in new_communities:
        if new_vname not in communities:
            ret_communities["failures"][new_vname] = {
                "old": current_communities[new_vname],
                "new": new_communities[new_vname],
            }
            ret_communities["changes"].pop(new_vname, None)

    # Verify that any new communities or existing communities that
    # needed to be changed were changed.
    for vname in communities:
        new_vdata = None
        if vname in new_communities:
            new_vdata = new_communities[vname]
        if communities[vname] != new_vdata:
            ret_communities["failures"][vname] = {
                "old": current_communities[vname],
                "new": new_vdata,
            }
            ret_communities["changes"].pop(vname, None)

    if ret_communities["failures"]:
        ret["comment"] = "Some communities failed to change."
        ret["changes"] = ret_communities
        ret["result"] = False
    else:
        ret["comment"] = "Set communities to contain the provided values."
        ret["changes"] = ret_communities["changes"]
        ret["result"] = True
    return ret
