# -*- coding: utf-8 -*-
"""
A state module to manage Palo Alto network devices.

:codeauthor: ``Spencer Ervin <spencer_ervin@hotmail.com>``
:maturity:   new
:depends:    none
:platform:   unix


About
=====
This state module was designed to handle connections to a Palo Alto based
firewall. This module relies on the Palo Alto proxy module to interface with the devices.

This state module is designed to give extreme flexibility in the control over XPATH values on the PANOS device. It
exposes the core XML API commands and allows state modules to chain complex XPATH commands.

Below is an example of how to construct a security rule and move to the top of the policy. This will take a config
lock to prevent execution during the operation, then remove the lock. After the XPATH has been deployed, it will
commit to the device.

.. code-block:: yaml

    panos/takelock:
        panos.add_config_lock
    panos/service_tcp_22:
        panos.set_config:
            - xpath: /config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/service
            - value: <entry name='tcp-22'><protocol><tcp><port>22</port></tcp></protocol></entry>
            - commit: False
    panos/create_rule1:
        panos.set_config:
            - xpath: /config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/rulebase/security/rules
            - value: '
              <entry name="rule1">
                <from><member>trust</member></from>
                <to><member>untrust</member></to>
                <source><member>10.0.0.1</member></source>
                <destination><member>10.0.1.1</member></destination>
                <service><member>tcp-22</member></service>
                <application><member>any</member></application>
                <action>allow</action>
                <disabled>no</disabled>
              </entry>'
            - commit: False
    panos/moveruletop:
        panos.move_config:
            - xpath: /config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys1']/rulebase/security/rules/entry[@name='rule1']
            - where: top
            - commit: False
    panos/removelock:
        panos.remove_config_lock
    panos/commit:
        panos.commit

Version Specific Configurations
===============================
Palo Alto devices running different versions will have different supported features and different command structures. In
order to account for this, the proxy module can be leveraged to check if the panos device is at a specific revision
level.

The proxy['panos.is_required_version'] method will check if a panos device is currently running a version equal or
greater than the passed version. For example, proxy['panos.is_required_version']('7.0.0') would match both 7.1.0 and
8.0.0.

.. code-block:: jinja

    {% if proxy['panos.is_required_version']('8.0.0') %}
    panos/deviceconfig/system/motd-and-banner:
      panos.set_config:
        - xpath: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system/motd-and-banner
        - value: |
          <banner-header>BANNER TEXT</banner-header>
          <banner-header-color>color2</banner-header-color>
          <banner-header-text-color>color18</banner-header-text-color>
          <banner-header-footer-match>yes</banner-header-footer-match>
        - commit: False
    {% endif %}

.. seealso::
    :py:mod:`Palo Alto Proxy Module <salt.proxy.panos>`

"""

# Import Python Libs
from __future__ import absolute_import

import logging

# Import salt libs
import salt.utils.xmlutil as xml
from salt._compat import ElementTree as ET

log = logging.getLogger(__name__)


def __virtual__():
    return "panos.commit" in __salt__


def _build_members(members, anycheck=False):
    """
    Builds a member formatted string for XML operation.

    """
    if isinstance(members, list):

        # This check will strip down members to a single any statement
        if anycheck and "any" in members:
            return "<member>any</member>"
        response = ""
        for m in members:
            response += "<member>{0}</member>".format(m)
        return response
    else:
        return "<member>{0}</member>".format(members)


def _default_ret(name):
    """
    Set the default response values.

    """
    ret = {"name": name, "changes": {}, "commit": None, "result": False, "comment": ""}
    return ret


def _edit_config(xpath, element):
    """
    Sends an edit request to the device.

    """
    query = {"type": "config", "action": "edit", "xpath": xpath, "element": element}

    response = __proxy__["panos.call"](query)

    return _validate_response(response)


def _get_config(xpath):
    """
    Retrieves an xpath from the device.

    """
    query = {"type": "config", "action": "get", "xpath": xpath}

    response = __proxy__["panos.call"](query)

    return response


def _move_after(xpath, target):
    """
    Moves an xpath to the after of its section.

    """
    query = {
        "type": "config",
        "action": "move",
        "xpath": xpath,
        "where": "after",
        "dst": target,
    }

    response = __proxy__["panos.call"](query)

    return _validate_response(response)


def _move_before(xpath, target):
    """
    Moves an xpath to the bottom of its section.

    """
    query = {
        "type": "config",
        "action": "move",
        "xpath": xpath,
        "where": "before",
        "dst": target,
    }

    response = __proxy__["panos.call"](query)

    return _validate_response(response)


def _move_bottom(xpath):
    """
    Moves an xpath to the bottom of its section.

    """
    query = {"type": "config", "action": "move", "xpath": xpath, "where": "bottom"}

    response = __proxy__["panos.call"](query)

    return _validate_response(response)


