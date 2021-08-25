import salt.utils.minions
import salt.utils.network
from tests.support.mock import patch


def test_connected_ids():
    """
    test ckminion connected_ids when
    local_port_tcp returns 127.0.0.1
    """
    opts = {"publish_port": 4505, "detect_remote_minions": False}
    minion = "minion"
    ip = salt.utils.network.ip_addrs()
    mdata = {"grains": {"ipv4": ip, "ipv6": []}}
    ckminions = salt.utils.minions.CkMinions({"minion_data_cache": True})
    patch_net = patch("salt.utils.network.local_port_tcp", return_value={"127.0.0.1"})
    patch_list = patch("salt.cache.Cache.list", return_value=[minion])
    patch_fetch = patch("salt.cache.Cache.fetch", return_value=mdata)
    with patch.dict(ckminions.opts, opts):
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
    }
    minion = "minion"
    minion2 = "minion2"
    minion2_ip = "192.168.2.10"
    ip = salt.utils.network.ip_addrs()
    mdata = {"grains": {"ipv4": ip, "ipv6": []}}
    mdata2 = {"grains": {"ipv4": [minion2_ip], "ipv6": []}}
    ckminions = salt.utils.minions.CkMinions({"minion_data_cache": True})
    patch_net = patch("salt.utils.network.local_port_tcp", return_value={"127.0.0.1"})
    patch_remote_net = patch(
        "salt.utils.network.remote_port_tcp", return_value={minion2_ip}
    )
    patch_list = patch("salt.cache.Cache.list", return_value=[minion, minion2])
    patch_fetch = patch("salt.cache.Cache.fetch", side_effect=[mdata, mdata2])
    with patch.dict(ckminions.opts, opts):
        with patch_net, patch_list, patch_fetch, patch_remote_net:
            ret = ckminions.connected_ids()
            assert ret == {minion2, minion}
