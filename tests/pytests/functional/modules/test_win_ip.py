import ipaddress

import pytest

import salt.utils.json
import salt.utils.validate.net
import salt.utils.win_pwsh
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import patch

pytestmark = [
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]

INSTALL_LOOPBACK_ADAPTER = r"""
$InstallSource = @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class LoopbackInstaller {
    [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern IntPtr SetupDiCreateDeviceInfoList(ref Guid ClassGuid, IntPtr hwndParent);

    [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern bool SetupDiCreateDeviceInfo(IntPtr DeviceInfoSet, string DeviceName, ref Guid ClassGuid, string DeviceDescription, IntPtr hwndParent, uint CreationFlags, ref SP_DEVINFO_DATA DeviceInfoData);

    [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern bool SetupDiSetDeviceRegistryProperty(IntPtr DeviceInfoSet, ref SP_DEVINFO_DATA DeviceInfoData, uint Property, byte[] PropertyBuffer, uint PropertyBufferSize);

    [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern bool SetupDiCallClassInstaller(uint InstallFunction, IntPtr DeviceInfoSet, ref SP_DEVINFO_DATA DeviceInfoData);

    [StructLayout(LayoutKind.Sequential)]
    public struct SP_DEVINFO_DATA {
        public uint cbSize;
        public Guid ClassGuid;
        public uint DevInst;
        public IntPtr Reserved;
    }

    public static void Install() {
        Guid netClassGuid = new Guid("{4d36e972-e325-11ce-bfc1-08002be10318}"); // Network Adapter Class GUID
        IntPtr deviceInfoSet = SetupDiCreateDeviceInfoList(ref netClassGuid, IntPtr.Zero);

        SP_DEVINFO_DATA deviceInfoData = new SP_DEVINFO_DATA();
        deviceInfoData.cbSize = (uint)Marshal.SizeOf(deviceInfoData);

        // Create the device node
        SetupDiCreateDeviceInfo(deviceInfoSet, "MSLOOP", ref netClassGuid, null, IntPtr.Zero, 1, ref deviceInfoData);

        // Set the HardwareID property so Windows knows to use the Loopback driver
        byte[] hwid = Encoding.Unicode.GetBytes("*MSLOOP\0\0");
        SetupDiSetDeviceRegistryProperty(deviceInfoSet, ref deviceInfoData, 1, hwid, (uint)hwid.Length);

        // DIF_INSTALLDEVICE = 0x19 (Tells Windows to actually install the driver for this node)
        SetupDiCallClassInstaller(0x19, deviceInfoSet, ref deviceInfoData);
    }
}
"@

# Add the installer code to the session
if (-not ([System.Management.Automation.PSTypeName]"LoopbackInstaller").Type) {
    Add-Type -TypeDefinition $InstallSource | Out-Null
}

# Execute the installation
[LoopbackInstaller]::Install() | Out-Null

# 1. Force the driver installation
# This adds the driver to the store and attempts to start the hardware node
pnputil /add-driver $env:windir\inf\netloop.inf /install
"""