def _move_top(xpath):
    """
    Moves an xpath to the top of its section.

    """
    query = {"type": "config", "action": "move", "xpath": xpath, "where": "top"}

    response = __proxy__["panos.call"](query)

    return _validate_response(response)


def _set_config(xpath, element):
    """
    Sends a set request to the device.

    """
    query = {"type": "config", "action": "set", "xpath": xpath, "element": element}

    response = __proxy__["panos.call"](query)

    return _validate_response(response)


def _validate_response(response):
    """
    Validates a response from a Palo Alto device. Used to verify success of commands.

    """
    if not response:
        return False, "Unable to validate response from device."
    elif "msg" in response:
        if "line" in response["msg"]:
            if response["msg"]["line"] == "already at the top":
                return True, response
            elif response["msg"]["line"] == "already at the bottom":
                return True, response
            else:
                return False, response
        elif response["msg"] == "command succeeded":
            return True, response
        else:
            return False, response
    elif "status" in response:
        if response["status"] == "success":
            return True, response
        else:
            return False, response
    else:
        return False, response


def add_config_lock(name):
    """
    Prevent other users from changing configuration until the lock is released.

    name: The name of the module function to execute.

    SLS Example:

    .. code-block:: yaml

        panos/takelock:
            panos.add_config_lock

    """
    ret = _default_ret(name)

    ret.update({"changes": __salt__["panos.add_config_lock"](), "result": True})

    return ret


def address_exists(
    name,
    addressname=None,
    vsys=1,
    ipnetmask=None,
    iprange=None,
    fqdn=None,
    description=None,
    commit=False,
):
    """
    Ensures that an address object exists in the configured state. If it does not exist or is not configured with the
    specified attributes, it will be adjusted to match the specified values.

    This module will only process a single address type (ip-netmask, ip-range, or fqdn). It will process the specified
    value if the following order: ip-netmask, ip-range, fqdn. For proper execution, only specify a single address
    type.

    name: The name of the module function to execute.

    addressname(str): The name of the address object.  The name is case-sensitive and can have up to 31 characters,
    which an be letters, numbers, spaces, hyphens, and underscores. The name must be unique on a firewall and, on
    Panorama, unique within its device group and any ancestor or descendant device groups.

    vsys(str): The string representation of the VSYS ID. Defaults to VSYS 1.

    ipnetmask(str): The IPv4 or IPv6 address or IP address range using the format ip_address/mask or ip_address where
    the mask is the number of significant binary digits used for the network portion of the address. Ideally, for IPv6,
    you specify only the network portion, not the host portion.

    iprange(str): A range of addresses using the format ip_address–ip_address where both addresses can be  IPv4 or both
    can be IPv6.

    fqdn(str): A fully qualified domain name format. The FQDN initially resolves at commit time. Entries are
    subsequently refreshed when the firewall performs a check every 30 minutes; all changes in the IP address for the
    entries are picked up at the refresh cycle.

    description(str): A description for the policy (up to 255 characters).

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/address/h-10.10.10.10:
            panos.address_exists:
              - addressname: h-10.10.10.10
              - vsys: 1
              - ipnetmask: 10.10.10.10
              - commit: False

        panos/address/10.0.0.1-10.0.0.50:
            panos.address_exists:
              - addressname: r-10.0.0.1-10.0.0.50
              - vsys: 1
              - iprange: 10.0.0.1-10.0.0.50
              - commit: False

        panos/address/foo.bar.com:
            panos.address_exists:
              - addressname: foo.bar.com
              - vsys: 1
              - fqdn: foo.bar.com
              - description: My fqdn object
              - commit: False

    """
    ret = _default_ret(name)

    if not addressname:
        ret.update({"comment": "The service name field must be provided."})
        return ret

    # Check if address object currently exists
    address = __salt__["panos.get_address"](addressname, vsys)["result"]

    if address and "entry" in address:
        address = address["entry"]
    else:
        address = {}

    element = ""

    # Verify the arguments
    if ipnetmask:
        element = "<ip-netmask>{0}</ip-netmask>".format(ipnetmask)
    elif iprange:
        element = "<ip-range>{0}</ip-range>".format(iprange)
    elif fqdn:
        element = "<fqdn>{0}</fqdn>".format(fqdn)
    else:
        ret.update({"comment": "A valid address type must be specified."})
        return ret

    if description:
        element += "<description>{0}</description>".format(description)

    full_element = "<entry name='{0}'>{1}</entry>".format(addressname, element)

    new_address = xml.to_dict(ET.fromstring(full_element), True)

    if address == new_address:
        ret.update(
            {
                "comment": "Address object already exists. No changes required.",
                "result": True,
            }
        )
        return ret
    else:
        xpath = (
            "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys{0}']/address/"
            "entry[@name='{1}']".format(vsys, addressname)
        )

        result, msg = _edit_config(xpath, full_element)

        if not result:
            ret.update({"comment": msg})
            return ret

    if commit is True:
        ret.update(
            {
                "changes": {"before": address, "after": new_address},
                "commit": __salt__["panos.commit"](),
                "comment": "Address object successfully configured.",
                "result": True,
            }
        )
    else:
        ret.update(
            {
                "changes": {"before": address, "after": new_address},
                "comment": "Service object successfully configured.",
                "result": True,
            }
        )

    return ret


