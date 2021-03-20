"""
NET Finder
==========

.. versionadded:: 2017.7.0

A runner to find network details easily and fast.
It's smart enough to know what you are looking for.

Configuration
-------------

- Minion (proxy) config

    To have the complete features, one needs to add the following mine configuration in the minion (proxy) config file:

    .. code-block:: yaml

        mine_functions:
          net.ipaddrs: []
          net.lldp: []
          net.mac: []
          net.arp: []
          net.interfaces: []

    Which instructs Salt to cache the data returned by the NAPALM-functions.
    While they are not mandatory, the less functions configured, the less details will be found by the runner.

    How often the mines are refreshed, can be specified using:

    .. code-block:: yaml

        mine_interval: <X minutes>

- Master config

    By default the following options can be configured on the master.
    They are not necessary, but available in case the user has different requirements.

    target: ``*``
        From what minions will collect the mine data. Default: ``*`` (collect from all minions).

    expr_form: ``glob``
        Minion matching expression form. Default: ``glob``.

    ignore_interfaces
        A list of interfaces name to ignore. By default will consider all interfaces.

    display: ``True``
        Display on the screen or return structured object? Default: ``True`` (return on the CLI).

    outputter: ``table``
        Specify the outputter name when displaying on the CLI. Default: :mod:`table <salt.output.napalm_bgp>`.

    Configuration example:

    .. code-block:: yaml

        runners:
          net.find:
            target: 'edge*'
            expr_form: 'glob'
            ignore_interfaces:
              - lo0
              - em1
              - jsrv
              - fxp0
            outputter: yaml
"""

import salt.output
import salt.utils.network

try:
    from netaddr import IPNetwork  # netaddr is already required by napalm
    from netaddr.core import AddrFormatError
    from napalm.base import helpers as napalm_helpers

    HAS_NAPALM = True
except ImportError:
    HAS_NAPALM = False

# -----------------------------------------------------------------------------
# module properties
# -----------------------------------------------------------------------------

_DEFAULT_TARGET = "*"
_DEFAULT_EXPR_FORM = "glob"
_DEFAULT_IGNORE_INTF = []
# 'lo0', 'em1', 'em0', 'jsrv', 'fxp0'
_DEFAULT_DISPLAY = True
_DEFAULT_OUTPUTTER = "table"


# -----------------------------------------------------------------------------
# global variables
# -----------------------------------------------------------------------------

# will cache several details to avoid loading them several times from the mines.
_CACHE = {}

# -----------------------------------------------------------------------------
# helper functions -- will not be exported
# -----------------------------------------------------------------------------

# Define the module's virtual name
__virtualname__ = "net"


def __virtual__():
    if HAS_NAPALM:
        return __virtualname__
    return (False, "The napalm module could not be imported")


def _get_net_runner_opts():
    """
    Return the net.find runner options.
    """
    runner_opts = __opts__.get("runners", {}).get("net.find", {})
    return {
        "target": runner_opts.get("target", _DEFAULT_TARGET),
        "expr_form": runner_opts.get("expr_form", _DEFAULT_EXPR_FORM),
        "ignore_interfaces": runner_opts.get("ignore_interfaces", _DEFAULT_IGNORE_INTF),
        "display": runner_opts.get("display", _DEFAULT_DISPLAY),
        "outputter": runner_opts.get("outputter", _DEFAULT_OUTPUTTER),
    }


def _get_mine(fun):
    """
    Return the mine function from all the targeted minions.
    Just a small helper to avoid redundant pieces of code.
    """
    if fun in _CACHE and _CACHE[fun]:
        return _CACHE[fun]
    net_runner_opts = _get_net_runner_opts()
    _CACHE[fun] = __salt__["mine.get"](
        net_runner_opts.get("target"), fun, tgt_type=net_runner_opts.get("expr_form")
    )
    return _CACHE[fun]


