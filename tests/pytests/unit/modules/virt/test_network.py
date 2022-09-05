import xml.etree.ElementTree as ET

import pytest

import salt.modules.virt as virt
import salt.utils.xmlutil as xmlutil

from .conftest import loader_modules_config
from .test_helpers import assert_called, assert_xml_equals, strip_xml


@pytest.fixture
def configure_loader_modules():
    return loader_modules_config()


def test_gen_xml():
    """
    Test virt._get_net_xml()
    """
    xml_data = virt._gen_net_xml("network", "main", "bridge", "openvswitch")
    root = ET.fromstring(xml_data)
    assert root.find("name").text == "network"
    assert root.find("bridge").attrib["name"] == "main"
    assert root.find("forward").attrib["mode"] == "bridge"
    assert root.find("virtualport").attrib["type"] == "openvswitch"


def test_gen_xml_nat():
    """
    Test virt._get_net_xml() in a nat setup
    """
    xml_data = virt._gen_net_xml(
        "network",
        "main",
        "nat",
        None,
        ip_configs=[
            {
                "cidr": "192.168.2.0/24",
                "dhcp_ranges": [
                    {"start": "192.168.2.10", "end": "192.168.2.25"},
                    {"start": "192.168.2.110", "end": "192.168.2.125"},
                ],
                "hosts": {
                    "192.168.2.10": {
                        "mac": "00:16:3e:77:e2:ed",
                        "name": "foo.example.com",
                    },
                },
                "bootp": {"file": "pxeboot.img", "server": "192.168.2.1"},
                "tftp": "/path/to/tftp",
            },
            {
                "cidr": "2001:db8:ca2:2::/64",
                "hosts": {
                    "2001:db8:ca2:2:3::1": {"name": "paul"},
                    "2001:db8:ca2:2:3::2": {
                        "id": "0:3:0:1:0:16:3e:11:22:33",
                        "name": "ralph",
                    },
                },
            },
        ],
        nat={
            "address": {"start": "1.2.3.4", "end": "1.2.3.10"},
            "port": {"start": 500, "end": 1000},
        },
        domain={"name": "acme.lab", "localOnly": True},
        mtu=9000,
    )
    root = ET.fromstring(xml_data)
    assert root.find("name").text == "network"
    assert root.find("bridge").attrib["name"] == "main"
    assert root.find("forward").attrib["mode"] == "nat"
    expected_ipv4 = ET.fromstring(
        """
        <ip family='ipv4' address='192.168.2.1' prefix='24'>
          <dhcp>
            <range start='192.168.2.10' end='192.168.2.25'/>
            <range start='192.168.2.110' end='192.168.2.125'/>
            <host ip='192.168.2.10' mac='00:16:3e:77:e2:ed' name='foo.example.com'/>
            <bootp file='pxeboot.img' server='192.168.2.1'/>
          </dhcp>
          <tftp root='/path/to/tftp'/>
        </ip>
        """
    )
    assert_xml_equals(root.find("./ip[@address='192.168.2.1']"), expected_ipv4)

    expected_ipv6 = ET.fromstring(
        """
        <ip family='ipv6' address='2001:db8:ca2:2::1' prefix='64'>
          <dhcp>
            <host ip='2001:db8:ca2:2:3::1' name='paul'/>
            <host ip='2001:db8:ca2:2:3::2' id='0:3:0:1:0:16:3e:11:22:33' name='ralph'/>
          </dhcp>
        </ip>
        """
    )
    assert_xml_equals(root.find("./ip[@address='2001:db8:ca2:2::1']"), expected_ipv6)

    actual_nat = ET.tostring(xmlutil.strip_spaces(root.find("./forward/nat")))
    expected_nat = strip_xml(
        """
        <nat>
          <address start='1.2.3.4' end='1.2.3.10'/>
          <port start='500' end='1000'/>
        </nat>
        """
    )
    assert actual_nat == expected_nat

    assert root.find("./domain").attrib == {"name": "acme.lab", "localOnly": "yes"}
    assert root.find("mtu").get("size") == "9000"


def test_gen_xml_dns():
    """
    Test virt._get_net_xml() with DNS configuration
    """
    xml_data = virt._gen_net_xml(
        "network",
        "main",
        "nat",
        None,
        ip_configs=[
            {
                "cidr": "192.168.2.0/24",
                "dhcp_ranges": [{"start": "192.168.2.10", "end": "192.168.2.25"}],
            }
        ],
        dns={
            "forwarders": [
                {"domain": "example.com", "addr": "192.168.1.1"},
                {"addr": "8.8.8.8"},
                {"domain": "www.example.com"},
            ],
            "txt": {
                "host.widgets.com.": "printer=lpr5",
                "example.com.": "reserved for doc",
            },
            "hosts": {"192.168.1.2": ["mirror.acme.lab", "test.acme.lab"]},
            "srvs": [
                {
                    "name": "srv1",
                    "protocol": "tcp",
                    "domain": "test-domain-name",
                    "target": ".",
                    "port": 1024,
                    "priority": 10,
                    "weight": 10,
                },
                {"name": "srv2", "protocol": "udp"},
            ],
        },
    )
    root = ET.fromstring(xml_data)
    expected_xml = ET.fromstring(
        """
        <dns>
          <forwarder domain='example.com' addr='192.168.1.1'/>
          <forwarder addr='8.8.8.8'/>
          <forwarder domain='www.example.com'/>
          <txt name='example.com.' value='reserved for doc'/>
          <txt name='host.widgets.com.' value='printer=lpr5'/>
          <host ip='192.168.1.2'>
            <hostname>mirror.acme.lab</hostname>
            <hostname>test.acme.lab</hostname>
          </host>
          <srv service='srv1' protocol='tcp' port='1024' target='.' priority='10' weight='10' domain='test-domain-name'/>
          <srv service='srv2' protocol='udp'/>
        </dns>
        """
    )
    assert_xml_equals(root.find("./dns"), expected_xml)


