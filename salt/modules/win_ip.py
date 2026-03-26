"""
The networking module for Windows based systems
"""

import ipaddress
import logging
import textwrap

import salt.utils.network
import salt.utils.platform
import salt.utils.validate.net
import salt.utils.win_pwsh
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "ip"


def __virtual__():
    """
    Confine this module to Windows systems
    """
    if not salt.utils.platform.is_windows():
        return False, "Module win_ip: Only available on Windows"
    if not salt.utils.win_pwsh.HAS_CLR:
        return False, "Module win_ip: Requires pythonnet (pip install pythonnet)"
    if not salt.utils.win_pwsh.HAS_PWSH_SDK:
        return (
            False,
            "Module win_ip: Requires the PowerShell SDK (System.Management.Automation)",
        )
    return __virtualname__


def _normalize_gateway_fields(data):
    """
    Ensure ``ipv4_gateways`` and ``ipv6_gateways`` are always lists.

    PowerShell 5.1's ``ConvertTo-Json`` unwraps single-element arrays to plain
    objects, so a single gateway arrives as a ``dict`` rather than a
    ``list[dict]``. This normalizes the parsed data in-place so callers always
    receive a consistent list type regardless of how many gateways are present.
    """
    for key in ("ipv4_gateways", "ipv6_gateways"):
        val = data.get(key)
        if isinstance(val, dict):
            data[key] = [val]
    return data


def _get_interfaces_legacy_format(name=None):
    """
    Returns interface data using the legacy netsh-style key names to avoid
    breaking existing scripts. The data is sourced from PowerShell objects,
    not netsh, so it is locale-independent.
    """
    if name:
        interfaces = get_interface_new(name)
    else:
        interfaces = list_interfaces(full=True)

    legacy = {}
    for name, data in interfaces.items():
        is_dhcp = data["ipv4_dhcp"]

        # Re-map to the specific netsh labels you had before
        legacy[name] = {
            "DHCP enabled": "Yes" if data["ipv4_dhcp"] else "No",
            "InterfaceMetric": data["ipv4_metric"],
            "Register with which suffix": (
                "Primary only" if data["dns_register"] else "None"
            ),
        }

        legacy[name]["ip_addrs"] = []
        if isinstance(data["ipv4_address"], str):
            data["ipv4_address"] = [data["ipv4_address"]]
        for addr in data["ipv4_address"]:
            ip_info = ipaddress.IPv4Interface(addr)
            legacy[name]["ip_addrs"].append(
                {
                    "IP Address": ip_info._string_from_ip_int(ip_info._ip),
                    "Netmask": str(ip_info.netmask),
                    "Subnet": str(ip_info.network),
                }
            )

        # Handle the dynamic Labeling for DNS/WINS
        if data["ipv4_dns"]:
            if isinstance(data["ipv4_dns"], str):
                dns_value = [data["ipv4_dns"]]
            else:
                dns_value = data["ipv4_dns"]
        else:
            dns_value = ["None"]
        if data["ipv4_wins"]:
            if isinstance(data["ipv4_wins"], str):
                wins_value = [data["ipv4_wins"]]
            else:
                wins_value = data["ipv4_wins"]
        else:
            wins_value = ["None"]
        if is_dhcp:
            legacy[name]["DNS servers configured through DHCP"] = dns_value
            legacy[name]["WINS servers configured through DHCP"] = wins_value
        else:
            legacy[name]["Statically Configured DNS Servers"] = dns_value
            legacy[name]["Statically Configured WINS Servers"] = wins_value

        # Add Gateway if it exists (ipv4_gateways is always a list after normalization)
        gws = [g for g in data["ipv4_gateways"] if g.get("ip")]
        if gws:
            legacy[name]["Default Gateway"] = gws[0]["ip"]
            legacy[name]["Gateway Metric"] = gws[0]["metric"]

    return legacy


def raw_interface_configs():
    """
    Return raw configs for all interfaces as returned by netsh. This command is
    localized and will return different text depending on the locality of the
    operating system.

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.raw_interface_configs
    """
    cmd = ["netsh", "interface", "ip", "show", "config"]
    return __salt__["cmd.run"](cmd, python_shell=False)


def get_all_interfaces():
    """
    This mimics the old method of getting ip settings using netsh.
    """
    return _get_interfaces_legacy_format()


def get_interface(iface):
    """
    Return the IP configuration of a single network interface

    Args:

        iface (str): The name of the interface

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.get_interface 'Local Area Connection'
    """
    return _get_interfaces_legacy_format(iface)


def is_enabled(iface):
    """
    Returns ``True`` if interface is enabled, otherwise ``False``

    Args:

        iface (str): The name of the interface to manage

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.is_enabled 'Local Area Connection #2'
    """
    with salt.utils.win_pwsh.PowerShellSession() as session:
        # Using SilentlyContinue ensures we get None/Empty if 'junk' is passed
        cmd = f"""
            [int](Get-NetAdapter -Name '{iface}' `
                            -ErrorAction SilentlyContinue).AdminStatus
        """
        status = session.run(cmd)

    try:
        # Use 0 as a fallback for None to trigger your "not found" check
        status = int(status if status is not None else 0)
    except (ValueError, TypeError):
        msg = f"Interface '{iface}' not found or invalid response."
        raise CommandExecutionError(msg)

    if status == 0:
        raise CommandExecutionError(f"Interface '{iface}' not found")

    return status == 1  # 1 is enabled


def is_disabled(iface):
    """
    Returns ``True`` if interface is disabled, otherwise ``False``

    Args:

        iface (str): The name of the interface to manage

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.is_disabled 'Local Area Connection #2'
    """
    with salt.utils.win_pwsh.PowerShellSession() as session:
        # Using SilentlyContinue ensures we get None/Empty if 'junk' is passed
        cmd = f"""
            [int](Get-NetAdapter -Name '{iface}' `
                                 -ErrorAction SilentlyContinue).AdminStatus
        """
        status = session.run(cmd)

    try:
        # Use 0 as a fallback for None to trigger your "not found" check
        status = int(status if status is not None else 0)
    except (ValueError, TypeError):
        msg = f"Interface '{iface}' not found or invalid response."
        raise CommandExecutionError(msg)

    if status == 0:
        raise CommandExecutionError(f"Interface '{iface}' not found")

    return status == 2  # 2 is disabled


def enable(iface):
    """
    Enable an interface

    Args:

        iface (str): The name of the interface to manage

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.enable 'Local Area Connection #2'
    """
    set_interface(iface, enabled=True)


def disable(iface):
    """
    Disable an interface

    Args:

        iface (str): The name of the interface to manage

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.disable 'Local Area Connection #2'
    """
    set_interface(iface, enabled=False)