def _display_runner(rows, labels, title, display=_DEFAULT_DISPLAY):
    """
    Display or return the rows.
    """
    if display:
        net_runner_opts = _get_net_runner_opts()
        if net_runner_opts.get("outputter") == "table":
            ret = salt.output.out_format(
                {"rows": rows, "labels": labels},
                "table",
                __opts__,
                title=title,
                rows_key="rows",
                labels_key="labels",
            )
        else:
            ret = salt.output.out_format(
                rows, net_runner_opts.get("outputter"), __opts__
            )
        print(ret)
    else:
        return rows


def _get_network_obj(addr):
    """
    Try to convert a string into a valid IP Network object.
    """
    ip_netw = None
    try:
        ip_netw = IPNetwork(addr)
    except AddrFormatError:
        return ip_netw
    return ip_netw


def _find_interfaces_ip(mac):
    """
    Helper to search the interfaces IPs using the MAC address.
    """
    try:
        mac = napalm_helpers.convert(napalm_helpers.mac, mac)
    except AddrFormatError:
        return ("", "", [])

    all_interfaces = _get_mine("net.interfaces")
    all_ipaddrs = _get_mine("net.ipaddrs")

    for device, device_interfaces in all_interfaces.items():
        if not device_interfaces.get("result", False):
            continue
        for interface, interface_details in device_interfaces.get("out", {}).items():
            try:
                interface_mac = napalm_helpers.convert(
                    napalm_helpers.mac, interface_details.get("mac_address")
                )
            except AddrFormatError:
                continue
            if mac != interface_mac:
                continue
            interface_ipaddrs = (
                all_ipaddrs.get(device, {}).get("out", {}).get(interface, {})
            )
            ip_addresses = interface_ipaddrs.get("ipv4", {})
            ip_addresses.update(interface_ipaddrs.get("ipv6", {}))
            interface_ips = [
                "{}/{}".format(ip_addr, addr_details.get("prefix_length", "32"))
                for ip_addr, addr_details in ip_addresses.items()
            ]
            return device, interface, interface_ips

    return ("", "", [])


def _find_interfaces_mac(ip):  # pylint: disable=invalid-name
    """
    Helper to get the interfaces hardware address using the IP Address.
    """
    all_interfaces = _get_mine("net.interfaces")
    all_ipaddrs = _get_mine("net.ipaddrs")

    for device, device_ipaddrs in all_ipaddrs.items():
        if not device_ipaddrs.get("result", False):
            continue
        for interface, interface_ipaddrs in device_ipaddrs.get("out", {}).items():
            ip_addresses = set(interface_ipaddrs.get("ipv4", {}).keys())
            ip_addresses.update(set(interface_ipaddrs.get("ipv6", {}).keys()))
            for ipaddr in ip_addresses:
                if ip != ipaddr:
                    continue
                interface_mac = (
                    all_interfaces.get(device, {})
                    .get("out", {})
                    .get(interface, {})
                    .get("mac_address", "")
                )
                return device, interface, interface_mac

    return ("", "", "")


# -----------------------------------------------------------------------------
# callable functions
# -----------------------------------------------------------------------------