REMOVE_LOOPBACK_ADAPTER = r"""
$UninstallSource = @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class LoopbackUninstaller {
    [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern IntPtr SetupDiGetClassDevs(ref Guid ClassGuid, string Enumerator, IntPtr hwndParent, uint Flags);

    [DllImport("setupapi.dll", SetLastError = true)]
    public static extern bool SetupDiEnumDeviceInfo(IntPtr DeviceInfoSet, uint MemberIndex, ref SP_DEVINFO_DATA DeviceInfoData);

    [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern bool SetupDiGetDeviceRegistryProperty(IntPtr DeviceInfoSet, ref SP_DEVINFO_DATA DeviceInfoData, uint Property, out uint PropertyRegDataType, byte[] PropertyBuffer, uint PropertyBufferSize, out uint RequiredSize);

    [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern bool SetupDiCallClassInstaller(uint InstallFunction, IntPtr DeviceInfoSet, ref SP_DEVINFO_DATA DeviceInfoData);

    [DllImport("setupapi.dll", SetLastError = true)]
    public static extern bool SetupDiDestroyDeviceInfoList(IntPtr DeviceInfoSet);

    [StructLayout(LayoutKind.Sequential)]
    public struct SP_DEVINFO_DATA {
        public uint cbSize;
        public Guid ClassGuid;
        public uint DevInst;
        public IntPtr Reserved;
    }

    public static void UninstallAll() {
        Guid netClassGuid = new Guid("{4d36e972-e325-11ce-bfc1-08002be10318}");
        // DIGCF_PRESENT = 0x2
        IntPtr deviceInfoSet = SetupDiGetClassDevs(ref netClassGuid, null, IntPtr.Zero, 0x2);

        SP_DEVINFO_DATA deviceInfoData = new SP_DEVINFO_DATA();
        deviceInfoData.cbSize = (uint)Marshal.SizeOf(deviceInfoData);

        uint i = 0;
        while (SetupDiEnumDeviceInfo(deviceInfoSet, i, ref deviceInfoData)) {
            uint propType;
            uint requiredSize;
            byte[] buffer = new byte[1024];

            // SPDRP_HARDWAREID = 0x1
            if (SetupDiGetDeviceRegistryProperty(deviceInfoSet, ref deviceInfoData, 1, out propType, buffer, (uint)buffer.Length, out requiredSize)) {
                string hwid = Encoding.Unicode.GetString(buffer).TrimEnd('\0');
                if (hwid.Contains("*MSLOOP")) {
                    // DIF_REMOVE = 0x05
                    SetupDiCallClassInstaller(0x05, deviceInfoSet, ref deviceInfoData);
                    // Don't increment 'i' because the list shifted after removal
                    continue;
                }
            }
            i++;
        }
        SetupDiDestroyDeviceInfoList(deviceInfoSet);
    }
}
"@

# Add the uninstaller to the session
Add-Type -TypeDefinition $UninstallSource
if (-not ([System.Management.Automation.PSTypeName]"LoopbackUninstaller").Type) {
    Add-Type -TypeDefinition $UninstallSource | Out-Null
}

# Execute the removal
[LoopbackUninstaller]::UninstallAll()
"""


@pytest.fixture(scope="module")
def ip(modules):
    return modules.ip


@pytest.fixture(scope="module")
def dummy_interface(request):
    """
    We need to create a dummy interface for messing with since we're gonna be
    enabling, disabling, changing dns, dhcp, gateways, etc
    """
    with salt.utils.win_pwsh.PowerShellSession() as session:
        session.run(INSTALL_LOOPBACK_ADAPTER)

        # Let's make sure cleanup happens
        def cleanup():
            with salt.utils.win_pwsh.PowerShellSession() as cleanup_session:
                cleanup_session.run(REMOVE_LOOPBACK_ADAPTER)

        request.addfinalizer(cleanup)

        cmd = """
            $dummy = Get-NetAdapter | Where-Object { $_.InterfaceDescription -match "KM-TEST Loopback" }
            Rename-NetAdapter -Name $dummy.Name -NewName "SaltTestLoopback" -Confirm:$false
            ConvertTo-Json -InputObject @($dummy.ifIndex, "SaltTestLoopback") -Compress
        """
        index, name = session.run_json(cmd)
        yield index, name


@pytest.fixture(scope="function")
def default_dhcp(ip, dummy_interface):
    index, name = dummy_interface

    # Ensure the interface is named correctly before configuring
    with salt.utils.win_pwsh.PowerShellSession() as session:
        cmd = f"""
            Get-NetAdapter -InterfaceIndex {index} | Rename-NetAdapter -NewName "{name}"
        """
        session.run(cmd)

    settings = {
        "enabled": True,
        "ipv4_enabled": True,
        "ipv4_dhcp": True,
        "ipv6_enabled": True,
        "ipv6_dhcp": True,
    }

    # 2. Apply settings
    ip.set_interface(iface=name, **settings)

    # 3. Verify settings
    new_settings = ip.get_interface_new(iface=name)[name]
    assert new_settings["enabled"] == settings["enabled"]
    assert new_settings["ipv4_enabled"] == settings["ipv4_enabled"]
    assert new_settings["ipv4_dhcp"] == settings["ipv4_dhcp"]
    assert new_settings["ipv6_enabled"] == settings["ipv6_enabled"]
    assert new_settings["ipv6_dhcp"] == settings["ipv6_dhcp"]

    return name, settings


