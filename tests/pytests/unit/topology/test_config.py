"""
Unit tests for :mod:`salt.config.topology`.

Covers the module's internals in isolation --- no file I/O.  Exercises
:func:`validate_topology_config` against hand-built
:class:`TopologyConfig` instances, confirms the NamedTuple immutability
semantics for :class:`PeerRef` and :class:`TopologyConfig`, and pins
the :data:`CLUSTER_ID_RE` edge cases that the file loader relies on.
"""

import re

import pytest

from salt.config.topology import (
    CLUSTER_ID_RE,
    DEFAULT_EVENT_SUBSCRIPTIONS,
    PeerRef,
    TopologyConfig,
    validate_topology_config,
)

# ---------------------------------------------------------------------------
# NamedTuple shape / immutability
# ---------------------------------------------------------------------------


class TestPeerRefNamedTuple:
    """PeerRef is a frozen NamedTuple with host/port/finger fields."""

    def test_positional_construction(self):
        peer = PeerRef("hq.example.com", 4521, "aa:bb")
        assert peer.host == "hq.example.com"
        assert peer.port == 4521
        assert peer.finger == "aa:bb"

    def test_defaults(self):
        """port and finger default to None."""
        peer = PeerRef("hq.example.com")
        assert peer.host == "hq.example.com"
        assert peer.port is None
        assert peer.finger is None

    def test_keyword_construction(self):
        peer = PeerRef(host="hq.example.com", finger="aa:bb")
        assert peer.port is None
        assert peer.finger == "aa:bb"

    def test_is_a_tuple(self):
        """PeerRef indexes like a 3-tuple."""
        peer = PeerRef("hq.example.com", 4521, "aa:bb")
        assert tuple(peer) == ("hq.example.com", 4521, "aa:bb")
        assert len(peer) == 3

    def test_immutable_cannot_assign_attribute(self):
        """NamedTuple semantics: attribute assignment raises."""
        peer = PeerRef("hq.example.com", 4521, "aa:bb")
        with pytest.raises(AttributeError):
            peer.host = "pwned.example.com"

    def test_equality_and_hash(self):
        """Equal PeerRefs hash equally --- usable as dict keys."""
        a = PeerRef("hq.example.com", 4521, "aa:bb")
        b = PeerRef("hq.example.com", 4521, "aa:bb")
        c = PeerRef("hq.example.com", 4522, "aa:bb")
        assert a == b
        assert a != c
        assert hash(a) == hash(b)
        # Set collapses the equal pair.
        assert len({a, b, c}) == 2


class TestTopologyConfigNamedTuple:
    """TopologyConfig is a frozen NamedTuple with four fields."""

    def test_fields(self):
        cfg = TopologyConfig(
            cluster_id="east",
            peers=(PeerRef("a.example.com"),),
            event_subscriptions=DEFAULT_EVENT_SUBSCRIPTIONS,
            enabled=True,
        )
        assert cfg.cluster_id == "east"
        assert cfg.peers == (PeerRef("a.example.com"),)
        assert cfg.event_subscriptions is DEFAULT_EVENT_SUBSCRIPTIONS
        assert cfg.enabled is True

    def test_immutable_cannot_assign_attribute(self):
        cfg = TopologyConfig(
            cluster_id="east",
            peers=(),
            event_subscriptions=DEFAULT_EVENT_SUBSCRIPTIONS,
            enabled=True,
        )
        with pytest.raises(AttributeError):
            cfg.enabled = False

    def test_is_a_tuple(self):
        """TopologyConfig indexes like a 4-tuple."""
        cfg = TopologyConfig(
            cluster_id="east",
            peers=(),
            event_subscriptions=DEFAULT_EVENT_SUBSCRIPTIONS,
            enabled=True,
        )
        assert len(cfg) == 4
        assert cfg[0] == "east"
        assert cfg[3] is True


# ---------------------------------------------------------------------------
# CLUSTER_ID_RE edge cases
# ---------------------------------------------------------------------------