def address_group_exists(
    name, groupname=None, vsys=1, members=None, description=None, commit=False
):
    """
    Ensures that an address group object exists in the configured state. If it does not exist or is not configured with
    the specified attributes, it will be adjusted to match the specified values.

    This module will enforce group membership. If a group exists and contains members this state does not include,
    those members will be removed and replaced with the specified members in the state.

    name: The name of the module function to execute.

    groupname(str): The name of the address group object.  The name is case-sensitive and can have up to 31 characters,
    which an be letters, numbers, spaces, hyphens, and underscores. The name must be unique on a firewall and, on
    Panorama, unique within its device group and any ancestor or descendant device groups.

    vsys(str): The string representation of the VSYS ID. Defaults to VSYS 1.

    members(str, list): The members of the address group. These must be valid address objects or address groups on the
    system that already exist prior to the execution of this state.

    description(str): A description for the policy (up to 255 characters).

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/address-group/my-group:
            panos.address_group_exists:
              - groupname: my-group
              - vsys: 1
              - members:
                - my-address-object
                - my-other-address-group
              - description: A group that needs to exist
              - commit: False

    """
    ret = _default_ret(name)

    if not groupname:
        ret.update({"comment": "The group name field must be provided."})
        return ret

    # Check if address group object currently exists
    group = __salt__["panos.get_address_group"](groupname, vsys)["result"]

    if group and "entry" in group:
        group = group["entry"]
    else:
        group = {}

    # Verify the arguments
    if members:
        element = "<static>{0}</static>".format(_build_members(members, True))
    else:
        ret.update({"comment": "The group members must be provided."})
        return ret

    if description:
        element += "<description>{0}</description>".format(description)

    full_element = "<entry name='{0}'>{1}</entry>".format(groupname, element)

    new_group = xml.to_dict(ET.fromstring(full_element), True)

    if group == new_group:
        ret.update(
            {
                "comment": "Address group object already exists. No changes required.",
                "result": True,
            }
        )
        return ret
    else:
        xpath = (
            "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys{0}']/address-group/"
            "entry[@name='{1}']".format(vsys, groupname)
        )

        result, msg = _edit_config(xpath, full_element)

        if not result:
            ret.update({"comment": msg})
            return ret

    if commit is True:
        ret.update(
            {
                "changes": {"before": group, "after": new_group},
                "commit": __salt__["panos.commit"](),
                "comment": "Address group object successfully configured.",
                "result": True,
            }
        )
    else:
        ret.update(
            {
                "changes": {"before": group, "after": new_group},
                "comment": "Address group object successfully configured.",
                "result": True,
            }
        )

    return ret


def clone_config(name, xpath=None, newname=None, commit=False):
    """
    Clone a specific XPATH and set it to a new name.

    name: The name of the module function to execute.

    xpath(str): The XPATH of the configuration API tree to clone.

    newname(str): The new name of the XPATH clone.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/clonerule:
            panos.clone_config:
              - xpath: /config/devices/entry/vsys/entry[@name='vsys1']/rulebase/security/rules&from=/config/devices/
              entry/vsys/entry[@name='vsys1']/rulebase/security/rules/entry[@name='rule1']
              - value: rule2
              - commit: True

    """
    ret = _default_ret(name)

    if not xpath:
        return ret

    if not newname:
        return ret

    query = {"type": "config", "action": "clone", "xpath": xpath, "newname": newname}

    result, response = _validate_response(__proxy__["panos.call"](query))

    ret.update({"changes": response, "result": result})

    if not result:
        return ret

    if commit is True:
        ret.update({"commit": __salt__["panos.commit"](), "result": True})

    return ret


def commit_config(name):
    """
    Commits the candidate configuration to the running configuration.

    name: The name of the module function to execute.

    SLS Example:

    .. code-block:: yaml

        panos/commit:
            panos.commit_config

    """
    ret = _default_ret(name)

    ret.update({"commit": __salt__["panos.commit"](), "result": True})

    return ret


def delete_config(name, xpath=None, commit=False):
    """
    Deletes a Palo Alto XPATH to a specific value.

    Use the xpath parameter to specify the location of the object to be deleted.

    name: The name of the module function to execute.

    xpath(str): The XPATH of the configuration API tree to control.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/deletegroup:
            panos.delete_config:
              - xpath: /config/devices/entry/vsys/entry[@name='vsys1']/address-group/entry[@name='test']
              - commit: True

    """
    ret = _default_ret(name)

    if not xpath:
        return ret

    query = {"type": "config", "action": "delete", "xpath": xpath}

    result, response = _validate_response(__proxy__["panos.call"](query))

    ret.update({"changes": response, "result": result})

    if not result:
        return ret

    if commit is True:
        ret.update({"commit": __salt__["panos.commit"](), "result": True})

    return ret


