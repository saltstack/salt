"""
Cluster scenarios.
"""

import getpass
import pathlib
import time

import pytest

import salt.crypt

# Every test in this file runs 3 salt-master daemons + a salt-minion +
# salt-cli invocations.  Under coverage 7.14 each salt subprocess pays
# ``coverage.process_startup()`` cost; with 5+ subprocesses lifetime'd
# over the test, the cluster's BlockingChannel / Raft AppendEntries
# timing can slip enough to leave two different ``cluster.pem``
# versions visible during the rotation window — observed on Debian 11
# in PR 69213 run 26356884763 as ``assert 2 == 1``.  Skip subprocess
# coverage so the cluster reaches steady state inside the test's
# polling window; parent pytest process is still traced.
pytestmark = [
    pytest.mark.no_subprocess_coverage,
]


@pytest.mark.flaky(max_runs=3)
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

    # Wait for the cluster to converge on a new aes session key.  Master 1
    # rotates locally and removes ``.dfn`` when its main loop next ticks;
    # masters 2 and 3 then pick up the rotated key via the cluster sync
    # channel asynchronously, and on slow runners (FIPS/Arm64 in particular)
    # that propagation can lag the local rotation by several seconds.  Poll
    # for full cluster convergence rather than the local dropfile signal
    # alone -- the previous ``2 * loop_interval`` (~2 s default) window was
    # tight enough to false-positive ``len(keys) == 2`` on those runners.
    convergence_timeout = 60
    start = time.monotonic()
    keys = set()
    while True:
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
        if not dfpath.exists() and len(keys) == 1 and next(iter(keys)) != orig_aes:
            break
        if time.monotonic() - start > convergence_timeout:
            break  # fall through to the assertions below for useful state
        time.sleep(1)

    assert not dfpath.exists(), f"Drop file never removed {dfpath}"
    assert len(keys) == 1, f"Cluster did not converge on a single aes key: {keys}"
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
