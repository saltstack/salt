"""
This salt util uses WMI to gather network information on Windows 7 and .NET 4.0+
on newer systems.
The reason for this is that calls to WMI tend to be slower. Especially if the
query has not been optimized. For example, timing to gather NIC info from WMI
and .NET were as follows in testing:
WMI: 3.4169998168945312 seconds
NET: 1.0390000343322754 seconds
Since this is used to generate grain information we want to avoid using WMI as
much as possible.
There are 3 functions in this salt util.
- get_interface_info_dot_net
- get_interface_info_wmi
- get_interface_info
The ``get_interface_info`` function will call one of the other two functions
depending on the version of Windows this is run on. Once support for Windows
7 is dropped we can remove the WMI stuff and just use .NET.
:depends: - pythonnet
          - wmi
"""

# https://docs.microsoft.com/en-us/dotnet/api/system.net.networkinformation.networkinterface.getallnetworkinterfaces?view=netframework-4.7.2

import logging
import platform

import salt.utils.win_reg
from salt._compat import ipaddress

IS_WINDOWS = platform.system() == "Windows"

log = logging.getLogger(__name__)

__virtualname__ = "win_network"

if IS_WINDOWS:
    # pythonnet 3.0.1 requires .NET 4.7.2 (461808). This isn't installed by
    # default until Windows Server 2019 / Windows 10 1809 (10.1.17763). But, it
    # can be installed on older versions of Windows. So, instead of checking
    # platform here, let's check the version of .NET
    net_release = salt.utils.win_reg.read_value(
        hive="HKLM",
        key=r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full",
        vname="Release",
    )
    # If the registry key is not found, or the value is less than 461808, we
    # need to use WMI
    if not net_release["success"] or net_release["vdata"] < 461808:
        USE_WMI = True
    else:
        USE_WMI = False
    if USE_WMI:
        # This is supported by all versions of Windows, but the database we're
        # using hasn't really been optimized, so it is much slower
        import wmi

        import salt.utils.winapi
    else:
        # This uses .NET to get network settings and is faster than WMI
        try:
            # pylint: disable=unused-import
            import clr

            # pylint: enable=unused-import
            from System.Net import NetworkInformation
        except RuntimeError:
            # In some environments, using the Relenv OneDir package, we can't
            # load pythonnet. Uninstalling and reinstalling pythonnet fixes the
            # issue, but it is a manual step. Until we figure it out, we are
            # just going to fall back to WMI. I was able to reproduce a failing
            # system using Windows 10 Home Edition
            log.debug("Failed to load pythonnet. Falling back to WMI")
            USE_WMI = True
            import wmi

            import salt.utils.winapi

# TODO: Should we deprecate support for pythonnet 2.5.2, these enumerations can
# TODO: be deleted
enum_adapter_types = {
    1: "Unknown",
    6: "Ethernet",
    9: "TokenRing",
    15: "FDDI",
    20: "BasicISDN",
    21: "PrimaryISDN",
    23: "PPP",
    24: "Loopback",
    26: "Ethernet3Megabit",
    28: "Slip",
    37: "ATM",
    48: "GenericModem",
    53: "TAPAdapter",  # Not in MSDN Defined enumeration
    62: "FastEthernetT",
    63: "ISDN",
    69: "FastEthernetFx",
    71: "Wireless802.11",
    94: "AsymmetricDSL",
    95: "RateAdaptDSL",
    96: "SymmetricDSL",
    97: "VeryHighSpeedDSL",
    114: "IPOverATM",
    117: "GigabitEthernet",
    131: "Tunnel",
    143: "MultiRateSymmetricDSL",
    144: "HighPerformanceSerialBus",
    237: "WMAN",
    243: "WWANPP",
    244: "WWANPP2",
}

enum_operational_status = {
    1: "Up",
    2: "Down",
    3: "Testing",
    4: "Unknown",
    5: "Dormant",
    6: "NotPresent",
    7: "LayerDown",
}