def test_gen_xml_isolated():
    """
    Test the virt._gen_net_xml() function for an isolated network
    """
    xml_data = virt._gen_net_xml("network", "main", None, None)
    assert ET.fromstring(xml_data).find("forward") is None


def test_gen_xml_passthrough_interfaces():
    """
    Test the virt._gen_net_xml() function for a passthrough forward mode
    """
    xml_data = virt._gen_net_xml(
        "network",
        "virbr0",
        "passthrough",
        None,
        interfaces="eth10 eth11 eth12",
    )
    root = ET.fromstring(xml_data)
    assert root.find("forward").get("mode") == "passthrough"
    assert [n.get("dev") for n in root.findall("forward/interface")] == [
        "eth10",
        "eth11",
        "eth12",
    ]


def test_gen_xml_hostdev_addresses():
    """
    Test the virt._gen_net_xml() function for a hostdev forward mode with PCI addresses
    """
    xml_data = virt._gen_net_xml(
        "network",
        "virbr0",
        "hostdev",
        None,
        addresses="0000:04:00.1 0000:e3:01.2",
    )
    root = ET.fromstring(xml_data)
    expected_forward = ET.fromstring(
        """
        <forward mode='hostdev' managed='yes'>
          <address type='pci' domain='0x0000' bus='0x04' slot='0x00' function='0x1'/>
          <address type='pci' domain='0x0000' bus='0xe3' slot='0x01' function='0x2'/>
        </forward>
        """
    )
    assert_xml_equals(root.find("./forward"), expected_forward)


def test_gen_xml_hostdev_pf():
    """
    Test the virt._gen_net_xml() function for a hostdev forward mode with physical function
    """
    xml_data = virt._gen_net_xml(
        "network", "virbr0", "hostdev", None, physical_function="eth0"
    )
    root = ET.fromstring(xml_data)
    expected_forward = strip_xml(
        """
        <forward mode='hostdev' managed='yes'>
          <pf dev='eth0'/>
        </forward>
        """
    )
    actual_forward = ET.tostring(xmlutil.strip_spaces(root.find("./forward")))
    assert actual_forward == expected_forward


def test_gen_xml_openvswitch():
    """
    Test the virt._gen_net_xml() function for an openvswitch setup with virtualport and vlan
    """
    xml_data = virt._gen_net_xml(
        "network",
        "ovsbr0",
        "bridge",
        {
            "type": "openvswitch",
            "parameters": {"interfaceid": "09b11c53-8b5c-4eeb-8f00-d84eaa0aaa4f"},
        },
        tag={
            "trunk": True,
            "tags": [{"id": 42, "nativeMode": "untagged"}, {"id": 47}],
        },
    )
    expected_xml = ET.fromstring(
        """
        <network>
          <name>network</name>
          <bridge name='ovsbr0'/>
          <forward mode='bridge'/>
          <virtualport type='openvswitch'>
            <parameters interfaceid='09b11c53-8b5c-4eeb-8f00-d84eaa0aaa4f'/>
          </virtualport>
          <vlan trunk='yes'>
            <tag id='42' nativeMode='untagged'/>
            <tag id='47'/>
          </vlan>
        </network>
        """
    )
    assert_xml_equals(ET.fromstring(xml_data), expected_xml)


@pytest.mark.parametrize(
    "autostart, start",
    [(True, True), (False, True), (False, False)],
)
def test_define(make_mock_network, autostart, start):
    """
    Test the virt.defined function
    """
    # We create a network mock to fake the autostart flag at start
    # and allow checking everything went fine. This doesn't mess up with the network define part
    mock_network = make_mock_network("<network><name>default</name></network>")
    assert virt.network_define(
        "default",
        "test-br0",
        "nat",
        ipv4_config={
            "cidr": "192.168.124.0/24",
            "dhcp_ranges": [{"start": "192.168.124.2", "end": "192.168.124.254"}],
        },
        autostart=autostart,
        start=start,
    )

    expected_xml = strip_xml(
        """
        <network>
          <name>default</name>
          <bridge name='test-br0'/>
          <forward mode='nat'/>
          <ip family='ipv4' address='192.168.124.1' prefix='24'>
            <dhcp>
              <range start='192.168.124.2' end='192.168.124.254'/>
            </dhcp>
          </ip>
        </network>
        """
    )
    define_mock = virt.libvirt.openAuth().networkDefineXML
    assert strip_xml(define_mock.call_args[0][0]) == expected_xml

    if autostart:
        mock_network.setAutostart.assert_called_with(1)
    else:
        mock_network.setAutostart.assert_not_called()

    assert_called(mock_network.create, autostart or start)


