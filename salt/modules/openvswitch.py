"""
Support for Open vSwitch - module with basic Open vSwitch commands.

Suitable for setting up Openstack Neutron.

:codeauthor: Jiri Kotlin <jiri.kotlin@ultimum.io>
"""

import logging

import salt.utils.path
from salt.exceptions import ArgumentValueError, CommandExecutionError
from salt.utils import json

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load the module if Open vSwitch is installed
    """
    if salt.utils.path.which("ovs-vsctl"):
        return "openvswitch"
    return (False, "Missing dependency: ovs-vsctl")


def _param_may_exist(may_exist):
    """
    Returns --may-exist parameter for Open vSwitch command.

    Args:
        may_exist: Boolean whether to use this parameter.

    Returns:
        String '--may-exist ' or empty string.
    """
    if may_exist:
        return "--may-exist "
    else:
        return ""


def _param_if_exists(if_exists):
    """
    Returns --if-exist parameter for Open vSwitch command.

    Args:
        if_exists: Boolean whether to use this parameter.

    Returns:
        String '--if-exist ' or empty string.
    """
    if if_exists:
        return "--if-exists "
    else:
        return ""


def _retcode_to_bool(retcode):
    """
    Evaulates Open vSwitch command`s retcode value.

    Args:
        retcode: Value of retcode field from response, should be 0, 1 or 2.

    Returns:
        True on 0, else False
    """
    if retcode == 0:
        return True
    else:
        return False


def _stdout_list_split(retcode, stdout="", splitstring="\n"):
    """
    Evaulates Open vSwitch command`s retcode value.

    Args:
        retcode: Value of retcode field from response, should be 0, 1 or 2.
        stdout: Value of stdout filed from response.
        splitstring: String used to split the stdout default new line.

    Returns:
        List or False.
    """
    if retcode == 0:
        ret = stdout.split(splitstring)
        return ret
    else:
        return False


def _convert_json(obj):
    """
    Converts from the JSON output provided by ovs-vsctl into a usable Python
    object tree. In particular, sets and maps are converted from lists to
    actual sets or maps.

    Args:
        obj: Object that shall be recursively converted.

    Returns:
        Converted version of object.
    """
    if isinstance(obj, dict):
        return {_convert_json(key): _convert_json(val) for (key, val) in obj.items()}
    elif isinstance(obj, list) and len(obj) == 2:
        first = obj[0]
        second = obj[1]
        if first == "set" and isinstance(second, list):
            return [_convert_json(elem) for elem in second]
        elif first == "map" and isinstance(second, list):
            for elem in second:
                if not isinstance(elem, list) or len(elem) != 2:
                    return obj
            return {elem[0]: _convert_json(elem[1]) for elem in second}
        else:
            return obj
    elif isinstance(obj, list):
        return [_convert_json(elem) for elem in obj]
    else:
        return obj


def _stdout_parse_json(stdout):
    """
    Parses JSON output from ovs-vsctl and returns the corresponding object
    tree.

    Args:
        stdout: Output that shall be parsed.

    Returns:
        Object represented by the output.
    """
    obj = json.loads(stdout)
    return _convert_json(obj)


def bridge_list():
    """
    Lists all existing real and fake bridges.

    Returns:
        List of bridges (or empty list), False on failure.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.bridge_list
    """
    cmd = "ovs-vsctl list-br"
    result = __salt__["cmd.run_all"](cmd)
    retcode = result["retcode"]
    stdout = result["stdout"]
    return _stdout_list_split(retcode, stdout)


def bridge_exists(br):
    """
    Tests whether bridge exists as a real or fake  bridge.

    Returns:
        True if Bridge exists, else False.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.bridge_exists br0
    """
    cmd = "ovs-vsctl br-exists {}".format(br)
    result = __salt__["cmd.run_all"](cmd)
    retcode = result["retcode"]
    return _retcode_to_bool(retcode)


def bridge_create(br, may_exist=True, parent=None, vlan=None):
    """
    Creates a new bridge.

    Args:
        br : string
            bridge name
        may_exist : bool
            if False - attempting to create a bridge that exists returns False.
        parent : string
            name of the parent bridge (if the bridge shall be created as a fake
            bridge). If specified, vlan must also be specified.
        .. versionadded:: 3006
        vlan : int
            VLAN ID of the bridge (if the bridge shall be created as a fake
            bridge). If specified, parent must also be specified.
        .. versionadded:: 3006

    Returns:
        True on success, else False.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.bridge_create br0
    """
    param_may_exist = _param_may_exist(may_exist)
    if parent is not None and vlan is None:
        raise ArgumentValueError("If parent is specified, vlan must also be specified.")
    if vlan is not None and parent is None:
        raise ArgumentValueError("If vlan is specified, parent must also be specified.")
    param_parent = "" if parent is None else " {}".format(parent)
    param_vlan = "" if vlan is None else " {}".format(vlan)
    cmd = "ovs-vsctl {1}add-br {0}{2}{3}".format(
        br, param_may_exist, param_parent, param_vlan
    )
    result = __salt__["cmd.run_all"](cmd)
    return _retcode_to_bool(result["retcode"])


def bridge_delete(br, if_exists=True):
    """
    Deletes bridge and all of  its  ports.

    Args:
        br: A string - bridge name
        if_exists: Bool, if False - attempting to delete a bridge that does not exist returns False.

    Returns:
        True on success, else False.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.bridge_delete br0
    """
    param_if_exists = _param_if_exists(if_exists)
    cmd = "ovs-vsctl {1}del-br {0}".format(br, param_if_exists)
    result = __salt__["cmd.run_all"](cmd)
    retcode = result["retcode"]
    return _retcode_to_bool(retcode)


def bridge_to_parent(br):
    """
    .. versionadded:: 3006

    Returns the parent bridge of a bridge.

    Args:
        br : string
            bridge name

    Returns:
        Name of the parent bridge. This is the same as the bridge name if the
        bridge is not a fake bridge. If the bridge does not exist, False is
        returned.

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.bridge_to_parent br0
    """
    cmd = "ovs-vsctl br-to-parent {}".format(br)
    result = __salt__["cmd.run_all"](cmd)
    if result["retcode"] != 0:
        return False
    return result["stdout"].strip()


def bridge_to_vlan(br):
    """
    .. versionadded:: 3006

    Returns the VLAN ID of a bridge.

    Args:
        br : string
            bridge name

    Returns:
        VLAN ID of the bridge. The VLAN ID is 0 if the bridge is not a fake
        bridge.  If the bridge does not exist, False is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.bridge_to_parent br0
    """
    cmd = "ovs-vsctl br-to-vlan {}".format(br)
    result = __salt__["cmd.run_all"](cmd)
    if result["retcode"] != 0:
        return False
    return int(result["stdout"])


def port_add(br, port, may_exist=False, internal=False):
    """
    Creates on bridge a new port named port.

    Returns:
        True on success, else False.

    Args:
        br: A string - bridge name
        port: A string - port name
        may_exist: Bool, if False - attempting to create a port that exists returns False.
        internal: A boolean to create an internal interface if one does not exist.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.port_add br0 8080
    """
    param_may_exist = _param_may_exist(may_exist)
    cmd = "ovs-vsctl {2}add-port {0} {1}".format(br, port, param_may_exist)
    if internal:
        cmd += " -- set interface {} type=internal".format(port)
    result = __salt__["cmd.run_all"](cmd)
    retcode = result["retcode"]
    return _retcode_to_bool(retcode)


def port_remove(br, port, if_exists=True):
    """
     Deletes port.

    Args:
        br: A string - bridge name (If bridge is None, port is removed from  whatever bridge contains it)
        port: A string - port name.
        if_exists: Bool, if False - attempting to delete a por that  does  not exist returns False. (Default True)

    Returns:
        True on success, else False.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.port_remove br0 8080
    """
    param_if_exists = _param_if_exists(if_exists)

    if port and not br:
        cmd = "ovs-vsctl {1}del-port {0}".format(port, param_if_exists)
    else:
        cmd = "ovs-vsctl {2}del-port {0} {1}".format(br, port, param_if_exists)
    result = __salt__["cmd.run_all"](cmd)
    retcode = result["retcode"]
    return _retcode_to_bool(retcode)


def port_list(br):
    """
    Lists all of the ports within bridge.

    Args:
        br: A string - bridge name.

    Returns:
        List of bridges (or empty list), False on failure.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.port_list br0
    """
    cmd = "ovs-vsctl list-ports {}".format(br)
    result = __salt__["cmd.run_all"](cmd)
    retcode = result["retcode"]
    stdout = result["stdout"]
    return _stdout_list_split(retcode, stdout)


def port_get_tag(port):
    """
    Lists tags of the port.

    Args:
        port: A string - port name.

    Returns:
        List of tags (or empty list), False on failure.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.port_get_tag tap0
    """
    cmd = "ovs-vsctl get port {} tag".format(port)
    result = __salt__["cmd.run_all"](cmd)
    retcode = result["retcode"]
    stdout = result["stdout"]
    return _stdout_list_split(retcode, stdout)


def interface_get_options(port):
    """
    Port's interface's optional parameters.

    Args:
        port: A string - port name.

    Returns:
        String containing optional parameters of port's interface, False on failure.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.interface_get_options tap0
    """
    cmd = "ovs-vsctl get interface {} options".format(port)
    result = __salt__["cmd.run_all"](cmd)
    retcode = result["retcode"]
    stdout = result["stdout"]
    return _stdout_list_split(retcode, stdout)


def interface_get_type(port):
    """
    Type of port's interface.

    Args:
        port: A string - port name.

    Returns:
        String - type of interface or empty string, False on failure.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' openvswitch.interface_get_type tap0
    """
    cmd = "ovs-vsctl get interface {} type".format(port)
    result = __salt__["cmd.run_all"](cmd)
    retcode = result["retcode"]
    stdout = result["stdout"]
    return _stdout_list_split(retcode, stdout)


def port_create_vlan(br, port, id, internal=False):
    """
    Isolate VM traffic using VLANs.

    Args:
        br: A string - bridge name.
        port: A string - port name.
        id: An integer in the valid range 0 to 4095 (inclusive), name of VLAN.
        internal: A boolean to create an internal interface if one does not exist.

    Returns:
        True on success, else False.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

       salt '*' openvswitch.port_create_vlan br0 tap0 100
    """
    interfaces = __salt__["network.interfaces"]()
    if not 0 <= id <= 4095:
        return False
    elif not bridge_exists(br):
        return False
    elif not internal and port not in interfaces:
        return False
    elif port in port_list(br):
        cmd = "ovs-vsctl set port {} tag={}".format(port, id)
        if internal:
            cmd += " -- set interface {} type=internal".format(port)
        result = __salt__["cmd.run_all"](cmd)
        return _retcode_to_bool(result["retcode"])
    else:
        cmd = "ovs-vsctl add-port {} {} tag={}".format(br, port, id)
        if internal:
            cmd += " -- set interface {} type=internal".format(port)
        result = __salt__["cmd.run_all"](cmd)
        return _retcode_to_bool(result["retcode"])


def port_create_gre(br, port, id, remote):
    """
    Generic Routing Encapsulation - creates GRE tunnel between endpoints.

    Args:
        br: A string - bridge name.
        port: A string - port name.
        id: An integer - unsigned 32-bit number, tunnel's key.
        remote: A string - remote endpoint's IP address.

    Returns:
        True on success, else False.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

       salt '*' openvswitch.port_create_gre br0 gre1 5001 192.168.1.10
    """
    if not 0 <= id < 2**32:
        return False
    elif not __salt__["dig.check_ip"](remote):
        return False
    elif not bridge_exists(br):
        return False
    elif port in port_list(br):
        cmd = "ovs-vsctl set interface {} type=gre options:remote_ip={} options:key={}".format(
            port, remote, id
        )
        result = __salt__["cmd.run_all"](cmd)
        return _retcode_to_bool(result["retcode"])
    else:
        cmd = (
            "ovs-vsctl add-port {0} {1} -- set interface {1} type=gre"
            " options:remote_ip={2} options:key={3}".format(br, port, remote, id)
        )
        result = __salt__["cmd.run_all"](cmd)
        return _retcode_to_bool(result["retcode"])


def port_create_vxlan(br, port, id, remote, dst_port=None):
    """
    Virtual eXtensible Local Area Network - creates VXLAN tunnel between endpoints.

    Args:
        br: A string - bridge name.
        port: A string - port name.
        id: An integer - unsigned 64-bit number, tunnel's key.
        remote: A string - remote endpoint's IP address.
        dst_port: An integer - port to use when creating tunnelport in the switch.

    Returns:
        True on success, else False.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

       salt '*' openvswitch.port_create_vxlan br0 vx1 5001 192.168.1.10 8472
    """
    dst_port = " options:dst_port=" + str(dst_port) if 0 < dst_port <= 65535 else ""
    if not 0 <= id < 2**64:
        return False
    elif not __salt__["dig.check_ip"](remote):
        return False
    elif not bridge_exists(br):
        return False
    elif port in port_list(br):
        cmd = (
            "ovs-vsctl set interface {} type=vxlan options:remote_ip={} "
            "options:key={}{}".format(port, remote, id, dst_port)
        )
        result = __salt__["cmd.run_all"](cmd)
        return _retcode_to_bool(result["retcode"])
    else:
        cmd = (
            "ovs-vsctl add-port {0} {1} -- set interface {1} type=vxlan"
            " options:remote_ip={2} options:key={3}{4}".format(
                br, port, remote, id, dst_port
            )
        )
        result = __salt__["cmd.run_all"](cmd)
        return _retcode_to_bool(result["retcode"])


def db_get(table, record, column, if_exists=False):
    """
    .. versionadded:: 3006

    Gets a column's value for a specific record.

    Args:
        table : string
            name of the database table
        record : string
            identifier of the record
        column : string
            name of the column
        if_exists : boolean
            if True, it is not an error if the record does not exist.

    Returns:
        The column's value.

    CLI Example:

    .. code-block:: bash

       salt '*' openvswitch.db_get Port br0 vlan_mode
    """
    cmd = ["ovs-vsctl", "--format=json", "--columns={}".format(column)]
    if if_exists:
        cmd += ["--if-exists"]
    cmd += ["list", table, record]
    result = __salt__["cmd.run_all"](cmd)
    if result["retcode"] != 0:
        raise CommandExecutionError(result["stderr"])
    output = _stdout_parse_json(result["stdout"])
    if output["data"] and output["data"][0]:
        return output["data"][0][0]
    else:
        return None


def db_set(table, record, column, value, if_exists=False):
    """
    .. versionadded:: 3006

    Sets a column's value for a specific record.

    Args:
        table : string
            name of the database table
        record : string
            identifier of the record
        column : string
            name of the column
        value : string
            the value to be set
        if_exists : boolean
            if True, it is not an error if the record does not exist.

    Returns:
        None on success and an error message on failure.

    CLI Example:

    .. code-block:: bash

       salt '*' openvswitch.db_set Interface br0 mac 02:03:04:05:06:07
    """
    cmd = ["ovs-vsctl"]
    if if_exists:
        cmd += ["--if-exists"]
    cmd += ["set", table, record, "{}={}".format(column, json.dumps(value))]
    result = __salt__["cmd.run_all"](cmd)
    if result["retcode"] != 0:
        return result["stderr"]
    else:
        return None