@pytest.fixture(scope="function")
def default_static(ip, dummy_interface):
    index, name = dummy_interface

    # 1. Ensure the interface is named correctly before configuring
    with salt.utils.win_pwsh.PowerShellSession() as session:
        cmd = f"""
            Get-NetAdapter -InterfaceIndex {index} | Rename-NetAdapter -NewName "{name}"
        """
        session.run(cmd)

    settings = {
        "enabled": True,
        "ipv4_enabled": True,
        "ipv4_address": "192.168.1.105/24",
        "ipv4_dhcp": False,
        "ipv4_dns": ["192.168.1.10"],
        "ipv4_gateways": [{"ip": "192.168.1.1", "metric": 5}],
        "ipv4_metric": 10,
        "ipv4_wins": ["192.168.1.11", "192.168.1.12"],
        "ipv6_enabled": True,
        "ipv6_address": "2001:db8::1/64",
        "ipv6_dhcp": False,
        "ipv6_dns": ["fd00:1234:5678:1::10"],
        # Use a ULA address rather than a link-local (fe80::) next hop.
        # Link-local addresses require a zone ID and are not valid default-route
        # next hops on loopback adapters.
        "ipv6_gateways": [{"ip": "fd00::1", "metric": 50}],
        "ipv6_metric": 100,
    }

    # 2. Apply settings
    ip.set_interface(iface=name, **settings)

    # 3. Verify settings
    new_settings = ip.get_interface_new(iface=name)[name]
    assert new_settings["enabled"] == settings["enabled"]
    assert new_settings["ipv4_enabled"] == settings["ipv4_enabled"]
    assert new_settings["ipv4_address"] == settings["ipv4_address"]
    assert new_settings["ipv4_dhcp"] == settings["ipv4_dhcp"]
    assert new_settings["ipv4_dns"] == settings["ipv4_dns"]
    assert new_settings["ipv4_gateways"] == settings["ipv4_gateways"]
    assert new_settings["ipv4_metric"] == settings["ipv4_metric"]
    assert new_settings["ipv4_wins"] == settings["ipv4_wins"]
    assert new_settings["ipv6_enabled"] == settings["ipv6_enabled"]
    assert new_settings["ipv6_address"] == "2001:db8::1/64"
    assert new_settings["ipv6_dhcp"] == settings["ipv6_dhcp"]
    assert new_settings["ipv6_dns"] == settings["ipv6_dns"]
    assert new_settings["ipv6_gateways"] == settings["ipv6_gateways"]
    assert new_settings["ipv6_metric"] == settings["ipv6_metric"]

    return name, settings


@pytest.fixture(scope="function")
def enabled(ip, dummy_interface):
    """
    We'll make sure the device is enabled and make sure it's still enabled
    when we're done
    """
    index, name = dummy_interface
    ip.enable(name)
    assert ip.is_enabled(name)
    return name


@pytest.fixture(scope="function")
def disabled(ip, dummy_interface):
    index, name = dummy_interface
    ip.disable(name)
    assert ip.is_disabled(name)
    return name


def test_is_enabled(ip, enabled):
    """
    Test that is_enabled returns True for an administratively up interface.
    """
    assert ip.is_enabled(enabled)


def test_is_enabled_invalid_interface(ip):
    """
    Test that is_enabled raises CommandExecutionError for non-existent interfaces.
    """
    with pytest.raises(CommandExecutionError) as excinfo:
        ip.is_enabled("does-not-exist")
    assert (
        str(excinfo.value)
        == "Interface 'does-not-exist' not found or invalid response."
    )


def test_is_disabled(ip, disabled):
    """
    Test that is_disabled returns True for an administratively down interface.
    """
    assert ip.is_disabled(disabled)


def test_is_disabled_invalid_interface(ip):
    """
    Test that is_disabled raises CommandExecutionError for non-existent interfaces.
    """
    with pytest.raises(CommandExecutionError) as excinfo:
        ip.is_disabled("does-not-exist")
    assert (
        str(excinfo.value)
        == "Interface 'does-not-exist' not found or invalid response."
    )


def test_enable(ip, disabled):
    """
    Test that enable() brings a disabled interface back to administrative up state.
    """
    ip.enable(disabled)
    assert ip.is_enabled(disabled)


def test_disable(ip, enabled):
    """
    Test that disable() takes an enabled interface to administrative down state.
    """
    ip.disable(enabled)
    assert ip.is_disabled(enabled)


def test_get_subnet_length(ip):
    """
    Test converting dotted-decimal netmasks to CIDR lengths.
    """
    # Standard Class C
    assert ip.get_subnet_length("255.255.255.0") == 24

    # Standard Class B
    assert ip.get_subnet_length("255.255.0.0") == 16

    # Standard Class A
    assert ip.get_subnet_length("255.0.0.0") == 8

    # Subnetted masks
    assert ip.get_subnet_length("255.255.255.192") == 26
    assert ip.get_subnet_length("255.255.252.0") == 22

    # Edge cases
    assert ip.get_subnet_length("255.255.255.255") == 32
    assert ip.get_subnet_length("0.0.0.0") == 0


