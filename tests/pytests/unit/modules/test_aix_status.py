import logging

import pytest

import salt.modules.status as status
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():

    return {
        status: {
            "__grains__": {
                "ip4_interfaces": {
                    "en0": ["129.40.94.58"],
                    "en1": ["172.24.94.58"],
                    "lo0": ["127.0.0.1"],
                },
                "ip6_interfaces": {"en0": [], "en1": [], "lo0": ["1"]},
                "kernel": "AIX",
                "osarch": "PowerPC_POWER8",
                "os": "AIX",
                "os_family": "AIX",
                "osmajorrelease": 7,
            },
        },
    }


def test_netdev():
    """
    Test status.netdev for AIX

    :return:
    """
    # Output from netstat -i -n -I <en0|en1|lo0> -f inet
    netstat_inet4_en0 = """Name   Mtu   Network     Address                 Ipkts     Ierrs        Opkts     Oerrs  Coll
en0    1500  link#2      fa.41.f5.e9.bd.20  1523125     0   759364     0     0
en0    1500  129.40.94.5 129.40.94.58      1523125     0   759364     0     0
"""

    netstat_inet4_en1 = """Name   Mtu   Network     Address                 Ipkts     Ierrs        Opkts     Oerrs  Coll
en1    1500  link#3      fa.41.f5.e9.bd.21     1089     0      402     0     0
en1    1500  172.24.94.5 172.24.94.58         1089     0      402     0     0
"""

    netstat_inet4_lo0 = """Name   Mtu   Network     Address                 Ipkts     Ierrs        Opkts     Oerrs  Coll
lo0    16896 link#1                          25568     0    25568     0     0
lo0    16896 127         127.0.0.1           25568     0    25568     0     0
"""

    # Output from netstat -i -n -I <en0|en1|lo0> -f inet6
    netstat_inet6_en0 = """Name   Mtu   Network     Address                 Ipkts     Ierrs        Opkts     Oerrs  Coll
en0    1500  link#2      fa.41.f5.e9.bd.20  1523160     0   759397     0     0
"""

    netstat_inet6_en1 = """Name   Mtu   Network     Address                 Ipkts     Ierrs        Opkts     Oerrs  Coll
en1    1500  link#3      fa.41.f5.e9.bd.21     1089     0      402     0     0
"""

    netstat_inet6_lo0 = """Name   Mtu   Network     Address                 Ipkts     Ierrs        Opkts     Oerrs  Coll
lo0    16896 link#1                          25611     0    25611     0     0
lo0    16896 ::1%1                           25611     0    25611     0     0
"""

    # allow en0, en1 and lo0 for ipv4 and ipv6
    netstats_out = MagicMock(
        side_effect=[
            netstat_inet4_en0,
            netstat_inet6_en0,
            netstat_inet4_en1,
            netstat_inet6_en1,
            netstat_inet4_lo0,
            netstat_inet6_lo0,
            netstat_inet4_en0,
            netstat_inet6_en0,
            netstat_inet4_en1,
            netstat_inet6_en1,
            netstat_inet4_lo0,
            netstat_inet6_lo0,
        ]
    )

    with patch.dict(
        status.__grains__,
        {
            "osarch": "PowerPC_POWER8",
            "ip4_interfaces": {
                "en0": ["129.40.94.58"],
                "en1": ["172.24.94.58"],
                "lo0": ["127.0.0.1"],
            },
            "ip6_interfaces": {
                "en0": [],
                "en1": [],
                "lo0": ["::1"],
            },
            "kernel": "AIX",
        },
    ), patch.dict(status.__salt__, {"cmd.run": netstats_out}):
        netdev_out = status.netdev()
        assert netstats_out.call_count == 12
        netstats_out.assert_any_call("netstat -i -n -I en0 -f inet")
        netstats_out.assert_any_call("netstat -i -n -I en1 -f inet")
        netstats_out.assert_any_call("netstat -i -n -I lo0 -f inet")
        netstats_out.assert_any_call("netstat -i -n -I en0 -f inet6")
        netstats_out.assert_any_call("netstat -i -n -I en1 -f inet6")
        netstats_out.assert_any_call("netstat -i -n -I lo0 -f inet6")
        expected = {
            "en0": [
                {
                    "ipv4": {
                        "Mtu": "1500",
                        "Network": "129.40.94.5",
                        "Address": "129.40.94.58",
                        "Ipkts": "1523125",
                        "Ierrs": "0",
                        "Opkts": "759364",
                        "Oerrs": "0",
                        "Coll": "0",
                    }
                }
            ],
            "en1": [
                {
                    "ipv4": {
                        "Mtu": "1500",
                        "Network": "172.24.94.5",
                        "Address": "172.24.94.58",
                        "Ipkts": "1089",
                        "Ierrs": "0",
                        "Opkts": "402",
                        "Oerrs": "0",
                        "Coll": "0",
                    }
                }
            ],
            "lo0": [
                {
                    "ipv4": {
                        "Mtu": "16896",
                        "Network": "127",
                        "Address": "127.0.0.1",
                        "Ipkts": "25568",
                        "Ierrs": "0",
                        "Opkts": "25568",
                        "Oerrs": "0",
                        "Coll": "0",
                    }
                },
                {
                    "ipv6": {
                        "Mtu": "16896",
                        "Network": "::1%1",
                        "Address": "25611",
                        "Ipkts": "0",
                        "Ierrs": "25611",
                        "Opkts": "0",
                        "Oerrs": "0",
                    }
                },
            ],
        }
        assert netdev_out == expected