enum_prefix_suffix = {
    0: "Other",
    1: "Manual",
    2: "WellKnown",
    3: "DHCP",
    4: "Router",
    5: "Random",
}

af_inet = 2
af_inet6 = 23


def __virtual__():
    """
    Only load if windows
    """
    if not IS_WINDOWS:
        return False, "This utility will only run on Windows"

    return __virtualname__


def _get_base_properties(i_face):
    raw_mac = i_face.GetPhysicalAddress().ToString()
    try:
        # pythonnet 3.0.1
        i_face_type = i_face.NetworkInterfaceType.ToString()
    except AttributeError:
        # pythonnet 2.5.2
        try:
            i_face_type = enum_adapter_types[i_face.NetworkInterfaceType]
        except KeyError:
            i_face_type = i_face.Description
    ret = {
        "alias": i_face.Name,
        "description": i_face.Description,
        "id": i_face.Id,
        "receive_only": i_face.IsReceiveOnly,
        "type": i_face_type,
        "physical_address": ":".join(raw_mac[i : i + 2] for i in range(0, 12, 2)),
    }
    try:
        # pythonnet 3.0.1
        ret["status"] = i_face.OperationalStatus.ToString()
    except AttributeError:
        # pythonnet 2.5.2
        ret["status"] = enum_operational_status[i_face.OperationalStatus]
    return ret


def _get_ip_base_properties(i_face):
    ip_properties = i_face.GetIPProperties()
    return {
        "dns_suffix": ip_properties.DnsSuffix,
        "dns_enabled": ip_properties.IsDnsEnabled,
        "dynamic_dns_enabled": ip_properties.IsDynamicDnsEnabled,
    }


def _get_ip_unicast_info(i_face):
    ip_properties = i_face.GetIPProperties()
    int_dict = {}
    if ip_properties.UnicastAddresses.Count > 0:
        names = {af_inet: "ip_addresses", af_inet6: "ipv6_addresses"}
        for addrs in ip_properties.UnicastAddresses:
            try:
                # pythonnet 3.0.1
                if addrs.Address.AddressFamily.ToString() == "InterNetwork":
                    family = 2
                else:
                    family = 23
            except AttributeError:
                # pythonnet 2.5.2
                family = addrs.Address.AddressFamily

            if family == af_inet:
                ip = addrs.Address.ToString()
                mask = addrs.IPv4Mask.ToString()
                net = ipaddress.IPv4Network(ip + "/" + mask, False)
                ip_info = {
                    "address": ip,
                    "netmask": mask,
                    "broadcast": net.broadcast_address.compressed,
                    "loopback": addrs.Address.Loopback.ToString(),
                }
            else:
                ip_info = {
                    "address": addrs.Address.ToString().split("%")[0],
                    # ScopeID is a suffix affixed to the end of an IPv6
                    # address it denotes the adapter. This is different from
                    # ScopeLevel. Need to figure out how to get ScopeLevel
                    # for feature parity with Linux
                    "interface_index": int(addrs.Address.ScopeId),
                }
            ip_info.update({"prefix_length": addrs.PrefixLength})
            try:
                # pythonnet 3.0.1
                ip_info.update(
                    {"prefix_origin": addrs.PrefixOrigin.ToString()},
                )
            except AttributeError:
                # pythonnet 2.5.2
                ip_info.update(
                    {"prefix_origin": enum_prefix_suffix[addrs.PrefixOrigin]},
                )
            try:
                # pythonnet 3.0.1
                ip_info.update(
                    {"suffix_origin": addrs.SuffixOrigin.ToString()},
                )
            except AttributeError:
                # pythonnet 2.5.2
                ip_info.update(
                    {"suffix_origin": enum_prefix_suffix[addrs.SuffixOrigin]},
                )
            int_dict.setdefault(names[family], []).append(ip_info)
    return int_dict


