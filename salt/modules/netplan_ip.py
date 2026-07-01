"""
The networking module for Debian-family distributions that use netplan
(Ubuntu 18.04+, and Debian systems where netplan is the active renderer).

This is the ``ip`` execution-module provider behind :py:func:`network.managed
<salt.states.network.managed>` on netplan systems. The legacy
:py:mod:`debian_ip <salt.modules.debian_ip>` provider writes
``/etc/network/interfaces`` (ifupdown), which netplan ignores -- see
issue #62219. This provider instead generates per-interface netplan YAML under
``/etc/netplan/`` and applies it with ``netplan``.

.. versionadded:: 3006.27

.. note::
    netplan is the source of truth here, so only the subset of the
    ``network.managed`` schema that maps cleanly onto netplan v2 is supported
    (addresses, gateway, nameservers, mtu, dhcp4/dhcp6). ifupdown-only options
    such as ethtool offload settings and up/down hook scripts have no netplan
    equivalent and raise an informative error rather than being silently
    dropped.
"""

import logging
import os

import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
import salt.utils.yaml
from salt.exceptions import CommandExecutionError

try:
    import ipaddress
except ImportError:  # pragma: no cover
    ipaddress = None

log = logging.getLogger(__name__)

__virtualname__ = "ip"

_NETPLAN_DIR = "/etc/netplan"
# Higher numeric prefix than cloud-init's 50-cloud-init.yaml so salt-managed
# config wins when both define the same interface; one file per interface keeps
# get_interface/build_interface diffs isolated.
_SALT_PREFIX = "90-salt"

# Map the network.managed interface type onto the netplan v2 top-level key.
_NETPLAN_SECTION = {
    "eth": "ethernets",
    "bond": "bonds",
    "slave": "ethernets",
    "vlan": "vlans",
    "bridge": "bridges",
}

# ifupdown/ethtool-era settings that do not map onto netplan v2.
_UNSUPPORTED = (
    "up_cmds",
    "down_cmds",
    "pre_up_cmds",
    "post_up_cmds",
    "pre_down_cmds",
    "post_down_cmds",
    "ethtool",
)


def __virtual__():
    """
    Confine to Debian-family systems where netplan is the active renderer.

    On a Debian-family box with netplan present this returns the ``ip``
    virtualname; ``debian_ip`` defers in that case so exactly one provider
    claims ``ip``.
    """
    if __grains__.get("os_family") != "Debian":
        return (False, "netplan_ip: only applicable to the Debian os_family")
    if not netplan_active():
        return (
            False,
            "netplan_ip: netplan is not the active renderer on this system",
        )
    return __virtualname__


def netplan_active():
    """
    Return True if netplan appears to be the active network renderer: the
    ``netplan`` command is available and ``/etc/netplan`` exists.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.netplan_active
    """
    return bool(salt.utils.path.which("netplan")) and os.path.isdir(_NETPLAN_DIR)


def _salt_file(iface):
    """Path of the salt-managed netplan file for ``iface``."""
    return os.path.join(_NETPLAN_DIR, f"{_SALT_PREFIX}-{iface}.yaml")


def _renderer():
    """
    Best-effort detection of the active netplan renderer, defaulting to
    ``networkd``. Honors a ``renderer:`` already declared in any netplan file.
    """
    try:
        for fname in sorted(os.listdir(_NETPLAN_DIR)):
            if not fname.endswith((".yaml", ".yml")):
                continue
            with salt.utils.files.fopen(os.path.join(_NETPLAN_DIR, fname)) as fp_:
                data = salt.utils.yaml.safe_load(fp_) or {}
            renderer = (data.get("network") or {}).get("renderer")
            if renderer:
                return renderer
    except (OSError, salt.utils.yaml.YAMLError):
        pass
    return "networkd"