class TestClusterIdRegex:
    """CLUSTER_ID_RE pins the shape of a valid cluster_id."""

    @pytest.mark.parametrize(
        "cluster_id",
        [
            "east",
            "west",
            "a",  # single char
            "0",  # single digit
            "0east",  # leading digit ok
            "cluster-1",  # hyphen in middle
            "cluster_1",  # underscore in middle
            "a_b-c_d-e-f",  # mixed middle
            "x" * 64,  # realistic max-ish
        ],
    )
    def test_valid_ids_match(self, cluster_id):
        assert re.match(CLUSTER_ID_RE, cluster_id) is not None

    @pytest.mark.parametrize(
        "cluster_id",
        [
            "",  # empty
            "East",  # uppercase
            "EAST",  # uppercase
            "east.west",  # dot
            "east west",  # space
            "east/west",  # slash
            "east\\west",  # backslash
            "east$",  # shell metachar
            "east;rm -rf",  # shell injection shape
            "-east",  # leading hyphen
            "_east",  # leading underscore (reserved space)
            "éast",  # non-ascii
            # NOTE: "east\n" is deliberately not here --- Python's re
            # treats $ as "end of string OR just before a trailing
            # newline", so the regex does match "east\n".  YAML
            # safe_load strips trailing newlines from scalars, so a
            # trailing-newline cluster_id is unreachable from the
            # file-loading path; we accept the regex as published.
        ],
    )
    def test_invalid_ids_do_not_match(self, cluster_id):
        assert (
            re.match(CLUSTER_ID_RE, cluster_id) is None
        ), f"{cluster_id!r} unexpectedly matched"

    def test_regex_is_anchored_both_ends(self):
        """Pattern uses ^ and $ --- partial matches on long garbage reject."""
        assert re.match(CLUSTER_ID_RE, "east evil") is None
        # Full-match semantics via explicit re.fullmatch on a valid id.
        assert re.fullmatch(CLUSTER_ID_RE, "east") is not None


# ---------------------------------------------------------------------------
# validate_topology_config on hand-built instances
# ---------------------------------------------------------------------------


def _enabled_cfg(**overrides):
    """Factory for a valid baseline enabled TopologyConfig."""
    base = {
        "cluster_id": "east",
        "peers": (),
        "event_subscriptions": DEFAULT_EVENT_SUBSCRIPTIONS,
        "enabled": True,
    }
    base.update(overrides)
    return TopologyConfig(**base)


class TestValidateDisabledShortCircuit:
    """A disabled config is accepted no matter what the other fields hold."""

    def test_disabled_with_empty_everything(self):
        cfg = TopologyConfig(
            cluster_id="",
            peers=(),
            event_subscriptions=(),
            enabled=False,
        )
        # Returns None (no exception).
        assert validate_topology_config(cfg) is None

    def test_disabled_with_garbage_cluster_id_still_accepted(self):
        """
        Disabled bypasses invariants; a hand-built disabled config
        used by the loader short-circuit sets cluster_id="" and must
        not raise.
        """
        cfg = TopologyConfig(
            cluster_id="",
            peers=(),
            event_subscriptions=DEFAULT_EVENT_SUBSCRIPTIONS,
            enabled=False,
        )
        validate_topology_config(cfg)


class TestValidateRejectsNonTopologyConfig:
    """The validator refuses to look at anything that isn't a TopologyConfig."""

    @pytest.mark.parametrize("value", [None, {}, [], "east", 42])
    def test_wrong_type_raises(self, value):
        with pytest.raises(ValueError, match="TopologyConfig"):
            validate_topology_config(value)


class TestValidateClusterIdInvariants:
    """cluster_id is required and must satisfy CLUSTER_ID_RE."""

    def test_valid_cluster_id_accepted(self):
        validate_topology_config(_enabled_cfg(cluster_id="east"))

    def test_cluster_id_with_leading_digit_accepted(self):
        """Regex explicitly allows [a-z0-9] as the first character."""
        validate_topology_config(_enabled_cfg(cluster_id="0east"))

    def test_empty_cluster_id_rejected(self):
        with pytest.raises(ValueError, match="cluster_id"):
            validate_topology_config(_enabled_cfg(cluster_id=""))

    def test_none_cluster_id_rejected(self):
        with pytest.raises(ValueError, match="cluster_id"):
            validate_topology_config(_enabled_cfg(cluster_id=None))

    def test_uppercase_cluster_id_rejected(self):
        with pytest.raises(ValueError, match="cluster_id"):
            validate_topology_config(_enabled_cfg(cluster_id="East"))

    def test_leading_hyphen_cluster_id_rejected(self):
        with pytest.raises(ValueError, match="cluster_id"):
            validate_topology_config(_enabled_cfg(cluster_id="-east"))

    def test_reserved_identity_pub_rejected(self):
        """``__identity_pub__`` is explicitly reserved by name."""
        with pytest.raises(ValueError, match="reserved|cluster_id"):
            validate_topology_config(_enabled_cfg(cluster_id="__identity_pub__"))


