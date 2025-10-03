"""
Cluster integration tests.
"""

import salt.utils.event


def test_basic_cluster_setup(
    cluster_master_1, cluster_master_2, cluster_pki_path, cluster_cache_path
):
    cli1 = cluster_master_1.salt_run_cli(timeout=120)
    ret = cli1.run("config.get", "cluster_pki_dir")
    assert str(cluster_pki_path) == ret.stdout
    ret = cli1.run("config.get", "cache_dir")
    assert str(cluster_cache_path) == ret.stdout
    ret = cli1.run("config.get", "cluster_peers")
    ret.data.sort()
    assert ["127.0.0.2", "127.0.0.3"] == ret.data

    cli2 = cluster_master_2.salt_run_cli(timeout=120)
    ret = cli2.run("config.get", "cluster_pki_dir")
    assert str(cluster_pki_path) == ret.stdout
    ret = cli2.run("config.get", "cache_dir")
    assert str(cluster_cache_path) == ret.stdout
    ret = cli2.run("config.get", "cluster_peers")
    ret.data.sort()
    assert ["127.0.0.1", "127.0.0.3"] == ret.data

    # Check for shared keys. Note: The third master 127.0.0.3 was never
    # started.
    peers_path = cluster_pki_path / "peers"
    unexpected = False
    found = []
    for key_path in peers_path.iterdir():
        if key_path.name == "127.0.0.1.pub":
            found.append("127.0.0.1")
        elif key_path.name == "127.0.0.2.pub":
            found.append("127.0.0.2")
        else:
            unexpected = True

    found.sort()

    assert ["127.0.0.1", "127.0.0.2"] == found
    assert unexpected is False

    assert (cluster_pki_path / ".aes").exists()


def test_basic_cluster_event(cluster_master_1, cluster_master_2):
    with salt.utils.event.get_event(
        "master", opts=cluster_master_2.config, listen=True
    ) as event2:
        event1 = salt.utils.event.get_event("master", opts=cluster_master_2.config)
        data = {"meh": "bah"}
        event1.fire_event(data, "meh/bah")
        evt = event2.get_event(tag="meh/bah", wait=5)
        assert data == evt


def test_basic_cluster_minion_1(cluster_master_1, cluster_master_2, cluster_minion_1):
    cli = cluster_master_1.salt_cli(timeout=120)
    ret = cli.run("test.ping", minion_tgt="cluster-minion-1")
    assert ret.data is True


def test_basic_cluster_minion_1_from_master_2(
    cluster_master_1, cluster_master_2, cluster_minion_1
):
    cli = cluster_master_2.salt_cli(timeout=120)
    ret = cli.run("test.ping", minion_tgt="cluster-minion-1")
    assert ret.data is True


def test_basic_cluster_minion_1_from_master_3(
    cluster_master_1, cluster_master_2, cluster_master_3, cluster_minion_1
):
    cli = cluster_master_3.salt_cli(timeout=120)
    ret = cli.run("test.ping", minion_tgt="cluster-minion-1")
    assert ret.data is True