def _to_cidr(addr, netmask):
    """Combine an address + dotted/prefix netmask into ``addr/prefix``."""
    if "/" in str(addr):
        return addr
    if ipaddress is None:
        raise CommandExecutionError("ipaddress module unavailable; cannot build CIDR")
    try:
        return str(ipaddress.ip_interface(f"{addr}/{netmask}").with_prefixlen)
    except ValueError as exc:
        raise CommandExecutionError(f"Invalid address/netmask {addr}/{netmask}: {exc}")


def _listify(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    # space- or comma-separated string
    return [v for v in str(value).replace(",", " ").split() if v]


def _check_unsupported(settings):
    bad = sorted(k for k in _UNSUPPORTED if settings.get(k))
    if bad:
        raise CommandExecutionError(
            "netplan does not support these network.managed options: "
            "{}. Manage them outside network.managed on netplan systems.".format(
                ", ".join(bad)
            )
        )


# salt bond option -> netplan bonds.parameters key
_BOND_PARAM_MAP = {
    "mode": "mode",
    "miimon": "mii-monitor-interval",
    "lacp_rate": "lacp-rate",
    "xmit_hash_policy": "transmit-hash-policy",
    "downdelay": "down-delay",
    "updelay": "up-delay",
    "arp_interval": "arp-interval",
    "primary": "primary",
}

# salt bridge option -> netplan bridges.parameters key
_BRIDGE_PARAM_MAP = {
    "fd": "forward-delay",
    "forward_delay": "forward-delay",
    "ageing": "ageing-time",
    "maxage": "max-age",
    "hello": "hello-time",
    "priority": "priority",
}


def _as_bool(value):
    """Coerce a salt-style truthy setting into a bool for netplan YAML."""
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("true", "yes", "on", "1")


def _bond_parameters(settings):
    params = {}
    for salt_key, np_key in _BOND_PARAM_MAP.items():
        if settings.get(salt_key) is not None:
            params[np_key] = settings[salt_key]
    return params


def _bridge_parameters(settings):
    params = {}
    if settings.get("stp") is not None:
        params["stp"] = _as_bool(settings["stp"])
    for salt_key, np_key in _BRIDGE_PARAM_MAP.items():
        if settings.get(salt_key) is not None:
            params[np_key] = settings[salt_key]
    return params


def _vlan_id_link(iface, settings):
    """
    Resolve a vlan's tag id and parent link from explicit settings, falling
    back to parsing a dotted interface name (e.g. ``eth0.100``).
    """
    vid = settings.get("vlan_id") or settings.get("id")
    link = (
        settings.get("vlan-raw-device")
        or settings.get("vlan_raw_device")
        or settings.get("parent")
        or settings.get("link")
    )
    if (vid is None or link is None) and "." in iface:
        base, _, tag = iface.rpartition(".")
        if link is None:
            link = base
        if vid is None and tag.isdigit():
            vid = tag
    if vid is not None and str(vid).isdigit():
        vid = int(vid)
    return vid, link


def _interface_dict(iface, iface_type, enabled, settings):
    """
    Translate the network.managed settings for a single interface into the
    netplan v2 per-interface mapping.
    """
    _check_unsupported(settings)
    sec = {}

    proto = str(settings.get("proto", "static")).lower()
    addresses = []
    if str(settings.get("ipaddr", "")) and settings.get("netmask"):
        addresses.append(_to_cidr(settings["ipaddr"], settings["netmask"]))
    for addr in _listify(settings.get("ipaddrs") or settings.get("addresses")):
        addresses.append(
            addr if "/" in addr else _to_cidr(addr, settings.get("netmask"))
        )

    sec["dhcp4"] = proto in ("dhcp", "dhcp4")

    ipv6proto = str(settings.get("ipv6proto", "")).lower()
    if ipv6proto in ("dhcp", "dhcp6"):
        sec["dhcp6"] = True
    if str(settings.get("ipv6ipaddr", "")) and settings.get("ipv6netmask"):
        addresses.append(_to_cidr(settings["ipv6ipaddr"], settings["ipv6netmask"]))
    for addr in _listify(settings.get("ipv6addrs")):
        addresses.append(addr)

    if addresses:
        sec["addresses"] = addresses

    routes = []
    if settings.get("gateway"):
        routes.append({"to": "default", "via": str(settings["gateway"])})
    if settings.get("ipv6gateway"):
        routes.append({"to": "default", "via": str(settings["ipv6gateway"])})
    if routes:
        sec["routes"] = routes

    nameservers = _listify(settings.get("dns") or settings.get("nameservers"))
    if nameservers:
        sec["nameservers"] = {"addresses": nameservers}

    if settings.get("mtu"):
        sec["mtu"] = int(settings["mtu"])

    # Type-specific keys. (eth/slave need nothing beyond the common section; a
    # slave is referenced from its bond's ``interfaces`` list.)
    itype = iface_type.lower()
    if itype == "bond":
        interfaces = _listify(settings.get("slaves") or settings.get("interfaces"))
        if interfaces:
            sec["interfaces"] = interfaces
        params = _bond_parameters(settings)
        if params:
            sec["parameters"] = params
    elif itype == "bridge":
        interfaces = _listify(
            settings.get("ports")
            or settings.get("bridge_ports")
            or settings.get("interfaces")
        )
        if interfaces:
            sec["interfaces"] = interfaces
        params = _bridge_parameters(settings)
        if params:
            sec["parameters"] = params
    elif itype == "vlan":
        vid, link = _vlan_id_link(iface, settings)
        if vid is not None:
            sec["id"] = vid
        if link:
            sec["link"] = link

    return sec


def _member_interfaces(iface, iface_type, settings):
    """
    Physical interfaces a bond/bridge/vlan references (slaves, ports, vlan
    parent). netplan rejects config that references an interface it cannot
    resolve, so these must be declared in the document too.
    """
    itype = iface_type.lower()
    if itype == "bond":
        return _listify(settings.get("slaves") or settings.get("interfaces"))
    if itype == "bridge":
        return _listify(
            settings.get("ports")
            or settings.get("bridge_ports")
            or settings.get("interfaces")
        )
    if itype == "vlan":
        _, link = _vlan_id_link(iface, settings)
        return [link] if link else []
    return []


def _document(iface, iface_type, enabled, settings):
    """Full netplan document (dict) for one managed interface."""
    section = _NETPLAN_SECTION.get(iface_type.lower())
    if section is None:
        raise CommandExecutionError(
            f"netplan_ip: unsupported interface type '{iface_type}'"
        )
    net = {
        "version": 2,
        "renderer": _renderer(),
        section: {iface: _interface_dict(iface, iface_type, enabled, settings)},
    }
    # Declare member/parent NICs (bond slaves, bridge ports, vlan parent) as
    # bare ethernets so `netplan generate` can resolve the references. setdefault
    # leaves any separately-managed definition of the same NIC intact on merge.
    members = _member_interfaces(iface, iface_type, settings)
    if members:
        ethernets = net.setdefault("ethernets", {})
        for member in members:
            if member != iface:
                ethernets.setdefault(member, {})
    return {"network": net}


def _dump_lines(doc):
    """Serialize a netplan document to a deterministic list of lines."""
    text = salt.utils.yaml.safe_dump(doc, default_flow_style=False, sort_keys=True)
    return [line + "\n" for line in text.splitlines()]


def build_interface(iface, iface_type, enabled, **settings):
    """
    Build (and, unless ``test=True``, write) the netplan configuration for a
    network interface. Returns the rendered YAML as a list of lines.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_interface eth0 eth True ipaddr=10.0.0.5 netmask=255.255.255.0
    """
    iface_type = iface_type.lower()
    if iface_type not in _NETPLAN_SECTION:
        raise CommandExecutionError(
            "netplan_ip supports interface types {}; got '{}'".format(
                ", ".join(sorted(_NETPLAN_SECTION)), iface_type
            )
        )

    doc = _document(iface, iface_type, enabled, settings)
    lines = _dump_lines(doc)

    if settings.get("test"):
        return lines

    path = _salt_file(iface)
    with salt.utils.files.fopen(path, "w") as fp_:
        fp_.write(salt.utils.stringutils.to_str("".join(lines)))
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover
        log.debug("Could not chmod %s to 0600", path)
    return lines


def get_interface(iface):
    """
    Return the salt-managed netplan configuration for ``iface`` as a list of
    lines, or an empty list if salt does not manage it yet.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_interface eth0
    """
    path = _salt_file(iface)
    if not os.path.isfile(path):
        return []
    with salt.utils.files.fopen(path) as fp_:
        return [salt.utils.stringutils.to_unicode(line) for line in fp_.readlines()]


def build_routes(iface, **settings):
    """
    Build the netplan routes for ``iface``. On netplan, routes live inside the
    interface definition, so this folds the provided routes into the
    salt-managed interface document. Returns the rendered routes as lines.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_routes eth0 routes='[{"name": "n", "ipaddr": "10.1.0.0", "netmask": "255.255.0.0", "gateway": "10.0.0.1"}]'
    """
    routes = []
    for route in settings.get("routes", []):
        dest = route.get("ipaddr") or route.get("destination") or route.get("name")
        if dest and dest not in ("default", "0.0.0.0"):
            netmask = route.get("netmask")
            dest = dest if "/" in str(dest) or not netmask else _to_cidr(dest, netmask)
        else:
            dest = "default"
        entry = {"to": dest}
        if route.get("gateway"):
            entry["via"] = route["gateway"]
        routes.append(entry)
    return _dump_lines({"routes": routes}) if routes else []


def get_routes(iface):
    """
    Return the routes currently declared for ``iface`` in the salt-managed
    netplan file, as a list of lines.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_routes eth0
    """
    path = _salt_file(iface)
    if not os.path.isfile(path):
        return []
    with salt.utils.files.fopen(path) as fp_:
        data = salt.utils.yaml.safe_load(fp_) or {}
    for section in (data.get("network") or {}).values():
        if isinstance(section, dict) and iface in section:
            routes = section[iface].get("routes")
            if routes:
                return _dump_lines({"routes": routes})
    return []


def get_network_settings():
    """
    netplan has no separate global network-settings file (the per-interface
    YAML carries everything). Returns an empty list.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_network_settings
    """
    return []


def build_network_settings(**settings):
    """
    No-op on netplan: there is no global ``/etc/network`` equivalent; settings
    are expressed per interface. Returns an empty list.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_network_settings
    """
    return []


def apply_network_settings(**settings):
    """
    Apply the generated netplan configuration with ``netplan apply``.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.apply_network_settings
    """
    if settings.get("test"):
        return True
    netplan = salt.utils.path.which("netplan")
    if not netplan:
        raise CommandExecutionError("netplan command not found")
    # generate validates+merges before apply so a bad file fails loudly.
    gen = __salt__["cmd.run_all"]([netplan, "generate"], python_shell=False)
    if gen["retcode"] != 0:
        raise CommandExecutionError(
            "netplan generate failed: {}".format(gen.get("stderr") or gen.get("stdout"))
        )
    out = __salt__["cmd.run_all"]([netplan, "apply"], python_shell=False)
    if out["retcode"] != 0:
        raise CommandExecutionError(
            "netplan apply failed: {}".format(out.get("stderr") or out.get("stdout"))
        )
    return True


def down(iface, iface_type=None):
    """
    Bring ``iface`` down with ``ip link set <iface> down``.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.down eth0
    """
    return __salt__["cmd.run"](
        ["ip", "link", "set", "dev", iface, "down"], python_shell=False
    )


def up(iface, iface_type=None):  # pylint: disable=invalid-name
    """
    Apply the netplan configuration (which brings managed interfaces up).

    CLI Example:

    .. code-block:: bash

        salt '*' ip.up eth0
    """
    return apply_network_settings()