def get_subnet_length(mask):
    """
    Convenience function to convert the netmask to the CIDR subnet length

    Args:

        mask (str): A netmask

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

    Args:

        iface (str):
            The name of the interface to manage

        addr (str):
            IP address with subnet length (ex. ``10.1.2.3/24``). The
            :mod:`ip.get_subnet_length <salt.modules.win_ip.get_subnet_length>`
            function can be used to calculate the subnet length from a netmask.

        gateway (:obj:`str`, optional):
            If specified, the default gateway will be set to this value.
            Default is ``None``.

        append (:obj:`bool`, optional):
            If ``True``, the address will be added as a secondary IP to the
            interface. If ``False``, all existing IPv4 addresses are cleared
            first. Defaults to ``False``.

    Returns:
        dict: A dictionary with the applied settings, e.g.::

            {"Address Info": ["192.168.1.5/24"], "Default Gateway": "192.168.1.1"}

        ``Default Gateway`` is only present when the ``gateway`` argument is
        provided.

    Raises:
        SaltInvocationError: If ``addr`` or ``gateway`` is not a valid IPv4
            address.
        CommandExecutionError: If the address already exists on the interface.

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.set_static_ip 'Local Area Connection' 10.1.2.3/24 gateway=10.1.2.1
        salt -G 'os_family:Windows' ip.set_static_ip 'Local Area Connection' 10.1.2.4/24 append=True
    """
    if not salt.utils.validate.net.ipv4_addr(addr):
        raise SaltInvocationError(f"Invalid address '{addr}'")

    if gateway and not salt.utils.validate.net.ipv4_addr(gateway):
        raise SaltInvocationError(f"Invalid default gateway '{gateway}'")

    if "/" not in addr:
        addr += "/24"

    ip, _ = addr.split("/") if "/" in addr else (addr, "24")

    with salt.utils.win_pwsh.PowerShellSession() as session:

        # Get interface Index
        index = get_interface_index(iface, session)

        cmd = f"""
            (Get-NetIPAddress -InterfaceIndex {index} `
                              -AddressFamily IPv4 `
                              -ErrorAction SilentlyContinue).IPAddress
        """
        result = session.run(cmd)

        if result is None:
            exists = False
        elif isinstance(result, list):
            exists = ip in result
        else:
            exists = ip == result.strip()

    if exists:
        msg = f"Address '{ip}' already exists on '{iface}'"
        raise CommandExecutionError(msg)

    set_interface(
        iface=iface,
        ipv4_address=addr,
        ipv4_gateways=gateway if gateway else None,
        append=append,
    )
    # Verify new settings
    new_settings = get_interface_new(iface)[iface]

    ret = {"Address Info": new_settings["ipv4_address"]}
    if gateway:
        gws = [g for g in new_settings["ipv4_gateways"] if g.get("ip")]
        if gws:
            ret["Default Gateway"] = gws[0]["ip"]

    return ret


def set_dhcp_ip(iface):
    """
    Set Windows NIC to get IP from DHCP

    Args:

        iface (str):
            The name of the interface to manage

    Returns:
        dict: ``{}`` if DHCP was already enabled, otherwise
        ``{"Interface": <name>, "DHCP enabled": "Yes"}``.

    Raises:
        CommandExecutionError: If DHCP cannot be enabled.

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.set_dhcp_ip 'Local Area Connection'
    """
    with salt.utils.win_pwsh.PowerShellSession() as session:
        index = get_interface_index(iface, session)

        # Check if dhcp is already enabled
        cmd = f"""
            [int](Get-NetIPInterface -InterfaceIndex {index} `
                                -AddressFamily IPv4 `
                                -ErrorAction SilentlyContinue).Dhcp
        """
        dhcp_enabled = session.run(cmd)

        if dhcp_enabled == 1:
            return {}

    # Enable DHCP — set_interface manages its own session
    set_interface(iface, ipv4_dhcp=True)

    with salt.utils.win_pwsh.PowerShellSession() as session:
        index = get_interface_index(iface, session)

        # Verify that dhcp is enabled
        cmd = f"""
            (Get-NetIPInterface -InterfaceIndex {index} `
                                -AddressFamily IPv4 `
                                -ErrorAction SilentlyContinue).Dhcp
        """
        dhcp_enabled = session.run_json(cmd)
        if dhcp_enabled == 1:
            return {"Interface": iface, "DHCP enabled": "Yes"}
        else:
            raise CommandExecutionError("Failed to enable DHCP")