def download_software(name, version=None, synch=False, check=False):
    """
    Ensures that a software version is downloaded.

    name: The name of the module function to execute.

    version(str): The software version to check. If this version is not already downloaded, it will attempt to download
    the file from Palo Alto.

    synch(bool): If true, after downloading the file it will be synched to its peer.

    check(bool): If true, the PANOS device will first attempt to pull the most recent software inventory list from Palo
    Alto.

    SLS Example:

    .. code-block:: yaml

        panos/version8.0.0:
            panos.download_software:
              - version: 8.0.0
              - synch: False
              - check: True

    """
    ret = _default_ret(name)

    if check is True:
        __salt__["panos.check_software"]()

    versions = __salt__["panos.get_software_info"]()["result"]

    if (
        "sw-updates" not in versions
        or "versions" not in versions["sw-updates"]
        or "entry" not in versions["sw-updates"]["versions"]
    ):
        ret.update(
            {
                "comment": "Software version is not found in the local software list.",
                "result": False,
            }
        )
        return ret

    for entry in versions["sw-updates"]["versions"]["entry"]:
        if entry["version"] == version and entry["downloaded"] == "yes":
            ret.update(
                {"comment": "Software version is already downloaded.", "result": True}
            )
        return ret

    ret.update(
        {
            "changes": __salt__["panos.download_software_version"](
                version=version, synch=synch
            )
        }
    )

    versions = __salt__["panos.get_software_info"]()["result"]

    if (
        "sw-updates" not in versions
        or "versions" not in versions["sw-updates"]
        or "entry" not in versions["sw-updates"]["versions"]
    ):
        ret.update({"result": False})
        return ret

    for entry in versions["sw-updates"]["versions"]["entry"]:
        if entry["version"] == version and entry["downloaded"] == "yes":
            ret.update({"result": True})
        return ret

    return ret


def edit_config(name, xpath=None, value=None, commit=False):
    """
    Edits a Palo Alto XPATH to a specific value. This will always overwrite the existing value, even if it is not
    changed.

    You can replace an existing object hierarchy at a specified location in the configuration with a new value. Use
    the xpath parameter to specify the location of the object, including the node to be replaced.

    This is the recommended state to enforce configurations on a xpath.

    name: The name of the module function to execute.

    xpath(str): The XPATH of the configuration API tree to control.

    value(str): The XML value to edit. This must be a child to the XPATH.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/addressgroup:
            panos.edit_config:
              - xpath: /config/devices/entry/vsys/entry[@name='vsys1']/address-group/entry[@name='test']
              - value: <static><entry name='test'><member>abc</member><member>xyz</member></entry></static>
              - commit: True

    """
    ret = _default_ret(name)

    # Verify if the current XPATH is equal to the specified value.
    # If we are equal, no changes required.
    xpath_split = xpath.split("/")

    # Retrieve the head of the xpath for validation.
    if len(xpath_split) > 0:
        head = xpath_split[-1]
        if "[" in head:
            head = head.split("[")[0]

    current_element = __salt__["panos.get_xpath"](xpath)["result"]

    if head and current_element and head in current_element:
        current_element = current_element[head]
    else:
        current_element = {}

    new_element = xml.to_dict(ET.fromstring(value), True)

    if current_element == new_element:
        ret.update(
            {
                "comment": "XPATH is already equal to the specified value.",
                "result": True,
            }
        )
        return ret

    result, msg = _edit_config(xpath, value)

    ret.update({"comment": msg, "result": result})

    if not result:
        return ret

    if commit is True:
        ret.update(
            {
                "changes": {"before": current_element, "after": new_element},
                "commit": __salt__["panos.commit"](),
                "result": True,
            }
        )
    else:
        ret.update(
            {
                "changes": {"before": current_element, "after": new_element},
                "result": True,
            }
        )

    return ret


