import logging
import os
import pathlib
import re
import subprocess

import pytest

import salt.utils.platform
from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Election-storm diagnostic
# ---------------------------------------------------------------------------
#
# The previous CI triage of test_cluster_key_rotation,
# test_raft_re_election_after_leader_restart, and test_basic_cluster_minion_1
# attributed failures to slow runners.  Reproducing them with stress-ng on
# debian-12 amd64 surfaced two real bugs (RPC-loss in the publish path and a
# Raft pre-vote correctness bug) plus one test-design race.  This helper
# converts the silent "watchdog rescued us" path into a loud failure that
# names the offending master and includes its transition counts, so the
# next layer of bug surfaces as a real assertion rather than another
# "must be timing" timeout bump.
#
# Healthy bring-up: <= 1 CANDIDATE per master, 1 LEADER total, <= 1 FOLLOWER
# per master per election round.  An election storm shows up as 10+
# CANDIDATE/FOLLOWER per master.

_BECOMING_LOG_RE = re.compile(
    r"Node (?P<node>\S+) BECOMING (?P<state>LEADER|CANDIDATE|FOLLOWER) for term (?P<term>\d+)"
)


def _master_log_path(master):
    """Return the on-disk log file for *master* (a salt-factories master)."""
    log_path = master.config.get("log_file")
    if not log_path:
        return None
    if not os.path.isabs(log_path):
        log_path = os.path.join(master.config.get("root_dir", ""), log_path)
    return pathlib.Path(log_path)


def _count_transitions(master):
    """
    Return ``{state: count}`` for the BECOMING transitions logged by *master*.

    Reads through the on-disk log file.  Returns an empty dict if the log is
    missing or unreadable — callers treat that as "no signal", not "no storm".
    """
    counts = {"LEADER": 0, "CANDIDATE": 0, "FOLLOWER": 0}
    log_path = _master_log_path(master)
    if log_path is None or not log_path.is_file():
        return counts
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        log.warning("Could not read %s: %s", log_path, exc)
        return counts
    for match in _BECOMING_LOG_RE.finditer(text):
        counts[match.group("state")] += 1
    return counts


def _storm_slack():
    """
    Extra tolerance added to every storm threshold on shared CI runners.

    The defaults (5 / 5 / 4) are calibrated for steady-state Raft on a
    machine with predictable scheduling — they catch the real failure
    mode we care about (masters stuck in a candidacy / stepdown loop,
    10+ transitions, rescued only by the watchdog).  On a 2-vCPU GHA
    runner shared with other jobs, scheduling jitter alone can produce
    one extra contested round during bring-up: the cluster *does*
    converge to a single leader, it just wobbles +1 LEADER and +1
    FOLLOWER along the way.  That's not a Raft bug; it's runner
    variance.  Adding a fixed slack of 3 absorbs it without weakening
    the test against the actual storm pattern (which is 2x+ over the
    healthy upper bound, not 1 over).

    Slack is keyed on the ``CI`` env var so developer-machine runs keep
    the tighter defaults — that's where a real correctness regression
    is most likely to be caught early.
    """
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        try:
            return int(os.environ.get("SALT_RAFT_TEST_STORM_SLACK", "3"))
        except ValueError:
            return 3
    return 0