def interfaces(
    device=None,
    interface=None,
    title=None,
    pattern=None,
    ipnet=None,
    best=True,
    display=_DEFAULT_DISPLAY,
):
    """
    Search for interfaces details in the following mine functions:

    - net.interfaces
    - net.ipaddrs

    Optional arguments:

    device
        Return interface data from a certain device only.

    interface
        Return data selecting by interface name.

    pattern
        Return interfaces that contain a certain pattern in their description.

    ipnet
        Return interfaces whose IP networks associated include this IP network.

    best: ``True``
        When ``ipnet`` is specified, this argument says if the runner should return only the best match
        (the output will contain at most one row). Default: ``True`` (return only the best match).

    display: True
        Display on the screen or return structured object? Default: ``True`` (return on the CLI).

    title
        Display a custom title for the table.

    CLI Example:

    .. code-block:: bash

        $ sudo salt-run net.interfaces interface=vt-0/0/10

    Output Example:

    .. code-block:: text

        Details for interface xe-0/0/0
        _________________________________________________________________________________________________________________
        |    Device    | Interface | Interface Description |  UP  | Enabled | Speed [Mbps] | MAC Address | IP Addresses |
        _________________________________________________________________________________________________________________
        | edge01.bjm01 | vt-0/0/10 |                       | True |   True  |     1000     |             |              |
        _________________________________________________________________________________________________________________
        | edge01.flw01 | vt-0/0/10 |                       | True |   True  |     1000     |             |              |
        _________________________________________________________________________________________________________________
        | edge01.pos01 | vt-0/0/10 |                       | True |   True  |     1000     |             |              |
        _________________________________________________________________________________________________________________
        | edge01.oua01 | vt-0/0/10 |                       | True |   True  |     1000     |             |              |
        _________________________________________________________________________________________________________________
    """

    def _ipnet_belongs(net):
        """
        Helper to tell if a IP address or network belong to a certain network.
        """
        if net == "0.0.0.0/0":
            return False
        net_obj = _get_network_obj(net)
        if not net_obj:
            return False
        return ipnet in net_obj or net_obj in ipnet

    labels = {
        "device": "Device",
        "interface": "Interface",
        "interface_description": "Interface Description",
        "is_up": "UP",
        "is_enabled": "Enabled",
        "speed": "Speed [Mbps]",
        "mac": "MAC Address",
        "ips": "IP Addresses",
    }
    rows = []

    net_runner_opts = _get_net_runner_opts()

    if pattern:
        title = (
            'Pattern "{}" found in the description of the following interfaces'.format(
                pattern
            )
        )
    if not title:
        title = "Details"
        if interface:
            title += " for interface {}".format(interface)
        else:
            title += " for all interfaces"
        if device:
            title += " on device {}".format(device)
        if ipnet:
            title += " that include network {net}".format(net=str(ipnet))
            if best:
                title += " - only best match returned"

    all_interfaces = _get_mine("net.interfaces")
    all_ipaddrs = _get_mine("net.ipaddrs")

    if device:
        all_interfaces = {device: all_interfaces.get(device, {})}

    if ipnet and not isinstance(ipnet, IPNetwork):
        ipnet = _get_network_obj(ipnet)

    best_row = {}
    best_net_match = IPNetwork("0.0.0.0/0")
    for (
        device,
        net_interfaces_out,
    ) in all_interfaces.items():  # pylint: disable=too-many-nested-blocks
        if not net_interfaces_out:
            continue
        if not net_interfaces_out.get("result", False):
            continue
        selected_device_interfaces = net_interfaces_out.get("out", {})
        if interface:
            selected_device_interfaces = {
                interface: selected_device_interfaces.get(interface, {})
            }
        for interface_name, interface_details in selected_device_interfaces.items():
            if not interface_details:
                continue
            if ipnet and interface_name in net_runner_opts.get("ignore_interfaces"):
                continue
            interface_description = interface_details.get("description", "") or ""
            if pattern:
                if pattern.lower() not in interface_description.lower():
                    continue
            if not all_ipaddrs.get(device, {}).get("result", False):
                continue
            ips = []
            device_entry = {
                "device": device,
                "interface": interface_name,
                "interface_description": interface_description,
                "is_up": (interface_details.get("is_up", "") or ""),
                "is_enabled": (interface_details.get("is_enabled", "") or ""),
                "speed": (interface_details.get("speed", "") or ""),
                "mac": napalm_helpers.convert(
                    napalm_helpers.mac, (interface_details.get("mac_address", "") or "")
                ),
                "ips": [],
            }
            intf_entry_found = False
            for intrf, interface_ips in (
                all_ipaddrs.get(device, {}).get("out", {}).items()
            ):
                if intrf.split(".")[0] == interface_name:
                    ip_addresses = interface_ips.get("ipv4", {})  # all IPv4 addresses
                    ip_addresses.update(
                        interface_ips.get("ipv6", {})
                    )  # and all IPv6 addresses
                    ips = [
                        "{}/{}".format(ip_addr, addr_details.get("prefix_length", "32"))
                        for ip_addr, addr_details in ip_addresses.items()
                    ]
                    interf_entry = {}
                    interf_entry.update(device_entry)
                    interf_entry["ips"] = ips
                    if display:
                        interf_entry["ips"] = "\n".join(interf_entry["ips"])
                    if ipnet:
                        inet_ips = [
                            str(ip) for ip in ips if _ipnet_belongs(ip)
                        ]  # filter and get only IP include ipnet
                        if inet_ips:  # if any
                            if best:
                                # determine the global best match
                                compare = [best_net_match]
                                compare.extend(list(map(_get_network_obj, inet_ips)))
                                new_best_net_match = max(compare)
                                if new_best_net_match != best_net_match:
                                    best_net_match = new_best_net_match
                                    best_row = interf_entry
                            else:
                                # or include all
                                intf_entry_found = True
                                rows.append(interf_entry)
                    else:
                        intf_entry_found = True
                        rows.append(interf_entry)
            if not intf_entry_found and not ipnet:
                interf_entry = {}
                interf_entry.update(device_entry)
                if display:
                    interf_entry["ips"] = ""
                rows.append(interf_entry)

    if ipnet and best and best_row:
        rows = [best_row]

    return _display_runner(rows, labels, title, display=display)