def test_get_subnet_length_errors(ip):
    """
    Test that invalid netmasks raise SaltInvocationError.
    """
    invalid_masks = [
        "255.255.255.256",  # Out of range
        "192.168.1.1",  # An IP, not a mask
        "255.255.0.255",  # Discontiguous mask
        "not-a-mask",  # Garbage string
    ]

    for mask in invalid_masks:
        with pytest.raises(SaltInvocationError) as excinfo:
            ip.get_subnet_length(mask)
        assert f"'{mask}' is not a valid netmask" in str(excinfo.value)


def test_set_static_ip_basic(ip, default_dhcp):
    """
    Test setting a basic static IP and gateway (overwriting existing).
    """
    name, settings = default_dhcp
    address = "10.1.2.3/24"
    gateway = "10.1.2.1"

    # Set the IP
    ret = ip.set_static_ip(iface=name, addr=address, gateway=gateway)

    # Verify return message
    assert ret["Address Info"] == "10.1.2.3/24"
    assert ret["Default Gateway"] == "10.1.2.1"

    result = ip.get_interface_new(name)[name]
    assert "10.1.2.3/24" == result["ipv4_address"]
    assert "10.1.2.1" == result["ipv4_gateways"][0]["ip"]


def test_set_static_ip_append(ip, default_dhcp):
    """
    Test appending an IP to an existing configuration.
    """
    name, settings = default_dhcp
    ip.set_static_ip(iface=name, addr="10.1.2.3/24")

    # Append a second IP
    ip.set_static_ip(iface=name, addr="10.1.2.4/24", append=True)

    result = ip.get_interface_new(name)[name]
    assert "10.1.2.3/24" in result["ipv4_address"]
    assert "10.1.2.4/24" in result["ipv4_address"]


def test_set_static_ip_append_duplicate_error(ip, default_dhcp):
    """
    Test that appending an existing IP raises CommandExecutionError.
    """
    name, settings = default_dhcp
    addr = "10.1.2.5/24"
    ip.set_static_ip(iface=name, addr=addr)
    assert ip.get_interface_new(name)[name]["ipv4_address"] == addr

    with pytest.raises(CommandExecutionError) as excinfo:
        ip.set_static_ip(iface=name, addr=addr, append=True)

    address, _ = addr.split("/") if "/" in addr else (addr, "24")
    msg = f"Address '{address}' already exists on '{name}'"
    assert excinfo.value.args[0] == msg


def test_set_static_ip_no_cidr_default(ip, default_dhcp):
    """
    Test that an IP without a CIDR defaults to /24.
    """
    name, settings = default_dhcp
    # The code specifically adds /24 if "/" is missing
    ip.set_static_ip(iface=name, addr="10.10.10.10")

    result = ip.get_interface_new(name)[name]
    assert "10.10.10.10/24" in result["ipv4_address"]


def test_set_static_ip_invalid_inputs(ip, dummy_interface):
    """
    Test validation for bad IP and Gateway strings.
    """
    index, name = dummy_interface

    with pytest.raises(SaltInvocationError):
        ip.set_static_ip(iface=name, addr="999.999.999.999")

    with pytest.raises(SaltInvocationError):
        ip.set_static_ip(iface=name, addr="10.1.1.1/24", gateway="not.an.ip")


def test_set_dhcp_ip_success(ip, default_static):
    """
    Test transitioning from a static IP to DHCP.
    """
    name, settings = default_static

    # 1. Start with a static IP to ensure we aren't already in DHCP mode
    ip.set_static_ip(iface=name, addr="10.1.2.3/24")
    assert ip.get_interface_new(name)[name]["ipv4_dhcp"] is False

    # 2. Run the DHCP setter
    ret = ip.set_dhcp_ip(iface=name)

    # 3. Verify return and actual state
    assert ret["DHCP enabled"] == "Yes"
    assert ip.get_interface_new(name)[name]["ipv4_dhcp"] is True


def test_set_dhcp_ip_already_enabled(ip, default_dhcp):
    """
    Test that calling set_dhcp_ip on an interface that already has DHCP
    enabled is a no-op and returns an empty dict.
    """
    name, settings = default_dhcp

    # Try to turn dhcp on (it's already on)
    ret = ip.set_dhcp_ip(iface=name)
    assert ret == {}


def test_set_dhcp_ip_invalid_interface(ip):
    """
    Test that set_dhcp_ip raises an exception when the interface does not exist.
    """
    with pytest.raises(Exception):
        ip.set_dhcp_ip(iface="ThisInterfaceDoesNotExist")


