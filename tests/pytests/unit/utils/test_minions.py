import pytest
import salt.utils.minions
import salt.utils.network
from tests.support.mock import patch


def test_connected_ids():
    """
    test ckminion connected_ids when
    local_port_tcp returns 127.0.0.1
    """
    opts = {"publish_port": 4505, "minion_data_cache": True}
    minion = "minion"
    ip = salt.utils.network.ip_addrs()
    mdata = {"grains": {"ipv4": ip, "ipv6": []}}
    patch_net = patch("salt.utils.network.local_port_tcp", return_value={"127.0.0.1"})
    patch_list = patch("salt.cache.Cache.list", return_value=[minion])
    patch_fetch = patch("salt.cache.Cache.fetch", return_value=mdata)
    ckminions = salt.utils.minions.CkMinions(opts)
    with patch_net, patch_list, patch_fetch:
        ret = ckminions.connected_ids()
        assert ret == {minion}


# These validate_tgt tests make the assumption that CkMinions.check_minions is
# correct. In other words, these tests are only worthwhile if check_minions is
# also correct.
def test_validate_tgt_should_return_false_when_no_valid_minions_have_been_found():
    ckminions = salt.utils.minions.CkMinions(opts={})
    with patch(
        "salt.utils.minions.CkMinions.check_minions", autospec=True, return_value={}
    ):
        result = ckminions.validate_tgt("fnord", "fnord", "fnord", minions=[])
        assert result is False


@pytest.mark.parametrize(
    "valid_minions, target_minions",
    [
        (["one", "two", "three"], ["one", "two", "five"]),
        (["one"], ["one", "two"]),
        (["one", "two", "three", "four"], ["five"]),
    ],
)
def test_validate_tgt_should_return_false_when_minions_have_minions_not_in_valid_minions(
    valid_minions, target_minions
):
    ckminions = salt.utils.minions.CkMinions(opts={})
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        autospec=True,
        return_value={"minions": valid_minions},
    ):
        result = ckminions.validate_tgt(
            "fnord", "fnord", "fnord", minions=target_minions
        )
        assert result is False


@pytest.mark.parametrize(
    "valid_minions, target_minions",
    [
        (["one", "two", "three", "five"], ["one", "two", "five"]),
        (["one"], ["one"]),
        (["one", "two", "three", "four", "five"], ["five"]),
    ],
)
def test_validate_tgt_should_return_true_when_all_minions_are_found_in_valid_minions(
    valid_minions, target_minions
):
    ckminions = salt.utils.minions.CkMinions(opts={})
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        autospec=True,
        return_value={"minions": valid_minions},
    ):
        result = ckminions.validate_tgt(
            "fnord", "fnord", "fnord", minions=target_minions
        )
        assert result is True
