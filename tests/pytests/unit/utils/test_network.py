import salt.utils.network


def test_junos_ifconfig_output_parsing():
    ret = salt.utils.network._junos_interfaces_ifconfig(
        "inet mtu 0 local=" + " " * 3456
    )
    assert ret == {"inet": {"up": False}}