def _get_ip_gateway_info(i_face):
    ip_properties = i_face.GetIPProperties()
    int_dict = {}
    if ip_properties.GatewayAddresses.Count > 0:
        names = {af_inet: "ip_gateways", af_inet6: "ipv6_gateways"}
        for addrs in ip_properties.GatewayAddresses:
            try:
                # pythonnet 3.0.1
                if addrs.Address.AddressFamily.ToString() == "InterNetwork":
                    family = 2
                else:
                    family = 23
            except AttributeError:
                # pythonnet 2.5.2
                family = addrs.Address.AddressFamily
            int_dict.setdefault(names[family], []).append(
                addrs.Address.ToString().split("%")[0]
            )
    return int_dict


def _get_ip_dns_info(i_face):
    ip_properties = i_face.GetIPProperties()
    int_dict = {}
    if ip_properties.DnsAddresses.Count > 0:
        names = {af_inet: "ip_dns", af_inet6: "ipv6_dns"}
        for addrs in ip_properties.DnsAddresses:
            try:
                # pythonnet 3.0.1
                if addrs.AddressFamily.ToString() == "InterNetwork":
                    family = 2
                else:
                    family = 23
            except AttributeError:
                # pythonnet 2.5.2
                family = addrs.AddressFamily
            int_dict.setdefault(names[family], []).append(
                addrs.ToString().split("%")[0]
            )
    return int_dict


def _get_ip_multicast_info(i_face):
    ip_properties = i_face.GetIPProperties()
    int_dict = {}
    if ip_properties.MulticastAddresses.Count > 0:
        names = {af_inet: "ip_multicast", af_inet6: "ipv6_multicast"}
        for addrs in ip_properties.MulticastAddresses:
            try:
                # pythonnet 3.0.1
                if addrs.Address.AddressFamily.ToString() == "InterNetwork":
                    family = 2
                else:
                    family = 23
            except AttributeError:
                # pythonnet 2.5.2
                family = addrs.Address.AddressFamily
            int_dict.setdefault(names[family], []).append(
                addrs.Address.ToString().split("%")[0]
            )
    return int_dict


def _get_ip_anycast_info(i_face):
    ip_properties = i_face.GetIPProperties()
    int_dict = {}
    if ip_properties.AnycastAddresses.Count > 0:
        names = {af_inet: "ip_anycast", af_inet6: "ipv6_anycast"}
        for addrs in ip_properties.AnycastAddresses:
            try:
                # pythonnet 3.0.1
                if addrs.Address.AddressFamily.ToString() == "InterNetwork":
                    family = 2
                else:
                    family = 23
            except AttributeError:
                # pythonnet 2.5.2
                family = addrs.Address.AddressFamily
            int_dict.setdefault(names[family], []).append(addrs.Address.ToString())
    return int_dict


def _get_ip_wins_info(i_face):
    ip_properties = i_face.GetIPProperties()
    int_dict = {}
    if ip_properties.WinsServersAddresses.Count > 0:
        for addrs in ip_properties.WinsServersAddresses:
            int_dict.setdefault("ip_wins", []).append(addrs.ToString())
    return int_dict


def _get_network_interfaces():
    # pylint: disable=used-before-assignment
    return NetworkInformation.NetworkInterface.GetAllNetworkInterfaces()


def get_interface_info_dot_net_formatted():
    """
    Returns data gathered via ``get_interface_info_dot_net`` and returns the
    info in the same manner as ``get_interface_info_wmi``

    Returns:
        dict: A dictionary of information about all interfaces on the system
    """
    # Massage the data returned by dotnet to mirror that returned by wmi
    interfaces = get_interface_info_dot_net()
    i_faces = {}
    for i_face in interfaces:
        if interfaces[i_face]["status"] == "Up":
            name = interfaces[i_face]["description"]
            i_faces.setdefault(name, {}).update(
                {"hwaddr": interfaces[i_face]["physical_address"], "up": True}
            )
            for ip in interfaces[i_face].get("ip_addresses", []):
                i_faces[name].setdefault("inet", []).append(
                    {
                        "address": ip["address"],
                        "broadcast": ip["broadcast"],
                        "netmask": ip["netmask"],
                        "gateway": interfaces[i_face].get("ip_gateways", [""])[0],
                        "label": name,
                    }
                )
            for ip in interfaces[i_face].get("ipv6_addresses", []):
                i_faces[name].setdefault("inet6", []).append(
                    {
                        "address": ip["address"],
                        "gateway": interfaces[i_face].get("ipv6_gateways", [""])[0],
                        "prefixlen": ip["prefix_length"],
                    }
                )

    return i_faces