def move_config(name, xpath=None, where=None, dst=None, commit=False):
    """
    Moves a XPATH value to a new location.

    Use the xpath parameter to specify the location of the object to be moved, the where parameter to
    specify type of move, and dst parameter to specify the destination path.

    name: The name of the module function to execute.

    xpath(str): The XPATH of the configuration API tree to move.

    where(str): The type of move to execute. Valid options are after, before, top, bottom. The after and before
    options will require the dst option to specify the destination of the action. The top action will move the
    XPATH to the top of its structure. The botoom action will move the XPATH to the bottom of its structure.

    dst(str): Optional. Specifies the destination to utilize for a move action. This is ignored for the top
    or bottom action.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes. If the operation is
    not successful, it will not commit.

    SLS Example:

    .. code-block:: yaml

        panos/moveruletop:
            panos.move_config:
              - xpath: /config/devices/entry/vsys/entry[@name='vsys1']/rulebase/security/rules/entry[@name='rule1']
              - where: top
              - commit: True

        panos/moveruleafter:
            panos.move_config:
              - xpath: /config/devices/entry/vsys/entry[@name='vsys1']/rulebase/security/rules/entry[@name='rule1']
              - where: after
              - dst: rule2
              - commit: True

    """
    ret = _default_ret(name)

    if not xpath:
        return ret

    if not where:
        return ret

    if where == "after":
        result, msg = _move_after(xpath, dst)
    elif where == "before":
        result, msg = _move_before(xpath, dst)
    elif where == "top":
        result, msg = _move_top(xpath)
    elif where == "bottom":
        result, msg = _move_bottom(xpath)

    ret.update({"result": result, "comment": msg})

    if not result:
        return ret

    if commit is True:
        ret.update({"commit": __salt__["panos.commit"](), "result": True})

    return ret


def remove_config_lock(name):
    """
    Release config lock previously held.

    name: The name of the module function to execute.

    SLS Example:

    .. code-block:: yaml

        panos/takelock:
            panos.remove_config_lock

    """
    ret = _default_ret(name)

    ret.update({"changes": __salt__["panos.remove_config_lock"](), "result": True})

    return ret


def rename_config(name, xpath=None, newname=None, commit=False):
    """
    Rename a Palo Alto XPATH to a specific value. This will always rename the value even if a change is not needed.

    name: The name of the module function to execute.

    xpath(str): The XPATH of the configuration API tree to control.

    newname(str): The new name of the XPATH value.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/renamegroup:
            panos.rename_config:
              - xpath: /config/devices/entry/vsys/entry[@name='vsys1']/address/entry[@name='old_address']
              - value: new_address
              - commit: True

    """
    ret = _default_ret(name)

    if not xpath:
        return ret

    if not newname:
        return ret

    query = {"type": "config", "action": "rename", "xpath": xpath, "newname": newname}

    result, response = _validate_response(__proxy__["panos.call"](query))

    ret.update({"changes": response, "result": result})

    if not result:
        return ret

    if commit is True:
        ret.update({"commit": __salt__["panos.commit"](), "result": True})

    return ret


