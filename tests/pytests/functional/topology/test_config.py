"""
Functional tests for :mod:`salt.config.topology`.

Exercises :func:`load_topology_config` end-to-end against real
``topology.conf`` files on disk, plus the full validator surface
reached via loader + file I/O.  Pure config-loading tests --- no
master daemon is started.  Starts-a-master coverage lives in the
shared harness tests under ``test_harness.py``.
"""

import logging
import os
import stat

import pytest

import salt.config.topology as topology_cfg
from salt.config.topology import (
    CLUSTER_ID_RE,
    DEFAULT_EVENT_SUBSCRIPTIONS,
    PeerRef,
    TopologyConfig,
    load_topology_config,
)

pytestmark = [
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def topology_conf_path(tmp_path):
    """Path to a per-test topology.conf (file may or may not exist)."""
    return tmp_path / "topology.conf"


def _opts(path, enabled=True):
    """Minimal master opts dict for topology loader tests."""
    return {
        "topology_enabled": enabled,
        "topology_config_file": str(path),
    }


def _write_conf(path, text):
    """Write raw YAML text to the given path."""
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_load_wellformed_config(topology_conf_path):
    """A well-formed topology.conf loads into an enabled TopologyConfig."""
    _write_conf(
        topology_conf_path,
        """
cluster_id: east
peers:
  - host: hq-master-1.example.com
    port: 4521
  - host: west-master-1.example.com
    finger: "00:11:22:33"
event_subscriptions:
  - 'salt/job/*/ret/*'
  - 'salt/job/*/new'
  - 'salt/presence/change'
""",
    )

    cfg = load_topology_config(_opts(topology_conf_path))

    assert isinstance(cfg, TopologyConfig)
    assert cfg.enabled is True
    assert cfg.cluster_id == "east"
    assert isinstance(cfg.peers, tuple)
    assert len(cfg.peers) == 2
    assert all(isinstance(p, PeerRef) for p in cfg.peers)
    assert cfg.peers[0].host == "hq-master-1.example.com"
    assert cfg.peers[0].port == 4521
    assert cfg.peers[0].finger is None
    assert cfg.peers[1].host == "west-master-1.example.com"
    assert cfg.peers[1].port is None
    assert cfg.peers[1].finger == "00:11:22:33"
    assert isinstance(cfg.event_subscriptions, tuple)
    assert cfg.event_subscriptions == (
        "salt/job/*/ret/*",
        "salt/job/*/new",
        "salt/presence/change",
    )


def test_load_minimal_config_only_cluster_id(topology_conf_path):
    """A conf with cluster_id and nothing else is valid; defaults fill in."""
    _write_conf(topology_conf_path, "cluster_id: solo\n")

    cfg = load_topology_config(_opts(topology_conf_path))

    assert cfg.enabled is True
    assert cfg.cluster_id == "solo"
    assert cfg.peers == ()
    assert cfg.event_subscriptions == DEFAULT_EVENT_SUBSCRIPTIONS


def test_event_subscriptions_default_when_omitted(topology_conf_path):
    """Omitting event_subscriptions yields DEFAULT_EVENT_SUBSCRIPTIONS."""
    _write_conf(
        topology_conf_path,
        """
cluster_id: east
peers: []
""",
    )

    cfg = load_topology_config(_opts(topology_conf_path))

    assert cfg.event_subscriptions == DEFAULT_EVENT_SUBSCRIPTIONS
    # Tuple, not list --- NamedTuple semantics / immutability.
    assert isinstance(cfg.event_subscriptions, tuple)


# ---------------------------------------------------------------------------
# Disabled / absent file paths (return disabled TopologyConfig)
# ---------------------------------------------------------------------------


def test_disabled_opt_returns_disabled_regardless_of_file(topology_conf_path):
    """
    topology_enabled=False short-circuits before touching the file.

    The on-disk conf is deliberately well-formed; the loader must not
    read it.
    """
    _write_conf(topology_conf_path, "cluster_id: east\n")

    cfg = load_topology_config(_opts(topology_conf_path, enabled=False))

    assert isinstance(cfg, TopologyConfig)
    assert cfg.enabled is False
    assert cfg.peers == ()
    # event_subscriptions is still a tuple on the disabled stub, so
    # callers can iterate without a None-check.
    assert isinstance(cfg.event_subscriptions, tuple)


def test_disabled_opt_does_not_open_file(topology_conf_path):
    """topology_enabled=False must not raise when the file does not exist."""
    assert not topology_conf_path.exists()
    cfg = load_topology_config(_opts(topology_conf_path, enabled=False))
    assert cfg.enabled is False


def test_missing_file_returns_disabled(topology_conf_path, caplog):
    """
    Missing config file: enabled opt is True but the file does not
    exist on disk.  Loader returns a disabled TopologyConfig and logs
    at INFO.
    """
    assert not topology_conf_path.exists()

    with caplog.at_level(logging.INFO, logger="salt.config.topology"):
        cfg = load_topology_config(_opts(topology_conf_path))

    assert cfg.enabled is False
    assert cfg.peers == ()
    # Loader emitted an INFO message naming the missing file so a
    # confused operator can grep for it.
    info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
    assert any(str(topology_conf_path) in m for m in info_messages), info_messages


# ---------------------------------------------------------------------------
# Malformed / invalid config
# ---------------------------------------------------------------------------


def test_malformed_yaml_raises(topology_conf_path):
    """YAML that cannot be parsed is a fatal ValueError at daemon start."""
    _write_conf(
        topology_conf_path,
        "cluster_id: east\npeers: [this is : not { valid: yaml\n",
    )

    with pytest.raises(ValueError):
        load_topology_config(_opts(topology_conf_path))


def test_missing_cluster_id_when_enabled_raises(topology_conf_path):
    """cluster_id is required when topology is enabled."""
    _write_conf(topology_conf_path, "peers: []\n")

    with pytest.raises(ValueError, match="cluster_id"):
        load_topology_config(_opts(topology_conf_path))


def test_empty_cluster_id_raises(topology_conf_path):
    """cluster_id present but empty is rejected the same as absent."""
    _write_conf(topology_conf_path, 'cluster_id: ""\n')

    with pytest.raises(ValueError, match="cluster_id"):
        load_topology_config(_opts(topology_conf_path))


@pytest.mark.parametrize(
    "bad_id",
    [
        "East",  # uppercase
        "has space",  # space
        "has.dot",  # dot
        "has/slash",  # slash (would collide with pki path layout)
        "has$dollar",  # shell metachar
        "-leadinghyphen",  # leading hyphen (regex: [a-z0-9] start)
        "_leading",  # leading underscore (reserved sentinel space)
    ],
)
def test_invalid_cluster_id_regex_rejected(topology_conf_path, bad_id):
    """cluster_id must satisfy CLUSTER_ID_RE."""
    _write_conf(topology_conf_path, f"cluster_id: {bad_id!r}\n")

    with pytest.raises(ValueError, match="cluster_id"):
        load_topology_config(_opts(topology_conf_path))


def test_reserved_cluster_id_identity_pub_rejected(topology_conf_path):
    """
    The MmapCache sentinel key ``__identity_pub__`` is explicitly
    reserved.  The regex already rejects leading underscores, but
    the loader must still refuse this specific name by name so a
    future regex relaxation cannot silently open the attack vector.
    """
    _write_conf(topology_conf_path, "cluster_id: __identity_pub__\n")

    with pytest.raises(ValueError, match="cluster_id|reserved"):
        load_topology_config(_opts(topology_conf_path))


# ---------------------------------------------------------------------------
# Peer validation
# ---------------------------------------------------------------------------


def test_duplicate_peer_conflicting_fingerprints_rejected(topology_conf_path):
    """
    Same (host, port) with two different fingerprints: a configuration
    bug the operator must resolve.  Fatal ValueError.
    """
    _write_conf(
        topology_conf_path,
        """
cluster_id: east
peers:
  - host: hq-master-1.example.com
    port: 4521
    finger: aa:aa:aa:aa
  - host: hq-master-1.example.com
    port: 4521
    finger: bb:bb:bb:bb
""",
    )

    with pytest.raises(ValueError, match="finger|duplicate|conflict"):
        load_topology_config(_opts(topology_conf_path))


def test_duplicate_peer_identical_fingerprint_deduplicates(topology_conf_path):
    """Same (host, port, finger) listed twice is silently deduped."""
    _write_conf(
        topology_conf_path,
        """
cluster_id: east
peers:
  - host: hq-master-1.example.com
    port: 4521
    finger: aa:aa:aa:aa
  - host: hq-master-1.example.com
    port: 4521
    finger: aa:aa:aa:aa
""",
    )

    cfg = load_topology_config(_opts(topology_conf_path))

    assert cfg.enabled is True
    assert len(cfg.peers) == 1
    assert cfg.peers[0].host == "hq-master-1.example.com"
    assert cfg.peers[0].port == 4521
    assert cfg.peers[0].finger == "aa:aa:aa:aa"


def test_duplicate_peer_one_without_finger_deduplicates(topology_conf_path):
    """
    (host, port) with finger + same (host, port) without finger: the
    pinned entry wins and the pair is deduplicated.  This is not a
    conflicting-fingerprint case (``None`` does not conflict with any
    specific value), so the loader keeps the stricter entry.
    """
    _write_conf(
        topology_conf_path,
        """
cluster_id: east
peers:
  - host: hq-master-1.example.com
    port: 4521
    finger: aa:aa:aa:aa
  - host: hq-master-1.example.com
    port: 4521
""",
    )

    cfg = load_topology_config(_opts(topology_conf_path))

    assert len(cfg.peers) == 1
    # Pinned fingerprint survives the dedupe --- the loader prefers
    # the more specific entry.
    assert cfg.peers[0].finger == "aa:aa:aa:aa"


def test_empty_string_host_rejected(topology_conf_path):
    """Empty-string host entries make no sense and are rejected."""
    _write_conf(
        topology_conf_path,
        """
cluster_id: east
peers:
  - host: ""
    port: 4521
""",
    )

    with pytest.raises(ValueError, match="host"):
        load_topology_config(_opts(topology_conf_path))


def test_missing_host_rejected(topology_conf_path):
    """A peer entry with no host key at all is rejected."""
    _write_conf(
        topology_conf_path,
        """
cluster_id: east
peers:
  - port: 4521
""",
    )

    with pytest.raises(ValueError, match="host"):
        load_topology_config(_opts(topology_conf_path))


@pytest.mark.parametrize("bad_port", [0, -1, 65536, 100000])
def test_port_out_of_range_rejected(topology_conf_path, bad_port):
    """TCP port must be in 1..65535 when provided."""
    _write_conf(
        topology_conf_path,
        f"""
cluster_id: east
peers:
  - host: hq.example.com
    port: {bad_port}
""",
    )

    with pytest.raises(ValueError, match="port"):
        load_topology_config(_opts(topology_conf_path))


def test_port_valid_edges_accepted(topology_conf_path):
    """1 and 65535 are the inclusive edges of the valid range."""
    _write_conf(
        topology_conf_path,
        """
cluster_id: east
peers:
  - host: a.example.com
    port: 1
  - host: b.example.com
    port: 65535
""",
    )

    cfg = load_topology_config(_opts(topology_conf_path))

    assert cfg.enabled is True
    assert cfg.peers[0].port == 1
    assert cfg.peers[1].port == 65535


def test_port_omitted_is_valid(topology_conf_path):
    """A peer with no ``port`` key loads with ``port=None`` (falls back
    to the master's own ``topology_link_port`` at connect time)."""
    _write_conf(
        topology_conf_path,
        """
cluster_id: east
peers:
  - host: a.example.com
""",
    )

    cfg = load_topology_config(_opts(topology_conf_path))

    assert cfg.enabled is True
    assert len(cfg.peers) == 1
    assert cfg.peers[0].port is None
    assert cfg.peers[0].finger is None


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.geteuid() == 0 if hasattr(os, "geteuid") else False,
    reason="chmod-based unreadable test does not apply to root",
)
@pytest.mark.skipif(
    not hasattr(os, "geteuid"),
    reason="POSIX permission test",
)
def test_unreadable_file_raises_oserror(topology_conf_path):
    """
    File exists but is not readable by this process: OSError is the
    documented contract.  Fatal at daemon start.
    """
    _write_conf(topology_conf_path, "cluster_id: east\n")
    topology_conf_path.chmod(0)
    try:
        with pytest.raises((OSError, PermissionError)):
            load_topology_config(_opts(topology_conf_path))
    finally:
        # Make sure the tmp_path teardown can actually clean up.
        topology_conf_path.chmod(stat.S_IRUSR | stat.S_IWUSR)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


def test_default_event_subscriptions_is_tuple():
    """DEFAULT_EVENT_SUBSCRIPTIONS is an immutable tuple, not a list."""
    assert isinstance(DEFAULT_EVENT_SUBSCRIPTIONS, tuple)
    # Job events only, matches the 'syndic_mode: cluster' baseline.
    assert "salt/job/*/ret/*" in DEFAULT_EVENT_SUBSCRIPTIONS
    assert "salt/job/*/new" in DEFAULT_EVENT_SUBSCRIPTIONS


def test_cluster_id_re_is_string_pattern():
    """CLUSTER_ID_RE is a str; callers compile with ``re.match``."""
    assert isinstance(CLUSTER_ID_RE, str)
    # Not accidentally a precompiled pattern (which would break
    # ``re.match`` call sites that pass ``CLUSTER_ID_RE`` as a str).
    assert hasattr(topology_cfg, "CLUSTER_ID_RE")