def set_static_dns(iface, *addrs):
    """
    Set static DNS configuration on a Windows NIC

    Args:

        iface (str): The name of the interface to manage

        addrs (list):
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
    # Addrs is undefined or None, No Changes
    if not addrs or str(addrs[0]).lower() == "none":
        return {"Interface": iface, "DNS Server": "No Changes"}

    # Clear the list of DNS servers if [] is passed
    if str(addrs[0]).lower() == "[]":
        # Use set_dhcp_dns to reset the interface
        return set_dhcp_dns(iface)

    # Get interface Index
    index = get_interface_index(iface)

    with salt.utils.win_pwsh.PowerShellSession() as session:
        # 1. Fetch current DNS to see if work is actually needed
        cmd = f"""
            (Get-DnsClientServerAddress -InterfaceIndex {index} `
                                        -AddressFamily IPv4 `
                                        -ErrorAction SilentlyContinue).ServerAddresses
        """
        current_dns = session.run(cmd)

        # If current_dns is None (empty stack), make it an empty list
        if current_dns is None:
            current_dns = []
        # If it's a string (single IP), put it in a list
        elif isinstance(current_dns, str):
            # Split by newlines/commas and strip whitespace
            current_dns = [
                d.strip()
                for d in current_dns.replace(",", "\n").splitlines()
                if d.strip()
            ]

        # 2. Check if there's anything to set
        requested_dns = list(addrs)
        if set(current_dns) == set(requested_dns):
            return {}

        # 3. Set static list (comma-separated for PowerShell)
        dns_str = ",".join([f"'{a}'" for a in requested_dns])
        cmd = f"""
            Set-DnsClientServerAddress -InterfaceIndex {index} `
                                       -ServerAddresses ({dns_str})
        """
        session.run(cmd)

        # 4. Verify successful changes
        cmd = f"""
            (Get-DnsClientServerAddress -InterfaceIndex {index} `
                                        -AddressFamily IPv4 `
                                        -ErrorAction SilentlyContinue).ServerAddresses
        """
        current_dns = session.run(cmd)
        # If current_dns is None (empty stack), make it an empty list
        if current_dns is None:
            current_dns = []
        # If it's a string (single IP), put it in a list
        elif isinstance(current_dns, str):
            # Split by newlines/commas and strip whitespace
            current_dns = [
                d.strip()
                for d in current_dns.replace(",", "\n").splitlines()
                if d.strip()
            ]
        if set(current_dns) == set(requested_dns):
            return {"Interface": iface, "DNS Server": current_dns}

    raise CommandExecutionError("Failed to set DNS.")


def set_dhcp_dns(iface):
    """
    Set DNS source to DHCP on Windows

    Args:

        iface (str): The name of the interface to manage

    Returns:
        dict: ``{}`` if DNS was already set to automatic (no static servers
        configured), otherwise ``{"Interface": <name>, "DNS Server": "DHCP (Empty)"}``.

    Raises:
        CommandExecutionError: If the DNS reset cannot be verified.

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.set_dhcp_dns 'Local Area Connection'
    """
    with salt.utils.win_pwsh.PowerShellSession() as session:
        # 1. Get the interface index
        index = get_interface_index(iface, session)

        # 2. Fetch current DNS to see if work is actually needed
        cmd = f"""
            (Get-DnsClientServerAddress -InterfaceIndex {index} `
                                        -AddressFamily IPv4 `
                                        -ErrorAction SilentlyContinue).ServerAddresses
        """
        current_dns = session.run(cmd)

        # If current_dns is None (empty stack), it's already set
        if not current_dns:
            return {}

        # 3. Apply the reset.
        # This is the PowerShell equivalent of clicking 'Obtain automatically'
        cmd = f"""
            Set-DnsClientServerAddress -InterfaceIndex {index} `
                                       -ResetServerAddresses
        """
        session.run(cmd)

        # 4. Verify by checking if ServerAddresses is now empty (or managed by DHCP)
        #    On many interfaces (like Loopback), a reset results in an empty list.
        cmd = f"""
            (Get-DnsClientServerAddress -InterfaceIndex {index} `
                                        -AddressFamily IPv4).ServerAddresses
        """
        res = session.run(cmd)

        # If it returns None or an empty string, it's successfully reset/empty
        if not res:
            return {"Interface": iface, "DNS Server": "DHCP (Empty)"}

    raise CommandExecutionError("Failed to set DNS source to DHCP.")


def set_dhcp_all(iface):
    """
    Set both IP Address and DNS to DHCP

    Args:

        iface (str): The name of the interface to manage

    Returns:
        dict: ``{"Interface": <name>, "DNS Server": "DHCP", "DHCP enabled": "Yes"}``

    Raises:
        CommandExecutionError: If either the IP or DNS cannot be switched to DHCP.

    CLI Example:

    .. code-block:: bash

        salt -G 'os_family:Windows' ip.set_dhcp_all 'Local Area Connection'
    """
    set_dhcp_ip(iface)
    set_dhcp_dns(iface)
    return {"Interface": iface, "DNS Server": "DHCP", "DHCP enabled": "Yes"}


def get_default_gateway(iface=None):
    """
    Get the Default Gateway on Windows.

    Args:

        iface (str, optional):
            The name or alias of the interface to query (e.g., 'Ethernet').
            If provided, the function returns the default gateway specific
            to that interface. If ``None`` (default), it returns the
            system-wide primary default gateway based on the lowest route
            metric.

    Returns:
        str: The IP address of the default gateway.

    Raises:
        CommandExecutionError: If no default gateway is found.

    CLI Example:

    .. code-block:: bash

        # Get the system's primary default gateway
        salt 'minion' ip.get_default_gateway

        # Get the gateway for a specific interface
        salt 'minion' ip.get_default_gateway iface='Local Area Connection'
    """
    with salt.utils.win_pwsh.PowerShellSession() as session:

        if iface:
            index = get_interface_index(iface)
            cmd = f"""
                Get-NetRoute -DestinationPrefix '0.0.0.0/0' `
                             -InterfaceIndex {index} `
                             -ErrorAction SilentlyContinue |
                    Sort-Object RouteMetric |
                    Select-Object -First 1 -ExpandProperty NextHop
            """
        else:
            cmd = f"""
                Get-NetRoute -DestinationPrefix '0.0.0.0/0' `
                             -ErrorAction SilentlyContinue |
                    Sort-Object RouteMetric |
                    Select-Object -First 1 -ExpandProperty NextHop
            """

        gateway = session.run(cmd)

    if not gateway:
        raise CommandExecutionError("Unable to find default gateway")

    return gateway


def get_interface_index(iface, session=None):
    """
    Return the integer ``ifIndex`` for the named interface.

    Args:

        iface (str):
            The interface name or alias (e.g., ``'Ethernet'``).

        session (:class:`~salt.utils.win_pwsh.PowerShellSession`, optional):
            An existing ``PowerShellSession`` to reuse. If ``None`` (default),
            a new session is opened for this call only.

    Returns:
        int: The interface index.

    Raises:
        CommandExecutionError: If the interface cannot be found.
    """
    cmd = f"""
        $adapter = Get-NetAdapter -Name "{iface}" `
                                  -ErrorAction SilentlyContinue
        if (-not $adapter) {{
            $adapter = Get-NetIPInterface -InterfaceAlias "{iface}" `
                                          -ErrorAction SilentlyContinue |
                Select-Object -First 1
        }}
        if ($adapter) {{ $adapter.ifIndex }} else {{ "0" }}
    """

    def _run(s):
        raw_index = s.run(cmd)
        try:
            index = int(raw_index)
        except (ValueError, TypeError):
            raise CommandExecutionError(
                f"Interface not found or not initialized: {iface}"
            )
        if index == 0:
            raise CommandExecutionError(f"Interface not found: {iface}")
        return index

    if session is not None:
        return _run(session)
    with salt.utils.win_pwsh.PowerShellSession() as s:
        return _run(s)


def set_interface(
    iface,
    alias=None,
    enabled=None,
    ipv4_enabled=None,
    ipv4_address=None,
    ipv4_dhcp=None,
    ipv4_dns=None,
    ipv4_forwarding=None,
    ipv4_gateways=None,
    ipv4_metric=None,
    ipv4_wins=None,
    ipv4_netbios=None,
    ipv6_enabled=None,
    ipv6_address=None,
    ipv6_dhcp=None,
    ipv6_dns=None,
    ipv6_forwarding=None,
    ipv6_gateways=None,
    ipv6_metric=None,
    dns_register=None,
    dns_suffix=None,
    mtu=None,
    append=False,
):
    """
    Configures a network interface on Windows.

    This function provides a context-aware interface for managing adapter
    properties, protocol bindings, and IP configurations. It utilizes the
    InterfaceIndex to ensure stability during renames.

    **Understanding Metrics on Windows:**
    Windows calculates route priority by summing the **Interface Metric**
    (protocol level) and the **Route Metric** (gateway level).

    * **Interface Metric:** Set via ``ipvX_metric``. A value of ``0``
        enables 'Automatic Metric', where Windows assigns priority based
        on link speed.
    * **Route Metric:** Set within the ``ipvX_gateways`` objects.
    * **Total Cost:** Interface Metric + Route Metric. The lowest total
        cost determines the primary route.

    **Context-Aware Behavior:**
    The function identifies the current state of protocol bindings (IPv4/IPv6)
    before applying settings.
    * If a protocol is disabled and ``ipvX_enabled`` is not passed as ``True``,
        configuration for that stack (IPs, DNS, etc.) is skipped to prevent
        errors.
    * If ``ipvX_dhcp`` is enabled, static IP and gateway configurations
        are ignored by the OS; therefore, this function skips applying
        static addresses unless DHCP is ``False``.

    Args:

        iface (str):
            The current name or alias of the interface (e.g., 'Ethernet').

        alias (str, optional):
            A new name for the interface.

        enabled (bool, optional):
            Administrative status of the adapter.

        ipv4_enabled (bool, optional):
            Whether the IPv4 protocol is bound to this adapter. If ``None``, the
            function discovers current state.

        ipv4_address (list, optional):
            An IPv4 address or list of addresses in CIDR notation
            (e.g., ``['192.168.1.5/24']``).

            .. note::
                If a CIDR prefix is not provided, it will default to ``/24``.

        ipv4_dhcp (bool, optional):
            Set to ``True`` to enable DHCP, ``False`` for static.

        ipv4_dns (list, optional):
            A list of IPv4 DNS server addresses. Passing an empty list ``[]``
            resets DNS to automatic.

        ipv4_forwarding (bool, optional):
            Enables or disables **IP Forwarding** for the IPv4 stack. When
            ``True``, this allows the Windows machine to act as a router,
            passing traffic between this interface and others.
            Default is ``None`` (no change).

        ipv4_gateways (list, str, dict):
            The default gateway(s). Accepts multiple formats:

            * **String:** A single IP address (e.g., ``'192.168.1.1'``).
            * **List of Strings:** Multiple gateways (e.g., ``['1.1.1.1', '1.0.0.1']``).
            * **Dictionary:** A single gateway with a specific route metric
              (e.g., ``{'ip': '192.168.1.1', 'metric': 5}``).
            * **List of Dictionaries:** Multiple gateways with individual metrics
              (e.g., ``[{'ip': '1.1.1.1', 'metric': 2}, {'ip': '1.0.0.1', 'metric': 10}]``).

            If a metric is not specified within a dictionary, or if a string/list
            of strings is provided, the function falls back to ``ipv4_metric``.

        ipv4_metric (int, optional):
            The IPv4 interface metric. Use ``0`` for Automatic.

        ipv4_wins (list, optional):
            A list of up to two WINS server addresses.

        ipv4_netbios (str, optional):
            Configures NetBIOS over TCP/IP behavior via the MSFT_NetIPInterface
            CIM class.

            * ``Default`` (0): Defer to DHCP server settings.
            * ``Enable`` (1): Explicitly enable NetBIOS.
            * ``Disable`` (2): Explicitly disable NetBIOS.

        ipv6_enabled (bool, optional):
            Whether the IPv6 protocol is bound.

        ipv6_address (list, optional):
            An IPv6 address or list of addresses in CIDR notation
            (e.g., ``['2001:db8::1/64']``).

            .. note::
                If a CIDR prefix is not provided, it will default to ``/64``.

        ipv6_dhcp (bool, optional):
            Set to ``True`` for IPv6 stateful configuration.

        ipv6_dns (list, optional):
            A list of IPv6 DNS server addresses.

        ipv6_forwarding (bool, optional):
            Enables or disables **IP Forwarding** for the IPv6 stack. When
            ``True``, this allows the Windows machine to act as a router,
            passing traffic between this interface and others.
            Default is ``None`` (no change).

        ipv6_gateways (list, optional):
            The default gateway(s) for IPv6. Accepts multiple formats:

            * **String:** A single IPv6 address (e.g., ``'2001:db8::1'``).
            * **List of Strings:** Multiple gateways (e.g., ``['2001:db8::1', 'fe80::1']``).
            * **Dictionary:** A single gateway with a specific route metric
              (e.g., ``{'ip': '2001:db8::1', 'metric': 5}``).
            * **List of Dictionaries:** Multiple gateways with individual metrics
              (e.g., ``[{'ip': '2001:db8::1', 'metric': 2}, {'ip': 'fe80::1', 'metric': 10}]``).

            If a metric is not specified within a dictionary, or if a string/list
            of strings is provided, the function falls back to ``ipv6_metric``.
            Note that link-local gateways (starting with ``fe80::``) are fully
            supported as Windows scopes them via the interface index.

        ipv6_metric (int, optional):
            The IPv6 interface metric. Use ``0`` for Automatic.

        dns_register (bool, optional):
            Controls whether the interface's IP addresses are registered in DNS
            using the computer's primary DNS suffix.

            * ``True`` (Default in Windows): Corresponds to "Primary only" in
              legacy output. The computer will attempt to dynamically update
              its DNS record (A/AAAA) on the DNS server.
            * ``False``: Corresponds to "None". The computer will not attempt
              to register its name for this specific connection.

        dns_suffix (str, optional):
            Sets the **Connection-Specific DNS Suffix** (e.g.,
            ``corp.example.com``). This value is used in DNS registration and
            resolution but does not change the global primary DNS suffix of the
            computer.

        mtu (int, optional):
            Configures the **Maximum Transmission Unit** size for the physical
            adapter. Accepts values between ``576`` and ``9000``. Common uses
            include setting ``9000`` for Jumbo Frames in iSCSI/Storage networks
            or lower values for VPN compatibility.

        append (bool):
            If ``True``, the provided IPv4 and IPv6 addresses will be added
            to the interface without removing existing ones. If ``False`` (default),
            all existing IPv4/IPv6 addresses on the interface will be removed
            before applying the new configuration.

            .. note::
                This flag only applies to IP addresses. Gateways (Default Routes)
                are always replaced if a new gateway is provided to ensure
                routing stability.

    Returns:
        bool: ``True`` if successful, otherwise raises an exception.

    CLI Examples:

    .. code-block:: bash

        # Set static IPv4 with a specific metric
        salt-call --local win_ip.set_interface "Ethernet" ipv4_dhcp=False \\
            ipv4_address="['192.168.1.10/24']" ipv4_metric=10

        # Set multiple gateways with different route priorities
        salt-call --local win_ip.set_interface "Test-Iface" \\
            ipv4_gateways="[{'ip': '10.0.0.1', 'metric': 2}, {'ip': '10.0.0.2', 'metric': 100}]"

        # Reset DNS to automatic/DHCP
        salt '*' win_ip.set_interface "Wi-Fi" ipv4_dns="[]"

        # Rename an interface and enable IPv6
        salt-call --local win_ip.set_interface "Ethernet 2" alias="Production" \\
            ipv6_enabled=True ipv6_dhcp=True
    """
    # 1. Input Validation
    if ipv4_netbios and ipv4_netbios.lower() not in ["default", "enable", "disable"]:
        raise SaltInvocationError(f"Invalid NetBIOS setting: {ipv4_netbios}")

    if mtu is not None and not (576 <= mtu <= 9000):
        raise SaltInvocationError("MTU must be between 576 and 9000.")

    ipv4_addrs = (
        ipv4_address
        if isinstance(ipv4_address, list)
        else ([ipv4_address] if ipv4_address else [])
    )
    ipv6_addrs = (
        ipv6_address
        if isinstance(ipv6_address, list)
        else ([ipv6_address] if ipv6_address else [])
    )

    # 1. Identity & Setup
    index = get_interface_index(iface)

    ps_script = textwrap.dedent(
        f"""
        $idx = {index}
        $ErrorActionPreference = 'Stop'
        # Internal Sanitizer for DHCP transitions
        function Sanitize-Stack {{
            param([int]$i, [string]$family)
            $stack = if($family -eq 'IPv4') {{ 'Tcpip' }} else {{ 'Tcpip6' }}
            $guid = (Get-NetAdapter -InterfaceIndex $i).DeviceGuid
            $reg = "HKLM:\\\\SYSTEM\\\\CurrentControlSet\\\\Services\\\\$stack\\\\Parameters\\\\Interfaces\\\\$guid"
            if (Test-Path $reg) {{
                Set-ItemProperty $reg 'NameServer' '' -ErrorAction SilentlyContinue
                Set-ItemProperty $reg 'DefaultGateway' ([string[]]@()) -ErrorAction SilentlyContinue
                if ($family -eq 'IPv4') {{
                    Set-ItemProperty $reg 'WINSPrimaryServer' '' -ErrorAction SilentlyContinue
                    Set-ItemProperty $reg 'WINSSecondaryServer' '' -ErrorAction SilentlyContinue
                    $bt = "HKLM:\\\\SYSTEM\\\\CurrentControlSet\\\\Services\\\\NetBT\\\\Parameters\\\\Interfaces\\\\TcpIp_$guid"
                    if (Test-Path $bt) {{ Set-ItemProperty $bt 'NameServerList' ([string[]]@()) -ErrorAction SilentlyContinue }}
                    # THE NUCLEAR ADDITION: Flush the WMI Cache specifically
                    $wmi = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "InterfaceIndex = $i" -ErrorAction SilentlyContinue
                    if ($wmi) {{
                        $wmi | Invoke-CimMethod -MethodName SetWINSServer -Arguments @{{WINSPrimaryServer=''; WINSSecondaryServer=''}} -ErrorAction SilentlyContinue
                    }}
                }}
            }}
            $prefix = if($family -eq 'IPv4') {{ '0.0.0.0/0' }} else {{ '::/0' }}
            $r = try {{ Get-NetRoute -InterfaceIndex $idx -DestinationPrefix $prefix -ErrorAction SilentlyContinue }} catch {{ $null }}
            if ($r) {{ try {{ $r | Remove-NetRoute -Confirm:$false }} catch {{ }} }}
            $a = try {{ Get-NetIPAddress -InterfaceIndex $idx -AddressFamily $family -ErrorAction SilentlyContinue | Where-Object {{ $_.PrefixOrigin -eq 'Manual' }} }} catch {{ $null }}
            if ($a) {{ try {{ $a | Remove-NetIPAddress -Confirm:$false }} catch {{ }} }}
            Set-DnsClientServerAddress -InterfaceIndex $idx -ResetServerAddresses -ErrorAction SilentlyContinue
        }}
    """
    )

    # 2. Administrative State & MTU
    if enabled is not None:
        action = "Enable-NetAdapter" if enabled else "Disable-NetAdapter"
        ps_script += textwrap.dedent(
            f"""
            Get-NetAdapter -InterfaceIndex $idx | {action} -Confirm:$false"""
        )

    if mtu is not None:
        ps_script += textwrap.dedent(
            f"""
            Set-NetIPInterface -InterfaceIndex $idx `
                               -AddressFamily IPv4 `
                               -NlMtuBytes {mtu} `
                               -Confirm:$false"""
        )
        # Applying to IPv6 as well for a consistent MTU across the interface
        ps_script += textwrap.dedent(
            f"""
            Set-NetIPInterface -InterfaceIndex $idx `
                               -AddressFamily IPv6 `
                               -NlMtuBytes {mtu} `
                               -Confirm:$false `
                               -ErrorAction SilentlyContinue"""
        )

    # 3. Protocol Binding & Basic Interface Settings
    for family, active, dhcp, forward, metric in [
        ("IPv4", ipv4_enabled, ipv4_dhcp, ipv4_forwarding, ipv4_metric),
        ("IPv6", ipv6_enabled, ipv6_dhcp, ipv6_forwarding, ipv6_metric),
    ]:
        if active is not None:
            comp = "ms_tcpip" if family == "IPv4" else "ms_tcpip6"
            action = (
                "Enable-NetAdapterBinding" if active else "Disable-NetAdapterBinding"
            )
            # SilentlyContinue: the binding toggle is idempotent and some adapter
            # types (e.g. loopback) emit non-fatal errors for already-set states.
            ps_script += textwrap.dedent(
                f"""
                Get-NetAdapter -InterfaceIndex $idx | {action} -ComponentID '{comp}' -ErrorAction SilentlyContinue"""
            )

        # IP Interface Properties (DHCP, Forwarding, Metric)
        if any(x is not None for x in [dhcp, forward, metric]):
            cmd = f"Set-NetIPInterface -InterfaceIndex $idx -AddressFamily {family}"
            if dhcp is not None:
                cmd += f" -Dhcp {'Enabled' if dhcp else 'Disabled'}"
            if forward is not None:
                cmd += f" -Forwarding {'Enabled' if forward else 'Disabled'}"
            if metric is not None:
                if metric == 0:
                    cmd += " -AutomaticMetric Enabled"
                else:
                    cmd += f" -AutomaticMetric Disabled -InterfaceMetric {metric}"
            ps_script += textwrap.dedent(
                f"""
                {cmd}"""
            )

            # Trigger Sanitizer if enabling DHCP
            if dhcp:
                ps_script += textwrap.dedent(
                    f"""
                    Sanitize-Stack -i $idx -family '{family}'"""
                )

    # 4. IP Addresses (Static)
    for family, addrs, dhcp in [
        ("IPv4", ipv4_addrs, ipv4_dhcp),
        ("IPv6", ipv6_addrs, ipv6_dhcp),
    ]:
        if addrs and not dhcp:
            if not append:
                ps_script += textwrap.dedent(
                    f"""
                    $currentIPs = try {{
                        Get-NetIPAddress -InterfaceIndex $idx `
                                         -AddressFamily {family} `
                                         -ErrorAction SilentlyContinue |
                        Where-Object {{ $_.IPAddress -notlike 'fe80*' -and $_.PrefixOrigin -eq 'Manual' }}
                    }} catch {{ $null }}
                    if ($currentIPs) {{
                        try {{ $currentIPs | Remove-NetIPAddress -Confirm:$false }} catch {{ }}
                    }}
                """
                )

            # 'addrs' is now GUARANTEED to be a list of strings
            for a in addrs:
                # Split logic
                parts = a.split("/")
                ip = parts[0]
                pref = (
                    parts[1] if len(parts) > 1 else ("24" if family == "IPv4" else "64")
                )

                ps_script += textwrap.dedent(
                    f"""
                    New-NetIPAddress -InterfaceIndex $idx `
                                     -IPAddress '{ip}' `
                                     -PrefixLength {pref} `
                                     -AddressFamily {family}
                """
                )

    # 5. Gateways (Default Routes)
    for family, gateways, metric_fallback in [
        ("IPv4", ipv4_gateways, ipv4_metric),
        ("IPv6", ipv6_gateways, ipv6_metric),
    ]:
        if gateways is not None:
            prefix = "0.0.0.0/0" if family == "IPv4" else "::/0"
            # Clear existing default routes first
            ps_script += textwrap.dedent(
                f"""
                $routes = try {{
                    Get-NetRoute -InterfaceIndex $idx `
                                 -DestinationPrefix '{prefix}' `
                                 -ErrorAction SilentlyContinue
                }} catch {{ $null }}
                if ($routes) {{
                    try {{ $routes | Remove-NetRoute -Confirm:$false }} catch {{ }}
                }}"""
            )

            gw_list = gateways if isinstance(gateways, list) else [gateways]
            for gw in gw_list:
                if isinstance(gw, dict):
                    ip, met = gw.get("ip"), gw.get(
                        "metric", metric_fallback if metric_fallback else 0
                    )
                else:
                    ip, met = gw, (metric_fallback if metric_fallback else 0)
                if ip:
                    ps_script += textwrap.dedent(
                        f"""
                        New-NetRoute -InterfaceIndex $idx `
                                     -DestinationPrefix '{prefix}' `
                                     -NextHop '{ip}' `
                                     -RouteMetric {met} `
                                     -Confirm:$false"""
                    )

    # 6. DNS, WINS, and NetBIOS
    if dns_suffix:
        ps_script += textwrap.dedent(
            f"""
            Set-DnsClient -InterfaceIndex $idx `
                          -ConnectionSpecificSuffix '{dns_suffix}'"""
        )
    if dns_register is not None:
        ps_script += textwrap.dedent(
            f"""
            Set-DnsClient -InterfaceIndex $idx `
                          -RegisterThisConnectionsAddress {'$true' if dns_register else '$false'}"""
        )

    for family, dns_servers in [("IPv4", ipv4_dns), ("IPv6", ipv6_dns)]:
        if dns_servers is not None:
            if not dns_servers:
                ps_script += textwrap.dedent(
                    f"""
                    Set-DnsClientServerAddress -InterfaceIndex $idx `
                                               -AddressFamily {family} `
                                               -ResetServerAddresses"""
                )
            else:
                s_list = dns_servers if isinstance(dns_servers, list) else [dns_servers]
                # 1. Format the PowerShell array string first
                # Result: "@('8.8.8.8','1.1.1.1')"
                dns_array_str = "@(" + ",".join([f"'{s}'" for s in s_list]) + ")"
                ps_script += textwrap.dedent(
                    f"""
                    Set-DnsClientServerAddress -InterfaceIndex $idx `
                                               -ServerAddresses {dns_array_str}"""
                )

    if ipv4_wins is not None:
        w = ipv4_wins if isinstance(ipv4_wins, list) else [ipv4_wins]
        p, s = (w[0] if len(w) > 0 else ""), (w[1] if len(w) > 1 else "")
        ps_script += textwrap.dedent(
            f"""
            $w = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "InterfaceIndex = $idx"
            if($w) {{
                $w | Invoke-CimMethod -MethodName SetWINSServer `
                                      -Arguments @{{WINSPrimaryServer='{p}'; WINSSecondaryServer='{s}'}}
            }}"""
        )

    if ipv4_netbios:
        nb_val = {"default": 0, "enable": 1, "disable": 2}[ipv4_netbios.lower()]
        ps_script += textwrap.dedent(
            f"""
            Set-NetIPInterface -InterfaceIndex $idx `
                               -AddressFamily IPv4 `
                               -NetbiosSetting {nb_val}"""
        )

    # 7. Rename & Finalize
    if alias and alias != iface:
        ps_script += textwrap.dedent(
            f"""
            Get-NetAdapter -InterfaceIndex $idx |
            Rename-NetAdapter -NewName '{alias}' `
                              -Confirm:$false"""
        )

    ps_script += textwrap.dedent(
        """
    $iface = Get-NetAdapter -InterfaceIndex $idx `
                            -ErrorAction SilentlyContinue
    if ($iface.AdminStatus -eq 1 -and $iface.MediaConnectionState -eq 1) {
        $timeout = [System.Diagnostics.Stopwatch]::StartNew()
        while ($timeout.Elapsed.TotalSeconds -lt 10) {
            # Check for any addresses still in the 'Tentative' state.
            # Wrap in try/catch: Get-NetIPAddress throws a terminating CIM error
            # when the IP stack is disabled, which -ErrorAction cannot suppress.
            $tentative = try {
                Get-NetIPAddress -InterfaceIndex $idx -ErrorAction SilentlyContinue |
                Where-Object { $_.AddressState -eq 'Tentative' }
            } catch { $null }
            if (-not $tentative) {
                break
            }
            Start-Sleep -Milliseconds 200
        }
    }
    """
    )

    # 8. Execution
    with salt.utils.win_pwsh.PowerShellSession() as session:
        session.import_modules(["NetAdapter", "NetTCPIP", "DnsClient"])
        session.run_strict(ps_script)

    return True


def get_interface_new(iface):
    """
    Retrieves the current configuration of a network interface on Windows.

    This function gathers comprehensive data about a network adapter, including
    administrative status, protocol bindings, IP addresses, DNS servers,
    gateways, and WINS configuration. The returned dictionary is structured
    to be directly compatible with the parameters of ``set_interface``.

    **Data Structures and Round-trip Logic:**
    * **Addresses:** IPs are returned in CIDR notation (e.g., ``10.0.0.5/24``)
        to ensure the setter can accurately recreate the subnet mask.
    * **Gateways:** Returned as a list of dictionaries containing both the
        IP (``ip``) and the route-specific metric (``metric``).
    * **Metrics:** A value of ``0`` indicates that the interface is
        configured for 'Automatic Metric' calculation by Windows.

    Args:

        iface (str):
            The name or alias of the interface (e.g., 'Ethernet'). This is used
            for the initial hardware lookup to find the permanent ``InterfaceIndex``.

    Returns:
        dict: A dictionary keyed by the interface name containing:

            - **alias** (str): The friendly name of the adapter.
            - **description** (str): Human-readable adapter description
              (e.g., ``"Microsoft Loopback Adapter"``).
            - **enabled** (bool): Administrative status (``True`` = Up).
            - **index** (int): The stable ``InterfaceIndex`` used internally
              by all CIM/PowerShell cmdlets.
            - **link_status** (str): Current link state reported by the driver
              (e.g., ``"Up"``, ``"Disconnected"``).
            - **mac_address** (str): The physical (MAC) address of the adapter.
            - **mtu** (int): MTU in bytes; defaults to ``1500`` when the
              adapter reports no value (``4294967295`` or ``None``).
            - **dns_register** (bool): ``True`` if the adapter registers its
              addresses in DNS using the computer's primary DNS suffix.
            - **dns_suffix** (str): Connection-specific DNS suffix, or
              ``None`` if not set.
            - **ipv4_enabled** (bool): Status of the IPv4 protocol binding.
            - **ipv4_dhcp** (bool): ``True`` if IPv4 DHCP is enabled.
            - **ipv4_metric** (int): The IPv4 interface metric (``0`` = Auto).
            - **ipv4_address** (list): List of IPv4 addresses in CIDR format.
            - **ipv4_gateways** (list): List of dicts, each with ``ip`` and
              ``metric`` keys, for IPv4 default routes. Always a list — even
              when only one gateway is configured — because
              :func:`_normalize_gateway_fields` corrects the PowerShell 5.1
              behavior of unwrapping single-element arrays.
            - **ipv4_dns** (list): List of IPv4 DNS server addresses.
            - **ipv4_forwarding** (bool | None): ``True`` if IPv4 forwarding
              is enabled, ``None`` if the IPv4 stack is not bound.
            - **ipv4_wins** (list): Primary and secondary WINS server
              addresses (empty list if none configured).
            - **ipv4_netbios** (str): NetBIOS configuration —
              ``"Default"``, ``"Enable"``, or ``"Disable"``.
            - **ipv6_enabled** (bool): Status of the IPv6 protocol binding.
            - **ipv6_dhcp** (bool): ``True`` if IPv6 stateful config is
              enabled.
            - **ipv6_metric** (int): The IPv6 interface metric (``0`` = Auto).
            - **ipv6_address** (list): List of IPv6 addresses in CIDR format.
            - **ipv6_gateways** (list): List of dicts, each with ``ip`` and
              ``metric`` keys, for IPv6 default routes. Always a list for the
              same reason as ``ipv4_gateways``.
            - **ipv6_dns** (list): List of IPv6 DNS server addresses.
            - **ipv6_forwarding** (bool | None): ``True`` if IPv6 forwarding
              is enabled, ``None`` if the IPv6 stack is not bound.

    Raises:
        CommandExecutionError: If the specified interface cannot be found.

    CLI Examples:

    .. code-block:: bash

        # Get details for a specific interface
        salt-call --local win_ip.get_interface_new "Ethernet"

        # Get details for the loopback test adapter
        salt '*' win_ip.get_interface_new "Test-Iface"
    """
    index = get_interface_index(iface)

    # ONE script to rule them all
    cmd = rf"""
        $idx = {index}
        $adapter = Get-NetAdapter -InterfaceIndex $idx -ErrorAction SilentlyContinue
        if (-not $adapter) {{ return @{{}} | ConvertTo-Json }}

        $ipv4 = Get-NetIPInterface -InterfaceIndex $idx -AddressFamily IPv4 -ErrorAction SilentlyContinue
        $ipv6 = Get-NetIPInterface -InterfaceIndex $idx -AddressFamily IPv6 -ErrorAction SilentlyContinue
        $dns  = Get-DnsClientServerAddress -InterfaceIndex $idx -ErrorAction SilentlyContinue
        $reg  = Get-DnsClient -InterfaceIndex $idx -ErrorAction SilentlyContinue
        $wmi  = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "InterfaceIndex = $idx" -ErrorAction SilentlyContinue

        $rawMtu = if ($ipv4) {{ $ipv4.NlMtu }} elseif ($ipv6) {{ $ipv6.NlMtu }} else {{ $adapter.MtuSize }}
        $finalMtu = if ($rawMtu -eq 4294967295 -or $null -eq $rawMtu) {{ 1500 }} else {{ $rawMtu }}

        # Helper to format IPs into CIDR
        function Get-CIDR {{
            param($family)
            $ips = Get-NetIPAddress -InterfaceIndex $idx -AddressFamily $family -ErrorAction SilentlyContinue |
                   Where-Object {{ $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike 'fe80*' }}
            if ($ips) {{ @($ips | ForEach-Object {{ "$($_.IPAddress)/$($_.PrefixLength)" }}) }} else {{ @() }}
        }}

        # Helper to format Gateways
        function Get-Gateways {{
            param($family)
            $prefix = if($family -eq 'IPv4') {{ "0.0.0.0/0" }} else {{ "::/0" }}
            $routes = Get-NetRoute -InterfaceIndex $idx -DestinationPrefix $prefix -ErrorAction SilentlyContinue |
                      Where-Object {{ $_.NextHop -and $_.NextHop -notmatch '^0\.0\.0\.0$|^::$' }}
            if ($routes) {{
                @($routes | Select-Object @{{Name='ip';Expression={{$_.NextHop}}}}, @{{Name='metric';Expression={{$_.RouteMetric}}}})
            }} else {{ @() }}
        }}

        $result = [PSCustomObject]@{{
            alias           = $adapter.Name
            description     = $adapter.InterfaceDescription
            dns_register    = $reg.RegisterThisConnectionsAddress
            dns_suffix      = $reg.ConnectionSpecificSuffix
            enabled         = $adapter.AdminStatus -eq 1
            index           = $idx
            link_status     = $adapter.Status
            mac_address     = $adapter.MacAddress
            mtu             = [int]$finalMtu

            # IPv4 Stack
            ipv4_address    = Get-CIDR -family IPv4
            ipv4_dhcp       = if($ipv4) {{ $ipv4.Dhcp -eq 1 }} else {{ $false }}
            ipv4_dns        = @($dns | Where-Object {{$_.AddressFamily -eq 2}} | Select-Object -ExpandProperty ServerAddresses)
            ipv4_enabled    = $null -ne $ipv4
            ipv4_forwarding = if ($ipv4) {{ $ipv4.Forwarding -eq 1 }} else {{ $null }}
            ipv4_gateways   = Get-Gateways -family IPv4
            ipv4_metric     = if($ipv4) {{ $ipv4.InterfaceMetric }} else {{ 0 }}
            ipv4_netbios    = switch($ipv4.NetbiosSetting) {{ 1 {{"Enable"}} 2 {{"Disable"}} Default {{"Default"}} }}
            ipv4_wins       = @($wmi.WINSPrimaryServer, $wmi.WINSSecondaryServer).Where({{$_}})

            # IPv6 Stack
            ipv6_address    = Get-CIDR -family IPv6
            ipv6_dhcp       = if($ipv6) {{ $ipv6.Dhcp -eq 1 }} else {{ $false }}
            ipv6_dns        = @($dns | Where-Object {{$_.AddressFamily -eq 23}} | Select-Object -ExpandProperty ServerAddresses)
            ipv6_enabled    = $null -ne $ipv6
            ipv6_forwarding = if ($ipv6) {{ $ipv6.Forwarding -eq 1 }} else {{ $null }}
            ipv6_gateways   = Get-Gateways -family IPv6
            ipv6_metric     = if($ipv6) {{ $ipv6.InterfaceMetric }} else {{ 0 }}
        }}

        $result | ConvertTo-Json -Depth 5 -Compress
        """

    with salt.utils.win_pwsh.PowerShellSession() as session:
        # Load modules once per session for efficiency
        session.import_modules(["NetAdapter", "NetTCPIP", "DnsClient"])
        data = session.run_json(cmd)

    if data:
        _normalize_gateway_fields(data)

    return {iface: data}


def list_interfaces(full=False):
    """
    Lists the available network interfaces on the system.

    Args:

        full (bool, optional): If ``True``, returns a dictionary keyed by
            interface names with detailed configuration for each adapter.
            If ``False``, returns a list of interface names only.
            Defaults to ``False``.

    Returns:
        list: When ``full=False``, a list of interface name strings.

        dict: When ``full=True``, a dictionary keyed by interface name.
            Each value has the same structure as the per-interface dict
            returned by :func:`get_interface_new` — see that function for
            the full field reference (``alias``, ``description``, ``enabled``,
            ``index``, ``link_status``, ``mac_address``, ``mtu``,
            ``dns_register``, ``dns_suffix``, ``ipv4_*``, ``ipv6_*``).

            The entire dataset is collected in a **single PowerShell
            invocation** rather than one session per adapter, so it is
            significantly faster than calling :func:`get_interface_new`
            in a loop.
    """
    with salt.utils.win_pwsh.PowerShellSession() as session:
        session.import_modules(["NetAdapter", "NetTCPIP", "DnsClient"])

        if not full:
            data = session.run_json("(Get-NetAdapter).Name")
            if not data:
                return []
            return data if isinstance(data, list) else [data]

        # Gather all adapter details in a single PowerShell invocation to avoid
        # opening N separate sessions (one per adapter).
        cmd = r"""
            function Get-CIDR {
                param([int]$idx, [string]$family)
                $ips = Get-NetIPAddress -InterfaceIndex $idx -AddressFamily $family -ErrorAction SilentlyContinue |
                       Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike 'fe80*' }
                if ($ips) { @($ips | ForEach-Object { "$($_.IPAddress)/$($_.PrefixLength)" }) } else { @() }
            }

            function Get-Gateways {
                param([int]$idx, [string]$family)
                $prefix = if ($family -eq 'IPv4') { "0.0.0.0/0" } else { "::/0" }
                $routes = Get-NetRoute -InterfaceIndex $idx -DestinationPrefix $prefix -ErrorAction SilentlyContinue |
                          Where-Object { $_.NextHop -and $_.NextHop -notmatch '^0\.0\.0\.0$|^::$' }
                if ($routes) {
                    @($routes | Select-Object @{Name='ip';Expression={$_.NextHop}}, @{Name='metric';Expression={$_.RouteMetric}})
                } else { @() }
            }

            $out = @{}
            Get-NetAdapter | ForEach-Object {
                $adapter = $_
                $idx     = [int]$adapter.ifIndex

                $ipv4 = Get-NetIPInterface -InterfaceIndex $idx -AddressFamily IPv4 -ErrorAction SilentlyContinue
                $ipv6 = Get-NetIPInterface -InterfaceIndex $idx -AddressFamily IPv6 -ErrorAction SilentlyContinue
                $dns  = Get-DnsClientServerAddress -InterfaceIndex $idx -ErrorAction SilentlyContinue
                $reg  = Get-DnsClient -InterfaceIndex $idx -ErrorAction SilentlyContinue
                $wmi  = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "InterfaceIndex = $idx" -ErrorAction SilentlyContinue

                $rawMtu   = if ($ipv4) { $ipv4.NlMtu } elseif ($ipv6) { $ipv6.NlMtu } else { $adapter.MtuSize }
                $finalMtu = if ($rawMtu -eq 4294967295 -or $null -eq $rawMtu) { 1500 } else { $rawMtu }

                $out[$adapter.Name] = [PSCustomObject]@{
                    alias           = $adapter.Name
                    description     = $adapter.InterfaceDescription
                    dns_register    = $reg.RegisterThisConnectionsAddress
                    dns_suffix      = $reg.ConnectionSpecificSuffix
                    enabled         = $adapter.AdminStatus -eq 1
                    index           = $idx
                    link_status     = $adapter.Status
                    mac_address     = $adapter.MacAddress
                    mtu             = [int]$finalMtu

                    ipv4_address    = Get-CIDR -idx $idx -family IPv4
                    ipv4_dhcp       = if ($ipv4) { $ipv4.Dhcp -eq 1 } else { $false }
                    ipv4_dns        = @($dns | Where-Object { $_.AddressFamily -eq 2 } | Select-Object -ExpandProperty ServerAddresses)
                    ipv4_enabled    = $null -ne $ipv4
                    ipv4_forwarding = if ($ipv4) { $ipv4.Forwarding -eq 1 } else { $null }
                    ipv4_gateways   = Get-Gateways -idx $idx -family IPv4
                    ipv4_metric     = if ($ipv4) { $ipv4.InterfaceMetric } else { 0 }
                    ipv4_netbios    = switch ($ipv4.NetbiosSetting) { 1 { "Enable" } 2 { "Disable" } Default { "Default" } }
                    ipv4_wins       = @($wmi.WINSPrimaryServer, $wmi.WINSSecondaryServer).Where({ $_ })

                    ipv6_address    = Get-CIDR -idx $idx -family IPv6
                    ipv6_dhcp       = if ($ipv6) { $ipv6.Dhcp -eq 1 } else { $false }
                    ipv6_dns        = @($dns | Where-Object { $_.AddressFamily -eq 23 } | Select-Object -ExpandProperty ServerAddresses)
                    ipv6_enabled    = $null -ne $ipv6
                    ipv6_forwarding = if ($ipv6) { $ipv6.Forwarding -eq 1 } else { $null }
                    ipv6_gateways   = Get-Gateways -idx $idx -family IPv6
                    ipv6_metric     = if ($ipv6) { $ipv6.InterfaceMetric } else { 0 }
                }
            }
            $out | ConvertTo-Json -Depth 5 -Compress
        """
        data = session.run_json(cmd)
        if not data:
            return {}
        for adapter_data in data.values():
            if isinstance(adapter_data, dict):
                _normalize_gateway_fields(adapter_data)
        return data