def findarp(
    device=None, interface=None, mac=None, ip=None, display=_DEFAULT_DISPLAY
):  # pylint: disable=invalid-name
    """
    Search for entries in the ARP tables using the following mine functions:

    - net.arp

    Optional arguments:

    device
        Return interface data from a certain device only.

    interface
        Return data selecting by interface name.

    mac
        Search using a specific MAC Address.

    ip
        Search using a specific IP Address.

    display: ``True``
        Display on the screen or return structured object? Default: ``True``, will return on the CLI.

    CLI Example:

    .. code-block:: bash

        $ sudo salt-run net.findarp mac=8C:60:0F:78:EC:41

    Output Example:

    .. code-block:: text

        ARP Entries for MAC 8C:60:0F:78:EC:41
        ________________________________________________________________________________
        |    Device    |     Interface     |        MAC        |       IP      |  Age  |
        ________________________________________________________________________________
        | edge01.bjm01 | irb.171 [ae0.171] | 8C:60:0F:78:EC:41 | 172.172.17.19 | 956.0 |
        ________________________________________________________________________________
    """
    labels = {
        "device": "Device",
        "interface": "Interface",
        "mac": "MAC",
        "ip": "IP",
        "age": "Age",
    }
    rows = []

    all_arp = _get_mine("net.arp")

    title = "ARP Entries"
    if device:
        title += " on device {device}".format(device=device)
    if interface:
        title += " on interface {interf}".format(interf=interface)
    if ip:
        title += " for IP {ip}".format(ip=ip)
    if mac:
        title += " for MAC {mac}".format(mac=mac)

    if device:
        all_arp = {device: all_arp.get(device)}

    for device, device_arp in all_arp.items():
        if not device_arp:
            continue
        if not device_arp.get("result", False):
            continue
        arp_table = device_arp.get("out", [])
        for arp_entry in arp_table:
            if (
                (mac and arp_entry.get("mac", "").lower() == mac.lower())
                or (  # pylint: disable=too-many-boolean-expressions
                    interface and interface in arp_entry.get("interface", "")
                )
                or (
                    ip
                    and napalm_helpers.convert(
                        napalm_helpers.ip, arp_entry.get("ip", "")
                    )
                    == napalm_helpers.convert(napalm_helpers.ip, ip)
                )
            ):
                rows.append(
                    {
                        "device": device,
                        "interface": arp_entry.get("interface"),
                        "mac": napalm_helpers.convert(
                            napalm_helpers.mac, arp_entry.get("mac")
                        ),
                        "ip": napalm_helpers.convert(
                            napalm_helpers.ip, arp_entry.get("ip")
                        ),
                        "age": arp_entry.get("age"),
                    }
                )

    return _display_runner(rows, labels, title, display=display)


