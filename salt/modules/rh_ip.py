# -*- coding: utf-8 -*-
"""
The networking module for RHEL/Fedora based distros
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import os
import os.path

# Import third party libs
import jinja2
import jinja2.exceptions

# Import salt libs
import salt.utils.files
import salt.utils.stringutils
import salt.utils.templates
import salt.utils.validate.net
from salt.exceptions import CommandExecutionError
from salt.ext import six

# Set up logging
log = logging.getLogger(__name__)

# Set up template environment
JINJA = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(salt.utils.templates.TEMPLATE_DIRNAME, "rh_ip")
    )
)

# Define the module's virtual name
__virtualname__ = "ip"


def __virtual__():
    """
    Confine this module to RHEL/Fedora based distros
    """
    if __grains__["os_family"] == "RedHat":
        return __virtualname__
    return (
        False,
        "The rh_ip execution module cannot be loaded: this module is only available on RHEL/Fedora based distributions.",
    )


# Setup networking attributes
_ETHTOOL_CONFIG_OPTS = [
    "autoneg",
    "speed",
    "duplex",
    "rx",
    "tx",
    "sg",
    "tso",
    "ufo",
    "gso",
    "gro",
    "lro",
    "advertise",
]
_RH_CONFIG_OPTS = [
    "domain",
    "peerdns",
    "peerntp",
    "defroute",
    "mtu",
    "static-routes",
    "gateway",
    "zone",
]
_RH_CONFIG_BONDING_OPTS = [
    "mode",
    "miimon",
    "arp_interval",
    "arp_ip_target",
    "downdelay",
    "updelay",
    "use_carrier",
    "lacp_rate",
    "hashing-algorithm",
    "max_bonds",
    "tx_queues",
    "num_grat_arp",
    "num_unsol_na",
    "primary",
    "primary_reselect",
    "ad_select",
    "xmit_hash_policy",
    "arp_validate",
    "fail_over_mac",
    "all_slaves_active",
    "resend_igmp",
]
_RH_NETWORK_SCRIPT_DIR = "/etc/sysconfig/network-scripts"
_RH_NETWORK_FILE = "/etc/sysconfig/network"
_RH_NETWORK_CONF_FILES = "/etc/modprobe.d"
_CONFIG_TRUE = ["yes", "on", "true", "1", True]
_CONFIG_FALSE = ["no", "off", "false", "0", False]
_IFACE_TYPES = [
    "eth",
    "bond",
    "alias",
    "clone",
    "ipsec",
    "dialup",
    "bridge",
    "slave",
    "vlan",
    "ipip",
    "ib",
]


def _error_msg_iface(iface, option, expected):
    """
    Build an appropriate error message from a given option and
    a list of expected values.
    """
    msg = "Invalid option -- Interface: {0}, Option: {1}, Expected: [{2}]"
    return msg.format(iface, option, "|".join(str(e) for e in expected))


def _error_msg_routes(iface, option, expected):
    """
    Build an appropriate error message from a given option and
    a list of expected values.
    """
    msg = "Invalid option -- Route interface: {0}, Option: {1}, Expected: [{2}]"
    return msg.format(iface, option, expected)


def _log_default_iface(iface, opt, value):
    log.info(
        "Using default option -- Interface: %s Option: %s Value: %s", iface, opt, value
    )


def _error_msg_network(option, expected):
    """
    Build an appropriate error message from a given option and
    a list of expected values.
    """
    msg = "Invalid network setting -- Setting: {0}, Expected: [{1}]"
    return msg.format(option, "|".join(str(e) for e in expected))


def _log_default_network(opt, value):
    log.info("Using existing setting -- Setting: %s Value: %s", opt, value)


def _parse_rh_config(path):
    rh_config = _read_file(path)
    cv_rh_config = {}
    if rh_config:
        for line in rh_config:
            line = line.strip()
            if len(line) == 0 or line.startswith("!") or line.startswith("#"):
                continue
            pair = [p.rstrip() for p in line.split("=", 1)]
            if len(pair) != 2:
                continue
            name, value = pair
            cv_rh_config[name.upper()] = value

    return cv_rh_config


def _parse_ethtool_opts(opts, iface):
    """
    Filters given options and outputs valid settings for ETHTOOLS_OPTS
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    """
    config = {}

    if "autoneg" in opts:
        if opts["autoneg"] in _CONFIG_TRUE:
            config.update({"autoneg": "on"})
        elif opts["autoneg"] in _CONFIG_FALSE:
            config.update({"autoneg": "off"})
        else:
            _raise_error_iface(iface, "autoneg", _CONFIG_TRUE + _CONFIG_FALSE)

    if "duplex" in opts:
        valid = ["full", "half"]
        if opts["duplex"] in valid:
            config.update({"duplex": opts["duplex"]})
        else:
            _raise_error_iface(iface, "duplex", valid)

    if "speed" in opts:
        valid = ["10", "100", "1000", "10000"]
        if six.text_type(opts["speed"]) in valid:
            config.update({"speed": opts["speed"]})
        else:
            _raise_error_iface(iface, opts["speed"], valid)

    if "advertise" in opts:
        valid = [
            "0x001",
            "0x002",
            "0x004",
            "0x008",
            "0x010",
            "0x020",
            "0x20000",
            "0x8000",
            "0x1000",
            "0x40000",
            "0x80000",
            "0x200000",
            "0x400000",
            "0x800000",
            "0x1000000",
            "0x2000000",
            "0x4000000",
        ]
        if six.text_type(opts["advertise"]) in valid:
            config.update({"advertise": opts["advertise"]})
        else:
            _raise_error_iface(iface, "advertise", valid)

    valid = _CONFIG_TRUE + _CONFIG_FALSE
    for option in ("rx", "tx", "sg", "tso", "ufo", "gso", "gro", "lro"):
        if option in opts:
            if opts[option] in _CONFIG_TRUE:
                config.update({option: "on"})
            elif opts[option] in _CONFIG_FALSE:
                config.update({option: "off"})
            else:
                _raise_error_iface(iface, option, valid)

    return config


def _parse_settings_bond(opts, iface):
    """
    Filters given options and outputs valid settings for requested
    operation. If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    """

    bond_def = {
        # 803.ad aggregation selection logic
        # 0 for stable (default)
        # 1 for bandwidth
        # 2 for count
        "ad_select": "0",
        # Max number of transmit queues (default = 16)
        "tx_queues": "16",
        # Link monitoring in milliseconds. Most NICs support this
        "miimon": "100",
        # ARP interval in milliseconds
        "arp_interval": "250",
        # Delay before considering link down in milliseconds (miimon * 2)
        "downdelay": "200",
        # lacp_rate 0: Slow - every 30 seconds
        # lacp_rate 1: Fast - every 1 second
        "lacp_rate": "0",
        # Max bonds for this driver
        "max_bonds": "1",
        # Specifies the time, in milliseconds, to wait before
        # enabling a slave after a link recovery has been
        # detected. Only used with miimon.
        "updelay": "0",
        # Used with miimon.
        # On: driver sends mii
        # Off: ethtool sends mii
        "use_carrier": "0",
        # Default. Don't change unless you know what you are doing.
        "xmit_hash_policy": "layer2",
    }

    if opts["mode"] in ["balance-rr", "0"]:
        log.info("Device: %s Bonding Mode: load balancing (round-robin)", iface)
        return _parse_settings_bond_0(opts, iface, bond_def)
    elif opts["mode"] in ["active-backup", "1"]:
        log.info("Device: %s Bonding Mode: fault-tolerance (active-backup)", iface)
        return _parse_settings_bond_1(opts, iface, bond_def)
    elif opts["mode"] in ["balance-xor", "2"]:
        log.info("Device: %s Bonding Mode: load balancing (xor)", iface)
        return _parse_settings_bond_2(opts, iface, bond_def)
    elif opts["mode"] in ["broadcast", "3"]:
        log.info("Device: %s Bonding Mode: fault-tolerance (broadcast)", iface)
        return _parse_settings_bond_3(opts, iface, bond_def)
    elif opts["mode"] in ["802.3ad", "4"]:
        log.info(
            "Device: %s Bonding Mode: IEEE 802.3ad Dynamic link " "aggregation", iface
        )
        return _parse_settings_bond_4(opts, iface, bond_def)
    elif opts["mode"] in ["balance-tlb", "5"]:
        log.info("Device: %s Bonding Mode: transmit load balancing", iface)
        return _parse_settings_bond_5(opts, iface, bond_def)
    elif opts["mode"] in ["balance-alb", "6"]:
        log.info("Device: %s Bonding Mode: adaptive load balancing", iface)
        return _parse_settings_bond_6(opts, iface, bond_def)
    else:
        valid = [
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "balance-rr",
            "active-backup",
            "balance-xor",
            "broadcast",
            "802.3ad",
            "balance-tlb",
            "balance-alb",
        ]
        _raise_error_iface(iface, "mode", valid)


def _parse_settings_bond_0(opts, iface, bond_def):
    """
    Filters given options and outputs valid settings for bond0.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    """

    # balance-rr shares miimon settings with balance-xor
    bond = _parse_settings_bond_1(opts, iface, bond_def)

    bond.update({"mode": "0"})

    # ARP targets in n.n.n.n form
    valid = ["list of ips (up to 16)"]
    if "arp_ip_target" in opts:
        if isinstance(opts["arp_ip_target"], list):
            if 1 <= len(opts["arp_ip_target"]) <= 16:
                bond.update({"arp_ip_target": ""})
                for ip in opts["arp_ip_target"]:  # pylint: disable=C0103
                    if len(bond["arp_ip_target"]) > 0:
                        bond["arp_ip_target"] = bond["arp_ip_target"] + "," + ip
                    else:
                        bond["arp_ip_target"] = ip
            else:
                _raise_error_iface(iface, "arp_ip_target", valid)
        else:
            _raise_error_iface(iface, "arp_ip_target", valid)
    elif "miimon" not in opts:
        _raise_error_iface(iface, "arp_ip_target", valid)

    if "arp_interval" in opts:
        try:
            int(opts["arp_interval"])
            bond.update({"arp_interval": opts["arp_interval"]})
        except Exception:  # pylint: disable=broad-except
            _raise_error_iface(iface, "arp_interval", ["integer"])
    else:
        _log_default_iface(iface, "arp_interval", bond_def["arp_interval"])
        bond.update({"arp_interval": bond_def["arp_interval"]})

    return bond


def _parse_settings_bond_1(opts, iface, bond_def):

    """
    Filters given options and outputs valid settings for bond1.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    """
    bond = {"mode": "1"}

    for binding in ["miimon", "downdelay", "updelay"]:
        if binding in opts:
            try:
                int(opts[binding])
                bond.update({binding: opts[binding]})
            except Exception:  # pylint: disable=broad-except
                _raise_error_iface(iface, binding, ["integer"])
        else:
            _log_default_iface(iface, binding, bond_def[binding])
            bond.update({binding: bond_def[binding]})

    if "use_carrier" in opts:
        if opts["use_carrier"] in _CONFIG_TRUE:
            bond.update({"use_carrier": "1"})
        elif opts["use_carrier"] in _CONFIG_FALSE:
            bond.update({"use_carrier": "0"})
        else:
            valid = _CONFIG_TRUE + _CONFIG_FALSE
            _raise_error_iface(iface, "use_carrier", valid)
    else:
        _log_default_iface(iface, "use_carrier", bond_def["use_carrier"])
        bond.update({"use_carrier": bond_def["use_carrier"]})

    if "primary" in opts:
        bond.update({"primary": opts["primary"]})

    return bond


def _parse_settings_bond_2(opts, iface, bond_def):
    """
    Filters given options and outputs valid settings for bond2.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    """

    bond = {"mode": "2"}

    valid = ["list of ips (up to 16)"]
    if "arp_ip_target" in opts:
        if isinstance(opts["arp_ip_target"], list):
            if 1 <= len(opts["arp_ip_target"]) <= 16:
                bond.update({"arp_ip_target": ""})
                for ip in opts["arp_ip_target"]:  # pylint: disable=C0103
                    if len(bond["arp_ip_target"]) > 0:
                        bond["arp_ip_target"] = bond["arp_ip_target"] + "," + ip
                    else:
                        bond["arp_ip_target"] = ip
            else:
                _raise_error_iface(iface, "arp_ip_target", valid)
        else:
            _raise_error_iface(iface, "arp_ip_target", valid)
    else:
        _raise_error_iface(iface, "arp_ip_target", valid)

    if "arp_interval" in opts:
        try:
            int(opts["arp_interval"])
            bond.update({"arp_interval": opts["arp_interval"]})
        except Exception:  # pylint: disable=broad-except
            _raise_error_iface(iface, "arp_interval", ["integer"])
    else:
        _log_default_iface(iface, "arp_interval", bond_def["arp_interval"])
        bond.update({"arp_interval": bond_def["arp_interval"]})

    if "hashing-algorithm" in opts:
        valid = ["layer2", "layer2+3", "layer3+4"]
        if opts["hashing-algorithm"] in valid:
            bond.update({"xmit_hash_policy": opts["hashing-algorithm"]})
        else:
            _raise_error_iface(iface, "hashing-algorithm", valid)

    return bond


def _parse_settings_bond_3(opts, iface, bond_def):

    """
    Filters given options and outputs valid settings for bond3.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    """
    bond = {"mode": "3"}

    for binding in ["miimon", "downdelay", "updelay"]:
        if binding in opts:
            try:
                int(opts[binding])
                bond.update({binding: opts[binding]})
            except Exception:  # pylint: disable=broad-except
                _raise_error_iface(iface, binding, ["integer"])
        else:
            _log_default_iface(iface, binding, bond_def[binding])
            bond.update({binding: bond_def[binding]})

    if "use_carrier" in opts:
        if opts["use_carrier"] in _CONFIG_TRUE:
            bond.update({"use_carrier": "1"})
        elif opts["use_carrier"] in _CONFIG_FALSE:
            bond.update({"use_carrier": "0"})
        else:
            valid = _CONFIG_TRUE + _CONFIG_FALSE
            _raise_error_iface(iface, "use_carrier", valid)
    else:
        _log_default_iface(iface, "use_carrier", bond_def["use_carrier"])
        bond.update({"use_carrier": bond_def["use_carrier"]})

    return bond


def _parse_settings_bond_4(opts, iface, bond_def):
    """
    Filters given options and outputs valid settings for bond4.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    """

    bond = {"mode": "4"}

    for binding in ["miimon", "downdelay", "updelay", "lacp_rate", "ad_select"]:
        if binding in opts:
            if binding == "lacp_rate":
                if opts[binding] == "fast":
                    opts.update({binding: "1"})
                if opts[binding] == "slow":
                    opts.update({binding: "0"})
                valid = ["fast", "1", "slow", "0"]
            else:
                valid = ["integer"]
            try:
                int(opts[binding])
                bond.update({binding: opts[binding]})
            except Exception:  # pylint: disable=broad-except
                _raise_error_iface(iface, binding, valid)
        else:
            _log_default_iface(iface, binding, bond_def[binding])
            bond.update({binding: bond_def[binding]})

    if "use_carrier" in opts:
        if opts["use_carrier"] in _CONFIG_TRUE:
            bond.update({"use_carrier": "1"})
        elif opts["use_carrier"] in _CONFIG_FALSE:
            bond.update({"use_carrier": "0"})
        else:
            valid = _CONFIG_TRUE + _CONFIG_FALSE
            _raise_error_iface(iface, "use_carrier", valid)
    else:
        _log_default_iface(iface, "use_carrier", bond_def["use_carrier"])
        bond.update({"use_carrier": bond_def["use_carrier"]})

    if "hashing-algorithm" in opts:
        valid = ["layer2", "layer2+3", "layer3+4"]
        if opts["hashing-algorithm"] in valid:
            bond.update({"xmit_hash_policy": opts["hashing-algorithm"]})
        else:
            _raise_error_iface(iface, "hashing-algorithm", valid)

    return bond


def _parse_settings_bond_5(opts, iface, bond_def):

    """
    Filters given options and outputs valid settings for bond5.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    """
    bond = {"mode": "5"}

    for binding in ["miimon", "downdelay", "updelay"]:
        if binding in opts:
            try:
                int(opts[binding])
                bond.update({binding: opts[binding]})
            except Exception:  # pylint: disable=broad-except
                _raise_error_iface(iface, binding, ["integer"])
        else:
            _log_default_iface(iface, binding, bond_def[binding])
            bond.update({binding: bond_def[binding]})

    if "use_carrier" in opts:
        if opts["use_carrier"] in _CONFIG_TRUE:
            bond.update({"use_carrier": "1"})
        elif opts["use_carrier"] in _CONFIG_FALSE:
            bond.update({"use_carrier": "0"})
        else:
            valid = _CONFIG_TRUE + _CONFIG_FALSE
            _raise_error_iface(iface, "use_carrier", valid)
    else:
        _log_default_iface(iface, "use_carrier", bond_def["use_carrier"])
        bond.update({"use_carrier": bond_def["use_carrier"]})

    if "primary" in opts:
        bond.update({"primary": opts["primary"]})

    return bond


def _parse_settings_bond_6(opts, iface, bond_def):

    """
    Filters given options and outputs valid settings for bond6.
    If an option has a value that is not expected, this
    function will log what the Interface, Setting and what it was
    expecting.
    """
    bond = {"mode": "6"}

    for binding in ["miimon", "downdelay", "updelay"]:
        if binding in opts:
            try:
                int(opts[binding])
                bond.update({binding: opts[binding]})
            except Exception:  # pylint: disable=broad-except
                _raise_error_iface(iface, binding, ["integer"])
        else:
            _log_default_iface(iface, binding, bond_def[binding])
            bond.update({binding: bond_def[binding]})

    if "use_carrier" in opts:
        if opts["use_carrier"] in _CONFIG_TRUE:
            bond.update({"use_carrier": "1"})
        elif opts["use_carrier"] in _CONFIG_FALSE:
            bond.update({"use_carrier": "0"})
        else:
            valid = _CONFIG_TRUE + _CONFIG_FALSE
            _raise_error_iface(iface, "use_carrier", valid)
    else:
        _log_default_iface(iface, "use_carrier", bond_def["use_carrier"])
        bond.update({"use_carrier": bond_def["use_carrier"]})

    if "primary" in opts:
        bond.update({"primary": opts["primary"]})

    return bond


def _parse_settings_vlan(opts, iface):

    """
    Filters given options and outputs valid settings for a vlan
    """
    vlan = {}
    if "reorder_hdr" in opts:
        if opts["reorder_hdr"] in _CONFIG_TRUE + _CONFIG_FALSE:
            vlan.update({"reorder_hdr": opts["reorder_hdr"]})
        else:
            valid = _CONFIG_TRUE + _CONFIG_FALSE
            _raise_error_iface(iface, "reorder_hdr", valid)

    if "vlan_id" in opts:
        if opts["vlan_id"] > 0:
            vlan.update({"vlan_id": opts["vlan_id"]})
        else:
            _raise_error_iface(iface, "vlan_id", "Positive integer")

    if "phys_dev" in opts:
        if len(opts["phys_dev"]) > 0:
            vlan.update({"phys_dev": opts["phys_dev"]})
        else:
            _raise_error_iface(iface, "phys_dev", "Non-empty string")

    return vlan


def _parse_settings_eth(opts, iface_type, enabled, iface):
    """
    Filters given options and outputs valid settings for a
    network interface.
    """
    result = {"name": iface}
    if "proto" in opts:
        valid = ["none", "bootp", "dhcp"]
        if opts["proto"] in valid:
            result["proto"] = opts["proto"]
        else:
            _raise_error_iface(iface, opts["proto"], valid)

    if "dns" in opts:
        result["dns"] = opts["dns"]
        result["peerdns"] = "yes"

    if "mtu" in opts:
        try:
            result["mtu"] = int(opts["mtu"])
        except ValueError:
            _raise_error_iface(iface, "mtu", ["integer"])

    if "hwaddr" in opts and "macaddr" in opts:
        msg = "Cannot pass both hwaddr and macaddr. Must use either hwaddr or macaddr"
        log.error(msg)
        raise AttributeError(msg)

    if iface_type not in ["bridge"]:
        ethtool = _parse_ethtool_opts(opts, iface)
        if ethtool:
            result["ethtool"] = ethtool

    if iface_type == "slave":
        result["proto"] = "none"

    if iface_type == "bond":
        bonding = _parse_settings_bond(opts, iface)
        if bonding:
            result["bonding"] = bonding
            result["devtype"] = "Bond"

    if iface_type == "vlan":
        vlan = _parse_settings_vlan(opts, iface)
        if vlan:
            result["devtype"] = "Vlan"
            for opt in vlan:
                result[opt] = opts[opt]

    if iface_type not in ["bond", "vlan", "bridge", "ipip"]:
        auto_addr = False
        if "addr" in opts:
            if salt.utils.validate.net.mac(opts["addr"]):
                result["addr"] = opts["addr"]
            elif opts["addr"] == "auto":
                auto_addr = True
            elif opts["addr"] != "none":
                _raise_error_iface(
                    iface, opts["addr"], ["AA:BB:CC:DD:EE:FF", "auto", "none"]
                )
        else:
            auto_addr = True

        if auto_addr:
            # If interface type is slave for bond, not setting hwaddr
            if iface_type != "slave":
                ifaces = __salt__["network.interfaces"]()
                if iface in ifaces and "hwaddr" in ifaces[iface]:
                    result["addr"] = ifaces[iface]["hwaddr"]
    if iface_type == "eth":
        result["devtype"] = "Ethernet"
    if iface_type == "bridge":
        result["devtype"] = "Bridge"
        bypassfirewall = True
        valid = _CONFIG_TRUE + _CONFIG_FALSE
        for opt in ["bypassfirewall"]:
            if opt in opts:
                if opts[opt] in _CONFIG_TRUE:
                    bypassfirewall = True
                elif opts[opt] in _CONFIG_FALSE:
                    bypassfirewall = False
                else:
                    _raise_error_iface(iface, opts[opt], valid)

        bridgectls = [
            "net.bridge.bridge-nf-call-ip6tables",
            "net.bridge.bridge-nf-call-iptables",
            "net.bridge.bridge-nf-call-arptables",
        ]

        if bypassfirewall:
            sysctl_value = 0
        else:
            sysctl_value = 1

        for sysctl in bridgectls:
            try:
                __salt__["sysctl.persist"](sysctl, sysctl_value)
            except CommandExecutionError:
                log.warning("Failed to set sysctl: %s", sysctl)

    else:
        if "bridge" in opts:
            result["bridge"] = opts["bridge"]

    if iface_type == "ipip":
        result["devtype"] = "IPIP"
        for opt in ["my_inner_ipaddr", "my_outer_ipaddr"]:
            if opt not in opts:
                _raise_error_iface(iface, opts[opt], ["1.2.3.4"])
            else:
                result[opt] = opts[opt]
    if iface_type == "ib":
        result["devtype"] = "InfiniBand"

    if "prefix" in opts:
        if "netmask" in opts:
            msg = "Cannot use prefix and netmask together"
            log.error(msg)
            raise AttributeError(msg)
        result["prefix"] = opts["prefix"]
    elif "netmask" in opts:
        result["netmask"] = opts["netmask"]

    for opt in [
        "ipaddr",
        "master",
        "srcaddr",
        "delay",
        "domain",
        "gateway",
        "uuid",
        "nickname",
        "zone",
    ]:
        if opt in opts:
            result[opt] = opts[opt]

    for opt in ["ipv6addr", "ipv6gateway"]:
        if opt in opts:
            result[opt] = opts[opt]

    if "ipaddrs" in opts:
        result["ipaddrs"] = []
        for opt in opts["ipaddrs"]:
            if salt.utils.validate.net.ipv4_addr(opt):
                ip, prefix = [i.strip() for i in opt.split("/")]
                result["ipaddrs"].append({"ipaddr": ip, "prefix": prefix})
            else:
                msg = "ipv4 CIDR is invalid"
                log.error(msg)
                raise AttributeError(msg)

    if "ipv6addrs" in opts:
        for opt in opts["ipv6addrs"]:
            if not salt.utils.validate.net.ipv6_addr(opt):
                msg = "ipv6 CIDR is invalid"
                log.error(msg)
                raise AttributeError(msg)
            result["ipv6addrs"] = opts["ipv6addrs"]

    if "enable_ipv6" in opts:
        result["enable_ipv6"] = opts["enable_ipv6"]

    valid = _CONFIG_TRUE + _CONFIG_FALSE
    for opt in [
        "onparent",
        "peerdns",
        "peerroutes",
        "slave",
        "vlan",
        "defroute",
        "stp",
        "ipv6_peerdns",
        "ipv6_defroute",
        "ipv6_peerroutes",
        "ipv6_autoconf",
        "ipv4_failure_fatal",
        "dhcpv6c",
    ]:
        if opt in opts:
            if opts[opt] in _CONFIG_TRUE:
                result[opt] = "yes"
            elif opts[opt] in _CONFIG_FALSE:
                result[opt] = "no"
            else:
                _raise_error_iface(iface, opts[opt], valid)

    if "onboot" in opts:
        log.warning(
            "The 'onboot' option is controlled by the 'enabled' option. "
            "Interface: %s Enabled: %s",
            iface,
            enabled,
        )

    if enabled:
        result["onboot"] = "yes"
    else:
        result["onboot"] = "no"

    # If the interface is defined then we want to always take
    # control away from non-root users; unless the administrator
    # wants to allow non-root users to control the device.
    if "userctl" in opts:
        if opts["userctl"] in _CONFIG_TRUE:
            result["userctl"] = "yes"
        elif opts["userctl"] in _CONFIG_FALSE:
            result["userctl"] = "no"
        else:
            _raise_error_iface(iface, opts["userctl"], valid)
    else:
        result["userctl"] = "no"

    # This vlan is in opts, and should be only used in range interface
    # will affect jinja template for interface generating
    if "vlan" in opts:
        if opts["vlan"] in _CONFIG_TRUE:
            result["vlan"] = "yes"
        elif opts["vlan"] in _CONFIG_FALSE:
            result["vlan"] = "no"
        else:
            _raise_error_iface(iface, opts["vlan"], valid)

    if "arpcheck" in opts:
        if opts["arpcheck"] in _CONFIG_FALSE:
            result["arpcheck"] = "no"

    if "ipaddr_start" in opts:
        result["ipaddr_start"] = opts["ipaddr_start"]

    if "ipaddr_end" in opts:
        result["ipaddr_end"] = opts["ipaddr_end"]

    if "clonenum_start" in opts:
        result["clonenum_start"] = opts["clonenum_start"]

    if "hwaddr" in opts:
        result["hwaddr"] = opts["hwaddr"]

    if "macaddr" in opts:
        result["macaddr"] = opts["macaddr"]

    # If NetworkManager is available, we can control whether we use
    # it or not
    if "nm_controlled" in opts:
        if opts["nm_controlled"] in _CONFIG_TRUE:
            result["nm_controlled"] = "yes"
        elif opts["nm_controlled"] in _CONFIG_FALSE:
            result["nm_controlled"] = "no"
        else:
            _raise_error_iface(iface, opts["nm_controlled"], valid)
    else:
        result["nm_controlled"] = "no"

    return result


def _parse_routes(iface, opts):
    """
    Filters given options and outputs valid settings for
    the route settings file.
    """
    # Normalize keys
    opts = dict((k.lower(), v) for (k, v) in six.iteritems(opts))
    result = {}
    if "routes" not in opts:
        _raise_error_routes(iface, "routes", "List of routes")

    for opt in opts:
        result[opt] = opts[opt]

    return result


def _parse_network_settings(opts, current):
    """
    Filters given options and outputs valid settings for
    the global network settings file.
    """
    # Normalize keys
    opts = dict((k.lower(), v) for (k, v) in six.iteritems(opts))
    current = dict((k.lower(), v) for (k, v) in six.iteritems(current))

    # Check for supported parameters
    retain_settings = opts.get("retain_settings", False)
    result = current if retain_settings else {}

    # Default quote type is an empty string, which will not quote values
    quote_type = ""

    valid = _CONFIG_TRUE + _CONFIG_FALSE
    if "enabled" not in opts:
        try:
            opts["networking"] = current["networking"]
            # If networking option is quoted, use its quote type
            quote_type = salt.utils.stringutils.is_quoted(opts["networking"])
            _log_default_network("networking", current["networking"])
        except ValueError:
            _raise_error_network("networking", valid)
    else:
        opts["networking"] = opts["enabled"]

    true_val = "{0}yes{0}".format(quote_type)
    false_val = "{0}no{0}".format(quote_type)

    networking = salt.utils.stringutils.dequote(opts["networking"])
    if networking in valid:
        if networking in _CONFIG_TRUE:
            result["networking"] = true_val
        elif networking in _CONFIG_FALSE:
            result["networking"] = false_val
    else:
        _raise_error_network("networking", valid)

    if "hostname" not in opts:
        try:
            opts["hostname"] = current["hostname"]
            _log_default_network("hostname", current["hostname"])
        except Exception:  # pylint: disable=broad-except
            _raise_error_network("hostname", ["server1.example.com"])

    if opts["hostname"]:
        result["hostname"] = "{1}{0}{1}".format(
            salt.utils.stringutils.dequote(opts["hostname"]), quote_type
        )
    else:
        _raise_error_network("hostname", ["server1.example.com"])

    if "nozeroconf" in opts:
        nozeroconf = salt.utils.stringutils.dequote(opts["nozeroconf"])
        if nozeroconf in valid:
            if nozeroconf in _CONFIG_TRUE:
                result["nozeroconf"] = true_val
            elif nozeroconf in _CONFIG_FALSE:
                result["nozeroconf"] = false_val
        else:
            _raise_error_network("nozeroconf", valid)

    for opt in opts:
        if opt not in ["networking", "hostname", "nozeroconf"]:
            result[opt] = "{1}{0}{1}".format(
                salt.utils.stringutils.dequote(opts[opt]), quote_type
            )
    return result


def _raise_error_iface(iface, option, expected):
    """
    Log and raise an error with a logical formatted message.
    """
    msg = _error_msg_iface(iface, option, expected)
    log.error(msg)
    raise AttributeError(msg)


def _raise_error_network(option, expected):
    """
    Log and raise an error with a logical formatted message.
    """
    msg = _error_msg_network(option, expected)
    log.error(msg)
    raise AttributeError(msg)


def _raise_error_routes(iface, option, expected):
    """
    Log and raise an error with a logical formatted message.
    """
    msg = _error_msg_routes(iface, option, expected)
    log.error(msg)
    raise AttributeError(msg)


def _read_file(path):
    """
    Reads and returns the contents of a file
    """
    try:
        with salt.utils.files.fopen(path, "rb") as rfh:
            lines = salt.utils.stringutils.to_unicode(rfh.read()).splitlines()
            try:
                lines.remove("")
            except ValueError:
                pass
            return lines
    except Exception:  # pylint: disable=broad-except
        return []  # Return empty list for type consistency


def _write_file_iface(iface, data, folder, pattern):
    """
    Writes a file to disk
    """
    filename = os.path.join(folder, pattern.format(iface))
    if not os.path.exists(folder):
        msg = "{0} cannot be written. {1} does not exist"
        msg = msg.format(filename, folder)
        log.error(msg)
        raise AttributeError(msg)
    with salt.utils.files.fopen(filename, "w") as fp_:
        fp_.write(salt.utils.stringutils.to_str(data))


def _write_file_network(data, filename):
    """
    Writes a file to disk
    """
    with salt.utils.files.fopen(filename, "w") as fp_:
        fp_.write(salt.utils.stringutils.to_str(data))


def _read_temp(data):
    lines = data.splitlines()
    try:  # Discard newlines if they exist
        lines.remove("")
    except ValueError:
        pass
    return lines


def build_bond(iface, **settings):
    """
    Create a bond script in /etc/modprobe.d with the passed settings
    and load the bonding kernel module.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_bond bond0 mode=balance-alb
    """
    rh_major = __grains__["osrelease"][:1]

    opts = _parse_settings_bond(settings, iface)
    try:
        template = JINJA.get_template("conf.jinja")
    except jinja2.exceptions.TemplateNotFound:
        log.error("Could not load template conf.jinja")
        return ""
    data = template.render({"name": iface, "bonding": opts})
    _write_file_iface(iface, data, _RH_NETWORK_CONF_FILES, "{0}.conf".format(iface))
    path = os.path.join(_RH_NETWORK_CONF_FILES, "{0}.conf".format(iface))
    if rh_major == "5":
        __salt__["cmd.run"](
            'sed -i -e "/^alias\\s{0}.*/d" /etc/modprobe.conf'.format(iface),
            python_shell=False,
        )
        __salt__["cmd.run"](
            'sed -i -e "/^options\\s{0}.*/d" /etc/modprobe.conf'.format(iface),
            python_shell=False,
        )
        __salt__["file.append"]("/etc/modprobe.conf", path)
    __salt__["kmod.load"]("bonding")

    if settings["test"]:
        return _read_temp(data)

    return _read_file(path)


def build_interface(iface, iface_type, enabled, **settings):
    """
    Build an interface script for a network interface.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_interface eth0 eth <settings>
    """
    if __grains__["os"] == "Fedora":
        if __grains__["osmajorrelease"] >= 18:
            rh_major = "7"
        else:
            rh_major = "6"
    elif __grains__["os"] == "Amazon":
        # TODO: Is there a better formula for this? -W. Werner, 2019-05-30
        # If not, it will need to be updated whenever Amazon releases
        # Amazon Linux 3
        if __grains__["osmajorrelease"] == 2:
            rh_major = "7"
        else:
            rh_major = "6"
    else:
        rh_major = __grains__["osrelease"][:1]

    iface_type = iface_type.lower()

    if iface_type not in _IFACE_TYPES:
        _raise_error_iface(iface, iface_type, _IFACE_TYPES)

    if iface_type == "slave":
        settings["slave"] = "yes"
        if "master" not in settings:
            msg = "master is a required setting for slave interfaces"
            log.error(msg)
            raise AttributeError(msg)

    if iface_type == "vlan":
        settings["vlan"] = "yes"

    if iface_type == "bridge":
        __salt__["pkg.install"]("bridge-utils")

    if iface_type in ["eth", "bond", "bridge", "slave", "vlan", "ipip", "ib", "alias"]:
        opts = _parse_settings_eth(settings, iface_type, enabled, iface)
        try:
            template = JINJA.get_template("rh{0}_eth.jinja".format(rh_major))
        except jinja2.exceptions.TemplateNotFound:
            log.error("Could not load template rh%s_eth.jinja", rh_major)
            return ""
        ifcfg = template.render(opts)

    if "test" in settings and settings["test"]:
        return _read_temp(ifcfg)

    _write_file_iface(iface, ifcfg, _RH_NETWORK_SCRIPT_DIR, "ifcfg-{0}")
    path = os.path.join(_RH_NETWORK_SCRIPT_DIR, "ifcfg-{0}".format(iface))

    return _read_file(path)


def build_routes(iface, **settings):
    """
    Build a route script for a network interface.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_routes eth0 <settings>
    """

    template = "rh6_route_eth.jinja"
    try:
        if int(__grains__["osrelease"][0]) < 6:
            template = "route_eth.jinja"
    except ValueError:
        pass
    log.debug("Template name: %s", template)

    opts = _parse_routes(iface, settings)
    log.debug("Opts: \n %s", opts)
    try:
        template = JINJA.get_template(template)
    except jinja2.exceptions.TemplateNotFound:
        log.error("Could not load template %s", template)
        return ""
    opts6 = []
    opts4 = []
    for route in opts["routes"]:
        ipaddr = route["ipaddr"]
        if salt.utils.validate.net.ipv6_addr(ipaddr):
            opts6.append(route)
        else:
            opts4.append(route)
    log.debug("IPv4 routes:\n%s", opts4)
    log.debug("IPv6 routes:\n%s", opts6)

    routecfg = template.render(routes=opts4, iface=iface)
    routecfg6 = template.render(routes=opts6, iface=iface)

    if settings["test"]:
        routes = _read_temp(routecfg)
        routes.extend(_read_temp(routecfg6))
        return routes

    _write_file_iface(iface, routecfg, _RH_NETWORK_SCRIPT_DIR, "route-{0}")
    _write_file_iface(iface, routecfg6, _RH_NETWORK_SCRIPT_DIR, "route6-{0}")

    path = os.path.join(_RH_NETWORK_SCRIPT_DIR, "route-{0}".format(iface))
    path6 = os.path.join(_RH_NETWORK_SCRIPT_DIR, "route6-{0}".format(iface))

    routes = _read_file(path)
    routes.extend(_read_file(path6))
    return routes


def down(iface, iface_type):
    """
    Shutdown a network interface

    CLI Example:

    .. code-block:: bash

        salt '*' ip.down eth0
    """
    # Slave devices are controlled by the master.
    if iface_type not in ["slave"]:
        return __salt__["cmd.run"]("ifdown {0}".format(iface))
    return None


def get_bond(iface):
    """
    Return the content of a bond script

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_bond bond0
    """
    path = os.path.join(_RH_NETWORK_CONF_FILES, "{0}.conf".format(iface))
    return _read_file(path)


def get_interface(iface):
    """
    Return the contents of an interface script

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_interface eth0
    """
    path = os.path.join(_RH_NETWORK_SCRIPT_DIR, "ifcfg-{0}".format(iface))
    return _read_file(path)


def up(iface, iface_type):  # pylint: disable=C0103
    """
    Start up a network interface

    CLI Example:

    .. code-block:: bash

        salt '*' ip.up eth0
    """
    # Slave devices are controlled by the master.
    if iface_type not in ["slave"]:
        return __salt__["cmd.run"]("ifup {0}".format(iface))
    return None


def get_routes(iface):
    """
    Return the contents of the interface routes script.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_routes eth0
    """
    path = os.path.join(_RH_NETWORK_SCRIPT_DIR, "route-{0}".format(iface))
    path6 = os.path.join(_RH_NETWORK_SCRIPT_DIR, "route6-{0}".format(iface))
    routes = _read_file(path)
    routes.extend(_read_file(path6))
    return routes


def get_network_settings():
    """
    Return the contents of the global network script.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_network_settings
    """
    return _read_file(_RH_NETWORK_FILE)


def apply_network_settings(**settings):
    """
    Apply global network configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.apply_network_settings
    """
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
        res = __salt__["service.restart"]("network")

    return hostname_res and res


def build_network_settings(**settings):
    """
    Build the global network script.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_network_settings <settings>
    """
    # Read current configuration and store default values
    current_network_settings = _parse_rh_config(_RH_NETWORK_FILE)

    # Build settings
    opts = _parse_network_settings(settings, current_network_settings)
    try:
        template = JINJA.get_template("network.jinja")
    except jinja2.exceptions.TemplateNotFound:
        log.error("Could not load template network.jinja")
        return ""
    network = template.render(opts)

    if settings["test"]:
        return _read_temp(network)

    # Write settings
    _write_file_network(network, _RH_NETWORK_FILE)

    return _read_file(_RH_NETWORK_FILE)
