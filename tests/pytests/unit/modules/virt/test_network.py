import salt.modules.virt as virt
from salt._compat import ElementTree as ET


def test_network():
    """
    Test virt._get_net_xml()
    """
    xml_data = virt._gen_net_xml("network", "main", "bridge", "openvswitch")
    root = ET.fromstring(xml_data)
    assert "network" == root.find("name").text
    assert "main" == root.find("bridge").attrib["name"]
    assert "bridge" == root.find("forward").attrib["mode"]
    assert "openvswitch" == root.find("virtualport").attrib["type"]


def test_network_nat():
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
            }
        ],
    )
    root = ET.fromstring(xml_data)
    assert "network" == root.find("name").text
    assert "main" == root.find("bridge").attrib["name"]
    assert "nat" == root.find("forward").attrib["mode"]
    assert "24" == root.find("./ip[@address='192.168.2.0']").attrib["prefix"]
    assert "ipv4" == root.find("./ip[@address='192.168.2.0']").attrib["family"]
    assert (
        "192.168.2.25"
        == root.find(
            "./ip[@address='192.168.2.0']/dhcp/range[@start='192.168.2.10']"
        ).attrib["end"]
    )
    assert (
        "192.168.2.125"
        == root.find(
            "./ip[@address='192.168.2.0']/dhcp/range[@start='192.168.2.110']"
        ).attrib["end"]
    )