def findmac(device=None, mac=None, interface=None, vlan=None, display=_DEFAULT_DISPLAY):
    """
    Search in the MAC Address tables, using the following mine functions:

    - net.mac

    Optional arguments:

    device
        Return interface data from a certain device only.

    interface
        Return data selecting by interface name.

    mac
        Search using a specific MAC Address.

    vlan
        Search using a VLAN ID.

    display: ``True``
        Display on the screen or return structured object? Default: ``True``, will return on the CLI.

    CLI Example:

    .. code-block:: bash

        $ sudo salt-run net.findmac mac=8C:60:0F:78:EC:41

    Output Example:

    .. code-block:: text

        MAC Address(es)
        _____________________________________________________________________________________________
        |    Device    | Interface |        MAC        | VLAN | Static | Active | Moves | Last move |
        _____________________________________________________________________________________________
        | edge01.bjm01 |  ae0.171  | 8C:60:0F:78:EC:41 | 171  | False  |  True  |   0   |    0.0    |
        _____________________________________________________________________________________________
    """
    labels = {
        "device": "Device",
        "interface": "Interface",
        "mac": "MAC",
        "vlan": "VLAN",
        "static": "Static",
        "active": "Active",
        "moves": "Moves",
        "last_move": "Last Move",
    }
    rows = []

    all_mac = _get_mine("net.mac")

    title = "MAC Address(es)"
    if device:
        title += " on device {device}".format(device=device)
    if interface:
        title += " on interface {interf}".format(interf=interface)
    if vlan:
        title += " on VLAN {vlan}".format(vlan=vlan)

    if device:
        all_mac = {device: all_mac.get(device)}

    for device, device_mac in all_mac.items():
        if not device_mac:
            continue
        if not device_mac.get("result", False):
            continue
        mac_table = device_mac.get("out", [])
        for mac_entry in mac_table:
            if (
                (
                    mac
                    and napalm_helpers.convert(  # pylint: disable=too-many-boolean-expressions
                        napalm_helpers.mac, mac_entry.get("mac", "")
                    )
                    == napalm_helpers.convert(napalm_helpers.mac, mac)
                )
                or (interface and interface in mac_entry.get("interface", ""))
                or (vlan and str(mac_entry.get("vlan", "")) == str(vlan))
            ):
                rows.append(
                    {
                        "device": device,
                        "interface": mac_entry.get("interface"),
                        "mac": napalm_helpers.convert(
                            napalm_helpers.mac, mac_entry.get("mac")
                        ),
                        "vlan": mac_entry.get("vlan"),
                        "static": mac_entry.get("static"),
                        "active": mac_entry.get("active"),
                        "moves": mac_entry.get("moves"),
                        "last_move": mac_entry.get("last_move"),
                    }
                )

    return _display_runner(rows, labels, title, display=display)


