import salt.config


def test_apply_no_cluster_id():
    defaults = salt.config.DEFAULT_MASTER_OPTS.copy()
    assert defaults["cluster_id"] is None

    overrides = {}

    opts = salt.config.apply_master_config(overrides, defaults)
    assert "cluster_id" in opts
    assert opts["cluster_id"] is None
    assert "cluster_pki_dir" in opts
    assert opts["cluster_pki_dir"] is None


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
    }

    opts = salt.config.apply_master_config(overrides, defaults)
    assert "cluster_id" in opts
    assert "test-cluster" == opts["cluster_id"]

    # the cluster pki dir defaults to pki_dir
    assert "cluster_pki_dir" in opts
    assert cluster_dir == opts["cluster_pki_dir"]

    # the cluster peers defaults to empty list
    assert "cluster_peers" in opts
    assert isinstance(opts["cluster_peers"], list)
    opts["cluster_peers"].sort()
    assert ["127.0.0.1", "127.0.0.3"] == opts["cluster_peers"]