def test_update_nat_nochange(make_mock_network):
    """
    Test updating a NAT network without changes
    """
    net_mock = make_mock_network(
        """
        <network>
          <name>default</name>
          <uuid>d6c95a31-16a2-473a-b8cd-7ad2fe2dd855</uuid>
          <forward mode='nat'>
            <nat>
              <port start='1024' end='65535'/>
            </nat>
          </forward>
          <bridge name='virbr0' stp='on' delay='0'/>
          <mac address='52:54:00:cd:49:6b'/>
          <domain name='my.lab' localOnly='yes'/>
          <ip address='192.168.122.1' netmask='255.255.255.0'>
            <dhcp>
              <range start='192.168.122.2' end='192.168.122.254'/>
              <host mac='52:54:00:46:4d:9e' name='mirror' ip='192.168.122.136'/>
              <bootp file='pxelinux.0' server='192.168.122.110'/>
            </dhcp>
          </ip>
        </network>
        """
    )
    assert not virt.network_update(
        "default",
        None,
        "nat",
        ipv4_config={
            "cidr": "192.168.122.0/24",
            "dhcp_ranges": [{"start": "192.168.122.2", "end": "192.168.122.254"}],
            "hosts": {
                "192.168.122.136": {"mac": "52:54:00:46:4d:9e", "name": "mirror"},
            },
            "bootp": {"file": "pxelinux.0", "server": "192.168.122.110"},
        },
        domain={"name": "my.lab", "localOnly": True},
        nat={"port": {"start": 1024, "end": "65535"}},
    )
    define_mock = virt.libvirt.openAuth().networkDefineXML
    define_mock.assert_not_called()


@pytest.mark.parametrize(
    "test, netmask",
    [(True, "netmask='255.255.255.0'"), (True, "prefix='24'"), (False, "prefix='24'")],
)
def test_update_nat_change(make_mock_network, test, netmask):
    """
    Test updating a NAT network with changes
    """
    net_mock = make_mock_network(
        """
        <network>
          <name>default</name>
          <uuid>d6c95a31-16a2-473a-b8cd-7ad2fe2dd855</uuid>
          <forward mode='nat'/>
          <bridge name='virbr0' stp='on' delay='0'/>
          <mac address='52:54:00:cd:49:6b'/>
          <domain name='my.lab' localOnly='yes'/>
          <ip address='192.168.122.1' {}>
            <dhcp>
              <range start='192.168.122.2' end='192.168.122.254'/>
            </dhcp>
          </ip>
        </network>
        """.format(
            netmask
        )
    )
    assert virt.network_update(
        "default",
        "test-br0",
        "nat",
        ipv4_config={
            "cidr": "192.168.124.0/24",
            "dhcp_ranges": [{"start": "192.168.124.2", "end": "192.168.124.254"}],
        },
        test=test,
    )
    define_mock = virt.libvirt.openAuth().networkDefineXML
    assert_called(define_mock, not test)

    if not test:
        # Test the passed new XML
        expected_xml = strip_xml(
            """
            <network>
              <name>default</name>
              <mac address='52:54:00:cd:49:6b'/>
              <uuid>d6c95a31-16a2-473a-b8cd-7ad2fe2dd855</uuid>
              <bridge name='test-br0'/>
              <forward mode='nat'/>
              <ip family='ipv4' address='192.168.124.1' prefix='24'>
                <dhcp>
                  <range start='192.168.124.2' end='192.168.124.254'/>
                </dhcp>
              </ip>
            </network>
            """
        )
        assert strip_xml(define_mock.call_args[0][0]) == expected_xml


@pytest.mark.parametrize("change", [True, False], ids=["changed", "unchanged"])
def test_update_hostdev_pf(make_mock_network, change):
    """
    Test updating a hostdev network without changes
    """
    net_mock = make_mock_network(
        """
        <network connections='1'>
          <name>test-hostdev</name>
          <uuid>51d0aaa5-7530-4c60-8498-5bc3ab8c655b</uuid>
          <forward mode='hostdev' managed='yes'>
            <pf dev='eth0'/>
            <address type='pci' domain='0x0000' bus='0x3d' slot='0x02' function='0x0'/>
            <address type='pci' domain='0x0000' bus='0x3d' slot='0x02' function='0x1'/>
          </forward>
        </network>
        """
    )
    assert (
        virt.network_update(
            "test-hostdev",
            None,
            "hostdev",
            physical_function="eth0" if not change else "eth1",
        )
        == change
    )
    define_mock = virt.libvirt.openAuth().networkDefineXML
    if change:
        define_mock.assert_called()
    else:
        define_mock.assert_not_called()