def lldp(
    device=None,
    interface=None,
    title=None,
    pattern=None,
    chassis=None,
    display=_DEFAULT_DISPLAY,
):
    """
    Search in the LLDP neighbors, using the following mine functions:

    - net.lldp

    Optional arguments:

    device
        Return interface data from a certain device only.

    interface
        Return data selecting by interface name.

    pattern
        Return LLDP neighbors that have contain this pattern in one of the following fields:

        - Remote Port ID
        - Remote Port Description
        - Remote System Name
        - Remote System Description

    chassis
        Search using a specific Chassis ID.

    display: ``True``
        Display on the screen or return structured object? Default: ``True`` (return on the CLI).

    display: ``True``
        Display on the screen or return structured object? Default: ``True`` (return on the CLI).

    title
        Display a custom title for the table.

    CLI Example:

    .. code-block:: bash

        $ sudo salt-run net.lldp pattern=Ethernet1/48

    Output Example:

    .. code-block:: text

        Pattern "Ethernet1/48" found in one of the following LLDP details
        _________________________________________________________________________________________________________________________________________________________________________________________
        |    Device    | Interface | Parent Interface | Remote Chassis ID | Remote Port ID | Remote Port Description |   Remote System Name   |            Remote System Description            |
        _________________________________________________________________________________________________________________________________________________________________________________________
        | edge01.bjm01 |  xe-2/3/4 |       ae0        | 8C:60:4F:3B:52:19 |                |       Ethernet1/48      | edge05.bjm01.dummy.net |   Cisco NX-OS(tm) n6000, Software (n6000-uk9),  |
        |              |           |                  |                   |                |                         |                        | Version 7.3(0)N7(5), RELEASE SOFTWARE Copyright |
        |              |           |                  |                   |                |                         |                        |  (c) 2002-2012 by Cisco Systems, Inc. Compiled  |
        |              |           |                  |                   |                |                         |                        |                2/17/2016 22:00:00               |
        _________________________________________________________________________________________________________________________________________________________________________________________
        | edge01.flw01 |  xe-1/2/3 |       ae0        | 8C:60:4F:1A:B4:22 |                |       Ethernet1/48      | edge05.flw01.dummy.net |   Cisco NX-OS(tm) n6000, Software (n6000-uk9),  |
        |              |           |                  |                   |                |                         |                        | Version 7.3(0)N7(5), RELEASE SOFTWARE Copyright |
        |              |           |                  |                   |                |                         |                        |  (c) 2002-2012 by Cisco Systems, Inc. Compiled  |
        |              |           |                  |                   |                |                         |                        |                2/17/2016 22:00:00               |
        _________________________________________________________________________________________________________________________________________________________________________________________
        | edge01.oua01 |  xe-0/1/2 |       ae1        | 8C:60:4F:51:A4:22 |                |       Ethernet1/48      | edge05.oua01.dummy.net |   Cisco NX-OS(tm) n6000, Software (n6000-uk9),  |
        |              |           |                  |                   |                |                         |                        | Version 7.3(0)N7(5), RELEASE SOFTWARE Copyright |
        |              |           |                  |                   |                |                         |                        |  (c) 2002-2012 by Cisco Systems, Inc. Compiled  |
        |              |           |                  |                   |                |                         |                        |                2/17/2016 22:00:00               |
        _________________________________________________________________________________________________________________________________________________________________________________________
    """
    all_lldp = _get_mine("net.lldp")

    labels = {
        "device": "Device",
        "interface": "Interface",
        "parent_interface": "Parent Interface",
        "remote_chassis_id": "Remote Chassis ID",
        "remote_port_id": "Remote Port ID",
        "remote_port_desc": "Remote Port Description",
        "remote_system_name": "Remote System Name",
        "remote_system_desc": "Remote System Description",
    }
    rows = []

    if pattern:
        title = 'Pattern "{}" found in one of the following LLDP details'.format(
            pattern
        )
    if not title:
        title = "LLDP Neighbors"
        if interface:
            title += " for interface {}".format(interface)
        else:
            title += " for all interfaces"
        if device:
            title += " on device {}".format(device)
        if chassis:
            title += " having Chassis ID {}".format(chassis)

    if device:
        all_lldp = {device: all_lldp.get(device)}

    for device, device_lldp in all_lldp.items():
        if not device_lldp:
            continue
        if not device_lldp.get("result", False):
            continue
        lldp_interfaces = device_lldp.get("out", {})
        if interface:
            lldp_interfaces = {interface: lldp_interfaces.get(interface, [])}
        for intrf, interface_lldp in lldp_interfaces.items():
            if not interface_lldp:
                continue
            for lldp_row in interface_lldp:
                rsn = lldp_row.get("remote_system_name", "") or ""
                rpi = lldp_row.get("remote_port_id", "") or ""
                rsd = lldp_row.get("remote_system_description", "") or ""
                rpd = lldp_row.get("remote_port_description", "") or ""
                rci = lldp_row.get("remote_chassis_id", "") or ""
                if pattern:
                    ptl = pattern.lower()
                    if not (
                        (ptl in rsn.lower())
                        or (ptl in rsd.lower())
                        or (ptl in rpd.lower())
                        or (ptl in rci.lower())
                    ):
                        # nothing matched, let's move on
                        continue
                if chassis:
                    if napalm_helpers.convert(
                        napalm_helpers.mac, rci
                    ) != napalm_helpers.convert(napalm_helpers.mac, chassis):
                        continue
                rows.append(
                    {
                        "device": device,
                        "interface": intrf,
                        "parent_interface": (
                            lldp_row.get("parent_interface", "") or ""
                        ),
                        "remote_chassis_id": napalm_helpers.convert(
                            napalm_helpers.mac, rci
                        ),
                        "remote_port_id": rpi,
                        "remote_port_descr": rpd,
                        "remote_system_name": rsn,
                        "remote_system_descr": rsd,
                    }
                )

    return _display_runner(rows, labels, title, display=display)


