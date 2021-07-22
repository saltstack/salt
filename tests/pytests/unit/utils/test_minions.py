import salt.utils.minions
import salt.utils.network
from tests.support.mock import patch


def test_connected_ids():
    """
    test ckminion connected_ids when
    local_port_tcp returns 127.0.0.1
    """
    opts = {"publish_port": 4505}
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