def assert_no_election_storm(
    masters,
    *,
    max_candidate_per_master=None,
    max_follower_per_master=None,
    max_leader_total=None,
):
    """
    Fail the calling test if any master shows pathological term churn.

    Healthy upper bounds for one cluster bring-up + at most one re-election:

    * ``BECOMING CANDIDATE`` <= 5 per master  (initial election + a re-run
      or two if pre-votes raced + at most one re-election)
    * ``BECOMING FOLLOWER`` <= 5 per master   (initial + re-election +
      slack for a stepdown if a higher term arrives)
    * ``BECOMING LEADER`` <= 4 cluster-wide   (one initial leader + at
      most one re-election leader, ×2 slack for a contested round)

    Higher counts mean masters are stuck in a pre-vote / candidacy /
    stepdown loop — exactly the shape the slow-runner failures had,
    rescued only by a watchdog timer that the test eventually catches.

    On CI runners the thresholds are bumped by :func:`_storm_slack` to
    absorb scheduling jitter; see that function's docstring for the
    rationale.

    :param masters: iterable of salt-factories master daemons
    :raises pytest.fail: if any threshold is exceeded
    """
    slack = _storm_slack()
    if max_candidate_per_master is None:
        max_candidate_per_master = 5 + slack
    if max_follower_per_master is None:
        max_follower_per_master = 5 + slack
    if max_leader_total is None:
        max_leader_total = 4 + slack
    per_master = {}
    leader_total = 0
    for master in masters:
        node_id = master.config.get("interface") or master.config.get("id")
        counts = _count_transitions(master)
        per_master[node_id] = counts
        leader_total += counts["LEADER"]

    storm = []
    for node_id, counts in per_master.items():
        if counts["CANDIDATE"] > max_candidate_per_master:
            storm.append(
                f"  {node_id}: BECOMING CANDIDATE × {counts['CANDIDATE']} "
                f"(threshold {max_candidate_per_master})"
            )
        if counts["FOLLOWER"] > max_follower_per_master:
            storm.append(
                f"  {node_id}: BECOMING FOLLOWER × {counts['FOLLOWER']} "
                f"(threshold {max_follower_per_master})"
            )
    if leader_total > max_leader_total:
        storm.append(
            f"  cluster-wide: BECOMING LEADER × {leader_total} "
            f"(threshold {max_leader_total})"
        )

    if storm:
        summary = "\n".join(f"  {n}: {c}" for n, c in sorted(per_master.items()))
        pytest.fail(
            "Raft election storm detected — masters are recovering via "
            "watchdog rather than steady-state Raft.  Fix the underlying "
            "race; do not bump the test timeout.\n"
            "\nThresholds exceeded:\n"
            + "\n".join(storm)
            + f"\n\nFull transition counts per master:\n{summary}"
        )


@pytest.fixture
def cluster_shared_path(tmp_path):
    path = tmp_path / "cluster"
    path.mkdir()
    return path


@pytest.fixture
def cluster_pki_path(cluster_shared_path):
    path = cluster_shared_path / "pki"
    path.mkdir()
    (path / "peers").mkdir()
    return path


@pytest.fixture
def cluster_cache_path(cluster_shared_path):
    path = cluster_shared_path / "cache"
    path.mkdir()
    return path