def find(addr, best=True, display=_DEFAULT_DISPLAY):
    """
    Search in all possible entities (Interfaces, MAC tables, ARP tables, LLDP neighbors),
    using the following mine functions:

    - net.mac
    - net.arp
    - net.lldp
    - net.ipaddrs
    - net.interfaces

    This function has the advantage that it knows where to look, but the output might
    become quite long as returns all possible matches.

    Optional arguments:

    best: ``True``
        Return only the best match with the interfaces IP networks
        when the saerching pattern is a valid IP Address or Network.

    display: ``True``
        Display on the screen or return structured object? Default: ``True`` (return on the CLI).

    CLI Example:

    .. code-block:: bash

        $ sudo salt-run net.find 10.10.10.7

    Output Example:

    .. code-block:: text

        Details for all interfaces that include network 10.10.10.7/32 - only best match returned
        ________________________________________________________________________________________________________________________
        |    Device    | Interface | Interface Description |  UP  | Enabled | Speed [Mbps] |    MAC Address    |  IP Addresses |
        ________________________________________________________________________________________________________________________
        | edge01.flw01 |    irb    |                       | True |   True  |      -1      | 5C:5E:AB:AC:52:B4 | 10.10.10.1/22 |
        ________________________________________________________________________________________________________________________

        ARP Entries for IP 10.10.10.7
        _____________________________________________________________________________
        |    Device    |     Interface     |        MAC        |     IP     |  Age  |
        _____________________________________________________________________________
        | edge01.flw01 | irb.349 [ae0.349] | 2C:60:0C:2A:4C:0A | 10.10.10.7 | 832.0 |
        _____________________________________________________________________________
    """
    if not addr:
        if display:
            print("Please type a valid MAC/IP Address / Device / Interface / VLAN")
        return {}

    device = ""
    interface = ""
    mac = ""
    ip = ""  # pylint: disable=invalid-name
    ipnet = None

    results = {
        "int_net": [],
        "int_descr": [],
        "int_name": [],
        "int_ip": [],
        "int_mac": [],
        "int_device": [],
        "lldp_descr": [],
        "lldp_int": [],
        "lldp_device": [],
        "lldp_mac": [],
        "lldp_device_int": [],
        "mac_device": [],
        "mac_int": [],
        "arp_device": [],
        "arp_int": [],
        "arp_mac": [],
        "arp_ip": [],
    }

    if isinstance(addr, int):
        results["mac"] = findmac(vlan=addr, display=display)
        if not display:
            return results
        else:
            return None

    try:
        mac = napalm_helpers.convert(napalm_helpers.mac, addr)
    except IndexError:
        # no problem, let's keep searching
        pass
    if salt.utils.network.is_ipv6(addr):
        mac = False
    if not mac:
        try:
            ip = napalm_helpers.convert(
                napalm_helpers.ip, addr
            )  # pylint: disable=invalid-name
        except ValueError:
            pass
        ipnet = _get_network_obj(addr)
        if ipnet:
            results["int_net"] = interfaces(ipnet=ipnet, best=best, display=display)
        if not (ipnet or ip):
            # search in all possible places
            # display all interfaces details
            results["int_descr"] = interfaces(pattern=addr, display=display)
            results["int_name"] = interfaces(interface=addr, display=display)
            results["int_device"] = interfaces(device=addr, display=display)
            # search in LLDP details
            results["lldp_descr"] = lldp(pattern=addr, display=display)
            results["lldp_int"] = lldp(interface=addr, display=display)
            results["lldp_device"] = lldp(device=addr, display=display)
            # search in MAC Address tables
            results["mac_device"] = findmac(device=addr, display=display)
            results["mac_int"] = findmac(interface=addr, display=display)
            # search in ARP tables
            results["arp_device"] = findarp(device=addr, display=display)
            results["arp_int"] = findarp(interface=addr, display=display)
            if not display:
                return results
    if mac:
        results["int_descr"] = findmac(mac=mac, display=display)
        results["arp_mac"] = findarp(mac=mac, display=display)
        results["lldp_mac"] = lldp(chassis=mac, display=display)
    if ip:
        results["arp_ip"] = findarp(ip=ip, display=display)

    # let's search in Interfaces

    if mac:
        device, interface, ips = _find_interfaces_ip(mac)
        ip = ", ".join(ips)  # pylint: disable=invalid-name
        if device and interface:
            title = "Interface {interface} on {device} has the physical address ({mac})".format(
                interface=interface, device=device, mac=mac
            )
            results["int_mac"] = interfaces(
                device=device, interface=interface, title=title, display=display
            )

    elif ip:
        device, interface, mac = _find_interfaces_mac(ip)
        if device and interface:
            title = (
                "IP Address {ip} is set for interface {interface}, on {device}".format(
                    interface=interface, device=device, ip=ip
                )
            )
            results["int_ip"] = interfaces(
                device=device, interface=interface, title=title, display=display
            )

    if device and interface:
        results["lldp_device_int"] = lldp(device, interface, display=display)

    if not display:
        return results


