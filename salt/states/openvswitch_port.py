"""
Management of Open vSwitch ports.
"""


def __virtual__():
    """
    Only make these states available if Open vSwitch module is available.
    """
    if "openvswitch.port_add" in __salt__:
        return True
    return (False, "openvswitch module could not be loaded")


def present(
    name, bridge, tunnel_type=None, id=None, remote=None, dst_port=None, internal=False
):
    """
    Ensures that the named port exists on bridge, eventually creates it.

    Args:
        name: The name of the port.
        bridge: The name of the bridge.
        tunnel_type: Optional type of interface to create, currently supports: vlan, vxlan and gre.
        id: Optional tunnel's key.
        remote: Remote endpoint's IP address.
        dst_port: Port to use when creating tunnelport in the switch.
        internal: Create an internal port if one does not exist

    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    tunnel_types = ("vlan", "vxlan", "gre")

    if tunnel_type and tunnel_type not in tunnel_types:
        raise TypeError(
            "The optional type argument must be one of these values: {}.".format(
                str(tunnel_types)
            )
        )

    bridge_exists = __salt__["openvswitch.bridge_exists"](bridge)
    port_list = []
    if bridge_exists:
        port_list = __salt__["openvswitch.port_list"](bridge)

    # Comment and change messages

    comments = {}

    comments["comment_bridge_notexists"] = f"Bridge {bridge} does not exist."
    comments["comment_port_exists"] = f"Port {name} already exists."
    comments["comment_port_created"] = "Port {} created on bridge {}.".format(
        name, bridge
    )
    comments["comment_port_notcreated"] = (
        f"Unable to create port {name} on bridge {bridge}."
    )
    comments["changes_port_created"] = {
        name: {
            "old": f"No port named {name} present.",
            "new": f"Created port {name} on bridge {bridge}.",
        }
    }
    comments["comment_port_internal"] = (
        "Port {} already exists, but interface type has been changed to internal.".format(
            name
        )
    )
    comments["changes_port_internal"] = {"internal": {"old": False, "new": True}}
    comments["comment_port_internal_not_changed"] = (
        "Port {} already exists, but the interface type could not be changed to"
        " internal.".format(name)
    )

    if tunnel_type:
        comments["comment_invalid_ip"] = "Remote is not valid ip address."
        if tunnel_type == "vlan":
            comments["comment_vlan_invalid_id"] = "VLANs id must be between 0 and 4095."
            comments["comment_vlan_invalid_name"] = (
                f"Could not find network interface {name}."
            )
            comments["comment_vlan_port_exists"] = (
                "Port {} with access to VLAN {} already exists on bridge {}.".format(
                    name, id, bridge
                )
            )
            comments["comment_vlan_created"] = (
                "Created port {} with access to VLAN {} on bridge {}.".format(
                    name, id, bridge
                )
            )
            comments["comment_vlan_notcreated"] = (
                "Unable to create port {} with access to VLAN {} on bridge {}.".format(
                    name, id, bridge
                )
            )
            comments["changes_vlan_created"] = {
                name: {
                    "old": (
                        "No port named {} with access to VLAN {} present on "
                        "bridge {} present.".format(name, id, bridge)
                    ),
                    "new": (
                        "Created port {1} with access to VLAN {2} on "
                        "bridge {0}.".format(bridge, name, id)
                    ),
                }
            }

        elif tunnel_type == "gre":
            comments["comment_gre_invalid_id"] = (
                "Id of GRE tunnel must be an unsigned 32-bit integer."
            )
            comments["comment_gre_interface_exists"] = (
                "GRE tunnel interface {} with rempte ip {} and key {} "
                "already exists on bridge {}.".format(name, remote, id, bridge)
            )
            comments["comment_gre_created"] = (
                "Created GRE tunnel interface {} with remote ip {}  and key {} "
                "on bridge {}.".format(name, remote, id, bridge)
            )
            comments["comment_gre_notcreated"] = (
                "Unable to create GRE tunnel interface {} with remote ip {} and key {} "
                "on bridge {}.".format(name, remote, id, bridge)
            )
            comments["changes_gre_created"] = {
                name: {
                    "old": (
                        "No GRE tunnel interface {} with remote ip {} and key {} "
                        "on bridge {} present.".format(name, remote, id, bridge)
                    ),
                    "new": (
                        "Created GRE tunnel interface {} with remote ip {} and key {} "
                        "on bridge {}.".format(name, remote, id, bridge)
                    ),
                }
            }
        elif tunnel_type == "vxlan":
            comments["comment_dstport"] = (
                " (dst_port" + str(dst_port) + ")" if 0 < dst_port <= 65535 else ""
            )
            comments["comment_vxlan_invalid_id"] = (
                "Id of VXLAN tunnel must be an unsigned 64-bit integer."
            )
            comments["comment_vxlan_interface_exists"] = (
                "VXLAN tunnel interface {} with rempte ip {} and key {} "
                "already exists on bridge {}{}.".format(
                    name, remote, id, bridge, comments["comment_dstport"]
                )
            )
            comments["comment_vxlan_created"] = (
                "Created VXLAN tunnel interface {} with remote ip {}  and key {} "
                "on bridge {}{}.".format(
                    name, remote, id, bridge, comments["comment_dstport"]
                )
            )
            comments["comment_vxlan_notcreated"] = (
                "Unable to create VXLAN tunnel interface {} with remote ip {} and key"
                " {} on bridge {}{}.".format(
                    name, remote, id, bridge, comments["comment_dstport"]
                )
            )
            comments["changes_vxlan_created"] = {
                name: {
                    "old": (
                        "No VXLAN tunnel interface {} with remote ip {} and key {} "
                        "on bridge {}{} present.".format(
                            name, remote, id, bridge, comments["comment_dstport"]
                        )
                    ),
                    "new": (
                        "Created VXLAN tunnel interface {} with remote ip {} and key {}"
                        " on bridge {}{}.".format(
                            name, remote, id, bridge, comments["comment_dstport"]
                        )
                    ),
                }
            }

    # Check VLANs attributes
    def _check_vlan():
        tag = __salt__["openvswitch.port_get_tag"](name)
        interfaces = __salt__["network.interfaces"]()
        if not 0 <= id <= 4095:
            ret["result"] = False
            ret["comment"] = comments["comment_vlan_invalid_id"]
        elif not internal and name not in interfaces:
            ret["result"] = False
            ret["comment"] = comments["comment_vlan_invalid_name"]
        elif tag and name in port_list:
            try:
                if int(tag[0]) == id:
                    ret["result"] = True
                    ret["comment"] = comments["comment_vlan_port_exists"]
            except (ValueError, KeyError):
                pass

    # Check GRE tunnels attributes
    def _check_gre():
        interface_options = __salt__["openvswitch.interface_get_options"](name)
        interface_type = __salt__["openvswitch.interface_get_type"](name)
        if not 0 <= id <= 2**32:
            ret["result"] = False
            ret["comment"] = comments["comment_gre_invalid_id"]
        elif not __salt__["dig.check_ip"](remote):
            ret["result"] = False
            ret["comment"] = comments["comment_invalid_ip"]
        elif interface_options and interface_type and name in port_list:
            interface_attroptions = (
                '{key="' + str(id) + '", remote_ip="' + str(remote) + '"}'
            )
            try:
                if (
                    interface_type[0] == "gre"
                    and interface_options[0] == interface_attroptions
                ):
                    ret["result"] = True
                    ret["comment"] = comments["comment_gre_interface_exists"]
            except KeyError:
                pass

    # Check VXLAN tunnels attributes
    def _check_vxlan():
        interface_options = __salt__["openvswitch.interface_get_options"](name)
        interface_type = __salt__["openvswitch.interface_get_type"](name)
        if not 0 <= id <= 2**64:
            ret["result"] = False
            ret["comment"] = comments["comment_vxlan_invalid_id"]
        elif not __salt__["dig.check_ip"](remote):
            ret["result"] = False
            ret["comment"] = comments["comment_invalid_ip"]
        elif interface_options and interface_type and name in port_list:
            opt_port = (
                'dst_port="' + str(dst_port) + '", ' if 0 < dst_port <= 65535 else ""
            )
            interface_attroptions = (
                f'{{{opt_port}key="' + str(id) + '", remote_ip="' + str(remote) + '"}'
            )
            try:
                if (
                    interface_type[0] == "vxlan"
                    and interface_options[0] == interface_attroptions
                ):
                    ret["result"] = True
                    ret["comment"] = comments["comment_vxlan_interface_exists"]
            except KeyError:
                pass

    # Dry run, test=true mode
    if __opts__["test"]:
        if bridge_exists:
            if tunnel_type == "vlan":
                _check_vlan()
                if not ret["comment"]:
                    ret["result"] = None
                    ret["comment"] = comments["comment_vlan_created"]
            elif tunnel_type == "vxlan":
                _check_vxlan()
                if not ret["comment"]:
                    ret["result"] = None
                    ret["comment"] = comments["comment_vxlan_created"]
            elif tunnel_type == "gre":
                _check_gre()
                if not ret["comment"]:
                    ret["result"] = None
                    ret["comment"] = comments["comment_gre_created"]
            else:
                if name in port_list:
                    ret["result"] = True
                    current_type = __salt__["openvswitch.interface_get_type"](name)
                    # The interface type is returned as a single-element list.
                    if internal and (current_type != ["internal"]):
                        ret["comment"] = comments["comment_port_internal"]
                    else:
                        ret["comment"] = comments["comment_port_exists"]
                else:
                    ret["result"] = None
                    ret["comment"] = comments["comment_port_created"]
        else:
            ret["result"] = None
            ret["comment"] = comments["comment_bridge_notexists"]

        return ret

    if bridge_exists:
        if tunnel_type == "vlan":
            _check_vlan()
            if not ret["comment"]:
                port_create_vlan = __salt__["openvswitch.port_create_vlan"](
                    bridge, name, id, internal
                )
                if port_create_vlan:
                    ret["result"] = True
                    ret["comment"] = comments["comment_vlan_created"]
                    ret["changes"] = comments["changes_vlan_created"]
                else:
                    ret["result"] = False
                    ret["comment"] = comments["comment_vlan_notcreated"]
        elif tunnel_type == "vxlan":
            _check_vxlan()
            if not ret["comment"]:
                port_create_vxlan = __salt__["openvswitch.port_create_vxlan"](
                    bridge, name, id, remote, dst_port
                )
                if port_create_vxlan:
                    ret["result"] = True
                    ret["comment"] = comments["comment_vxlan_created"]
                    ret["changes"] = comments["changes_vxlan_created"]
                else:
                    ret["result"] = False
                    ret["comment"] = comments["comment_vxlan_notcreated"]
        elif tunnel_type == "gre":
            _check_gre()
            if not ret["comment"]:
                port_create_gre = __salt__["openvswitch.port_create_gre"](
                    bridge, name, id, remote
                )
                if port_create_gre:
                    ret["result"] = True
                    ret["comment"] = comments["comment_gre_created"]
                    ret["changes"] = comments["changes_gre_created"]
                else:
                    ret["result"] = False
                    ret["comment"] = comments["comment_gre_notcreated"]
        else:
            if name in port_list:
                current_type = __salt__["openvswitch.interface_get_type"](name)
                # The interface type is returned as a single-element list.
                if internal and (current_type != ["internal"]):
                    # We do not have a direct way of only setting the interface
                    # type to internal, so we add the port with the --may-exist
                    # option.
                    port_add = __salt__["openvswitch.port_add"](
                        bridge, name, may_exist=True, internal=internal
                    )
                    if port_add:
                        ret["result"] = True
                        ret["comment"] = comments["comment_port_internal"]
                        ret["changes"] = comments["changes_port_internal"]
                    else:
                        ret["result"] = False
                        ret["comment"] = comments["comment_port_internal_not_changed"]
                else:
                    ret["result"] = True
                    ret["comment"] = comments["comment_port_exists"]
            else:
                port_add = __salt__["openvswitch.port_add"](
                    bridge, name, internal=internal
                )
                if port_add:
                    ret["result"] = True
                    ret["comment"] = comments["comment_port_created"]
                    ret["changes"] = comments["changes_port_created"]
                else:
                    ret["result"] = False
                    ret["comment"] = comments["comment_port_notcreated"]
    else:
        ret["result"] = False
        ret["comment"] = comments["comment_bridge_notexists"]

    return ret


def absent(name, bridge=None):
    """
    Ensures that the named port exists on bridge, eventually deletes it.
    If bridge is not set, port is removed from  whatever bridge contains it.

    Args:
        name: The name of the port.
        bridge: The name of the bridge.

    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    bridge_exists = False
    if bridge:
        bridge_exists = __salt__["openvswitch.bridge_exists"](bridge)
        if bridge_exists:
            port_list = __salt__["openvswitch.port_list"](bridge)
        else:
            port_list = ()
    else:
        port_list = [name]

    # Comment and change messages
    comments = {}
    comments["comment_bridge_notexists"] = f"Bridge {bridge} does not exist."
    comments["comment_port_notexists"] = "Port {} does not exist on bridge {}.".format(
        name, bridge
    )
    comments["comment_port_deleted"] = f"Port {name} deleted."
    comments["comment_port_notdeleted"] = f"Unable to delete port {name}."
    comments["changes_port_deleted"] = {
        name: {
            "old": f"Port named {name} may exist.",
            "new": f"Deleted port {name}.",
        }
    }

    # Dry run, test=true mode
    if __opts__["test"]:
        if bridge and not bridge_exists:
            ret["result"] = None
            ret["comment"] = comments["comment_bridge_notexists"]
        elif name not in port_list:
            ret["result"] = True
            ret["comment"] = comments["comment_port_notexists"]
        else:
            ret["result"] = None
            ret["comment"] = comments["comment_port_deleted"]
        return ret

    if bridge and not bridge_exists:
        ret["result"] = False
        ret["comment"] = comments["comment_bridge_notexists"]
    elif name not in port_list:
        ret["result"] = True
        ret["comment"] = comments["comment_port_notexists"]
    else:
        if bridge:
            port_remove = __salt__["openvswitch.port_remove"](br=bridge, port=name)
        else:
            port_remove = __salt__["openvswitch.port_remove"](br=None, port=name)

        if port_remove:
            ret["result"] = True
            ret["comment"] = comments["comment_port_deleted"]
            ret["changes"] = comments["changes_port_deleted"]
        else:
            ret["result"] = False
            ret["comment"] = comments["comment_port_notdeleted"]

    return ret
