import logging

import salt.config
from tests.support.mock import MagicMock, patch


def test_apply_no_cluster_id():
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy() | {"id": "config-test-master"}
    assert defaults["cluster_id"] is None

    overrides = {}

    opts = salt.config.apply_master_config(overrides, defaults)
    assert "cluster_id" in opts
    assert opts["cluster_id"] is None
    assert "cluster_pki_dir" in opts
    assert opts["cluster_pki_dir"] is None
    assert "cluster_pool_port" in opts
    assert opts["cluster_pool_port"] == 4520


def test_apply_default_for_cluster():
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy() | {"id": "config-test-master"}
    assert defaults["cluster_id"] is None

    overrides = {"cluster_id": "test-cluster"}

    opts = salt.config.apply_master_config(overrides, defaults)
    assert "cluster_id" in opts
    assert "test-cluster" == opts["cluster_id"]

    # the cluster pki dir defaults to pki_dir
    assert "cluster_pki_dir" in opts
    assert opts["pki_dir"] == opts["cluster_pki_dir"]

    # the cluster peers defaults to empty list
    assert "cluster_peers" in opts
    assert [] == opts["cluster_peers"]

    # the cluster pool port defaults to 4520
    assert "cluster_pool_port" in opts
    assert opts["cluster_pool_port"] == 4520


def test_apply_for_cluster():
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy() | {"id": "config-test-master"}
    assert defaults["cluster_id"] is None

    cluster_dir = "/tmp/cluster"
    overrides = {
        "cluster_id": "test-cluster",
        "cluster_peers": [
            "127.0.0.1",
            "127.0.0.3",
        ],
        "cluster_pki_dir": cluster_dir,
        "cluster_pool_port": 5500,
    }

    opts = salt.config.apply_master_config(overrides, defaults)
    assert "cluster_id" in opts
    assert "test-cluster" == opts["cluster_id"]

    # the cluster pki dir defaults to pki_dir
    assert "cluster_pki_dir" in opts
    assert cluster_dir == opts["cluster_pki_dir"]

    # the cluster pool port defaults to 4520
    assert "cluster_pool_port" in opts
    assert opts["cluster_pool_port"] == 5500

    # the cluster peers defaults to empty list
    assert "cluster_peers" in opts
    assert isinstance(opts["cluster_peers"], list)
    opts["cluster_peers"].sort()
    assert ["127.0.0.1", "127.0.0.3"] == opts["cluster_peers"]


def test_cluster_port_alias_warns_and_aliases_cluster_pool_port(caplog):
    """
    Regression for https://github.com/saltstack/salt/issues/69877.

    The Raft rewrite for master clustering accidentally read the peer-pool
    port from an undocumented ``cluster_port`` opt instead of the
    documented ``cluster_pool_port``. ``apply_master_config`` now accepts
    ``cluster_port`` as a soft-deprecated alias: it copies the value into
    ``cluster_pool_port`` (if the caller did not set that explicitly) and
    emits a deprecation warning.
    """
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy() | {"id": "config-test-master"}
    overrides = {"cluster_port": 6520}

    with caplog.at_level(logging.WARNING, logger="salt.config"):
        opts = salt.config.apply_master_config(overrides, defaults)

    assert opts["cluster_pool_port"] == 6520
    assert any(
        "cluster_port" in rec.message and "deprecated" in rec.message
        for rec in caplog.records
    ), f"expected deprecation warning; got: {[r.message for r in caplog.records]}"


def test_cluster_pool_port_wins_over_cluster_port_alias():
    """
    If both ``cluster_port`` and ``cluster_pool_port`` are set, the
    documented ``cluster_pool_port`` wins -- the alias is a soft landing
    for operators who happened to pick up the buggy name, not a co-equal
    setting.
    """
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy() | {"id": "config-test-master"}
    overrides = {"cluster_port": 55596, "cluster_pool_port": 6520}

    opts = salt.config.apply_master_config(overrides, defaults)
    assert opts["cluster_pool_port"] == 6520


def test___cli_path_is_expanded():
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy() | {"id": "config-test-master"}
    overrides = {}
    with patch(
        "salt.utils.path.expand", MagicMock(return_value="/path/to/testcli")
    ) as expand_mock:
        opts = salt.config.apply_master_config(overrides, defaults)
        assert expand_mock.called
        assert opts["__cli"] == "testcli"


def test_mminion_config_reuses_caller_grains(tmp_path):
    """
    ``mminion_config`` should reuse a grains dict the caller already
    computed instead of running ``salt.loader.grains`` again -- otherwise
    every ``MasterMinion`` instantiation (and there are many during
    ``salt-master`` startup) repeats the full grain refresh.  See #62168.
    """
    conf_file = tmp_path / "minion"
    conf_file.write_text("")
    caller_grains = {"os": "Fake", "fqdns": ["cached.example.com"]}
    overrides = {"conf_file": str(conf_file), "grains": caller_grains}
    with patch("salt.loader.grains") as loader_grains:
        opts = salt.config.mminion_config(str(conf_file), overrides)
    assert loader_grains.call_count == 0, (
        "salt.loader.grains should not be invoked when the caller already "
        "supplied a populated grains dict"
    )
    assert opts["grains"] is caller_grains


def test_mminion_config_computes_grains_when_caller_omits_them(tmp_path):
    """
    When no grains are provided, ``mminion_config`` must still compute
    them via ``salt.loader.grains`` so first-time startup works.
    """
    conf_file = tmp_path / "minion"
    conf_file.write_text("")
    overrides = {"conf_file": str(conf_file)}
    sentinel = {"os": "Sentinel"}
    with patch("salt.loader.grains", return_value=sentinel) as loader_grains:
        opts = salt.config.mminion_config(str(conf_file), overrides)
    assert loader_grains.call_count == 1
    assert opts["grains"] is sentinel
