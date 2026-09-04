import pytest

import salt.config
import salt.utils.minions
import salt.utils.network
from tests.support.mock import patch


def test_connected_ids():
    """
    test ckminion connected_ids when
    local_port_tcp returns 127.0.0.1
    """
    opts = salt.config.minion_config(None)
    opts.update(
        {
            "publish_port": 4505,
            "detect_remote_minions": False,
            "minion_data_cache": True,
            "__role": "minion",
        }
    )
    minion = "minion"
    ips = {"203.0.113.1", "203.0.113.2", "127.0.0.1"}
    mdata = {"ipv4": ips, "ipv6": []}
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
    opts = salt.config.minion_config(None)
    opts.update(
        {
            "publish_port": 4505,
            "detect_remote_minions": True,
            "remote_minions_port": 22,
            "minion_data_cache": True,
            "__role": "master",
        }
    )
    minion = "minion"
    minion2 = "minion2"
    minion2_ip = "192.168.2.10"
    minion_ips = {"203.0.113.1", "203.0.113.2", "127.0.0.1"}
    mdata = {"ipv4": minion_ips, "ipv6": []}
    mdata2 = {"ipv4": [minion2_ip], "ipv6": []}
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


# These validate_tgt tests make the assumption that CkMinions.check_minions is
# correct. In other words, these tests are only worthwhile if check_minions is
# also correct.
def test_validate_tgt_returns_true_when_no_valid_minions_have_been_found():
    """
    CKMinions is only able to check against minions the master knows about. If
    no minion keys have been accepted it will return True.
    """
    opts = salt.config.master_config(None)
    ckminions = salt.utils.minions.CkMinions(opts=opts)
    with patch(
        "salt.utils.minions.CkMinions.check_minions", autospec=True, return_value={}
    ):
        result = ckminions.validate_tgt("fnord", "fnord", "fnord", minions=[])
        assert result is True


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
    opts = salt.config.master_config(None)
    ckminions = salt.utils.minions.CkMinions(opts=opts)
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
    opts = salt.config.master_config(None)
    ckminions = salt.utils.minions.CkMinions(opts=opts)
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        autospec=True,
        return_value={"minions": valid_minions},
    ):
        result = ckminions.validate_tgt(
            "fnord", "fnord", "fnord", minions=target_minions
        )
        assert result is True


def test_grain_target_excludes_minions_missing_from_cache(tmp_path):
    """
    Regression test for #68976: grain targeting must not include minions
    whose grain cache entry is missing.

    When the master receives ``salt -G 'asd:def' ...`` and a minion has an
    accepted key but no entry in the master's grain cache (e.g. the minion
    has been offline long enough that its cache directory was pruned, or
    has never returned data), ``CkMinions._check_cache_minions`` with the
    default ``greedy=True`` previously added that minion to the result set
    regardless of the grain expression. The minion would then be added to
    the "missing returners" wait list and reported as not returning.

    Only minions whose cached grains actually match the expression should
    be returned.
    """
    pki_dir = tmp_path / "pki"
    minions_dir = pki_dir / "minions"
    minions_dir.mkdir(parents=True)
    matching_minion = "matching_minion"
    nonmatching_minion = "nonmatching_minion"
    uncached_minion = "uncached_minion"
    for mid in (matching_minion, nonmatching_minion, uncached_minion):
        (minions_dir / mid).write_text("")

    opts = {
        "pki_dir": str(pki_dir),
        "minion_data_cache": True,
        "key_cache": False,
        "transport": "zeromq",
        "extension_modules": str(tmp_path / "extmods"),
        "cachedir": str(tmp_path / "cache"),
        # ``salt.key.Key.__init__`` (used by ``CkMinions``) reads this
        # directly; without it the helper raises KeyError before the
        # cache mocks below get a chance to run.
        "keys.cache_driver": "localfs_key",
        "__role": "master",
    }

    # On 3008.x ``_check_cache_minions`` calls
    # ``self.cache.fetch(search_type, minion_id)`` against a per-bank
    # store (e.g. ``self.cache.fetch("grains", "matching_minion")``)
    # and returns the bare grain dict, not the legacy
    # ``minions/<id>``/``data`` envelope used on 3006.x/3007.x.  Mirror
    # that layout in the fake.
    cache_data = {
        matching_minion: {"asd": "def"},
        nonmatching_minion: {"asd": "other"},
        # uncached_minion intentionally absent
    }

    def fake_list(bank):
        return list(cache_data)

    def fake_fetch(bank, key):
        return cache_data.get(key)

    ckminions = salt.utils.minions.CkMinions(opts)
    # Bypass ``_pki_minions`` (which goes through ``salt.key.Key`` and the
    # configured ``keys.cache_driver``); the bug under test lives in
    # ``_check_cache_minions``, not in the on-disk key listing.
    pki_minions = {matching_minion, nonmatching_minion, uncached_minion}
    with patch.object(
        ckminions, "_pki_minions", return_value=pki_minions
    ), patch.object(ckminions.cache, "list", side_effect=fake_list), patch.object(
        ckminions.cache, "fetch", side_effect=fake_fetch
    ):
        result = ckminions.check_minions("asd:def", "grain")

    assert uncached_minion not in result["minions"], (
        "Minion with no cached grain data should not be included in grain "
        "target matches (#68976)"
    )
    assert nonmatching_minion not in result["minions"]
    assert matching_minion in result["minions"]