def security_rule_exists(
    name,
    rulename=None,
    vsys="1",
    action=None,
    disabled=None,
    sourcezone=None,
    destinationzone=None,
    source=None,
    destination=None,
    application=None,
    service=None,
    description=None,
    logsetting=None,
    logstart=None,
    logend=None,
    negatesource=None,
    negatedestination=None,
    profilegroup=None,
    datafilter=None,
    fileblock=None,
    spyware=None,
    urlfilter=None,
    virus=None,
    vulnerability=None,
    wildfire=None,
    move=None,
    movetarget=None,
    commit=False,
):
    """
    Ensures that a security rule exists on the device. Also, ensure that all configurations are set appropriately.

    This method will create the rule if it does not exist. If the rule does exist, it will ensure that the
    configurations are set appropriately.

    If the rule does not exist and is created, any value that is not provided will be provided as the default.
    The action, to, from, source, destination, application, and service fields are mandatory and must be provided.

    This will enforce the exact match of the rule. For example, if the rule is currently configured with the log-end
    option, but this option is not specified in the state method, it will be removed and reset to the system default.

    It is strongly recommended to specify all options to ensure proper operation.

    When defining the profile group settings, the device can only support either a profile group or individual settings.
    If both are specified, the profile group will be preferred and the individual settings are ignored. If neither are
    specified, the value will be set to system default of none.

    name: The name of the module function to execute.

    rulename(str): The name of the security rule.  The name is case-sensitive and can have up to 31 characters, which
    can be letters, numbers, spaces, hyphens, and underscores. The name must be unique on a firewall and, on Panorama,
    unique within its device group and any ancestor or descendant device groups.

    vsys(str): The string representation of the VSYS ID. Defaults to VSYS 1.

    action(str): The action that the security rule will enforce. Valid options are: allow, deny, drop, reset-client,
    reset-server, reset-both.

    disabled(bool): Controls if the rule is disabled. Set 'True' to disable and 'False' to enable.

    sourcezone(str, list): The source zone(s). The value 'any' will match all zones.

    destinationzone(str, list): The destination zone(s). The value 'any' will match all zones.

    source(str, list): The source address(es). The value 'any' will match all addresses.

    destination(str, list): The destination address(es). The value 'any' will match all addresses.

    application(str, list): The application(s) matched. The value 'any' will match all applications.

    service(str, list): The service(s) matched. The value 'any' will match all services. The value
    'application-default' will match based upon the application defined ports.

    description(str): A description for the policy (up to 255 characters).

    logsetting(str): The name of a valid log forwarding profile.

    logstart(bool): Generates a traffic log entry for the start of a session (disabled by default).

    logend(bool): Generates a traffic log entry for the end of a session (enabled by default).

    negatesource(bool): Match all but the specified source addresses.

    negatedestination(bool): Match all but the specified destination addresses.

    profilegroup(str): A valid profile group name.

    datafilter(str): A valid data filter profile name. Ignored with the profilegroup option set.

    fileblock(str): A valid file blocking profile name. Ignored with the profilegroup option set.

    spyware(str): A valid spyware profile name. Ignored with the profilegroup option set.

    urlfilter(str): A valid URL filtering profile name. Ignored with the profilegroup option set.

    virus(str): A valid virus profile name. Ignored with the profilegroup option set.

    vulnerability(str): A valid vulnerability profile name. Ignored with the profilegroup option set.

    wildfire(str): A valid vulnerability profile name. Ignored with the profilegroup option set.

    move(str): An optional argument that ensure the rule is moved to a specific location. Valid options are 'top',
    'bottom', 'before', or 'after'. The 'before' and 'after' options require the use of the 'movetarget' argument
    to define the location of the move request.

    movetarget(str): An optional argument that defines the target of the move operation if the move argument is
    set to 'before' or 'after'.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/rulebase/security/rule01:
            panos.security_rule_exists:
              - rulename: rule01
              - vsys: 1
              - action: allow
              - disabled: False
              - sourcezone: untrust
              - destinationzone: trust
              - source:
                - 10.10.10.0/24
                - 1.1.1.1
              - destination:
                - 2.2.2.2-2.2.2.4
              - application:
                - any
              - service:
                - tcp-25
              - description: My test security rule
              - logsetting: logprofile
              - logstart: False
              - logend: True
              - negatesource: False
              - negatedestination: False
              - profilegroup: myprofilegroup
              - move: top
              - commit: False

        panos/rulebase/security/rule01:
            panos.security_rule_exists:
              - rulename: rule01
              - vsys: 1
              - action: allow
              - disabled: False
              - sourcezone: untrust
              - destinationzone: trust
              - source:
                - 10.10.10.0/24
                - 1.1.1.1
              - destination:
                - 2.2.2.2-2.2.2.4
              - application:
                - any
              - service:
                - tcp-25
              - description: My test security rule
              - logsetting: logprofile
              - logstart: False
              - logend: False
              - datafilter: foobar
              - fileblock: foobar
              - spyware: foobar
              - urlfilter: foobar
              - virus: foobar
              - vulnerability: foobar
              - wildfire: foobar
              - move: after
              - movetarget: rule02
              - commit: False
    """
    ret = _default_ret(name)

    if not rulename:
        return ret

    # Check if rule currently exists
    rule = __salt__["panos.get_security_rule"](rulename, vsys)["result"]

    if rule and "entry" in rule:
        rule = rule["entry"]
    else:
        rule = {}

    # Build the rule element
    element = ""
    if sourcezone:
        element += "<from>{0}</from>".format(_build_members(sourcezone, True))
    else:
        ret.update({"comment": "The sourcezone field must be provided."})
        return ret

    if destinationzone:
        element += "<to>{0}</to>".format(_build_members(destinationzone, True))
    else:
        ret.update({"comment": "The destinationzone field must be provided."})
        return ret

    if source:
        element += "<source>{0}</source>".format(_build_members(source, True))
    else:
        ret.update({"comment": "The source field must be provided."})
        return

    if destination:
        element += "<destination>{0}</destination>".format(
            _build_members(destination, True)
        )
    else:
        ret.update({"comment": "The destination field must be provided."})
        return ret

    if application:
        element += "<application>{0}</application>".format(
            _build_members(application, True)
        )
    else:
        ret.update({"comment": "The application field must be provided."})
        return ret

    if service:
        element += "<service>{0}</service>".format(_build_members(service, True))
    else:
        ret.update({"comment": "The service field must be provided."})
        return ret

    if action:
        element += "<action>{0}</action>".format(action)
    else:
        ret.update({"comment": "The action field must be provided."})
        return ret

    if disabled is not None:
        if disabled:
            element += "<disabled>yes</disabled>"
        else:
            element += "<disabled>no</disabled>"

    if description:
        element += "<description>{0}</description>".format(description)

    if logsetting:
        element += "<log-setting>{0}</log-setting>".format(logsetting)

    if logstart is not None:
        if logstart:
            element += "<log-start>yes</log-start>"
        else:
            element += "<log-start>no</log-start>"

    if logend is not None:
        if logend:
            element += "<log-end>yes</log-end>"
        else:
            element += "<log-end>no</log-end>"

    if negatesource is not None:
        if negatesource:
            element += "<negate-source>yes</negate-source>"
        else:
            element += "<negate-source>no</negate-source>"

    if negatedestination is not None:
        if negatedestination:
            element += "<negate-destination>yes</negate-destination>"
        else:
            element += "<negate-destination>no</negate-destination>"

    # Build the profile settings
    profile_string = None
    if profilegroup:
        profile_string = "<group><member>{0}</member></group>".format(profilegroup)
    else:
        member_string = ""
        if datafilter:
            member_string += "<data-filtering><member>{0}</member></data-filtering>".format(
                datafilter
            )
        if fileblock:
            member_string += "<file-blocking><member>{0}</member></file-blocking>".format(
                fileblock
            )
        if spyware:
            member_string += "<spyware><member>{0}</member></spyware>".format(spyware)
        if urlfilter:
            member_string += "<url-filtering><member>{0}</member></url-filtering>".format(
                urlfilter
            )
        if virus:
            member_string += "<virus><member>{0}</member></virus>".format(virus)
        if vulnerability:
            member_string += "<vulnerability><member>{0}</member></vulnerability>".format(
                vulnerability
            )
        if wildfire:
            member_string += "<wildfire-analysis><member>{0}</member></wildfire-analysis>".format(
                wildfire
            )
        if member_string != "":
            profile_string = "<profiles>{0}</profiles>".format(member_string)

    if profile_string:
        element += "<profile-setting>{0}</profile-setting>".format(profile_string)

    full_element = "<entry name='{0}'>{1}</entry>".format(rulename, element)

    new_rule = xml.to_dict(ET.fromstring(full_element), True)

    config_change = False

    if rule == new_rule:
        ret.update({"comment": "Security rule already exists. No changes required."})
    else:
        config_change = True
        xpath = (
            "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys{0}']/rulebase/"
            "security/rules/entry[@name='{1}']".format(vsys, rulename)
        )

        result, msg = _edit_config(xpath, full_element)

        if not result:
            ret.update({"comment": msg})
            return ret

        ret.update(
            {
                "changes": {"before": rule, "after": new_rule},
                "comment": "Security rule verified successfully.",
            }
        )

    if move:
        movepath = (
            "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys{0}']/rulebase/"
            "security/rules/entry[@name='{1}']".format(vsys, rulename)
        )
        move_result = False
        move_msg = ""
        if move == "before" and movetarget:
            move_result, move_msg = _move_before(movepath, movetarget)
        elif move == "after":
            move_result, move_msg = _move_after(movepath, movetarget)
        elif move == "top":
            move_result, move_msg = _move_top(movepath)
        elif move == "bottom":
            move_result, move_msg = _move_bottom(movepath)

        if config_change:
            ret.update(
                {"changes": {"before": rule, "after": new_rule, "move": move_msg}}
            )
        else:
            ret.update({"changes": {"move": move_msg}})

        if not move_result:
            ret.update({"comment": move_msg})
            return ret

    if commit is True:
        ret.update({"commit": __salt__["panos.commit"](), "result": True})
    else:
        ret.update({"result": True})

    return ret