def get_interface_info_dot_net():
    """
    Uses .NET 4.0+ to gather Network Interface information. Should only run on
    Windows systems newer than Windows 7/Server 2008R2

    Returns:
        dict: A dictionary of information about all interfaces on the system
    """
    interfaces = {}
    for i_face in _get_network_interfaces():
        temp_dict = _get_base_properties(i_face)
        temp_dict.update(_get_ip_base_properties(i_face))
        temp_dict.update(_get_ip_unicast_info(i_face))
        temp_dict.update(_get_ip_gateway_info(i_face))
        temp_dict.update(_get_ip_dns_info(i_face))
        temp_dict.update(_get_ip_multicast_info(i_face))
        temp_dict.update(_get_ip_anycast_info(i_face))
        temp_dict.update(_get_ip_wins_info(i_face))
        interfaces[i_face.Name] = temp_dict

    return interfaces


def get_interface_info_wmi():
    """
    Uses WMI to gather Network Interface information. Should only run on
    Windows 7/2008 R2 and lower systems. This code was pulled from the
    ``win_interfaces`` function in ``salt.utils.network`` unchanged.

    Returns:
        dict: A dictionary of information about all interfaces on the system
    """
    with salt.utils.winapi.Com():
        c = wmi.WMI()
        i_faces = {}
        for i_face in c.Win32_NetworkAdapterConfiguration(IPEnabled=1):
            i_faces[i_face.Description] = {}
            if i_face.MACAddress:
                i_faces[i_face.Description]["hwaddr"] = i_face.MACAddress
            if i_face.IPEnabled:
                i_faces[i_face.Description]["up"] = True
                for ip in i_face.IPAddress:
                    if "." in ip:
                        if "inet" not in i_faces[i_face.Description]:
                            i_faces[i_face.Description]["inet"] = []
                        item = {"address": ip, "label": i_face.Description}
                        if i_face.DefaultIPGateway:
                            broadcast = next(
                                (i for i in i_face.DefaultIPGateway if "." in i), ""
                            )
                            if broadcast:
                                item["broadcast"] = broadcast
                        if i_face.IPSubnet:
                            netmask = next((i for i in i_face.IPSubnet if "." in i), "")
                            if netmask:
                                item["netmask"] = netmask
                        i_faces[i_face.Description]["inet"].append(item)
                    if ":" in ip:
                        if "inet6" not in i_faces[i_face.Description]:
                            i_faces[i_face.Description]["inet6"] = []
                        item = {"address": ip}
                        if i_face.DefaultIPGateway:
                            broadcast = next(
                                (i for i in i_face.DefaultIPGateway if ":" in i), ""
                            )
                            if broadcast:
                                item["broadcast"] = broadcast
                        if i_face.IPSubnet:
                            prefixlen = next(
                                (int(i) for i in i_face.IPSubnet if "." not in i), None
                            )
                            if prefixlen:
                                item["prefixlen"] = prefixlen
                        i_faces[i_face.Description]["inet6"].append(item)
            else:
                i_faces[i_face.Description]["up"] = False
    return i_faces


def get_interface_info():
    """
    This function will return network interface information for the system and
    will use the best method to retrieve that information. Windows 7/2008R2 and
    below will use WMI. Newer systems will use .NET.
    Returns:
        dict: A dictionary of information about the Network interfaces
    """
    # On Windows 7 machines, use WMI as dotnet 4.0 is not available by default
    if USE_WMI:
        return get_interface_info_wmi()
    else:
        return get_interface_info_dot_net_formatted()