def test_set_static_dns_single(ip, dummy_interface):
    """
    Test setting a single static DNS server.
    """
    index, name = dummy_interface
    dns_target = ["1.1.1.1"]

    ret = ip.set_static_dns(name, *dns_target)

    assert ret["Interface"] == name
    # Ensure the DNS is set in the stack
    result = ip.get_interface_new(name)[name]
    assert "1.1.1.1" in result["ipv4_dns"]


def test_set_static_dns_multiple(ip, dummy_interface):
    """
    Test setting multiple DNS servers in specific order.
    """
    index, name = dummy_interface
    dns_targets = ["8.8.8.8", "8.8.4.4"]

    ret = ip.set_static_dns(name, *dns_targets)

    assert set(ret["DNS Server"]) == set(dns_targets)
    result = ip.get_interface_new(name)[name]
    assert all(dns in result["ipv4_dns"] for dns in dns_targets)


def test_set_static_dns_no_changes(ip, dummy_interface):
    """
    Test that passing 'None' or no addresses returns 'No Changes'.
    """
    index, name = dummy_interface
    ret = ip.set_static_dns(name, "None")
    assert ret["DNS Server"] == "No Changes"


def test_set_static_dns_already_set(ip, dummy_interface):
    """
    Test that setting the same DNS again returns an empty dict (idempotency).
    """
    index, name = dummy_interface
    dns = "9.9.9.9"

    # First set
    ip.set_static_dns(name, dns)

    # Ensure the DNS is set in the stack
    result = ip.get_interface_new(name)[name]
    assert "9.9.9.9" in result["ipv4_dns"]

    # Second set
    ret = ip.set_static_dns(name, dns)

    assert ret == {}


def test_set_static_dns_clear_via_list_string(ip, dummy_interface):
    """
    Test that passing '[]' calls set_dhcp_dns.
    """
    index, name = dummy_interface

    # 1. Set it to something static first
    ip.set_static_dns(name, "1.1.1.1")

    # 2. Call the clear logic (the real deal, no mocks)
    ret = ip.set_static_dns(name, "[]")

    # 3. Verify the real-world result
    assert ret["DNS Server"] == "DHCP (Empty)"
    result = ip.get_interface_new(name)[name]
    # Check that the static IP we set is gone
    assert "1.1.1.1" not in result.get("ipv4_dns", [])


def test_set_dhcp_dns_success(ip, dummy_interface):
    """
    Test transitioning from static DNS back to automatic (DHCP-sourced) DNS.

    Verifies that after the reset the previously configured static server is no
    longer present in the interface's DNS server list.
    """
    index, name = dummy_interface

    # 1. Start by setting a static DNS to ensure we aren't already in DHCP mode
    ip.set_static_dns(name, "1.1.1.1")

    result = ip.get_interface_new(name)[name]
    assert "1.1.1.1" in result["ipv4_dns"]

    # 2. Reset DNS to automatic
    ret = ip.set_dhcp_dns(iface=name)

    # 3. Verify return message and actual state
    assert ret["DNS Server"] == "DHCP (Empty)"
    assert ret["Interface"] == name

    result = ip.get_interface_new(name)[name]
    assert "1.1.1.1" not in result.get("ipv4_dns", [])


def test_set_dhcp_dns_already_enabled(ip, dummy_interface):
    """
    Test that calling set_dhcp_dns on an interface already using DHCP
    returns an empty dict (idempotency).
    """
    index, name = dummy_interface

    # Ensure it's in DHCP mode first
    ip.set_dhcp_dns(iface=name)

    # Call it again
    ret = ip.set_dhcp_dns(iface=name)
    assert ret == {}


def test_set_dhcp_dns_invalid_interface(ip):
    """
    Test that an invalid interface raises an error.
    """
    with pytest.raises(Exception):
        ip.set_dhcp_dns(iface="NonExistentInterface")


def test_set_dhcp_all(ip, dummy_interface):
    """
    Integration test to ensure both IP and DNS are reset to DHCP.
    """
    index, name = dummy_interface

    # 1. Manually "dirty" the interface with static settings
    ip.set_static_ip(iface=name, addr="10.1.2.3/24", gateway="10.1.2.1")
    ip.set_static_dns(name, "1.1.1.1")

    # 2. Run the "All" reset
    ret = ip.set_dhcp_all(iface=name)

    # 3. Verify the return structure
    assert ret["Interface"] == name
    assert ret["DHCP enabled"] == "Yes"
    assert ret["DNS Server"] == "DHCP"

    # 4. Verify the actual stack state via our getter
    result = ip.get_interface_new(name)[name]
    assert result["ipv4_dhcp"] is True
    # If your getter tracks DNS source, check that too.
    # Otherwise, ensure the static IP is gone.
    assert "10.1.2.3/24" not in result["ipv4_address"]