def service_exists(
    name,
    servicename=None,
    vsys=1,
    protocol=None,
    port=None,
    description=None,
    commit=False,
):
    """
    Ensures that a service object exists in the configured state. If it does not exist or is not configured with the
    specified attributes, it will be adjusted to match the specified values.

    name: The name of the module function to execute.

    servicename(str): The name of the security object.  The name is case-sensitive and can have up to 31 characters,
    which an be letters, numbers, spaces, hyphens, and underscores. The name must be unique on a firewall and, on
    Panorama, unique within its device group and any ancestor or descendant device groups.

    vsys(str): The string representation of the VSYS ID. Defaults to VSYS 1.

    protocol(str): The protocol that is used by the service object. The only valid options are tcp and udp.

    port(str): The port number that is used by the service object. This can be specified as a single integer or a
    valid range of ports.

    description(str): A description for the policy (up to 255 characters).

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/service/tcp-80:
            panos.service_exists:
              - servicename: tcp-80
              - vsys: 1
              - protocol: tcp
              - port: 80
              - description: Hypertext Transfer Protocol
              - commit: False

        panos/service/udp-500-550:
            panos.service_exists:
              - servicename: udp-500-550
              - vsys: 3
              - protocol: udp
              - port: 500-550
              - commit: False

    """
    ret = _default_ret(name)

    if not servicename:
        ret.update({"comment": "The service name field must be provided."})
        return ret

    # Check if service object currently exists
    service = __salt__["panos.get_service"](servicename, vsys)["result"]

    if service and "entry" in service:
        service = service["entry"]
    else:
        service = {}

    # Verify the arguments
    if not protocol and protocol not in ["tcp", "udp"]:
        ret.update({"comment": "The protocol must be provided and must be tcp or udp."})
        return ret
    if not port:
        ret.update({"comment": "The port field must be provided."})
        return ret

    element = "<protocol><{0}><port>{1}</port></{0}></protocol>".format(protocol, port)

    if description:
        element += "<description>{0}</description>".format(description)

    full_element = "<entry name='{0}'>{1}</entry>".format(servicename, element)

    new_service = xml.to_dict(ET.fromstring(full_element), True)

    if service == new_service:
        ret.update(
            {
                "comment": "Service object already exists. No changes required.",
                "result": True,
            }
        )
        return ret
    else:
        xpath = (
            "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys{0}']/service/"
            "entry[@name='{1}']".format(vsys, servicename)
        )

        result, msg = _edit_config(xpath, full_element)

        if not result:
            ret.update({"comment": msg})
            return ret

    if commit is True:
        ret.update(
            {
                "changes": {"before": service, "after": new_service},
                "commit": __salt__["panos.commit"](),
                "comment": "Service object successfully configured.",
                "result": True,
            }
        )
    else:
        ret.update(
            {
                "changes": {"before": service, "after": new_service},
                "comment": "Service object successfully configured.",
                "result": True,
            }
        )

    return ret


