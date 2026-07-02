"""
The networking module for RedHat-family distributions managed by
NetworkManager (RHEL/CentOS/Alma/Rocky 8+, Fedora).

This is the ``ip`` execution-module provider behind :py:func:`network.managed
<salt.states.network.managed>` on NetworkManager systems. The legacy
:py:mod:`rh_ip <salt.modules.rh_ip>` provider writes
``/etc/sysconfig/network-scripts/ifcfg-*`` and brings interfaces up with
``ifup``/``ifdown`` from the ``network-scripts`` package. On EL8+ that package
is not installed by default (and is removed entirely on EL10), so ``rh_ip``
fails with ``No such file or directory: 'ifdown'`` and no interface is
configured -- see issues #54791, #68252 and #62844.

This provider instead writes NetworkManager keyfiles under
``/etc/NetworkManager/system-connections/`` and applies them with ``nmcli``,
which is the supported way to manage networking on modern RedHat systems.

.. versionadded:: 3006.28

.. note::
    NetworkManager is the source of truth here, so only the subset of the
    ``network.managed`` schema that maps cleanly onto NM connection keyfiles is
    supported (addresses, gateway, nameservers, mtu, dhcp, bond/vlan/bridge).
    ifcfg/ifupdown-only options such as ethtool offload settings and up/down
    hook scripts have no keyfile equivalent and raise an informative error
    rather than being silently dropped.
"""

import logging
import os
import uuid

import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

try:
    import ipaddress
except ImportError:  # pragma: no cover
    ipaddress = None

log = logging.getLogger(__name__)

__virtualname__ = "ip"

_NM_DIR = "/etc/NetworkManager/system-connections"
# Deterministic namespace so a given interface always maps to the same
# connection uuid; that keeps build_interface output byte-identical to the
# keyfile NetworkManager reads back, so the state's diff is stable/idempotent.
_UUID_NS = uuid.UUID("6f7a2c1e-3b4d-5e6f-8a9b-0c1d2e3f4a5b")

# network.managed interface type -> NetworkManager connection type.
_NM_TYPE = {
    "eth": "ethernet",
    "slave": "ethernet",
    "bond": "bond",
    "vlan": "vlan",
    "bridge": "bridge",
}

# ifcfg/ethtool-era settings with no keyfile equivalent.
_UNSUPPORTED = (
    "up_cmds",
    "down_cmds",
    "pre_up_cmds",
    "post_up_cmds",
    "pre_down_cmds",
    "post_down_cmds",
    "ethtool",
)

# salt bond option -> NM [bond] key. NM stores bond options with the kernel
# option names, same as the sysfs bonding interface.
_BOND_OPT_MAP = {
    "mode": "mode",
    "miimon": "miimon",
    "lacp_rate": "lacp_rate",
    "xmit_hash_policy": "xmit_hash_policy",
    "downdelay": "downdelay",
    "updelay": "updelay",
    "arp_interval": "arp_interval",
    "arp_ip_target": "arp_ip_target",
    "primary": "primary",
    "use_carrier": "use_carrier",
}

# salt bridge option -> NM [bridge] key.
_BRIDGE_OPT_MAP = {
    "fd": "forward-delay",
    "forward_delay": "forward-delay",
    "ageing": "ageing-time",
    "maxage": "max-age",
    "hello": "hello-time",
    "priority": "priority",
}


def __virtual__():
    """
    Confine to RedHat-family systems where NetworkManager is the active network
    service and the legacy ``ifup``/``ifdown`` tooling is unavailable.

    That combination is exactly where :py:mod:`rh_ip` breaks, so ``rh_ip``
    defers under the same condition and precisely one provider claims ``ip``.
    Hosts that still have ``network-scripts`` installed keep the legacy
    ``rh_ip`` behavior untouched.
    """
    if __grains__.get("os_family") != "RedHat":
        return (False, "nm_ip: only applicable to the RedHat os_family")
    if not nm_managed():
        return (
            False,
            "nm_ip: NetworkManager is not managing this system, or the legacy "
            "ifup/ifdown tooling is present (rh_ip handles it)",
        )
    return __virtualname__


def _has_legacy_ifupdown():
    """True if both ``ifup`` and ``ifdown`` are on PATH (network-scripts)."""
    return bool(salt.utils.path.which("ifup")) and bool(salt.utils.path.which("ifdown"))