def test_get_default_gateway_success(ip):
    """
    Test that we can retrieve a gateway on a live system.
    Note: This assumes the test runner has internet access/a gateway.
    """
    try:
        gateway = ip.get_default_gateway()
        # Verify it looks like an IP address
        assert salt.utils.validate.net.ipv4_addr(gateway)
    except CommandExecutionError:
        pytest.skip("No default gateway found on this system.")


def test_get_default_gateway_selection(ip, dummy_interface):
    """
    Test that the function selects the gateway with the lowest metric.
    """
    index, name = dummy_interface

    # 1. Set a gateway with a high metric
    ip.set_interface(
        iface=name,
        ipv4_address="10.99.99.2/24",
        ipv4_gateways={"ip": "10.99.99.1", "metric": 1},
    )

    # 2. Check the gateway. On a test machine with no other internet,
    # this should return our dummy gateway.
    gateway = ip.get_default_gateway(iface=name)
    assert gateway == "10.99.99.1"


def test_get_default_gateway_no_route(ip):
    """
    Test that the function raises CommandExecutionError when no route is found,
    using unittest.mock to simulate an empty PowerShell return.
    """
    # We patch the 'run' method of the PowerShellSession class
    # located within the win_pwsh utility module.
    with patch("salt.utils.win_pwsh.PowerShellSession.run") as mock_run:
        # Simulate PowerShell returning nothing (empty string or None)
        mock_run.return_value = ""

        with pytest.raises(CommandExecutionError) as excinfo:
            ip.get_default_gateway()

        assert "Unable to find default gateway" in str(excinfo.value)

        # Optional: Verify that the correct PowerShell command was attempted
        # We check the first argument of the last call to mock_run
        called_cmd = mock_run.call_args[0][0]
        assert "Get-NetRoute" in called_cmd
        assert "0.0.0.0/0" in called_cmd


def test_get_interface_static(ip, default_static):
    """
    Test that get_interface returns the correct legacy-format keys for a
    statically configured interface (DHCP disabled, static IP/DNS/WINS/gateway).
    """
    name, settings = default_static
    result = ip.get_interface(name)[name]
    assert result["DHCP enabled"] == "No"
    assert result["Default Gateway"] == settings["ipv4_gateways"][0]["ip"]
    assert result["InterfaceMetric"] == settings["ipv4_metric"]
    assert result["Register with which suffix"] == "Primary only"
    assert result["Statically Configured DNS Servers"] == settings["ipv4_dns"]
    assert result["Statically Configured WINS Servers"] == settings["ipv4_wins"]
    ip_info = ipaddress.IPv4Interface(settings["ipv4_address"])
    expected_ip_addrs = [
        {
            "IP Address": ip_info._string_from_ip_int(ip_info._ip),
            "Netmask": str(ip_info.netmask),
            "Subnet": str(ip_info.network),
        },
    ]
    assert result["ip_addrs"] == expected_ip_addrs


def test_get_interface_dhcp(ip, default_dhcp):
    """
    Test that get_interface returns the correct legacy-format keys for an
    interface configured to obtain its IP and DNS from DHCP.
    """
    name, settings = default_dhcp
    result = ip.get_interface(name)[name]
    assert result["DHCP enabled"] == "Yes"
    assert result["Register with which suffix"] == "Primary only"
    assert result["DNS servers configured through DHCP"] == ["None"]
    assert result["WINS servers configured through DHCP"] == ["None"]


def test_get_interface_new_static(ip, default_static):
    """
    Test that get_interface_new returns the full structured configuration for a
    statically configured interface, including both IPv4 and IPv6 addresses,
    gateways, DNS, WINS, and metric values.
    """
    name, settings = default_static
    result = ip.get_interface_new(name)[name]
    assert result["alias"] == name
    assert result["description"] == "Microsoft KM-TEST Loopback Adapter"
    for setting in settings:
        assert result[setting] == settings[setting]


def test_get_interface_new_dhcp(ip, default_dhcp):
    """
    Test that get_interface_new returns the correct structured configuration for
    an interface configured to use DHCP for both IPv4 and IPv6.
    """
    name, settings = default_dhcp
    result = ip.get_interface_new(name)[name]
    assert result["alias"] == name
    assert result["description"] == "Microsoft KM-TEST Loopback Adapter"
    for setting in settings:
        assert result[setting] == settings[setting]


@pytest.mark.parametrize(
    "gateways_input, expected_gateways",
    [
        # Case 1: Single string gateway — metric falls back to ipv4_metric (10)
        ("192.168.1.1", [{"ip": "192.168.1.1", "metric": 10}]),
        # Case 2: List of string gateways — metric falls back to ipv4_metric (10)
        (["192.168.1.1"], [{"ip": "192.168.1.1", "metric": 10}]),
        # Case 3: Single dict with custom metric
        ({"ip": "192.168.1.1", "metric": 5}, [{"ip": "192.168.1.1", "metric": 5}]),
        # Case 4: List of dicts
        ([{"ip": "192.168.1.1", "metric": 99}], [{"ip": "192.168.1.1", "metric": 99}]),
    ],
)
def test_set_interface_flexible_gateways(
    ip, dummy_interface, gateways_input, expected_gateways
):
    """
    Test that set_interface accepts gateways in all supported input formats
    (plain string, list of strings, dict, list of dicts) and that
    get_interface_new always returns them as a normalized list of
    ``{"ip": ..., "metric": ...}`` dicts.  When no per-gateway metric is
    supplied the interface-level ``ipv4_metric`` is used as the fallback.
    """
    index, name = dummy_interface

    settings = {
        "ipv4_gateways": gateways_input,
        "ipv4_metric": 10,  # The fallback metric
        "ipv4_dhcp": False,
        "ipv4_address": "192.168.1.200/24",
    }

    ip.set_interface(iface=name, **settings)
    result = ip.get_interface_new(name)[name]

    # Verify the gateway matches the expected dictionary format
    # Note: result["ipv4_gateways"] will be a list of dicts based on our getter
    assert result["ipv4_gateways"] == expected_gateways


def test_ipv4_cidr_defaulting(ip, dummy_interface):
    """
    Test that IPv4 addresses supplied without a prefix length default to /24,
    while addresses that already include a prefix keep their original length.
    """
    index, name = dummy_interface

    # Pass a list of naked IPs and one with CIDR
    ips = ["172.16.0.5", "172.16.0.6/16"]
    ip.set_interface(iface=name, ipv4_address=ips, ipv4_dhcp=False)

    result = ip.get_interface_new(name)[name]

    # Check that the first one defaulted to /24 and the second kept its /16
    assert "172.16.0.5/24" in result["ipv4_address"]
    assert "172.16.0.6/16" in result["ipv4_address"]


def test_dhcp_with_manual_metric(ip, dummy_interface):
    """
    Test that an explicit interface metric can be set alongside DHCP,
    confirming that metric and DHCP mode are independent settings.
    """
    index, name = dummy_interface

    # Enable DHCP but force a very high metric
    ip.set_interface(iface=name, ipv4_dhcp=True, ipv4_metric=500)

    result = ip.get_interface_new(name)[name]
    assert result["ipv4_dhcp"] is True
    assert result["ipv4_metric"] == 500


def test_interface_hardware_and_dns_suffix(ip, dummy_interface):
    """
    Test that MTU and the connection-specific DNS suffix can be set and are
    accurately reflected by get_interface_new.
    """
    index, name = dummy_interface

    ip.set_interface(iface=name, mtu=1450, dns_suffix="test.saltstack.com")

    res = ip.get_interface_new(iface=name)[name]
    assert res["mtu"] == 1450
    assert res["dns_suffix"] == "test.saltstack.com"


def test_interface_forwarding_toggles(ip, dummy_interface):
    """
    Test that IP forwarding can be independently enabled and disabled for both
    the IPv4 and IPv6 stacks, and that the change is reflected by get_interface_new.
    """
    index, name = dummy_interface

    # 1. Enable forwarding on both stacks
    ip.set_interface(iface=name, ipv4_forwarding=True, ipv6_forwarding=True)

    res = ip.get_interface_new(iface=name)[name]
    assert res["ipv4_forwarding"] is True
    assert res["ipv6_forwarding"] is True

    # 2. Disable and verify
    ip.set_interface(iface=name, ipv4_forwarding=False, ipv6_forwarding=False)
    res = ip.get_interface_new(iface=name)[name]
    assert res["ipv4_forwarding"] is False
    assert res["ipv6_forwarding"] is False


