"""
Cluster integration tests with *per-master* ``cluster_pki_dir`` and
``cache_dir`` — i.e. no shared filesystem between masters.

Each master fixture allocates its own pki+cache trees.  The founder
generates ``cluster.pem`` / ``cluster.pub`` / ``cluster_aes`` locally;
joiners must receive them over the wire via ``cluster/peer/join-reply``
to come up correctly.  Subsequent minion-key acceptance and job-state
events propagate over the cluster event bus so a CLI on any peer can
target a minion connected to any other peer.

Together these tests cover items #1–#4 of the no-shared-FS plan.
"""

import pathlib
import time

import pytest

import salt.cache
import salt.utils.files
from tests.conftest import FIPS_TESTRUN

pytestmark = [
    pytest.mark.slow_test,
    # Each test spawns 3 isolated cluster masters + minions and
    # exercises ``join-reply`` / event-bus / state-sync paths.  Each
    # salt-master subprocess pays ``coverage.process_startup()`` cost
    # under coverage 7.14; with 6+ children running concurrently
    # ``cluster.pem`` replication can take longer than the polling
    # window the tests use, observed on Photon 4 FIPS in PR 69213 run
    # 26356884763 as ``test_isolated_cluster_pem_propagates``
    # asserting "cluster.pem differs between masters".  Skip subprocess
    # coverage so the cluster reaches steady state inside the test
    # window; parent pytest process is still traced.
    pytest.mark.no_subprocess_coverage,
]


def _read(path):
    if not pathlib.Path(path).exists():
        return None
    with salt.utils.files.fopen(path, "rb") as fp:
        return fp.read()


def test_isolated_cluster_aes_converges(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
):
    """
    All three masters end up with the same cluster session AES key
    even though no master can read another master's
    ``cluster_pki_dir/.aes`` from a shared filesystem.

    Master 1 (founder) writes ``.aes`` locally.  Masters 2 and 3 must
    install the founder's value from the ``cluster_aes`` field in their
    ``cluster/peer/join-reply``.
    """
    masters = [
        cluster_master_1_isolated,
        cluster_master_2_isolated,
        cluster_master_3_isolated,
    ]

    # Convergence is asynchronous: each master writes its initial random
    # ``.aes`` during ``populate_secrets``, then masters 2 and 3 receive
    # the founder's value via ``cluster/peer/join-reply`` and overwrite
    # their local file.  The fixture's ``factory.started()`` waits for
    # ``ret_port`` to bind, not for the join handshake to complete, so
    # we poll until all three files match (or the deadline expires).
    aes_values = [None, None, None]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        aes_values = [
            _read(pathlib.Path(m.config["cluster_pki_dir"]) / ".aes") for m in masters
        ]
        if all(v is not None for v in aes_values) and len(set(aes_values)) == 1:
            break
        time.sleep(0.5)

    assert all(v is not None for v in aes_values), (
        f"Some masters never wrote .aes: "
        f"{[m.config['interface'] for m, v in zip(masters, aes_values) if v is None]}"
    )
    # All three .aes contents must be identical: founder's value should
    # have propagated via wire on join-reply.
    distinct = set(aes_values)
    assert len(distinct) == 1, (
        f"Cluster did not converge on a single cluster_aes across "
        f"isolated cluster_pki_dirs: {len(distinct)} distinct values"
    )


def _make_isolated_minion(master, minion_id):
    """Spawn a minion attached only to *master* under the isolated-FS set."""
    config_defaults = {"transport": master.config["transport"]}
    port = master.config["ret_port"]
    addr = master.config["interface"]
    config_overrides = {
        "master": f"{addr}:{port}",
        "test.foo": "baz",
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
            "salt.utils.event": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    return master.salt_minion_daemon(
        minion_id,
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )


@pytest.fixture
def cluster_minion_2_isolated(cluster_master_2_isolated):
    """A second minion attached only to isolated master_2."""
    factory = _make_isolated_minion(cluster_master_2_isolated, "cluster-minion-2-iso")
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def cluster_minion_3_isolated(cluster_master_3_isolated):
    """A third minion attached only to isolated master_3."""
    factory = _make_isolated_minion(cluster_master_3_isolated, "cluster-minion-3-iso")
    with factory.started(start_timeout=120):
        yield factory


def _fetch_minion_key(master, minion_id):
    """Look up an accepted minion key via whatever ``keys.cache_driver``
    the master is running.  Returns ``{"state": ..., "pub": ...}`` or
    ``None``."""
    cache = salt.cache.Cache(master.config, driver=master.config["keys.cache_driver"])
    return cache.fetch("keys", minion_id)


def test_isolated_minion_key_replicates_to_peers(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    cluster_minion_1_isolated,
):
    """
    A minion that auto-accepts on master_1 must end up registered as an
    accepted key on every cluster peer too — even though no master sees
    another's ``pki_dir``.  ``salt.key.Key.change_state`` fires
    ``salt/key/accept`` carrying the pub bytes;
    ``EventMonitor._apply_peer_key_change`` calls ``cache.store("keys",
    ...)`` on each peer using whatever backend it has configured.
    """
    minion_id = cluster_minion_1_isolated.id
    masters = [
        cluster_master_1_isolated,
        cluster_master_2_isolated,
        cluster_master_3_isolated,
    ]

    deadline = time.monotonic() + 30
    entries = [None, None, None]
    while time.monotonic() < deadline:
        entries = [_fetch_minion_key(m, minion_id) for m in masters]
        if all(e and e.get("state") == "accepted" for e in entries):
            break
        time.sleep(0.5)
    missing = [
        m.config["interface"]
        for m, e in zip(masters, entries)
        if not e or e.get("state") != "accepted"
    ]
    assert not missing, f"Minion {minion_id!r} key did not replicate to: {missing}"
    pubs = {e["pub"] for e in entries}
    assert len(pubs) == 1, "Minion pub key body differs between cluster peers"


def test_isolated_test_ping_via_peer_master(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    cluster_minion_1_isolated,
):
    """
    End-to-end no-shared-FS scenario: a minion connected only to
    master_1 must be reachable via ``salt cluster-minion-1-iso
    test.ping`` issued from a CLI on master_2.

    Exercises every wire-delivery item:
      * ``cluster_aes`` and ``cluster.pem`` distributed during join
        (so peer signatures verify).
      * Accepted minion key replicated to master_2 so master_2 can
        verify the minion's return signature.
      * Job submission and return forwarded to master_2's local job
        cache so the CLI on master_2 can deliver the result.
    """
    cli = cluster_master_2_isolated.salt_cli(timeout=30)
    minion_id = cluster_minion_1_isolated.id
    deadline = time.monotonic() + 120
    last_ret = None
    while time.monotonic() < deadline:
        last_ret = cli.run("test.ping", minion_tgt=minion_id)
        if last_ret.data is True:
            break
        time.sleep(1)
    assert last_ret is not None and last_ret.data is True, (
        f"test.ping for {minion_id!r} via master_2 (isolated FS) never "
        f"returned True (last result: {last_ret!r})"
    )


def test_isolated_cluster_pem_propagates(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
):
    """
    Each master ends up with the same ``cluster.pem`` even though
    their ``cluster_pki_dir`` paths are private to each master.

    Master 1 generates the cluster RSA key pair locally on first
    start.  Masters 2 and 3 are expected to receive the PEM body in
    their join-reply (hybrid-encrypted under a one-shot Crypticle
    session key wrapped to each joiner's RSA pub).
    """
    masters = [
        cluster_master_1_isolated,
        cluster_master_2_isolated,
        cluster_master_3_isolated,
    ]
    pems = []
    pubs = []
    for m in masters:
        pki = pathlib.Path(m.config["cluster_pki_dir"])
        pems.append(_read(pki / "cluster.pem"))
        pubs.append(_read(pki / "cluster.pub"))
    assert all(v is not None for v in pems), (
        f"Some masters missing cluster.pem: "
        f"{[m.config['interface'] for m, v in zip(masters, pems) if v is None]}"
    )
    assert all(v is not None for v in pubs), (
        f"Some masters missing cluster.pub: "
        f"{[m.config['interface'] for m, v in zip(masters, pubs) if v is None]}"
    )
    assert len(set(pems)) == 1, "cluster.pem differs between masters"
    assert len(set(pubs)) == 1, "cluster.pub differs between masters"


_DEMO_SLS_BODY = "test-id:\n  test.succeed_without_changes\n"
_DEMO_PILLAR_BODY = "base:\n  '*':\n    - cluster_demo\n"


@pytest.fixture
def seed_master_1_roots_for_late_join(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    cluster_file_roots_path_isolated,
    cluster_pillar_roots_path_isolated,
):
    """
    Drop a known SLS file and pillar top.sls into master_1's
    ``file_roots[base][0]`` / ``pillar_roots[base][0]`` *after* masters
    1–3 are running but *before* the late-joining master_4 starts.

    Pytest resolves fixtures in argument order, so by depending on this
    fixture between ``cluster_master_3_isolated`` and
    ``cluster_master_4_isolated`` the test guarantees master_1 has the
    content on disk when master_4 sends its join request.
    """
    sls_path = cluster_file_roots_path_isolated["127.0.0.1"] / "demo" / "init.sls"
    sls_path.parent.mkdir(parents=True, exist_ok=True)
    sls_path.write_text(_DEMO_SLS_BODY)
    pillar_top = cluster_pillar_roots_path_isolated["127.0.0.1"] / "top.sls"
    pillar_top.write_text(_DEMO_PILLAR_BODY)
    return {"sls": sls_path, "pillar": pillar_top}


def test_isolated_late_joiner_receives_file_and_pillar_roots(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    cluster_file_roots_path_isolated,
    cluster_pillar_roots_path_isolated,
    seed_master_1_roots_for_late_join,
    cluster_master_4_isolated,
):
    """
    ``file_roots`` and ``pillar_roots`` content present on master_1 at
    join time must be delivered to a late-joining master via the bulk
    state-sync embedded in ``cluster/peer/join-reply``.
    """
    # ``apply_root_tree`` writes into ``roots[env][0]`` — pull the
    # actual destinations from master_4's running config rather than
    # guessing, since salt-factories prepends its own state-tree path
    # ahead of any file_roots/pillar_roots override.
    dst_file_root = pathlib.Path(
        cluster_master_4_isolated.config["file_roots"]["base"][0]
    )
    dst_pillar_root = pathlib.Path(
        cluster_master_4_isolated.config["pillar_roots"]["base"][0]
    )
    dst_sls = dst_file_root / "demo" / "init.sls"
    dst_pillar = dst_pillar_root / "top.sls"

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if dst_sls.is_file() and dst_pillar.is_file():
            break
        time.sleep(0.5)
    assert dst_sls.is_file(), (
        f"Late-joining master_4 never received init.sls from master_1's "
        f"file_roots via state-sync (looked under {dst_file_root})"
    )
    assert dst_pillar.is_file(), (
        f"Late-joining master_4 never received pillar top.sls from "
        f"master_1's pillar_roots via state-sync (looked under {dst_pillar_root})"
    )
    assert dst_sls.read_text() == _DEMO_SLS_BODY, "file_roots content mismatch"
    assert dst_pillar.read_text() == _DEMO_PILLAR_BODY, "pillar_roots content mismatch"


def test_isolated_late_joiner_state_sync(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    cluster_minion_1_isolated,
    cluster_master_4_isolated,
):
    """
    A 4th master joining a cluster that already has an accepted minion
    key must learn that key from the bulk state-sync embedded in
    ``cluster/peer/join-reply``, not from event-driven replication.

    Sequence:
      1. masters 1–3 bootstrap with ``cluster_isolated_filesystem=True``.
      2. ``cluster_minion_1_isolated`` connects to master_1 and is
         auto-accepted (event-driven replication populates 1, 2, 3).
      3. master_4 starts.  At this point no fresh ``salt/key/accept``
         event will ever fire for the existing minion, so master_4 can
         only learn it via state-sync.
      4. Within 30 s master_4's keys cache contains the accepted entry.
    """
    minion_id = cluster_minion_1_isolated.id
    deadline = time.monotonic() + 30
    entry = None
    while time.monotonic() < deadline:
        entry = _fetch_minion_key(cluster_master_4_isolated, minion_id)
        if entry and entry.get("state") == "accepted":
            break
        time.sleep(0.5)
    assert entry and entry.get("state") == "accepted", (
        f"Late-joining master_4 never received minion {minion_id!r} key "
        f"via state-sync (last fetch: {entry!r})"
    )


def _glob_ping_all(cli, expected_ids, deadline_secs=180):
    """
    Run ``salt '*' test.ping`` via *cli* and wait until the return covers
    every minion in *expected_ids*.  Returns the final ``cli.run`` result
    so the caller can assert on it.

    A glob target with multiple minions is asynchronous in the worst
    case (publish fan-out, return aggregation, return-cache lookup), so
    we poll instead of demanding a single shot to land everything.
    """
    deadline = time.monotonic() + deadline_secs
    last_ret = None
    expected = set(expected_ids)
    while time.monotonic() < deadline:
        last_ret = cli.run("test.ping", minion_tgt="*")
        data = last_ret.data or {}
        if (
            isinstance(data, dict)
            and expected.issubset(data)
            and all(data[mid] is True for mid in expected)
        ):
            return last_ret
        time.sleep(2)
    return last_ret


def test_isolated_multi_minion_targetable_from_every_master(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    cluster_minion_1_isolated,
    cluster_minion_2_isolated,
    cluster_minion_3_isolated,
):
    """
    Three minions, one per master, all reachable via ``salt '*'
    test.ping`` issued from any master CLI.

    Exercises the full event-driven replication path under load:
      * Each master auto-accepts its own minion's key locally.
      * Cluster events deliver each minion's accepted key to the other
        two peers, so any peer can verify the minion's return signature.
      * Glob targeting (``'*'``) on any peer's CLI publishes through
        the cluster fan-out and aggregates returns from minions
        connected to other peers.
    """
    minion_ids = {
        cluster_minion_1_isolated.id,
        cluster_minion_2_isolated.id,
        cluster_minion_3_isolated.id,
    }
    masters = (
        cluster_master_1_isolated,
        cluster_master_2_isolated,
        cluster_master_3_isolated,
    )
    for master in masters:
        cli = master.salt_cli(timeout=60)
        ret = _glob_ping_all(cli, minion_ids)
        data = ret.data if ret is not None else None
        assert isinstance(data, dict) and set(data) >= minion_ids, (
            f"`salt '*' test.ping` via {master.config['id']} did not reach "
            f"every minion: expected {minion_ids}, got {data!r}"
        )
        for mid in minion_ids:
            assert data[mid] is True, (
                f"Minion {mid!r} did not return True via {master.config['id']} "
                f"(got {data[mid]!r})"
            )


@pytest.mark.timeout(300, func_only=True)
def test_isolated_late_joiner_targets_all_existing_minions(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    cluster_minion_1_isolated,
    cluster_minion_2_isolated,
    cluster_minion_3_isolated,
    cluster_master_4_isolated,
):
    """
    A late-joining master (master_4) must end up able to target every
    minion that was already accepted on the cluster, exercising the
    full ``cluster_isolated_filesystem`` state-sync path:

      * Bulk state-sync inside ``cluster/peer/join-reply`` delivers the
        three accepted-minion keys before master_4 becomes a Raft
        learner.
      * Cluster event fan-out continues working on master_4 so that the
        publish reaches all three minions on their respective masters
        and the returns find their way back to master_4's local job
        cache.

    Failure modes this catches:
      * State-sync only ships a subset of minions (e.g. drops keys
        that aren't in some bank).
      * master_4 cannot verify minion signatures because peer-AES or
        per-minion key delivery is incomplete.
    """
    minion_ids = {
        cluster_minion_1_isolated.id,
        cluster_minion_2_isolated.id,
        cluster_minion_3_isolated.id,
    }
    cli = cluster_master_4_isolated.salt_cli(timeout=60)
    ret = _glob_ping_all(cli, minion_ids, deadline_secs=300)
    data = ret.data if ret is not None else None
    assert isinstance(data, dict) and set(data) >= minion_ids, (
        f"Late-joining master_4 could not target every existing minion: "
        f"expected {minion_ids}, got {data!r}"
    )
    for mid in minion_ids:
        assert data[mid] is True, (
            f"Minion {mid!r} did not return True via late-joining master_4 "
            f"(got {data[mid]!r})"
        )


# ---------------------------------------------------------------------------
# cluster.sync_roots runner — operator-driven content fan-out
# ---------------------------------------------------------------------------


def test_isolated_sync_roots_runner_propagates_content(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
):
    """
    Content added to master_1's ``file_roots`` and ``pillar_roots`` *after*
    the cluster is up must propagate to every peer when the operator runs
    ``salt-run cluster.sync_roots``.

    Pins the runner-to-peer fan-out contract:

    * The runner returns immediately with ``status: "fan-out initiated"``.
    * The actual sync happens asynchronously inside the master daemon.
    * Each peer's content tree gets the new files via the same encrypted
      state-sync transport used at join time — no special path, no IPC.

    Distinct from ``test_isolated_late_joiner_receives_file_and_pillar_roots``:
    that one tests *join-time* bulk sync (content present before a master
    joins).  This one tests *post-join* operator-driven sync (content added
    after the cluster is steady-state).
    """
    src_file_root = pathlib.Path(
        cluster_master_1_isolated.config["file_roots"]["base"][0]
    )
    src_pillar_root = pathlib.Path(
        cluster_master_1_isolated.config["pillar_roots"]["base"][0]
    )

    # Unique marker so we can't be fooled by leftover state from a
    # neighbouring test or a previous run.
    marker = f"sync-roots-marker-{int(time.time())}"
    sls_body = f"post-join-id:\n  test.succeed_without_changes:\n    - name: {marker}\n"
    pillar_body = f"sync_roots_marker: {marker}\n"

    sls_path = src_file_root / "post_join_synced.sls"
    pillar_path = src_pillar_root / "post_join_synced.sls"
    sls_path.write_text(sls_body)
    pillar_path.write_text(pillar_body)

    # Fire the runner from master_1.  Returns immediately; the daemon
    # owns the fan-out.
    salt_run = cluster_master_1_isolated.salt_run_cli(timeout=60)
    ret = salt_run.run("cluster.sync_roots")
    assert ret.returncode == 0, (
        f"cluster.sync_roots exited non-zero (stdout={ret.stdout!r}, "
        f"stderr={ret.stderr!r})"
    )
    # JSON deserialisation may give us a dict or the raw string depending
    # on output format; just check the success substring loosely.
    assert "fan-out initiated" in (ret.stdout or "") or (
        isinstance(ret.data, dict) and ret.data.get("status") == "fan-out initiated"
    ), f"runner output missing fan-out marker: {ret.stdout!r} / {ret.data!r}"

    # Poll for content arrival on master_2 and master_3.  Same transport
    # as the join-time bulk sync, so 30 s is comfortably above the
    # observed live-cluster window (~5-8 s on a healthy LAN).
    peers = (cluster_master_2_isolated, cluster_master_3_isolated)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        all_landed = True
        for master in peers:
            dst_sls = (
                pathlib.Path(master.config["file_roots"]["base"][0])
                / "post_join_synced.sls"
            )
            dst_pillar = (
                pathlib.Path(master.config["pillar_roots"]["base"][0])
                / "post_join_synced.sls"
            )
            if not dst_sls.is_file() or not dst_pillar.is_file():
                all_landed = False
                break
        if all_landed:
            break
        time.sleep(0.5)

    # Per-peer assertions so a failure points at the right master.
    for master in peers:
        addr = master.config["interface"]
        dst_sls = (
            pathlib.Path(master.config["file_roots"]["base"][0])
            / "post_join_synced.sls"
        )
        dst_pillar = (
            pathlib.Path(master.config["pillar_roots"]["base"][0])
            / "post_join_synced.sls"
        )
        assert dst_sls.is_file(), (
            f"master {addr} never received post_join_synced.sls "
            f"(looked under {dst_sls.parent})"
        )
        assert dst_pillar.is_file(), (
            f"master {addr} never received post_join_synced.sls pillar "
            f"(looked under {dst_pillar.parent})"
        )
        assert (
            marker in dst_sls.read_text()
        ), f"master {addr} received the file but marker is wrong"
        assert (
            marker in dst_pillar.read_text()
        ), f"master {addr} received the pillar but marker is wrong"


def test_isolated_sync_roots_runner_file_only(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
):
    """
    ``cluster.sync_roots roots=file`` syncs only ``file_roots``; pillars
    on the peers are unchanged.  Pins the channel-filter contract so an
    operator who only wanted SLS updates doesn't accidentally fan out
    secret pillar data.
    """
    src_file_root = pathlib.Path(
        cluster_master_1_isolated.config["file_roots"]["base"][0]
    )
    src_pillar_root = pathlib.Path(
        cluster_master_1_isolated.config["pillar_roots"]["base"][0]
    )

    marker = f"file-only-{int(time.time())}"
    file_path = src_file_root / "file_only.sls"
    pillar_path = src_pillar_root / "file_only_pillar.sls"
    file_path.write_text(f"id:\n  test.nop:\n    - name: {marker}\n")
    pillar_path.write_text(f"never_fanned_out: {marker}\n")

    salt_run = cluster_master_1_isolated.salt_run_cli(timeout=60)
    ret = salt_run.run("cluster.sync_roots", "roots=file")
    assert ret.returncode == 0

    peers = (cluster_master_2_isolated, cluster_master_3_isolated)

    # Wait for the file_roots side to land; we deliberately do not wait
    # for the pillar (because it shouldn't land at all).
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if all(
            (
                pathlib.Path(m.config["file_roots"]["base"][0]) / "file_only.sls"
            ).is_file()
            for m in peers
        ):
            break
        time.sleep(0.5)

    for master in peers:
        addr = master.config["interface"]
        dst_file = (
            pathlib.Path(master.config["file_roots"]["base"][0]) / "file_only.sls"
        )
        dst_pillar = (
            pathlib.Path(master.config["pillar_roots"]["base"][0])
            / "file_only_pillar.sls"
        )
        assert (
            dst_file.is_file()
        ), f"master {addr} did not receive file_only.sls via roots=file"
        assert not dst_pillar.is_file(), (
            f"master {addr} received file_only_pillar.sls despite roots=file "
            "(pillar should be excluded)"
        )