def nm_managed():
    """
    Return True if this system is managed by NetworkManager without the legacy
    network-scripts tooling: ``nmcli`` is available, NetworkManager is running
    (``/run/NetworkManager`` exists) and neither ``ifup`` nor ``ifdown`` is on
    PATH.

    This is the deterministic, load-time-safe condition that decides whether
    ``nm_ip`` or ``rh_ip`` owns the ``ip`` provider -- both modules test it, so
    exactly one claims it and no runtime service call is needed during
    ``__virtual__`` resolution.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.nm_managed
    """
    return (
        bool(salt.utils.path.which("nmcli"))
        and os.path.isdir("/run/NetworkManager")
        and not _has_legacy_ifupdown()
    )


def _keyfile(iface):
    """Path of the salt-managed NM keyfile for ``iface``."""
    return os.path.join(_NM_DIR, f"{iface}.nmconnection")


def _conn_uuid(iface):
    """Deterministic connection uuid for ``iface``."""
    return str(uuid.uuid5(_UUID_NS, f"salt-{iface}"))


def _check_unsupported(settings):
    bad = sorted(k for k in _UNSUPPORTED if settings.get(k))
    if bad:
        raise CommandExecutionError(
            "NetworkManager keyfiles do not support these network.managed "
            "options: {}. Manage them outside network.managed on NetworkManager "
            "systems.".format(", ".join(bad))
        )


def _listify(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    # space- or comma-separated string
    return [v for v in str(value).replace(",", " ").split() if v]


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("true", "yes", "on", "1")


def _to_cidr(addr, netmask):
    """Combine an address + dotted/prefix netmask into ``addr/prefix``."""
    if "/" in str(addr):
        return str(addr)
    if netmask is None:
        raise CommandExecutionError(f"No netmask supplied for address {addr}")
    if ipaddress is None:
        raise CommandExecutionError("ipaddress module unavailable; cannot build CIDR")
    try:
        return str(ipaddress.ip_interface(f"{addr}/{netmask}").with_prefixlen)
    except ValueError as exc:
        raise CommandExecutionError(f"Invalid address/netmask {addr}/{netmask}: {exc}")


def _ipv4_section(settings):
    """Build the ordered ``[ipv4]`` key/value list for the connection."""
    proto = str(settings.get("proto", "")).lower()
    addresses = []
    if str(settings.get("ipaddr", "")):
        addresses.append(_to_cidr(settings["ipaddr"], settings.get("netmask")))
    for addr in _listify(settings.get("ipaddrs") or settings.get("addresses")):
        addresses.append(
            addr if "/" in str(addr) else _to_cidr(addr, settings.get("netmask"))
        )

    kvs = []
    if proto in ("dhcp", "dhcp4", "bootp"):
        kvs.append(("method", "auto"))
    elif addresses:
        kvs.append(("method", "manual"))
        gateway = settings.get("gateway")
        for idx, addr in enumerate(addresses, start=1):
            if idx == 1 and gateway:
                kvs.append((f"address{idx}", f"{addr},{gateway}"))
            else:
                kvs.append((f"address{idx}", addr))
    elif proto in ("none", "disabled", "off"):
        kvs.append(("method", "disabled"))
    else:
        # Nothing about IPv4 was specified; leave it on automatic like NM's
        # own default so a lone IPv6 config doesn't strand v4.
        kvs.append(("method", "auto"))

    dns = _listify(settings.get("dns") or settings.get("nameservers"))
    v4dns = [d for d in dns if ":" not in str(d)]
    if v4dns:
        kvs.append(("dns", ";".join(v4dns) + ";"))
    search = _listify(settings.get("dns_search") or settings.get("domain"))
    if search:
        kvs.append(("dns-search", ";".join(search) + ";"))
    return kvs


def _ipv6_section(settings):
    """Build the ordered ``[ipv6]`` key/value list for the connection."""
    proto = str(settings.get("ipv6proto", "")).lower()
    addresses = []
    if str(settings.get("ipv6ipaddr", "")):
        addresses.append(_to_cidr(settings["ipv6ipaddr"], settings.get("ipv6netmask")))
    for addr in _listify(settings.get("ipv6addrs")):
        addresses.append(addr)

    kvs = []
    if proto in ("disabled", "off", "none"):
        kvs.append(("method", "disabled"))
    elif proto in ("dhcp", "dhcp6"):
        kvs.append(("method", "dhcp"))
    elif addresses:
        kvs.append(("method", "manual"))
        gateway = settings.get("ipv6gateway")
        for idx, addr in enumerate(addresses, start=1):
            if idx == 1 and gateway:
                kvs.append((f"address{idx}", f"{addr},{gateway}"))
            else:
                kvs.append((f"address{idx}", addr))
    else:
        # NM default: SLAAC. Keeps interfaces dual-stack unless told otherwise.
        kvs.append(("method", "auto"))

    dns = _listify(settings.get("dns") or settings.get("nameservers"))
    v6dns = [d for d in dns if ":" in str(d)]
    if v6dns:
        kvs.append(("dns", ";".join(v6dns) + ";"))
    return kvs


def _vlan_id_parent(iface, settings):
    """Resolve a vlan's tag id and parent link (parse ``eth0.100`` as fallback)."""
    vid = settings.get("vlan_id") or settings.get("id")
    parent = (
        settings.get("vlan-raw-device")
        or settings.get("vlan_raw_device")
        or settings.get("parent")
        or settings.get("link")
    )
    if (vid is None or parent is None) and "." in iface:
        base, _, tag = iface.rpartition(".")
        if parent is None:
            parent = base
        if vid is None and tag.isdigit():
            vid = tag
    return vid, parent


def _bond_options(settings):
    opts = {}
    for salt_key, nm_key in _BOND_OPT_MAP.items():
        if settings.get(salt_key) is not None:
            opts[nm_key] = settings[salt_key]
    return opts


def _bridge_options(settings):
    kvs = []
    if settings.get("stp") is not None:
        kvs.append(("stp", "true" if _as_bool(settings["stp"]) else "false"))
    for salt_key, nm_key in _BRIDGE_OPT_MAP.items():
        if settings.get(salt_key) is not None:
            kvs.append((nm_key, settings[salt_key]))
    return kvs


def _member_interfaces(iface, iface_type, settings):
    """
    Physical NICs a bond/bridge enslaves. NetworkManager models each as its own
    port connection, so build_interface writes one keyfile per member.
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
    return []


def _connection_sections(iface, iface_type, enabled, settings, master=None):
    """
    Build the ordered list of ``(section, [(key, value), ...])`` tuples for one
    NetworkManager connection keyfile.

    ``master`` (a ``(master_iface, slave_type)`` tuple) marks this connection as
    a bond/bridge port: it carries no IP config and is controlled by its master.
    """
    _check_unsupported(settings)
    itype = iface_type.lower()
    nm_type = _NM_TYPE.get(itype)
    if nm_type is None:
        raise CommandExecutionError(
            "nm_ip supports interface types {}; got '{}'".format(
                ", ".join(sorted(_NM_TYPE)), iface_type
            )
        )

    conn = [
        ("id", iface),
        ("uuid", _conn_uuid(iface)),
        ("type", nm_type),
        ("interface-name", iface),
        ("autoconnect", "true" if enabled else "false"),
    ]

    if itype == "slave":
        master = master or (settings.get("master"), settings.get("slave_type", "bond"))

    if master and master[0]:
        conn.append(("master", master[0]))
        conn.append(("slave-type", master[1]))
        # A port has no L3 config; the master owns it.
        return [("connection", conn)]

    sections = [("connection", conn)]

    # One device section per connection, named after the NM connection type.
    # mtu folds into it so a connection never emits a duplicate section.
    device_section = nm_type
    device_kvs = []
    if itype == "bond":
        if "mode" not in settings:
            raise CommandExecutionError(
                f"Missing required option 'mode' for bond interface '{iface}'"
            )
        opts = _bond_options(settings)
        device_kvs = [(k, opts[k]) for k in sorted(opts)]
    elif itype == "bridge":
        device_kvs = _bridge_options(settings)
    elif itype == "vlan":
        vid, parent = _vlan_id_parent(iface, settings)
        if vid is None or not parent:
            raise CommandExecutionError(
                f"vlan interface '{iface}' needs both a vlan id and a parent "
                "(set vlan_id/id and parent, or name it like eth0.100)"
            )
        device_kvs = [("id", int(vid)), ("parent", parent)]

    # mtu is a property of the wired (ethernet) setting; NM's bond/bridge/vlan
    # settings have no mtu key, so only fold it into an ethernet section.
    if settings.get("mtu") and nm_type == "ethernet":
        device_kvs.append(("mtu", int(settings["mtu"])))

    if device_kvs:
        sections.append((device_section, device_kvs))

    sections.append(("ipv4", _ipv4_section(settings)))
    sections.append(("ipv6", _ipv6_section(settings)))
    return sections


def _dump_lines(sections):
    """Serialize ordered keyfile sections to a deterministic list of lines."""
    lines = []
    for name, kvs in sections:
        lines.append(f"[{name}]\n")
        for key, value in kvs:
            lines.append(f"{key}={value}\n")
        lines.append("\n")
    return lines


def _write_keyfile(iface, lines):
    """Write ``lines`` to ``iface``'s keyfile with the 0600 NM requires."""
    path = _keyfile(iface)
    with salt.utils.files.fopen(path, "w") as fp_:
        fp_.write(salt.utils.stringutils.to_str("".join(lines)))
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover
        log.debug("Could not chmod %s to 0600", path)


def build_interface(iface, iface_type, enabled, **settings):
    """
    Build (and, unless ``test=True``, write) the NetworkManager keyfile for a
    network interface. Returns the rendered keyfile as a list of lines.

    For bond and bridge interfaces the enslaved members (``slaves`` / ``ports``)
    are written out as their own port keyfiles as a side effect.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_interface eth0 eth True ipaddr=10.0.0.5 netmask=255.255.255.0 gateway=10.0.0.1
    """
    itype = iface_type.lower()
    if itype not in _NM_TYPE:
        raise CommandExecutionError(
            "nm_ip supports interface types {}; got '{}'".format(
                ", ".join(sorted(_NM_TYPE)), iface_type
            )
        )

    sections = _connection_sections(iface, itype, enabled, settings)
    lines = _dump_lines(sections)

    if settings.get("test"):
        return lines

    _write_keyfile(iface, lines)

    # Write port keyfiles for any enslaved members. slave-type follows the
    # master's device type (bond/bridge).
    slave_type = "bond" if itype == "bond" else "bridge"
    for member in _member_interfaces(iface, itype, settings):
        if member == iface:
            continue
        member_lines = _dump_lines(
            _connection_sections(
                member, "slave", enabled, {}, master=(iface, slave_type)
            )
        )
        _write_keyfile(member, member_lines)

    return lines


def get_interface(iface):
    """
    Return the salt-managed NetworkManager keyfile for ``iface`` as a list of
    lines, or an empty list if salt does not manage it yet.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_interface eth0
    """
    path = _keyfile(iface)
    if not os.path.isfile(path):
        return []
    with salt.utils.files.fopen(path) as fp_:
        return [salt.utils.stringutils.to_unicode(line) for line in fp_.readlines()]


def build_routes(iface, **settings):
    """
    Fold static routes into ``iface``'s salt-managed keyfile as NM
    ``routeN=<dest>,<nexthop>`` entries in the matching ipv4/ipv6 section.
    Returns the rendered route lines.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_routes eth0 routes='[{"ipaddr": "10.1.0.0", "netmask": "255.255.0.0", "gateway": "10.0.0.1"}]'
    """
    v4, v6 = [], []
    for route in settings.get("routes", []):
        dest = route.get("ipaddr") or route.get("destination") or route.get("name")
        gateway = route.get("gateway")
        if not dest or str(dest) in ("default", "0.0.0.0", "::"):
            dest = "0.0.0.0/0" if gateway and ":" not in str(gateway) else "::/0"
        else:
            netmask = route.get("netmask")
            dest = (
                str(dest)
                if "/" in str(dest) or not netmask
                else _to_cidr(dest, netmask)
            )
        entry = dest if not gateway else f"{dest},{gateway}"
        if ":" in dest or (gateway and ":" in str(gateway)):
            v6.append(entry)
        else:
            v4.append(entry)

    lines = []
    for family, entries in (("ipv4", v4), ("ipv6", v6)):
        if entries:
            kvs = [(f"route{i}", e) for i, e in enumerate(entries, start=1)]
            lines.extend(_dump_lines([(family, kvs)]))

    if lines and not settings.get("test"):
        _merge_routes(iface, v4, v6)
    return lines


def _merge_routes(iface, v4, v6):
    """Inject route entries into the existing keyfile's ipv4/ipv6 sections."""
    path = _keyfile(iface)
    if not os.path.isfile(path):
        return
    with salt.utils.files.fopen(path) as fp_:
        existing = [salt.utils.stringutils.to_unicode(x) for x in fp_.readlines()]

    out, current = [], None
    injected = {"ipv4": False, "ipv6": False}
    routes = {"ipv4": v4, "ipv6": v6}

    def _emit(section):
        for idx, entry in enumerate(routes[section], start=1):
            out.append(f"route{idx}={entry}\n")

    for line in existing:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            # Leaving a section: flush routes into it before the section break.
            if current in routes and routes[current] and not injected[current]:
                # remove trailing blank line, add routes, restore blank
                while out and out[-1].strip() == "":
                    out.pop()
                _emit(current)
                out.append("\n")
                injected[current] = True
            current = stripped[1:-1]
        # Drop any pre-existing route entries so re-runs stay idempotent.
        if current in routes and stripped.startswith("route") and "=" in stripped:
            continue
        out.append(line)

    if current in routes and routes[current] and not injected[current]:
        while out and out[-1].strip() == "":
            out.pop()
        _emit(current)
        out.append("\n")

    _write_keyfile(iface, out)


def get_routes(iface):
    """
    Return the static routes currently declared for ``iface`` in the
    salt-managed keyfile, as a list of lines.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_routes eth0
    """
    path = _keyfile(iface)
    if not os.path.isfile(path):
        return []
    with salt.utils.files.fopen(path) as fp_:
        existing = [salt.utils.stringutils.to_unicode(x) for x in fp_.readlines()]

    current, out = None, {"ipv4": [], "ipv6": []}
    for line in existing:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1]
        elif current in out and stripped.startswith("route") and "=" in stripped:
            out[current].append(stripped.split("=", 1)[1])

    lines = []
    for family in ("ipv4", "ipv6"):
        if out[family]:
            kvs = [(f"route{i}", e) for i, e in enumerate(out[family], start=1)]
            lines.extend(_dump_lines([(family, kvs)]))
    return lines