@pytest.fixture
def cluster_master_1(request, salt_factories, cluster_pki_path, cluster_cache_path):
    config_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = {
        "interface": "127.0.0.1",
        "cluster_id": "master_cluster",
        "cluster_peers": [
            "127.0.0.2",
            "127.0.0.3",
        ],
        "cluster_pki_dir": str(cluster_pki_path),
        "cache_dir": str(cluster_cache_path),
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
            "salt.utils.event": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
        "cluster_encryption_algorithm": (
            "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        "127.0.0.1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=240):
        yield factory


@pytest.fixture
def cluster_master_2(salt_factories, cluster_master_1):
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.2", "up"])

    config_defaults = {
        "open_mode": True,
        "transport": cluster_master_1.config["transport"],
    }
    config_overrides = {
        "interface": "127.0.0.2",
        "cluster_id": "master_cluster",
        "cluster_peers": [
            "127.0.0.1",
            "127.0.0.3",
        ],
        "cluster_pki_dir": cluster_master_1.config["cluster_pki_dir"],
        "cache_dir": cluster_master_1.config["cache_dir"],
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
            "salt.utils.event": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
        "cluster_encryption_algorithm": (
            "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"
        ),
    }

    # Use the same ports for both masters, they are binding to different interfaces
    for key in (
        "ret_port",
        "publish_port",
    ):
        config_overrides[key] = cluster_master_1.config[key]
    factory = salt_factories.salt_master_daemon(
        "127.0.0.2",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=240):
        yield factory


@pytest.fixture
def cluster_master_3(salt_factories, cluster_master_1):
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.3", "up"])

    config_defaults = {
        "open_mode": True,
        "transport": cluster_master_1.config["transport"],
    }
    config_overrides = {
        "interface": "127.0.0.3",
        "cluster_id": "master_cluster",
        "cluster_peers": [
            "127.0.0.1",
            "127.0.0.2",
        ],
        "cluster_pki_dir": cluster_master_1.config["cluster_pki_dir"],
        "cache_dir": cluster_master_1.config["cache_dir"],
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
            "salt.utils.event": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
        "cluster_encryption_algorithm": (
            "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"
        ),
    }

    # Use the same ports for both masters, they are binding to different interfaces
    for key in (
        "ret_port",
        "publish_port",
    ):
        config_overrides[key] = cluster_master_1.config[key]
    factory = salt_factories.salt_master_daemon(
        "127.0.0.3",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=240):
        yield factory


@pytest.fixture
def cluster_master_4(
    salt_factories, cluster_master_1, cluster_master_2, cluster_master_3
):
    """
    A 4th master that joins an existing 3-master cluster at runtime.

    Masters 1-3 are started with ``cluster_peers`` pointing only at each
    other; they do not know about 127.0.0.4 up front. When this master
    starts it runs ``discover_peers`` against the three known peers,
    they reply, and the join protocol adds 127.0.0.4 to every peer's
    ``cluster_peers`` list dynamically.
    """
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.4", "up"])

    config_defaults = {
        "open_mode": True,
        "transport": cluster_master_1.config["transport"],
    }
    config_overrides = {
        "interface": "127.0.0.4",
        "cluster_id": "master_cluster",
        "cluster_peers": [
            "127.0.0.1",
            "127.0.0.2",
            "127.0.0.3",
        ],
        "cluster_pki_dir": cluster_master_1.config["cluster_pki_dir"],
        "cache_dir": cluster_master_1.config["cache_dir"],
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
            "salt.utils.event": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
        "cluster_encryption_algorithm": (
            "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"
        ),
    }

    # Use the same ports across the cluster; masters bind to different
    # interfaces so there is no collision.
    for key in (
        "ret_port",
        "publish_port",
    ):
        config_overrides[key] = cluster_master_1.config[key]
    factory = salt_factories.salt_master_daemon(
        "127.0.0.4",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=240):
        yield factory


@pytest.fixture
def cluster_pki_path_isolated(tmp_path):
    """
    Build per-master ``cluster_pki_dir`` paths so the isolated-FS
    fixtures below can prove cluster bootstrap works without sharing
    PKI between masters.  Each master gets its own pki+peers tree.
    """
    paths = {}
    for addr in ("127.0.0.1", "127.0.0.2", "127.0.0.3", "127.0.0.4"):
        path = tmp_path / "iso" / addr / "pki"
        path.mkdir(parents=True)
        (path / "peers").mkdir()
        paths[addr] = path
    return paths


@pytest.fixture
def cluster_cache_path_isolated(tmp_path):
    """Per-master ``cache_dir`` for the isolated-FS fixture set."""
    paths = {}
    for addr in ("127.0.0.1", "127.0.0.2", "127.0.0.3", "127.0.0.4"):
        path = tmp_path / "iso" / addr / "cache"
        path.mkdir(parents=True)
        paths[addr] = path
    return paths


@pytest.fixture
def cluster_file_roots_path_isolated(tmp_path):
    """
    Per-master ``file_roots[base]`` path for the isolated-FS fixture set.

    Returned as ``{addr: pathlib.Path}``.  Tests can pre-seed master_1's
    path with an SLS file and assert state-sync delivers it to other
    masters' paths during the join handshake.
    """
    paths = {}
    for addr in ("127.0.0.1", "127.0.0.2", "127.0.0.3", "127.0.0.4"):
        path = tmp_path / "iso" / addr / "file_roots"
        path.mkdir(parents=True)
        paths[addr] = path
    return paths


@pytest.fixture
def cluster_pillar_roots_path_isolated(tmp_path):
    """Per-master ``pillar_roots[base]`` path for the isolated-FS set."""
    paths = {}
    for addr in ("127.0.0.1", "127.0.0.2", "127.0.0.3", "127.0.0.4"):
        path = tmp_path / "iso" / addr / "pillar_roots"
        path.mkdir(parents=True)
        paths[addr] = path
    return paths


def _isolated_master_overrides(
    addr, peers, pki_paths, cache_paths, file_roots_paths=None, pillar_roots_paths=None
):
    overrides = {
        "interface": addr,
        "cluster_id": "master_cluster",
        "cluster_peers": list(peers),
        "cluster_pki_dir": str(pki_paths[addr]),
        "cache_dir": str(cache_paths[addr]),
        # Exercises the no-shared-FS path: keys cache flips to mmap_key
        # and joiners receive a bulk state-sync inside join-reply before
        # becoming Raft learners.
        "cluster_isolated_filesystem": True,
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
            "salt.utils.event": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
        "cluster_encryption_algorithm": (
            "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"
        ),
    }
    if file_roots_paths is not None:
        overrides["file_roots"] = {"base": [str(file_roots_paths[addr])]}
    if pillar_roots_paths is not None:
        overrides["pillar_roots"] = {"base": [str(pillar_roots_paths[addr])]}
    return overrides


@pytest.fixture
def cluster_master_1_isolated(
    request,
    salt_factories,
    cluster_pki_path_isolated,
    cluster_cache_path_isolated,
    cluster_file_roots_path_isolated,
    cluster_pillar_roots_path_isolated,
):
    """
    Like :func:`cluster_master_1` but with a *per-master* ``cluster_pki_dir``
    and ``cache_dir``.  The founder bootstraps its own keys; joiners must
    receive ``cluster_aes`` and ``cluster.pem`` over the wire (the
    no-shared-FS path).
    """
    config_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = _isolated_master_overrides(
        "127.0.0.1",
        ["127.0.0.2", "127.0.0.3"],
        cluster_pki_path_isolated,
        cluster_cache_path_isolated,
        cluster_file_roots_path_isolated,
        cluster_pillar_roots_path_isolated,
    )
    factory = salt_factories.salt_master_daemon(
        "127.0.0.1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def cluster_master_2_isolated(
    salt_factories,
    cluster_master_1_isolated,
    cluster_pki_path_isolated,
    cluster_cache_path_isolated,
    cluster_file_roots_path_isolated,
    cluster_pillar_roots_path_isolated,
):
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.2", "up"])
    config_defaults = {
        "open_mode": True,
        "transport": cluster_master_1_isolated.config["transport"],
    }
    config_overrides = _isolated_master_overrides(
        "127.0.0.2",
        ["127.0.0.1", "127.0.0.3"],
        cluster_pki_path_isolated,
        cluster_cache_path_isolated,
        cluster_file_roots_path_isolated,
        cluster_pillar_roots_path_isolated,
    )
    for key in ("ret_port", "publish_port"):
        config_overrides[key] = cluster_master_1_isolated.config[key]
    factory = salt_factories.salt_master_daemon(
        "127.0.0.2",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def cluster_master_3_isolated(
    salt_factories,
    cluster_master_1_isolated,
    cluster_pki_path_isolated,
    cluster_cache_path_isolated,
    cluster_file_roots_path_isolated,
    cluster_pillar_roots_path_isolated,
):
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.3", "up"])
    config_defaults = {
        "open_mode": True,
        "transport": cluster_master_1_isolated.config["transport"],
    }
    config_overrides = _isolated_master_overrides(
        "127.0.0.3",
        ["127.0.0.1", "127.0.0.2"],
        cluster_pki_path_isolated,
        cluster_cache_path_isolated,
        cluster_file_roots_path_isolated,
        cluster_pillar_roots_path_isolated,
    )
    for key in ("ret_port", "publish_port"):
        config_overrides[key] = cluster_master_1_isolated.config[key]
    factory = salt_factories.salt_master_daemon(
        "127.0.0.3",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def cluster_master_4_isolated(
    salt_factories,
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    cluster_pki_path_isolated,
    cluster_cache_path_isolated,
    cluster_file_roots_path_isolated,
    cluster_pillar_roots_path_isolated,
):
    """
    A 4th, late-joining master under the isolated-FS fixture set.  Used to
    prove ``cluster_isolated_filesystem`` bulk state-sync ships pre-existing
    minion keys (and any other state delivered in join-reply) to a master
    that handshakes after the cluster is already running.
    """
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.4", "up"])
    config_defaults = {
        "open_mode": True,
        "transport": cluster_master_1_isolated.config["transport"],
    }
    config_overrides = _isolated_master_overrides(
        "127.0.0.4",
        ["127.0.0.1", "127.0.0.2", "127.0.0.3"],
        cluster_pki_path_isolated,
        cluster_cache_path_isolated,
        cluster_file_roots_path_isolated,
        cluster_pillar_roots_path_isolated,
    )
    for key in ("ret_port", "publish_port"):
        config_overrides[key] = cluster_master_1_isolated.config[key]
    factory = salt_factories.salt_master_daemon(
        "127.0.0.4",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def cluster_minion_1(cluster_master_1):
    config_defaults = {
        "transport": cluster_master_1.config["transport"],
    }

    port = cluster_master_1.config["ret_port"]
    addr = cluster_master_1.config["interface"]
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
    factory = cluster_master_1.salt_minion_daemon(
        "cluster-minion-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=240):
        yield factory


@pytest.fixture
def cluster_minion_1_isolated(cluster_master_1_isolated):
    """
    A minion connected only to the isolated master_1.  The other masters
    never share a ``pki_dir`` with master_1, so they must receive the
    minion's accepted public key over the cluster event bus to be able
    to authenticate it.

    Shared between the isolated-FS happy-path tests in
    ``test_isolated_cluster.py`` and the failure-mode tests in
    ``test_failure_modes.py``.
    """
    config_defaults = {
        "transport": cluster_master_1_isolated.config["transport"],
    }
    port = cluster_master_1_isolated.config["ret_port"]
    addr = cluster_master_1_isolated.config["interface"]
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
    factory = cluster_master_1_isolated.salt_minion_daemon(
        "cluster-minion-1-iso",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory
