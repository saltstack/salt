"""
Functional tests for :mod:`salt.config.topology`.

Exercises :func:`load_topology_config` end-to-end against opts dicts
and the full validator surface reached via the loader.  No master
daemon is started.  Starts-a-master coverage lives in the shared
harness tests under ``test_harness.py``.
"""

import pytest

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
# Helpers
# ---------------------------------------------------------------------------


def _opts(enabled=True, cluster_id="east", peers=None, event_subscriptions=None):
    """Minimal master opts dict for topology loader tests."""
    return {
        "topology_enabled": enabled,
        "cluster_id": cluster_id,
        "topology_peers": list(peers) if peers else [],
        "topology_event_subscriptions": event_subscriptions,
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_load_wellformed_opts():
    """A well-formed opts dict loads into an enabled TopologyConfig."""
    cfg = load_topology_config(
        _opts(
            cluster_id="east",
            peers=[
                {"host": "hq-master-1.example.com", "port": 4521},
                {"host": "west-master-1.example.com", "finger": "00:11:22:33"},
            ],
            event_subscriptions=[
                "salt/job/*/ret/*",
                "salt/job/*/new",
                "salt/presence/change",
            ],
        )
    )

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


def test_load_minimal_opts_only_cluster_id():
    """Enabled + cluster_id and nothing else is valid; defaults fill in."""
    cfg = load_topology_config(_opts(cluster_id="solo"))

    assert cfg.enabled is True
    assert cfg.cluster_id == "solo"
    assert cfg.peers == ()
    assert cfg.event_subscriptions == DEFAULT_EVENT_SUBSCRIPTIONS


def test_event_subscriptions_default_when_none():
    """Unset ``topology_event_subscriptions`` yields the default tuple."""
    cfg = load_topology_config(_opts(cluster_id="east", event_subscriptions=None))

    assert cfg.event_subscriptions == DEFAULT_EVENT_SUBSCRIPTIONS


def test_event_subscriptions_empty_list_honored():
    """
    An explicit empty list is distinct from None: it means "forward
    nothing" and must survive the loader as an empty tuple.
    """
    cfg = load_topology_config(_opts(cluster_id="east", event_subscriptions=[]))

    assert cfg.event_subscriptions == ()


# ---------------------------------------------------------------------------
# Disabled short-circuit
# ---------------------------------------------------------------------------


def test_disabled_returns_inert_config():
    """``topology_enabled: False`` returns a disabled TopologyConfig."""
    cfg = load_topology_config(_opts(enabled=False))

    assert cfg.enabled is False
    assert cfg.cluster_id == ""
    assert cfg.peers == ()
    assert cfg.event_subscriptions == DEFAULT_EVENT_SUBSCRIPTIONS


def test_disabled_ignores_other_opts():
    """
    A disabled loader does NOT read ``cluster_id`` or
    ``topology_peers``.  Operators who flip ``topology_enabled`` off
    expect the entire feature to go inert.
    """
    cfg = load_topology_config(
        {
            "topology_enabled": False,
            "cluster_id": "east",
            "topology_peers": [{"host": "ignored", "port": 4521}],
        }
    )

    assert cfg.enabled is False
    assert cfg.cluster_id == ""
    assert cfg.peers == ()


def test_enabled_missing_opts_treated_as_empty():
    """
    Enabled + no ``topology_peers`` -> empty peers tuple (not an
    error).  Lets a solo master run without any peers configured.
    """
    cfg = load_topology_config(
        {
            "topology_enabled": True,
            "cluster_id": "solo",
        }
    )
    assert cfg.enabled is True
    assert cfg.cluster_id == "solo"
    assert cfg.peers == ()


# ---------------------------------------------------------------------------
# cluster_id invariants
# ---------------------------------------------------------------------------


def test_missing_cluster_id_rejected():
    """Enabled + empty cluster_id fails validation."""
    with pytest.raises(ValueError, match="cluster_id is required"):
        load_topology_config(_opts(cluster_id=""))


@pytest.mark.parametrize(
    "bad_id",
    [
        "EAST",  # uppercase
        "east master",  # whitespace
        "east!",  # shell-sensitive
        "east/west",  # path separator
        "-east",  # leading dash
        "_east",  # leading underscore (hits reserved-prefix guard)
    ],
)
def test_cluster_id_regex_rejects_bad_shapes(bad_id):
    """Each shape forbidden by :data:`CLUSTER_ID_RE` is rejected."""
    with pytest.raises(ValueError, match="cluster_id"):
        load_topology_config(_opts(cluster_id=bad_id))


@pytest.mark.parametrize("reserved", ["__identity_pub__", "__cluster_meta__"])
def test_cluster_id_rejects_reserved_names(reserved):
    """
    The MmapCache sentinel keys are rejected even if a future regex
    relaxation would otherwise admit them.
    """
    import re

    # Belt-and-braces: the current regex happens to reject these
    # (double-underscore leading) but this test is specifically for
    # the explicit-reserved-set guard, so we only run it when the
    # regex would otherwise admit the name.
    if not re.match(CLUSTER_ID_RE, reserved):
        pytest.skip("reserved name is already caught by the regex")
    with pytest.raises(ValueError, match="reserved"):
        load_topology_config(_opts(cluster_id=reserved))


# ---------------------------------------------------------------------------
# peers invariants
# ---------------------------------------------------------------------------


def test_peers_must_be_list():
    """A non-list ``topology_peers`` is rejected before coercion."""
    with pytest.raises(ValueError, match="topology_peers must be a list"):
        load_topology_config(
            {
                "topology_enabled": True,
                "cluster_id": "east",
                "topology_peers": "not-a-list",
            }
        )


def test_peer_entry_must_be_mapping():
    """Each entry must be a dict (host/port/finger)."""
    with pytest.raises(ValueError, match=r"topology_peers\[0\]"):
        load_topology_config(
            _opts(cluster_id="east", peers=["not-a-dict"]),
        )


def test_peer_entry_requires_host_key():
    """A peer entry missing ``host`` is rejected."""
    with pytest.raises(ValueError, match="missing required 'host' key"):
        load_topology_config(_opts(cluster_id="east", peers=[{"port": 4521}]))


def test_peer_port_must_be_int():
    """A non-int port is rejected with a key-naming error."""
    with pytest.raises(ValueError, match="port must be int"):
        load_topology_config(
            _opts(cluster_id="east", peers=[{"host": "h", "port": "4521"}]),
        )


def test_peer_port_out_of_range_rejected():
    """A port outside 1-65535 is rejected."""
    with pytest.raises(ValueError, match="out of range"):
        load_topology_config(
            _opts(cluster_id="east", peers=[{"host": "h", "port": 99999}]),
        )


def test_peer_dedup_exact_duplicates():
    """
    Two identical ``(host, port, finger)`` entries are collapsed to
    one; no error.
    """
    cfg = load_topology_config(
        _opts(
            cluster_id="east",
            peers=[
                {"host": "a", "port": 4521},
                {"host": "a", "port": 4521},
            ],
        )
    )
    assert len(cfg.peers) == 1


def test_peer_dedup_promotes_pinned():
    """
    Duplicate (host, port) with one pinned fingerprint keeps the
    pinned entry (more specific wins).
    """
    cfg = load_topology_config(
        _opts(
            cluster_id="east",
            peers=[
                {"host": "a", "port": 4521},
                {"host": "a", "port": 4521, "finger": "aa:bb"},
            ],
        )
    )
    assert len(cfg.peers) == 1
    assert cfg.peers[0].finger == "aa:bb"


def test_peer_conflicting_fingerprints_rejected():
    """Two different non-None fingerprints on the same (host, port) fail."""
    with pytest.raises(ValueError, match="conflicting fingerprints"):
        load_topology_config(
            _opts(
                cluster_id="east",
                peers=[
                    {"host": "a", "port": 4521, "finger": "aa:bb"},
                    {"host": "a", "port": 4521, "finger": "cc:dd"},
                ],
            )
        )


# ---------------------------------------------------------------------------
# event_subscriptions invariants
# ---------------------------------------------------------------------------


def test_event_subscriptions_must_be_list_or_none():
    """A non-list event_subscriptions is rejected."""
    with pytest.raises(ValueError, match="topology_event_subscriptions must be a list"):
        load_topology_config(
            {
                "topology_enabled": True,
                "cluster_id": "east",
                "topology_peers": [],
                "topology_event_subscriptions": "salt/job/*",
            }
        )


def test_event_subscriptions_non_string_entry_rejected():
    """A non-string entry in event_subscriptions fails validation."""
    with pytest.raises(ValueError, match="event_subscriptions"):
        load_topology_config(
            _opts(cluster_id="east", event_subscriptions=[123, "salt/job/*"])
        )


def test_event_subscriptions_empty_string_entry_rejected():
    """An empty-string entry in event_subscriptions is rejected."""
    with pytest.raises(ValueError, match="event_subscriptions"):
        load_topology_config(_opts(cluster_id="east", event_subscriptions=[""]))
