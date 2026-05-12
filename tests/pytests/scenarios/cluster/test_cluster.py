"""
Cluster scenarios.
"""

import getpass
import pathlib
import time

import pytest

import salt.crypt


def test_cluster_key_rotation(
    cluster_master_1,
    cluster_master_2,
    cluster_master_3,
    cluster_minion_1,
    cluster_cache_path,
):
    cli = cluster_master_2.salt_cli(timeout=120)
    ret = cli.run("test.ping", minion_tgt="cluster-minion-1")
    assert ret.data is True

    # Validate the aes session key for all masters match
    keys = set()
    for master in (
        cluster_master_1,
        cluster_master_2,
        cluster_master_3,
    ):
        config = cluster_minion_1.config.copy()
        config["master_uri"] = (
            f"tcp://{master.config['interface']}:{master.config['ret_port']}"
        )
        auth = salt.crypt.SAuth(config)
        auth.authenticate()
        assert "aes" in auth._creds
        keys.add(auth._creds["aes"])

    assert len(keys) == 1
    orig_aes = keys.pop()

    # Create a drop file and wait for the master to do a key rotation.
    dfpath = pathlib.Path(cluster_master_1.config["cachedir"]) / ".dfn"
    assert not dfpath.exists()
    salt.crypt.dropfile(
        cluster_master_1.config["cachedir"],
        user=getpass.getuser(),
        master_id=cluster_master_1.config["id"],
    )
    assert dfpath.exists()
    timeout = 2 * cluster_master_1.config["loop_interval"]
    start = time.monotonic()
    while True:
        if not dfpath.exists():
            break
        if time.monotonic() - start > timeout:
            assert False, f"Drop file never removed {dfpath}"

    keys = set()

    # Validate the aes session key for all masters match
    for master in (
        cluster_master_1,
        cluster_master_2,
        cluster_master_3,
    ):
        config = cluster_minion_1.config.copy()
        config["master_uri"] = (
            f"tcp://{master.config['interface']}:{master.config['ret_port']}"
        )
        auth = salt.crypt.SAuth(config)
        auth.authenticate()
        assert "aes" in auth._creds
        keys.add(auth._creds["aes"])

    assert len(keys) == 1
    # Validate the aes session key actually changed
    assert orig_aes != keys.pop()


@pytest.mark.skip_on_fips_enabled_platform
def test_fourth_master_joins_existing_cluster(
    cluster_master_1,
    cluster_master_2,
    cluster_master_3,
    cluster_master_4,
    cluster_minion_1,
):
    """
    A master (127.0.0.4) that comes up after a 3-node cluster is
    already running must successfully join via the dynamic discover/
    join protocol and end up sharing the same AES session key as the
    existing peers. Minion commands routed through the late joiner
    must return just like they do through the original peers.
    """
    masters = (
        cluster_master_1,
        cluster_master_2,
        cluster_master_3,
        cluster_master_4,
    )

    # Every master -- including the late joiner -- must hand out the
    # same AES session key when the minion authenticates against it.
    # The join protocol is asynchronous; give it a short grace period
    # to propagate and converge before failing the test.
    deadline = time.monotonic() + 30
    while True:
        keys = set()
        for master in masters:
            config = cluster_minion_1.config.copy()
            config["master_uri"] = (
                f"tcp://{master.config['interface']}:{master.config['ret_port']}"
            )
            auth = salt.crypt.SAuth(config)
            auth.authenticate()
            assert (
                "aes" in auth._creds
            ), f"Master {master.config['id']} did not return an aes key"
            keys.add(auth._creds["aes"])
        if len(keys) == 1:
            break
        if time.monotonic() >= deadline:
            pytest.fail(
                "Masters did not converge on a single AES session key "
                f"after cluster_master_4 joined: {len(keys)} distinct keys"
            )
        time.sleep(1)

    # Commanding the minion through the late joiner exercises the full
    # publish path on the new peer (pub/ret channel, local event bus,
    # and the peer cluster auth fan-out).
    #
    # The peer-AES key exchange between the late joiner (master 4) and
    # the original cluster members is asynchronous.  Poll until the full
    # round-trip (publish → minion → return → CLI) succeeds, or we hit
    # a hard deadline.
    cli = cluster_master_4.salt_cli(timeout=30)
    deadline = time.monotonic() + 300
    last_ret = None
    while time.monotonic() < deadline:
        last_ret = cli.run("test.ping", minion_tgt="cluster-minion-1")
        if last_ret.data is True:
            break
    assert last_ret is not None and last_ret.data is True, (
        f"test.ping via cluster_master_4 never returned True "
        f"within 300 s (last result: {last_ret!r})"
    )

    # And through every other peer too, to confirm the late joiner did
    # not disturb the existing cluster's ability to serve the minion.
    for master in (cluster_master_1, cluster_master_2, cluster_master_3):
        cli = master.salt_cli(timeout=120)
        ret = cli.run("test.ping", minion_tgt="cluster-minion-1")
        assert (
            ret.data is True
        ), f"test.ping via {master.config['id']} returned {ret.data!r}"
