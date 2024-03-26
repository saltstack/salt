"""
The networking module for Windows based systems
"""

import logging
import time

import salt.utils.network
import salt.utils.platform
import salt.utils.validate.net
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "ip"


def __virtual__():
    """
    Confine this module to Windows systems
    """
    if salt.utils.platform.is_windows():
        return __virtualname__
    return (False, "Module win_ip: module only works on Windows systems")


def _interface_configs():
    """
    Return all interface configs
    """
    cmd = ["netsh", "interface", "ip", "show", "config"]
    lines = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    ret = {}
    current_iface = None
    current_ip_list = None

    for line in lines:

        line = line.strip()
        if not line:
            current_iface = None
            current_ip_list = None
            continue

        if "Configuration for interface" in line:
            _, iface = line.rstrip('"').split('"', 1)  # get iface name
            current_iface = {}
            ret[iface] = current_iface
            continue

        if ":" not in line:
            if current_ip_list:
                current_ip_list.append(line)
            else:
                log.warning('Cannot parse "%s"', line)
            continue

        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()

        lkey = key.lower()
        if ("dns servers" in lkey) or ("wins servers" in lkey):
            current_ip_list = []
            current_iface[key] = current_ip_list
            current_ip_list.append(val)

        elif "ip address" in lkey:
            current_iface.setdefault("ip_addrs", []).append({key: val})

        elif "subnet prefix" in lkey:
            subnet, _, netmask = val.split(" ", 2)
            last_ip = current_iface["ip_addrs"][-1]
            last_ip["Subnet"] = subnet.strip()
            last_ip["Netmask"] = netmask.lstrip().rstrip(")")

        else:
            current_iface[key] = val

    return ret


def raw_interface_configs():
    """
    Return raw configs for all interfaces

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.raw_interface_configs
    """
    cmd = ["netsh", "interface", "ip", "show", "config"]
    return __salt__["cmd.run"](cmd, python_shell=False)


def get_all_interfaces():
    """
    Return configs for all interfaces

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.get_all_interfaces
    """
    return _interface_configs()


def get_interface(iface):
    """
    Return the configuration of a network interface

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.get_interface 'Local Area Connection'
    """
    return _interface_configs().get(iface, {})


def is_enabled(iface):
    """
    Returns ``True`` if interface is enabled, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.is_enabled 'Local Area Connection #2'
    """
    cmd = ["netsh", "interface", "show", "interface", f"name={iface}"]
    iface_found = False
    for line in __salt__["cmd.run"](cmd, python_shell=False).splitlines():
        if "Connect state:" in line:
            iface_found = True
            return line.split()[-1] == "Connected"
    if not iface_found:
        raise CommandExecutionError(f"Interface '{iface}' not found")
    return False


def is_disabled(iface):
    """
    Returns ``True`` if interface is disabled, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.is_disabled 'Local Area Connection #2'
    """
    return not is_enabled(iface)


def enable(iface):
    """
    Enable an interface

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.enable 'Local Area Connection #2'
    """
    if is_enabled(iface):
        return True
    cmd = [
        "netsh",
        "interface",
        "set",
        "interface",
        f"name={iface}",
        "admin=ENABLED",
    ]
    __salt__["cmd.run"](cmd, python_shell=False)
    return is_enabled(iface)


def disable(iface):
    """
    Disable an interface

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.disable 'Local Area Connection #2'
    """
    if is_disabled(iface):
        return True
    cmd = [
        "netsh",
        "interface",
        "set",
        "interface",
        f"name={iface}",
        "admin=DISABLED",
    ]
    __salt__["cmd.run"](cmd, python_shell=False)
    return is_disabled(iface)


def get_subnet_length(mask):
    """
    Convenience function to convert the netmask to the CIDR subnet length

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.get_subnet_length 255.255.255.0
    """
    if not salt.utils.validate.net.netmask(mask):
        raise SaltInvocationError(f"'{mask}' is not a valid netmask")
    return salt.utils.network.get_net_size(mask)