def get_network_settings():
    """
    NetworkManager has no separate global network-settings file (each
    connection keyfile is self-contained). Returns an empty list.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_network_settings
    """
    return []


def build_network_settings(**settings):
    """
    No-op on NetworkManager: there is no global ``/etc/sysconfig/network``
    equivalent that this provider manages; settings are expressed per
    connection. Returns an empty list.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.build_network_settings
    """
    return []


def _nmcli():
    nmcli = salt.utils.path.which("nmcli")
    if not nmcli:
        raise CommandExecutionError("nmcli command not found")
    return nmcli


def apply_network_settings(**settings):
    """
    Reload NetworkManager so it picks up the keyfiles written by
    build_interface (``nmcli connection reload``).

    CLI Example:

    .. code-block:: bash

        salt '*' ip.apply_network_settings
    """
    if settings.get("test"):
        return True
    out = __salt__["cmd.run_all"](
        [_nmcli(), "connection", "reload"], python_shell=False
    )
    if out["retcode"] != 0:
        raise CommandExecutionError(
            "nmcli connection reload failed: {}".format(
                out.get("stderr") or out.get("stdout")
            )
        )
    return True


def down(iface, iface_type=None):
    """
    Deactivate ``iface``'s NetworkManager connection.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.down eth0
    """
    # Ports are controlled by their master.
    if iface_type and iface_type.lower() in ("slave", "teamport"):
        return None
    return __salt__["cmd.run"](
        [_nmcli(), "connection", "down", iface], python_shell=False
    )


def up(iface, iface_type=None):  # pylint: disable=invalid-name
    """
    Reload keyfiles and (re)activate ``iface``'s NetworkManager connection.

    CLI Example:

    .. code-block:: bash

        salt '*' ip.up eth0
    """
    # Ports are controlled by their master.
    if iface_type and iface_type.lower() in ("slave", "teamport"):
        return None
    nmcli = _nmcli()
    # Reload first so a freshly written keyfile is known to NM before we bring
    # the connection up.
    __salt__["cmd.run_all"]([nmcli, "connection", "reload"], python_shell=False)
    return __salt__["cmd.run"]([nmcli, "connection", "up", iface], python_shell=False)
