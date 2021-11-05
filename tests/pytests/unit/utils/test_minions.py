import salt.utils.minions
import salt.utils.network
from tests.support.mock import patch


def test_connected_ids():
    """
    test ckminion connected_ids when
    local_port_tcp returns 127.0.0.1
    """
    opts = {
        "publish_port": 4505,
        "detect_remote_minions": False,
        "minion_data_cache": True,
    }
    minion = "minion"
    ips = {"203.0.113.1", "203.0.113.2", "127.0.0.1"}
    mdata = {"grains": {"ipv4": ips, "ipv6": []}}
    patch_net = patch("salt.utils.network.local_port_tcp", return_value=ips)
    patch_list = patch("salt.cache.Cache.list", return_value=[minion])
    patch_fetch = patch("salt.cache.Cache.fetch", return_value=mdata)
    ckminions = salt.utils.minions.CkMinions(opts)
    with patch_net, patch_list, patch_fetch:
        ret = ckminions.connected_ids()
        assert ret == {minion}


def test_connected_ids_remote_minions():
    """
    test ckminion connected_ids when
    detect_remote_minions is set
    """
    opts = {
        "publish_port": 4505,
        "detect_remote_minions": True,
        "remote_minions_port": 22,
        "minion_data_cache": True,
    }
    minion = "minion"
    minion2 = "minion2"
    minion2_ip = "192.168.2.10"
    minion_ips = {"203.0.113.1", "203.0.113.2", "127.0.0.1"}
    mdata = {"grains": {"ipv4": minion_ips, "ipv6": []}}
    mdata2 = {"grains": {"ipv4": [minion2_ip], "ipv6": []}}
    patch_net = patch("salt.utils.network.local_port_tcp", return_value=minion_ips)
    patch_remote_net = patch(
        "salt.utils.network.remote_port_tcp", return_value={minion2_ip}
    )
    patch_list = patch("salt.cache.Cache.list", return_value=[minion, minion2])
    patch_fetch = patch("salt.cache.Cache.fetch", side_effect=[mdata, mdata2])
    ckminions = salt.utils.minions.CkMinions(opts)
    with patch_net, patch_list, patch_fetch, patch_remote_net:
        ret = ckminions.connected_ids()
        assert ret == {minion2, minion}
