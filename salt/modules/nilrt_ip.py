# -*- coding: utf-8 -*-
"""
The networking module for NI Linux Real-Time distro

"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import re
import time

# Import salt libs
import salt.exceptions
import salt.utils.files
import salt.utils.validate.net
from salt.ext import six

# Import 3rd-party libs
# pylint: disable=import-error,redefined-builtin,no-name-in-module
from salt.ext.six.moves import configparser, map, range

# pylint: enable=import-error,redefined-builtin,no-name-in-module

try:
    import pyconnman
except ImportError:
    pyconnman = None

try:
    import dbus
except ImportError:
    dbus = None

try:
    import pyiface
except ImportError:
    pyiface = None

try:
    from requests.structures import CaseInsensitiveDict
except ImportError:
    CaseInsensitiveDict = None

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "ip"

SERVICE_PATH = "/net/connman/service/"
INTERFACES_CONFIG = "/var/lib/connman/interfaces.config"
NIRTCFG_PATH = "/usr/local/natinst/bin/nirtcfg"
INI_FILE = "/etc/natinst/share/ni-rt.ini"
_CONFIG_TRUE = ["yes", "on", "true", "1", True]
IFF_LOOPBACK = 0x8
IFF_RUNNING = 0x40
NIRTCFG_ETHERCAT = "EtherCAT"


def _assume_condition(condition, err):
    """
    Raise an exception if the condition is false
    """
    if not condition:
        raise RuntimeError(err)


def __virtual__():
    """
    Confine this module to NI Linux Real-Time based distros
    """
    try:
        msg = "The nilrt_ip module could not be loaded: unsupported OS family"
        _assume_condition(__grains__["os_family"] == "NILinuxRT", msg)
        _assume_condition(
            CaseInsensitiveDict, "The python package request is not installed"
        )
        _assume_condition(pyiface, "The python pyiface package is not installed")
        if __grains__["lsb_distrib_id"] != "nilrt":
            _assume_condition(
                pyconnman, "The python package pyconnman is not installed"
            )
            _assume_condition(dbus, "The python DBus package is not installed")
            _assume_condition(_get_state() != "offline", "Connman is not running")
    except RuntimeError as exc:
        return False, str(exc)
    return __virtualname__


def _get_state():
    """
    Returns the state of connman
    """
    try:
        return pyconnman.ConnManager().get_property("State")
    except KeyError:
        return "offline"
    except dbus.DBusException as exc:
        raise salt.exceptions.CommandExecutionError(
            "Connman daemon error: {0}".format(exc)
        )


def _get_technologies():
    """
    Returns the technologies of connman
    """
    tech = ""
    technologies = pyconnman.ConnManager().get_technologies()
    for path, params in technologies:
        tech += "{0}\n\tName = {1}\n\tType = {2}\n\tPowered = {3}\n\tConnected = {4}\n".format(
            path,
            params["Name"],
            params["Type"],
            params["Powered"] == 1,
            params["Connected"] == 1,
        )
    return tech


def _get_services():
    """
    Returns a list with all connman services
    """
    serv = []
    services = pyconnman.ConnManager().get_services()
    for path, _ in services:
        serv.append(six.text_type(path[len(SERVICE_PATH) :]))
    return serv


def _connected(service):
    """
    Verify if a connman service is connected
    """
    state = pyconnman.ConnService(os.path.join(SERVICE_PATH, service)).get_property(
        "State"
    )
    return state == "online" or state == "ready"


def _space_delimited_list(value):
    """
    validate that a value contains one or more space-delimited values
    """
    if isinstance(value, str):
        items = value.split(" ")
        valid = items and all(items)
    else:
        valid = hasattr(value, "__iter__") and (value != [])

    if valid:
        return (True, "space-delimited string")
    else:
        return (False, "{0} is not a valid list.\n".format(value))


def _validate_ipv4(value):
    """
    validate ipv4 values
    """
    if len(value) == 3:
        if not salt.utils.validate.net.ipv4_addr(value[0].strip()):
            return False, "Invalid ip address: {0} for ipv4 option".format(value[0])
        if not salt.utils.validate.net.netmask(value[1].strip()):
            return False, "Invalid netmask: {0} for ipv4 option".format(value[1])
        if not salt.utils.validate.net.ipv4_addr(value[2].strip()):
            return False, "Invalid gateway: {0} for ipv4 option".format(value[2])
    else:
        return False, "Invalid value: {0} for ipv4 option".format(value)
    return True, ""


def _interface_to_service(iface):
    """
    returns the coresponding service to given interface if exists, otherwise return None
    """
    for _service in _get_services():
        service_info = pyconnman.ConnService(os.path.join(SERVICE_PATH, _service))
        if service_info.get_property("Ethernet")["Interface"] == iface:
            return _service
    return None


def _get_service_info(service):
    """
    return details about given connman service
    """
    service_info = pyconnman.ConnService(os.path.join(SERVICE_PATH, service))
    data = {
        "label": service,
        "wireless": service_info.get_property("Type") == "wifi",
        "connectionid": six.text_type(
            service_info.get_property("Ethernet")["Interface"]
        ),
        "hwaddr": six.text_type(service_info.get_property("Ethernet")["Address"]),
    }

    state = service_info.get_property("State")
    if state == "ready" or state == "online":
        data["up"] = True
        data["ipv4"] = {"gateway": "0.0.0.0"}
        ipv4 = "IPv4"
        if service_info.get_property("IPv4")["Method"] == "manual":
            ipv4 += ".Configuration"
        ipv4_info = service_info.get_property(ipv4)
        for info in ["Method", "Address", "Netmask", "Gateway"]:
            value = ipv4_info.get(info)
            if value is None:
                log.warning("Unable to get IPv4 %s for service %s\n", info, service)
                continue
            if info == "Method":
                info = "requestmode"
                if value == "dhcp":
                    value = "dhcp_linklocal"
                elif value in ("manual", "fixed"):
                    value = "static"
            data["ipv4"][info.lower()] = six.text_type(value)

        ipv6_info = service_info.get_property("IPv6")
        for info in ["Address", "Prefix", "Gateway"]:
            value = ipv6_info.get(info)
            if value is None:
                log.warning("Unable to get IPv6 %s for service %s\n", info, service)
                continue
            data["ipv6"][info.lower()] = [six.text_type(value)]

        nameservers = []
        for nameserver_prop in service_info.get_property("Nameservers"):
            nameservers.append(six.text_type(nameserver_prop))
        data["ipv4"]["dns"] = nameservers
    else:
        data["up"] = False

    if "ipv4" in data:
        data["ipv4"]["supportedrequestmodes"] = ["static", "dhcp_linklocal"]
    return data


def _get_dns_info():
    """
    return dns list
    """
    dns_list = []
    try:
        with salt.utils.files.fopen("/etc/resolv.conf", "r+") as dns_info:
            lines = dns_info.readlines()
            for line in lines:
                if "nameserver" in line:
                    dns = line.split()[1].strip()
                    if dns not in dns_list:
                        dns_list.append(dns)
    except IOError:
        log.warning("Could not get domain\n")
    return dns_list


def _remove_quotes(value):
    """
    Remove leading and trailing double quotes if they exist.
    """
    # nirtcfg writes values with quotes
    if len(value) > 1 and value[0] == value[-1] == '"':
        value = value[1:-1]
    return value


def _load_config(section, options, default_value="", filename=INI_FILE):
    """
    Get values for some options and a given section from a config file.

    :param section: Section Name
    :param options: List of options
    :param default_value: Default value if an option doesn't have a value. Default is empty string.
    :param filename: config file. Default is INI_FILE.
    :return:
    """
    results = {}
    if not options:
        return results
    with salt.utils.files.fopen(filename, "r") as config_file:
        config_parser = configparser.RawConfigParser(dict_type=CaseInsensitiveDict)
        config_parser.readfp(config_file)
        for option in options:
            if six.PY2:
                results[option] = (
                    _remove_quotes(config_parser.get(section, option))
                    if config_parser.has_option(section, option)
                    else default_value
                )
            else:
                results[option] = _remove_quotes(
                    config_parser.get(section, option, fallback=default_value)
                )

    return results


def _get_request_mode_info(interface):
    """
    return requestmode for given interface
    """
    settings = _load_config(interface, ["linklocalenabled", "dhcpenabled"], -1)
    link_local_enabled = int(settings["linklocalenabled"])
    dhcp_enabled = int(settings["dhcpenabled"])

    if dhcp_enabled == 1:
        return "dhcp_linklocal" if link_local_enabled == 1 else "dhcp_only"
    else:
        if link_local_enabled == 1:
            return "linklocal_only"
        if link_local_enabled == 0:
            return "static"

    # some versions of nirtcfg don't set the dhcpenabled/linklocalenabled variables
    # when selecting "DHCP or Link Local" from MAX, so return it by default to avoid
    # having the requestmode "None" because none of the conditions above matched.
    return "dhcp_linklocal"


def _get_adapter_mode_info(interface):
    """
    return adaptermode for given interface
    """
    mode = _load_config(interface, ["mode"])["mode"].lower()
    return mode if mode in ["disabled", "ethercat"] else "tcpip"


def _get_possible_adapter_modes(interface, blacklist):
    """
    Return possible adapter modes for a given interface using a blacklist.

    :param interface: interface name
    :param blacklist: given blacklist
    :return: list of possible adapter modes
    """
    adapter_modes = []
    protocols = _load_config("lvrt", ["AdditionalNetworkProtocols"])[
        "AdditionalNetworkProtocols"
    ].lower()
    sys_interface_path = os.readlink("/sys/class/net/{0}".format(interface))
    with salt.utils.files.fopen(
        "/sys/class/net/{0}/uevent".format(interface)
    ) as uevent_file:
        uevent_lines = uevent_file.readlines()
    uevent_devtype = ""
    for line in uevent_lines:
        if line.startswith("DEVTYPE="):
            uevent_devtype = line.split("=")[1].strip()
            break

    for adapter_mode in blacklist:
        if adapter_mode == "_":
            continue
        value = blacklist.get(adapter_mode, {})
        if value.get("additional_protocol") and adapter_mode not in protocols:
            continue

        if interface not in value["name"] and not any(
            (blacklist["_"][iface_type] == "sys" and iface_type in sys_interface_path)
            or (blacklist["_"][iface_type] == "uevent" and iface_type == uevent_devtype)
            for iface_type in value["type"]
        ):
            adapter_modes += [adapter_mode]
    return adapter_modes


def _get_static_info(interface):
    """
    Return information about an interface from config file.

    :param interface: interface label
    """
    data = {
        "connectionid": interface.name,
        "label": interface.name,
        "hwaddr": interface.hwaddr[:-1],
        "up": False,
        "ipv4": {
            "supportedrequestmodes": ["static", "dhcp_linklocal"],
            "requestmode": "static",
        },
        "wireless": False,
    }
    hwaddr_section_number = "".join(data["hwaddr"].split(":"))
    if os.path.exists(INTERFACES_CONFIG):
        information = _load_config(
            hwaddr_section_number, ["IPv4", "Nameservers"], filename=INTERFACES_CONFIG
        )
        if information["IPv4"] != "":
            ipv4_information = information["IPv4"].split("/")
            data["ipv4"]["address"] = ipv4_information[0]
            data["ipv4"]["dns"] = information["Nameservers"].split(",")
            data["ipv4"]["netmask"] = ipv4_information[1]
            data["ipv4"]["gateway"] = ipv4_information[2]
    return data


def _get_interface_info(interface):
    """
    return details about given interface
    """
    blacklist = {
        "tcpip": {"name": [], "type": [], "additional_protocol": False},
        "disabled": {
            "name": ["eth0"],
            "type": ["gadget"],
            "additional_protocol": False,
        },
        "ethercat": {
            "name": ["eth0"],
            "type": ["gadget", "usb", "wlan"],
            "additional_protocol": True,
        },
        "_": {"usb": "sys", "gadget": "uevent", "wlan": "uevent"},
    }
    data = {
        "label": interface.name,
        "connectionid": interface.name,
        "supported_adapter_modes": _get_possible_adapter_modes(
            interface.name, blacklist
        ),
        "adapter_mode": _get_adapter_mode_info(interface.name),
        "up": False,
        "ipv4": {
            "supportedrequestmodes": [
                "dhcp_linklocal",
                "dhcp_only",
                "linklocal_only",
                "static",
            ],
            "requestmode": _get_request_mode_info(interface.name),
        },
        "hwaddr": interface.hwaddr[:-1],
    }
    needed_settings = []
    if data["ipv4"]["requestmode"] == "static":
        needed_settings += ["IP_Address", "Subnet_Mask", "Gateway", "DNS_Address"]
    if data["adapter_mode"] == "ethercat":
        needed_settings += ["MasterID"]
    settings = _load_config(interface.name, needed_settings)
    if interface.flags & IFF_RUNNING != 0:
        data["up"] = True
        data["ipv4"]["address"] = interface.sockaddrToStr(interface.addr)
        data["ipv4"]["netmask"] = interface.sockaddrToStr(interface.netmask)
        data["ipv4"]["gateway"] = "0.0.0.0"
        data["ipv4"]["dns"] = _get_dns_info()
    elif data["ipv4"]["requestmode"] == "static":
        data["ipv4"]["address"] = settings["IP_Address"]
        data["ipv4"]["netmask"] = settings["Subnet_Mask"]
        data["ipv4"]["gateway"] = settings["Gateway"]
        data["ipv4"]["dns"] = [settings["DNS_Address"]]

    with salt.utils.files.fopen("/proc/net/route", "r") as route_file:
        pattern = re.compile(
            r"^{interface}\t[0]{{8}}\t([0-9A-Z]{{8}})".format(interface=interface.name),
            re.MULTILINE,
        )
        match = pattern.search(route_file.read())
        iface_gateway_hex = None if not match else match.group(1)
    if iface_gateway_hex is not None and len(iface_gateway_hex) == 8:
        data["ipv4"]["gateway"] = ".".join(
            [str(int(iface_gateway_hex[i : i + 2], 16)) for i in range(6, -1, -2)]
        )
    if data["adapter_mode"] == "ethercat":
        data["ethercat"] = {"masterid": settings["MasterID"]}
    return data


def _dict_to_string(dictionary):
    """
    converts a dictionary object into a list of strings
    """
    ret = ""
    for key, val in sorted(dictionary.items()):
        if isinstance(val, dict):
            for line in _dict_to_string(val):
                ret += six.text_type(key) + "-" + line + "\n"
        elif isinstance(val, list):
            text = " ".join([six.text_type(item) for item in val])
            ret += six.text_type(key) + ": " + text + "\n"
        else:
            ret += six.text_type(key) + ": " + six.text_type(val) + "\n"
    return ret.splitlines()


def _get_info(interface):
    """
    Return information about an interface even if it's not associated with a service.

    :param interface: interface label
    """
    service = _interface_to_service(interface.name)
    if service is not None:
        return _get_service_info(service)
    return _get_static_info(interface)


def get_interfaces_details():
    """
    Get details about all the interfaces on the minion

    :return: information about all interfaces omitting loopback
    :rtype: dictionary

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_interfaces_details
    """
    _interfaces = [
        interface
        for interface in pyiface.getIfaces()
        if interface.flags & IFF_LOOPBACK == 0
    ]
    if __grains__["lsb_distrib_id"] == "nilrt":
        return {"interfaces": list(map(_get_interface_info, _interfaces))}
    return {"interfaces": list(map(_get_info, _interfaces))}


def _change_state(interface, new_state):
    """
    Enable or disable an interface

    Change adapter mode to TCP/IP. If previous adapter mode was EtherCAT, the target will need reboot.

    :param interface: interface label
    :param new_state: up or down
    :return: True if the service was enabled, otherwise an exception will be thrown.
    :rtype: bool
    """
    if __grains__["lsb_distrib_id"] == "nilrt":
        initial_mode = _get_adapter_mode_info(interface)
        _save_config(interface, "Mode", "TCPIP")
        if initial_mode == "ethercat":
            __salt__["system.set_reboot_required_witnessed"]()
        else:
            out = __salt__["cmd.run_all"](
                "ip link set {0} {1}".format(interface, new_state)
            )
            if out["retcode"] != 0:
                msg = "Couldn't {0} interface {1}. Error: {2}".format(
                    "enable" if new_state == "up" else "disable",
                    interface,
                    out["stderr"],
                )
                raise salt.exceptions.CommandExecutionError(msg)
        return True
    service = _interface_to_service(interface)
    if not service:
        raise salt.exceptions.CommandExecutionError(
            "Invalid interface name: {0}".format(interface)
        )
    if not _connected(service):
        service = pyconnman.ConnService(os.path.join(SERVICE_PATH, service))
        try:
            state = service.connect() if new_state == "up" else service.disconnect()
            return state is None
        except Exception:  # pylint: disable=broad-except
            raise salt.exceptions.CommandExecutionError(
                "Couldn't {0} service: {1}\n".format(
                    "enable" if new_state == "up" else "disable", service
                )
            )
    return True


def up(interface, iface_type=None):  # pylint: disable=invalid-name,unused-argument
    """
    Enable the specified interface

    Change adapter mode to TCP/IP. If previous adapter mode was EtherCAT, the target will need reboot.

    :param str interface: interface label
    :return: True if the service was enabled, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.up interface-label
    """
    return _change_state(interface, "up")


def enable(interface):
    """
    Enable the specified interface

    Change adapter mode to TCP/IP. If previous adapter mode was EtherCAT, the target will need reboot.

    :param str interface: interface label
    :return: True if the service was enabled, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.enable interface-label
    """
    return up(interface)


def down(interface, iface_type=None):  # pylint: disable=unused-argument
    """
    Disable the specified interface

    Change adapter mode to Disabled. If previous adapter mode was EtherCAT, the target will need reboot.

    :param str interface: interface label
    :return: True if the service was disabled, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.down interface-label
    """
    return _change_state(interface, "down")


def disable(interface):
    """
    Disable the specified interface

    Change adapter mode to Disabled. If previous adapter mode was EtherCAT, the target will need reboot.

    :param str interface: interface label
    :return: True if the service was disabled, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.disable interface-label
    """
    return down(interface)


def _save_config(section, token, value):
    """
    Helper function to persist a configuration in the ini file
    """
    cmd = NIRTCFG_PATH
    cmd += " --set section={0},token='{1}',value='{2}'".format(section, token, value)
    if __salt__["cmd.run_all"](cmd)["retcode"] != 0:
        exc_msg = "Error: could not set {} to {} for {}\n".format(token, value, section)
        raise salt.exceptions.CommandExecutionError(exc_msg)


def set_ethercat(interface, master_id):
    """
    Configure specified adapter to use EtherCAT adapter mode. If successful, the target will need reboot if it doesn't
    already use EtherCAT adapter mode, otherwise will return true.

    :param interface: interface label
    :param master_id: EtherCAT Master ID
    :return: True if the settings were applied, otherwise an exception will be thrown.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.set_ethercat interface-label master-id
    """
    if __grains__["lsb_distrib_id"] == "nilrt":
        initial_mode = _get_adapter_mode_info(interface)
        _save_config(interface, "Mode", NIRTCFG_ETHERCAT)
        _save_config(interface, "MasterID", master_id)
        if initial_mode != "ethercat":
            __salt__["system.set_reboot_required_witnessed"]()
        return True
    raise salt.exceptions.CommandExecutionError("EtherCAT is not supported")


def _restart(interface):
    """
    Disable and enable an interface
    """
    disable(interface)
    enable(interface)


def set_dhcp_linklocal_all(interface):
    """
    Configure specified adapter to use DHCP with linklocal fallback

    Change adapter mode to TCP/IP. If previous adapter mode was EtherCAT, the target will need reboot.

    :param str interface: interface label
    :return: True if the settings were applied, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.set_dhcp_linklocal_all interface-label
    """
    if __grains__["lsb_distrib_id"] == "nilrt":
        initial_mode = _get_adapter_mode_info(interface)
        _save_config(interface, "Mode", "TCPIP")
        _save_config(interface, "dhcpenabled", "1")
        _save_config(interface, "linklocalenabled", "1")
        if initial_mode == "ethercat":
            __salt__["system.set_reboot_required_witnessed"]()
        else:
            _restart(interface)
        return True
    service = _interface_to_service(interface)
    if not service:
        raise salt.exceptions.CommandExecutionError(
            "Invalid interface name: {0}".format(interface)
        )
    service = pyconnman.ConnService(os.path.join(SERVICE_PATH, service))
    ipv4 = service.get_property("IPv4.Configuration")
    ipv4["Method"] = dbus.String("dhcp", variant_level=1)
    ipv4["Address"] = dbus.String("", variant_level=1)
    ipv4["Netmask"] = dbus.String("", variant_level=1)
    ipv4["Gateway"] = dbus.String("", variant_level=1)
    try:
        service.set_property("IPv4.Configuration", ipv4)
        service.set_property(
            "Nameservers.Configuration", [""]
        )  # reset nameservers list
    except Exception as exc:  # pylint: disable=broad-except
        exc_msg = "Couldn't set dhcp linklocal for service: {0}\nError: {1}\n".format(
            service, exc
        )
        raise salt.exceptions.CommandExecutionError(exc_msg)
    return True


def set_dhcp_only_all(interface):
    """
    Configure specified adapter to use DHCP only

    Change adapter mode to TCP/IP. If previous adapter mode was EtherCAT, the target will need reboot.

    :param str interface: interface label
    :return: True if the settings were applied, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.dhcp_only_all interface-label
    """
    if not __grains__["lsb_distrib_id"] == "nilrt":
        raise salt.exceptions.CommandExecutionError("Not supported in this version")
    initial_mode = _get_adapter_mode_info(interface)
    _save_config(interface, "Mode", "TCPIP")
    _save_config(interface, "dhcpenabled", "1")
    _save_config(interface, "linklocalenabled", "0")
    if initial_mode == "ethercat":
        __salt__["system.set_reboot_required_witnessed"]()
    else:
        _restart(interface)
    return True


def set_linklocal_only_all(interface):
    """
    Configure specified adapter to use linklocal only

    Change adapter mode to TCP/IP. If previous adapter mode was EtherCAT, the target will need reboot.

    :param str interface: interface label
    :return: True if the settings were applied, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.linklocal_only_all interface-label
    """
    if not __grains__["lsb_distrib_id"] == "nilrt":
        raise salt.exceptions.CommandExecutionError("Not supported in this version")
    initial_mode = _get_adapter_mode_info(interface)
    _save_config(interface, "Mode", "TCPIP")
    _save_config(interface, "dhcpenabled", "0")
    _save_config(interface, "linklocalenabled", "1")
    if initial_mode == "ethercat":
        __salt__["system.set_reboot_required_witnessed"]()
    else:
        _restart(interface)
    return True


def _configure_static_interface(interface, **settings):
    """
    Configure an interface that is not detected as a service by Connman (i.e. link is down)

    :param interface: interface label
    :param settings:
            - ip
            - netmask
            - gateway
            - dns
            - name
    :return: True if settings were applied successfully.
    :rtype: bool
    """
    interface = pyiface.Interface(name=interface)
    parser = configparser.ConfigParser()
    if os.path.exists(INTERFACES_CONFIG):
        try:
            with salt.utils.files.fopen(INTERFACES_CONFIG, "r") as config_file:
                parser.readfp(config_file)
        except configparser.MissingSectionHeaderError:
            pass
    hwaddr = interface.hwaddr[:-1]
    hwaddr_section_number = "".join(hwaddr.split(":"))
    if not parser.has_section("interface_{0}".format(hwaddr_section_number)):
        parser.add_section("interface_{0}".format(hwaddr_section_number))
    ip_address = settings.get("ip", "0.0.0.0")
    netmask = settings.get("netmask", "0.0.0.0")
    gateway = settings.get("gateway", "0.0.0.0")
    dns_servers = settings.get("dns", "")
    name = settings.get("name", "ethernet_cable_{0}".format(hwaddr_section_number))
    parser.set(
        "interface_{0}".format(hwaddr_section_number),
        "IPv4",
        "{0}/{1}/{2}".format(ip_address, netmask, gateway),
    )
    parser.set(
        "interface_{0}".format(hwaddr_section_number), "Nameservers", dns_servers
    )
    parser.set("interface_{0}".format(hwaddr_section_number), "Name", name)
    parser.set("interface_{0}".format(hwaddr_section_number), "MAC", hwaddr)
    parser.set("interface_{0}".format(hwaddr_section_number), "Type", "ethernet")
    with salt.utils.files.fopen(INTERFACES_CONFIG, "w") as config_file:
        parser.write(config_file)
    return True


def set_static_all(interface, address, netmask, gateway, nameservers):
    """
    Configure specified adapter to use ipv4 manual settings

    Change adapter mode to TCP/IP. If previous adapter mode was EtherCAT, the target will need reboot.

    :param str interface: interface label
    :param str address: ipv4 address
    :param str netmask: ipv4 netmask
    :param str gateway: ipv4 gateway
    :param str nameservers: list of nameservers servers separated by spaces
    :return: True if the settings were applied, otherwise an exception will be thrown.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' ip.set_static_all interface-label address netmask gateway nameservers
    """
    validate, msg = _validate_ipv4([address, netmask, gateway])
    if not validate:
        raise salt.exceptions.CommandExecutionError(msg)
    validate, msg = _space_delimited_list(nameservers)
    if not validate:
        raise salt.exceptions.CommandExecutionError(msg)
    if not isinstance(nameservers, list):
        nameservers = nameservers.split(" ")
    if __grains__["lsb_distrib_id"] == "nilrt":
        initial_mode = _get_adapter_mode_info(interface)
        _save_config(interface, "Mode", "TCPIP")
        _save_config(interface, "dhcpenabled", "0")
        _save_config(interface, "linklocalenabled", "0")
        _save_config(interface, "IP_Address", address)
        _save_config(interface, "Subnet_Mask", netmask)
        _save_config(interface, "Gateway", gateway)
        if nameservers:
            _save_config(interface, "DNS_Address", nameservers[0])
        if initial_mode == "ethercat":
            __salt__["system.set_reboot_required_witnessed"]()
        else:
            _restart(interface)
        return True
    service = _interface_to_service(interface)
    if not service:
        if interface in pyiface.getIfaces():
            return _configure_static_interface(
                interface,
                **{
                    "ip": address,
                    "dns": ",".join(nameservers),
                    "netmask": netmask,
                    "gateway": gateway,
                }
            )
        raise salt.exceptions.CommandExecutionError(
            "Invalid interface name: {0}".format(interface)
        )
    service = pyconnman.ConnService(os.path.join(SERVICE_PATH, service))
    ipv4 = service.get_property("IPv4.Configuration")
    ipv4["Method"] = dbus.String("manual", variant_level=1)
    ipv4["Address"] = dbus.String("{0}".format(address), variant_level=1)
    ipv4["Netmask"] = dbus.String("{0}".format(netmask), variant_level=1)
    ipv4["Gateway"] = dbus.String("{0}".format(gateway), variant_level=1)
    try:
        service.set_property("IPv4.Configuration", ipv4)
        service.set_property(
            "Nameservers.Configuration",
            [dbus.String("{0}".format(d)) for d in nameservers],
        )
    except Exception as exc:  # pylint: disable=broad-except
        exc_msg = "Couldn't set manual settings for service: {0}\nError: {1}\n".format(
            service, exc
        )
        raise salt.exceptions.CommandExecutionError(exc_msg)
    return True


def get_interface(iface):
    """
    Returns details about given interface.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_interface eth0
    """
    _interfaces = get_interfaces_details()
    for _interface in _interfaces["interfaces"]:
        if _interface["connectionid"] == iface:
            return _dict_to_string(_interface)
    return None


def build_interface(iface, iface_type, enabled, **settings):
    """
    Build an interface script for a network interface.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_interface eth0 eth <settings>
    """
    if __grains__["lsb_distrib_id"] == "nilrt":
        raise salt.exceptions.CommandExecutionError("Not supported in this version.")
    if iface_type != "eth":
        raise salt.exceptions.CommandExecutionError(
            "Interface type not supported: {0}:".format(iface_type)
        )

    if (
        "proto" not in settings or settings["proto"] == "dhcp"
    ):  # default protocol type used is dhcp
        set_dhcp_linklocal_all(iface)
    elif settings["proto"] != "static":
        exc_msg = "Protocol type: {0} is not supported".format(settings["proto"])
        raise salt.exceptions.CommandExecutionError(exc_msg)
    else:
        address = settings["ipaddr"]
        netmask = settings["netmask"]
        gateway = settings["gateway"]
        dns = []
        for key, val in six.iteritems(settings):
            if "dns" in key or "domain" in key:
                dns += val
        set_static_all(iface, address, netmask, gateway, dns)

    if enabled:
        up(iface)

    return get_interface(iface)


def build_network_settings(**settings):
    """
    Build the global network script.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_network_settings <settings>
    """
    if __grains__["lsb_distrib_id"] == "nilrt":
        raise salt.exceptions.CommandExecutionError("Not supported in this version.")
    changes = []
    if "networking" in settings:
        if settings["networking"] in _CONFIG_TRUE:
            __salt__["service.enable"]("connman")
        else:
            __salt__["service.disable"]("connman")

    if "hostname" in settings:
        new_hostname = settings["hostname"].split(".", 1)[0]
        settings["hostname"] = new_hostname
        old_hostname = __salt__["network.get_hostname"]
        if new_hostname != old_hostname:
            __salt__["network.mod_hostname"](new_hostname)
            changes.append("hostname={0}".format(new_hostname))

    return changes


def get_network_settings():
    """
    Return the contents of the global network script.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_network_settings
    """
    if __grains__["lsb_distrib_id"] == "nilrt":
        raise salt.exceptions.CommandExecutionError("Not supported in this version.")
    settings = []
    networking = "no" if _get_state() == "offline" else "yes"
    settings.append("networking={0}".format(networking))
    hostname = __salt__["network.get_hostname"]
    settings.append("hostname={0}".format(hostname))
    return settings


def apply_network_settings(**settings):
    """
    Apply global network configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.apply_network_settings
    """
    if __grains__["lsb_distrib_id"] == "nilrt":
        raise salt.exceptions.CommandExecutionError("Not supported in this version.")
    if "require_reboot" not in settings:
        settings["require_reboot"] = False

    if "apply_hostname" not in settings:
        settings["apply_hostname"] = False

    hostname_res = True
    if settings["apply_hostname"] in _CONFIG_TRUE:
        if "hostname" in settings:
            hostname_res = __salt__["network.mod_hostname"](settings["hostname"])
        else:
            log.warning(
                "The network state sls is trying to apply hostname "
                "changes but no hostname is defined."
            )
            hostname_res = False

    res = True
    if settings["require_reboot"] in _CONFIG_TRUE:
        log.warning(
            "The network state sls is requiring a reboot of the system to "
            "properly apply network configuration."
        )
        res = True
    else:
        stop = __salt__["service.stop"]("connman")
        time.sleep(2)
        res = stop and __salt__["service.start"]("connman")

    return hostname_res and res