def test_interface_rename_persistence(ip, dummy_interface):
    """
    Test that renaming an interface via set_interface (alias parameter) is
    persisted: the new name is discoverable by get_interface_new and the
    InterfaceIndex remains unchanged.  The original name is restored in the
    finally block so subsequent tests are not affected.
    """
    index, name = dummy_interface
    new_name = "Salt-Rename-Test"

    try:
        # 1. Rename via the setter
        ip.set_interface(iface=name, alias=new_name)

        # 2. Verify the getter can find it by the NEW name
        res = ip.get_interface_new(iface=new_name)[new_name]
        assert res["alias"] == new_name
        assert res["index"] == index

    finally:
        # 3. Clean up: Rename it back to the original fixture name
        ip.set_interface(iface=new_name, alias=name)


def test_interface_ip_append(ip, dummy_interface):
    """
    Test that passing append=True to set_interface adds an additional IP
    address without removing the previously configured one.
    """
    index, name = dummy_interface
    primary_ip = "10.10.10.10/24"
    secondary_ip = "10.10.10.11/24"

    # 1. Set first IP
    ip.set_interface(iface=name, ipv4_address=primary_ip, ipv4_dhcp=False)

    # 2. Append second IP
    ip.set_interface(iface=name, ipv4_address=secondary_ip, append=True)

    res = ip.get_interface_new(iface=name)[name]
    # Verify BOTH IPs exist in the list
    assert primary_ip in res["ipv4_address"]
    assert secondary_ip in res["ipv4_address"]


def test_interface_invalid_mtu_raises(ip, dummy_interface):
    """
    Test that set_interface raises SaltInvocationError when an MTU value
    outside the supported range (576–9000) is provided.
    """
    index, name = dummy_interface

    with pytest.raises(SaltInvocationError):
        ip.set_interface(iface=name, mtu=9999)


def test_set_interface_atomic_multi_change(ip, dummy_interface):
    """
    Test that set_interface applies multiple unrelated settings (MTU, IPv6
    forwarding, DNS suffix, interface metric) atomically in a single call, and
    that all changes are reflected correctly by get_interface_new.
    """
    index, name = dummy_interface

    # Mix hardware, protocol, and client settings
    ip.set_interface(
        iface=name,
        mtu=1400,
        ipv6_forwarding=True,
        dns_suffix="atomic.test",
        ipv4_metric=42,
    )

    res = ip.get_interface_new(iface=name)[name]
    assert res["mtu"] == 1400
    assert res["ipv6_forwarding"] is True
    assert res["dns_suffix"] == "atomic.test"
    assert res["ipv4_metric"] == 42


def test_set_interface_protocol_binding(ip, dummy_interface):
    """
    Test that the IPv6 protocol binding (ms_tcpip6) can be disabled and
    re-enabled via set_interface, and that the change is visible through
    the ipv6_enabled field in get_interface_new.
    """
    index, name = dummy_interface

    # Disable IPv6 binding
    ip.set_interface(iface=name, ipv6_enabled=False)
    res = ip.get_interface_new(iface=name)[name]
    assert res["ipv6_enabled"] is False

    # Re-enable
    ip.set_interface(iface=name, ipv6_enabled=True)
    res = ip.get_interface_new(iface=name)[name]
    assert res["ipv6_enabled"] is True


def test_set_interface_dns_registration(ip, dummy_interface):
    """
    Test that the dns_register flag can be toggled via set_interface, controlling
    whether the interface registers its addresses in DNS with the computer's
    primary DNS suffix.
    """
    index, name = dummy_interface

    # Disable registration
    ip.set_interface(iface=name, dns_register=False)
    res = ip.get_interface_new(iface=name)[name]
    assert res["dns_register"] is False

    # Enable registration
    ip.set_interface(iface=name, dns_register=True)
    res = ip.get_interface_new(iface=name)[name]
    assert res["dns_register"] is True


def test_interface_protocol_binding_toggles(ip, dummy_interface):
    """
    Test that the IPv4 and IPv6 protocol bindings can each be disabled
    independently and then re-enabled together, verifying the state after each
    change via get_interface_new.
    """
    index, name = dummy_interface

    # 1. Disable IPv4 Stack
    ip.set_interface(iface=name, ipv4_enabled=False)
    res = ip.get_interface_new(iface=name)[name]
    assert res["ipv4_enabled"] is False

    # 2. Disable IPv6 Stack
    ip.set_interface(iface=name, ipv6_enabled=False)
    res = ip.get_interface_new(iface=name)[name]
    assert res["ipv6_enabled"] is False

    # 3. Re-enable both for cleanup
    ip.set_interface(iface=name, ipv4_enabled=True, ipv6_enabled=True)
    res = ip.get_interface_new(iface=name)[name]
    assert res["ipv4_enabled"] is True
    assert res["ipv6_enabled"] is True