def multi_find(*patterns, **kwargs):
    """
    Execute multiple search tasks.
    This function is based on the `find` function.
    Depending on the search items, some information might overlap.

    Optional arguments:

    best: ``True``
        Return only the best match with the interfaces IP networks
        when the saerching pattern is a valid IP Address or Network.

    display: ``True``
        Display on the screen or return structured object? Default: `True` (return on the CLI).

    CLI Example:

    .. code-block:: bash

        $ sudo salt-run net.multi_find Ethernet1/49 xe-0/1/2

    Output Example:

    .. code-block:: text

        Pattern "Ethernet1/49" found in one of the following LLDP details

            -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            |    Device    | Interface | Parent Interface | Remote Chassis ID | Remote Port Description | Remote Port ID |          Remote System Description          |   Remote System Name   |
            -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            | edge01.oua04 |  xe-0/1/2 |       ae1        | DE:AD:BE:EF:DE:AD |       Ethernet1/49      |                | Cisco NX-OS(tm) n6000, Software (n6000-uk9) | edge07.oua04.dummy.net |
            -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        Details for interface xe-0/1/2

            -----------------------------------------------------------------------------------------------------------------------
            |    Device    | Interface | Interface Description | IP Addresses | Enabled |  UP  |    MAC Address    | Speed [Mbps] |
            -----------------------------------------------------------------------------------------------------------------------
            | edge01.oua04 |  xe-0/1/2 |     ae1 sw01.oua04    |              |   True  | True | BE:EF:DE:AD:BE:EF |    10000     |
            -----------------------------------------------------------------------------------------------------------------------

        LLDP Neighbors for interface xe-0/1/2

            -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            |    Device    | Interface | Parent Interface | Remote Chassis ID | Remote Port Description | Remote Port ID |          Remote System Description          |   Remote System Name   |
            -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            | edge01.oua04 |  xe-0/1/2 |       ae1        | DE:AD:BE:EF:DE:AD |       Ethernet1/49      |                | Cisco NX-OS(tm) n6000, Software (n6000-uk9) | edge07.oua04.dummy.net |
            -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    """
    out = {}
    for pattern in set(patterns):
        search_result = find(
            pattern,
            best=kwargs.get("best", True),
            display=kwargs.get("display", _DEFAULT_DISPLAY),
        )
        out[pattern] = search_result
    if not kwargs.get("display", _DEFAULT_DISPLAY):
        return out