def service_group_exists(
    name, groupname=None, vsys=1, members=None, description=None, commit=False
):
    """
    Ensures that a service group object exists in the configured state. If it does not exist or is not configured with
    the specified attributes, it will be adjusted to match the specified values.

    This module will enforce group membership. If a group exists and contains members this state does not include,
    those members will be removed and replaced with the specified members in the state.

    name: The name of the module function to execute.

    groupname(str): The name of the service group object.  The name is case-sensitive and can have up to 31 characters,
    which an be letters, numbers, spaces, hyphens, and underscores. The name must be unique on a firewall and, on
    Panorama, unique within its device group and any ancestor or descendant device groups.

    vsys(str): The string representation of the VSYS ID. Defaults to VSYS 1.

    members(str, list): The members of the service group. These must be valid service objects or service groups on the
    system that already exist prior to the execution of this state.

    description(str): A description for the policy (up to 255 characters).

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/service-group/my-group:
            panos.service_group_exists:
              - groupname: my-group
              - vsys: 1
              - members:
                - tcp-80
                - custom-port-group
              - description: A group that needs to exist
              - commit: False

    """
    ret = _default_ret(name)

    if not groupname:
        ret.update({"comment": "The group name field must be provided."})
        return ret

    # Check if service group object currently exists
    group = __salt__["panos.get_service_group"](groupname, vsys)["result"]

    if group and "entry" in group:
        group = group["entry"]
    else:
        group = {}

    # Verify the arguments
    if members:
        element = "<members>{0}</members>".format(_build_members(members, True))
    else:
        ret.update({"comment": "The group members must be provided."})
        return ret

    if description:
        element += "<description>{0}</description>".format(description)

    full_element = "<entry name='{0}'>{1}</entry>".format(groupname, element)

    new_group = xml.to_dict(ET.fromstring(full_element), True)

    if group == new_group:
        ret.update(
            {
                "comment": "Service group object already exists. No changes required.",
                "result": True,
            }
        )
        return ret
    else:
        xpath = (
            "/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='vsys{0}']/service-group/"
            "entry[@name='{1}']".format(vsys, groupname)
        )

        result, msg = _edit_config(xpath, full_element)

        if not result:
            ret.update({"comment": msg})
            return ret

    if commit is True:
        ret.update(
            {
                "changes": {"before": group, "after": new_group},
                "commit": __salt__["panos.commit"](),
                "comment": "Service group object successfully configured.",
                "result": True,
            }
        )
    else:
        ret.update(
            {
                "changes": {"before": group, "after": new_group},
                "comment": "Service group object successfully configured.",
                "result": True,
            }
        )

    return ret


def set_config(name, xpath=None, value=None, commit=False):
    """
    Sets a Palo Alto XPATH to a specific value. This will always overwrite the existing value, even if it is not
    changed.

    You can add or create a new object at a specified location in the configuration hierarchy. Use the xpath parameter
    to specify the location of the object in the configuration

    name: The name of the module function to execute.

    xpath(str): The XPATH of the configuration API tree to control.

    value(str): The XML value to set. This must be a child to the XPATH.

    commit(bool): If true the firewall will commit the changes, if false do not commit changes.

    SLS Example:

    .. code-block:: yaml

        panos/hostname:
            panos.set_config:
              - xpath: /config/devices/entry[@name='localhost.localdomain']/deviceconfig/system
              - value: <hostname>foobar</hostname>
              - commit: True

    """
    ret = _default_ret(name)

    result, msg = _set_config(xpath, value)

    ret.update({"comment": msg, "result": result})

    if not result:
        return ret

    if commit is True:
        ret.update({"commit": __salt__["panos.commit"](), "result": True})

    return ret
