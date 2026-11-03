import logging

import salt.config
from tests.support.mock import MagicMock, patch


def test_apply_no_cluster_id():
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy()
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
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy()
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
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy()
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
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy()
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
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy()
    overrides = {"cluster_port": 55596, "cluster_pool_port": 6520}

    opts = salt.config.apply_master_config(overrides, defaults)
    assert opts["cluster_pool_port"] == 6520


def test___cli_path_is_expanded():
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy()
    overrides = {}
    with patch(
        "salt.utils.path.expand", MagicMock(return_value="/path/to/testcli")
    ) as expand_mock:
        opts = salt.config.apply_master_config(overrides, defaults)
        assert expand_mock.called
        assert opts["__cli"] == "testcli"