def set_static_ip(iface, addr, gateway=None, append=False):
    """
    Set static IP configuration on a Windows NIC

    iface
        The name of the interface to manage

    addr
        IP address with subnet length (ex. ``10.1.2.3/24``). The
        :mod:`ip.get_subnet_length <salt.modules.win_ip.get_subnet_length>`
        function can be used to calculate the subnet length from a netmask.

    gateway : None
        If specified, the default gateway will be set to this value.

    append : False
        If ``True``, this IP address will be added to the interface. Default is
        ``False``, which overrides any existing configuration for the interface
        and sets ``addr`` as the only address on the interface.

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.set_static_ip 'Local Area Connection' 10.1.2.3/24 gateway=10.1.2.1
        salt -G 'os_family:Windows' ip.set_static_ip 'Local Area Connection' 10.1.2.4/24 append=True
    """

    def _find_addr(iface, addr, timeout=1):
        ip, cidr = addr.rsplit("/", 1)
        netmask = salt.utils.network.cidr_to_ipv4_netmask(cidr)
        for idx in range(timeout):
            for addrinfo in get_interface(iface).get("ip_addrs", []):
                if addrinfo["IP Address"] == ip and addrinfo["Netmask"] == netmask:
                    return addrinfo
            time.sleep(1)
        return {}

    if not salt.utils.validate.net.ipv4_addr(addr):
        raise SaltInvocationError(f"Invalid address '{addr}'")

    if gateway and not salt.utils.validate.net.ipv4_addr(addr):
        raise SaltInvocationError(f"Invalid default gateway '{gateway}'")

    if "/" not in addr:
        addr += "/32"

    if append and _find_addr(iface, addr):
        raise CommandExecutionError(
            f"Address '{addr}' already exists on interface '{iface}'"
        )

    cmd = ["netsh", "interface", "ip"]
    if append:
        cmd.append("add")
    else:
        cmd.append("set")
    cmd.extend(["address", f"name={iface}"])
    if not append:
        cmd.append("source=static")
    cmd.append(f"address={addr}")
    if gateway:
        cmd.append(f"gateway={gateway}")

    result = __salt__["cmd.run_all"](cmd, python_shell=False)
    if result["retcode"] != 0:
        raise CommandExecutionError(
            "Unable to set IP address: {}".format(result["stderr"])
        )

    new_addr = _find_addr(iface, addr, timeout=10)
    if not new_addr:
        return {}

    ret = {"Address Info": new_addr}
    if gateway:
        ret["Default Gateway"] = gateway
    return ret


def set_dhcp_ip(iface):
    """
    Set Windows NIC to get IP from DHCP

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.set_dhcp_ip 'Local Area Connection'
    """
    cmd = ["netsh", "interface", "ip", "set", "address", iface, "dhcp"]
    __salt__["cmd.run"](cmd, python_shell=False)
    return {"Interface": iface, "DHCP enabled": "Yes"}


def set_static_dns(iface, *addrs):
    """
    Set static DNS configuration on a Windows NIC

    Args:

        iface (str): The name of the interface to set

        addrs (*):
            One or more DNS servers to be added. To clear the list of DNS
            servers pass an empty list (``[]``). If undefined or ``None`` no
            changes will be made.

    Returns:
        dict: A dictionary containing the new DNS settings

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.set_static_dns 'Local Area Connection' '192.168.1.1'
        salt -G 'os_family:Windows' ip.set_static_dns 'Local Area Connection' '192.168.1.252' '192.168.1.253'
    """
    if not addrs or str(addrs[0]).lower() == "none":
        return {"Interface": iface, "DNS Server": "No Changes"}
    # Clear the list of DNS servers if [] is passed
    if str(addrs[0]).lower() == "[]":
        log.debug("Clearing list of DNS servers")
        cmd = [
            "netsh",
            "interface",
            "ip",
            "set",
            "dns",
            f"name={iface}",
            "source=static",
            "address=none",
        ]
        __salt__["cmd.run"](cmd, python_shell=False)
        return {"Interface": iface, "DNS Server": []}
    addr_index = 1
    for addr in addrs:
        if addr_index == 1:
            cmd = [
                "netsh",
                "interface",
                "ip",
                "set",
                "dns",
                f"name={iface}",
                "source=static",
                f"address={addr}",
                "register=primary",
            ]
            __salt__["cmd.run"](cmd, python_shell=False)
            addr_index = addr_index + 1
        else:
            cmd = [
                "netsh",
                "interface",
                "ip",
                "add",
                "dns",
                f"name={iface}",
                f"address={addr}",
                f"index={addr_index}",
            ]
            __salt__["cmd.run"](cmd, python_shell=False)
            addr_index = addr_index + 1
    return {"Interface": iface, "DNS Server": addrs}


def set_dhcp_dns(iface):
    """
    Set DNS source to DHCP on Windows

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.set_dhcp_dns 'Local Area Connection'
    """
    cmd = ["netsh", "interface", "ip", "set", "dns", iface, "dhcp"]
    __salt__["cmd.run"](cmd, python_shell=False)
    return {"Interface": iface, "DNS Server": "DHCP"}


def set_dhcp_all(iface):
    """
    Set both IP Address and DNS to DHCP

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.set_dhcp_all 'Local Area Connection'
    """
    set_dhcp_ip(iface)
    set_dhcp_dns(iface)
    return {"Interface": iface, "DNS Server": "DHCP", "DHCP enabled": "Yes"}


def get_default_gateway():
    """
    Set DNS source to DHCP on Windows

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.get_default_gateway
    """
    try:
        return next(
            iter(
                x.split()[-1]
                for x in __salt__["cmd.run"](
                    ["netsh", "interface", "ip", "show", "config"], python_shell=False
                ).splitlines()
                if "Default Gateway:" in x
            )
        )
    except StopIteration:
        raise CommandExecutionError("Unable to find default gateway")