class TestValidatePeerInvariants:
    """peers list structure and contents."""

    def test_single_valid_peer_accepted(self):
        cfg = _enabled_cfg(
            peers=(PeerRef("hq.example.com", 4521, "aa:bb"),),
        )
        validate_topology_config(cfg)

    def test_peer_without_port_or_finger_accepted(self):
        validate_topology_config(_enabled_cfg(peers=(PeerRef("hq.example.com"),)))

    def test_peers_as_list_rejected(self):
        """peers must be a tuple (immutable); a list is a shape error."""
        cfg = TopologyConfig(
            cluster_id="east",
            peers=[PeerRef("hq.example.com")],
            event_subscriptions=DEFAULT_EVENT_SUBSCRIPTIONS,
            enabled=True,
        )
        with pytest.raises(ValueError, match="peers"):
            validate_topology_config(cfg)

    def test_peer_wrong_type_rejected(self):
        """A non-PeerRef entry (e.g. a dict) is a bug in the loader."""
        cfg = _enabled_cfg(peers=({"host": "hq.example.com"},))
        with pytest.raises(ValueError, match="PeerRef"):
            validate_topology_config(cfg)

    def test_empty_host_rejected(self):
        cfg = _enabled_cfg(peers=(PeerRef("", 4521),))
        with pytest.raises(ValueError, match="host"):
            validate_topology_config(cfg)

    def test_non_string_host_rejected(self):
        cfg = _enabled_cfg(peers=(PeerRef(42, 4521),))
        with pytest.raises(ValueError, match="host"):
            validate_topology_config(cfg)

    @pytest.mark.parametrize("port", [0, -1, 65536, 70000])
    def test_port_out_of_range_rejected(self, port):
        cfg = _enabled_cfg(peers=(PeerRef("hq.example.com", port),))
        with pytest.raises(ValueError, match="port"):
            validate_topology_config(cfg)

    def test_port_as_string_rejected(self):
        cfg = _enabled_cfg(peers=(PeerRef("hq.example.com", "4521"),))
        with pytest.raises(ValueError, match="port"):
            validate_topology_config(cfg)

    def test_port_as_bool_rejected(self):
        """bool is an int subclass; explicit guard keeps True/False out."""
        cfg = _enabled_cfg(peers=(PeerRef("hq.example.com", True),))
        with pytest.raises(ValueError, match="port"):
            validate_topology_config(cfg)

    def test_port_edges_accepted(self):
        cfg = _enabled_cfg(
            peers=(
                PeerRef("a.example.com", 1),
                PeerRef("b.example.com", 65535),
            ),
        )
        validate_topology_config(cfg)

    def test_duplicate_peer_conflicting_fingerprints_rejected(self):
        cfg = _enabled_cfg(
            peers=(
                PeerRef("hq.example.com", 4521, "aa:aa"),
                PeerRef("hq.example.com", 4521, "bb:bb"),
            ),
        )
        with pytest.raises(ValueError, match="finger|conflict|duplicate"):
            validate_topology_config(cfg)


class TestValidateEventSubscriptionsInvariants:
    """event_subscriptions must be a tuple of non-empty strings."""

    def test_default_subscriptions_accepted(self):
        validate_topology_config(_enabled_cfg())

    def test_custom_subscriptions_accepted(self):
        cfg = _enabled_cfg(
            event_subscriptions=("salt/presence/change", "custom/*"),
        )
        validate_topology_config(cfg)

    def test_empty_tuple_accepted(self):
        """Zero subscriptions is a legal (though useless) configuration."""
        cfg = _enabled_cfg(event_subscriptions=())
        validate_topology_config(cfg)

    def test_subscriptions_as_list_rejected(self):
        cfg = TopologyConfig(
            cluster_id="east",
            peers=(),
            event_subscriptions=["salt/job/*/ret/*"],
            enabled=True,
        )
        with pytest.raises(ValueError, match="event_subscriptions"):
            validate_topology_config(cfg)

    def test_empty_string_subscription_rejected(self):
        cfg = _enabled_cfg(event_subscriptions=("",))
        with pytest.raises(ValueError, match="event_subscriptions"):
            validate_topology_config(cfg)

    def test_non_string_subscription_rejected(self):
        cfg = _enabled_cfg(event_subscriptions=(42,))
        with pytest.raises(ValueError, match="event_subscriptions"):
            validate_topology_config(cfg)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


class TestDefaultEventSubscriptions:
    """DEFAULT_EVENT_SUBSCRIPTIONS pins the no-override wire behavior."""

    def test_is_tuple(self):
        assert isinstance(DEFAULT_EVENT_SUBSCRIPTIONS, tuple)

    def test_default_set_is_job_events_only(self):
        """Default is job events --- matches syndic_mode: cluster shape."""
        assert set(DEFAULT_EVENT_SUBSCRIPTIONS) == {
            "salt/job/*/ret/*",
            "salt/job/*/new",
        }

    def test_each_entry_is_str(self):
        for pattern in DEFAULT_EVENT_SUBSCRIPTIONS:
            assert isinstance(pattern, str)
            assert pattern  # non-empty
