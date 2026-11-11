"""
Functional tests for :mod:`salt.topology.summary`.

Covers :class:`ClusterSummary` construction and pure helpers against a
real running master provided by the shared topology harness
(``single_master`` fixture) --- the ``collect`` entry point must be
able to read the live accepted-key count out of the master's PKI dir,
not a mocked one.

Behavioral invariants under test:

* ``collect`` returns a ``ClusterSummary`` with ``cluster_id`` from
  ``opts["cluster_id"]``, a one-element ``path`` tuple, a non-negative
  ``minion_count`` sourced from the master's accepted-key state, and
  a strictly-monotonic ``origin_seq`` across successive calls.
* ``collect`` only materializes ``grain_histograms`` when
  ``opts["topology_summary_grains"]`` is set (empty dict otherwise, to
  keep summary size bounded).
* ``with_path_extended`` is a pure functional update ---
  NamedTuple semantics mean the input is never mutated.
* ``is_cycle_for`` is symmetric with ``path`` membership.
* ``serialize`` / ``deserialize`` round-trip preserves every field;
  malformed input raises ``ValueError`` without coercion.
* ``merge_into`` folds counts + histograms into caller-owned aggregate
  dicts without touching the input summary (pure accumulator).
"""

import pytest

import salt.topology.summary as summary_mod
from salt.topology.summary import ClusterSummary

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# collect(opts) against a real master
# ---------------------------------------------------------------------------


def test_collect_returns_cluster_summary(single_master):
    """``collect(opts)`` returns a ``ClusterSummary`` NamedTuple."""
    cluster = single_master(cluster_id="east")
    opts = dict(cluster.masters[0].config)
    opts["cluster_id"] = cluster.cluster_id

    result = summary_mod.collect(opts)

    assert isinstance(result, ClusterSummary)


def test_collect_cluster_id_from_opts(single_master):
    """``summary.cluster_id`` is driven by ``opts["cluster_id"]``."""
    cluster = single_master(cluster_id="west")
    opts = dict(cluster.masters[0].config)
    opts["cluster_id"] = cluster.cluster_id

    result = summary_mod.collect(opts)

    assert result.cluster_id == "west"


def test_collect_path_is_single_hop_origin(single_master):
    """At the origin, ``path = (cluster_id,)`` --- a one-element tuple."""
    cluster = single_master(cluster_id="north")
    opts = dict(cluster.masters[0].config)
    opts["cluster_id"] = cluster.cluster_id

    result = summary_mod.collect(opts)

    assert isinstance(result.path, tuple)
    assert result.path == ("north",)


def test_collect_origin_at_is_recent_timestamp(single_master):
    """``origin_at`` is a Unix timestamp near now (sanity check)."""
    import time

    cluster = single_master(cluster_id="east")
    opts = dict(cluster.masters[0].config)
    opts["cluster_id"] = cluster.cluster_id

    before = time.time()
    result = summary_mod.collect(opts)
    after = time.time()

    assert isinstance(result.origin_at, float)
    assert before <= result.origin_at <= after


def test_collect_origin_seq_monotonic_same_origin(single_master):
    """Successive ``collect`` calls at the same origin produce strictly
    increasing ``origin_seq`` --- addresses clock-skew ordering concern."""
    cluster = single_master(cluster_id="east")
    opts = dict(cluster.masters[0].config)
    opts["cluster_id"] = cluster.cluster_id

    a = summary_mod.collect(opts)
    b = summary_mod.collect(opts)
    c = summary_mod.collect(opts)

    assert a.origin_seq < b.origin_seq < c.origin_seq


def test_collect_minion_count_is_non_negative(single_master):
    """``minion_count`` is a non-negative int; empty master -> 0."""
    cluster = single_master(cluster_id="east")
    opts = dict(cluster.masters[0].config)
    opts["cluster_id"] = cluster.cluster_id

    result = summary_mod.collect(opts)

    assert isinstance(result.minion_count, int)
    assert result.minion_count >= 0


def test_collect_up_count_bounded_by_minion_count(single_master):
    """``up_count <= minion_count`` --- a present minion must be accepted."""
    cluster = single_master(cluster_id="east")
    opts = dict(cluster.masters[0].config)
    opts["cluster_id"] = cluster.cluster_id

    result = summary_mod.collect(opts)

    assert isinstance(result.up_count, int)
    assert result.up_count >= 0
    assert result.up_count <= result.minion_count


def test_collect_empty_master_counts_zero(single_master):
    """A master with no minions reports minion_count == up_count == 0."""
    cluster = single_master(cluster_id="east")
    opts = dict(cluster.masters[0].config)
    opts["cluster_id"] = cluster.cluster_id

    result = summary_mod.collect(opts)

    assert result.minion_count == 0
    assert result.up_count == 0


def test_collect_grain_histograms_empty_by_default(single_master):
    """Without ``topology_summary_grains`` set, histograms are empty."""
    cluster = single_master(cluster_id="east")
    opts = dict(cluster.masters[0].config)
    opts["cluster_id"] = cluster.cluster_id
    # Explicitly ensure the opt is absent.
    opts.pop("topology_summary_grains", None)

    result = summary_mod.collect(opts)

    assert result.grain_histograms == {}


def test_collect_grain_histograms_structure_when_requested(single_master):
    """When ``topology_summary_grains`` lists keys, histograms is a dict
    keyed by those grain names (values may be empty when no minion data
    exists --- shape is what we lock here)."""
    cluster = single_master(cluster_id="east")
    opts = dict(cluster.masters[0].config)
    opts["cluster_id"] = cluster.cluster_id
    opts["topology_summary_grains"] = ["os", "osmajorrelease"]

    result = summary_mod.collect(opts)

    assert isinstance(result.grain_histograms, dict)
    assert set(result.grain_histograms.keys()) == {"os", "osmajorrelease"}
    for value_counts in result.grain_histograms.values():
        assert isinstance(value_counts, dict)


# ---------------------------------------------------------------------------
# with_path_extended --- pure, immutable update
# ---------------------------------------------------------------------------


def test_with_path_extended_appends_next_hop():
    """``with_path_extended(summary, hop)`` returns a copy whose path
    has ``hop`` appended."""
    original = ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=5,
        up_count=3,
        grain_histograms={},
        origin_seq=42,
        origin_at=1_700_000_000.0,
    )

    extended = summary_mod.with_path_extended(original, "west")

    assert extended.path == ("east", "west")


def test_with_path_extended_returns_new_instance():
    """The result is a *new* ClusterSummary; the input is unchanged
    (NamedTuple semantics)."""
    original = ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=5,
        up_count=3,
        grain_histograms={},
        origin_seq=42,
        origin_at=1_700_000_000.0,
    )

    extended = summary_mod.with_path_extended(original, "west")

    assert extended is not original
    assert original.path == ("east",)


def test_with_path_extended_preserves_other_fields():
    """Only ``path`` changes; every other field is copied through."""
    original = ClusterSummary(
        cluster_id="east",
        path=("east", "west"),
        minion_count=5,
        up_count=3,
        grain_histograms={"os": {"RHEL": 2}},
        origin_seq=42,
        origin_at=1_700_000_000.5,
    )

    extended = summary_mod.with_path_extended(original, "south")

    assert extended.cluster_id == "east"
    assert extended.minion_count == 5
    assert extended.up_count == 3
    assert extended.grain_histograms == {"os": {"RHEL": 2}}
    assert extended.origin_seq == 42
    assert extended.origin_at == 1_700_000_000.5
    assert extended.path == ("east", "west", "south")


# ---------------------------------------------------------------------------
# is_cycle_for
# ---------------------------------------------------------------------------


def test_is_cycle_for_true_when_in_path():
    """Returns True when ``cluster_id`` appears anywhere in path."""
    summary = ClusterSummary(
        cluster_id="east",
        path=("east", "mid", "west"),
        minion_count=0,
        up_count=0,
        grain_histograms={},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )

    assert summary_mod.is_cycle_for(summary, "mid") is True
    assert summary_mod.is_cycle_for(summary, "east") is True
    assert summary_mod.is_cycle_for(summary, "west") is True


def test_is_cycle_for_false_when_not_in_path():
    """Returns False when ``cluster_id`` is absent from path."""
    summary = ClusterSummary(
        cluster_id="east",
        path=("east", "mid", "west"),
        minion_count=0,
        up_count=0,
        grain_histograms={},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )

    assert summary_mod.is_cycle_for(summary, "north") is False
    assert summary_mod.is_cycle_for(summary, "south") is False


def test_is_cycle_for_single_hop_path():
    """A fresh single-element path only cycles for its own cluster_id."""
    summary = ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=0,
        up_count=0,
        grain_histograms={},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )

    assert summary_mod.is_cycle_for(summary, "east") is True
    assert summary_mod.is_cycle_for(summary, "other") is False


# ---------------------------------------------------------------------------
# serialize / deserialize round-trip
# ---------------------------------------------------------------------------


def test_serialize_returns_dict():
    """``serialize`` emits a plain dict (not the NamedTuple)."""
    summary = ClusterSummary(
        cluster_id="east",
        path=("east", "west"),
        minion_count=10,
        up_count=7,
        grain_histograms={"os": {"Ubuntu": 5, "RHEL": 2}},
        origin_seq=99,
        origin_at=1_700_000_000.25,
    )

    data = summary_mod.serialize(summary)

    assert isinstance(data, dict)
    assert not isinstance(data, ClusterSummary)


def test_serialize_field_names_match_namedtuple():
    """Field names on the wire match the NamedTuple attribute names."""
    summary = ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=1,
        up_count=1,
        grain_histograms={},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )

    data = summary_mod.serialize(summary)

    assert set(data.keys()) == {
        "cluster_id",
        "path",
        "minion_count",
        "up_count",
        "grain_histograms",
        "origin_seq",
        "origin_at",
    }


def test_serialize_path_is_list_not_tuple():
    """Wire form uses ``list`` for ``path`` (msgpack-friendly)."""
    summary = ClusterSummary(
        cluster_id="east",
        path=("east", "west"),
        minion_count=0,
        up_count=0,
        grain_histograms={},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )

    data = summary_mod.serialize(summary)

    assert isinstance(data["path"], list)
    assert data["path"] == ["east", "west"]


def test_roundtrip_preserves_all_fields():
    """``deserialize(serialize(x)) == x`` for every field."""
    original = ClusterSummary(
        cluster_id="east",
        path=("east", "mid", "west"),
        minion_count=10,
        up_count=7,
        grain_histograms={"os": {"Ubuntu": 5, "RHEL": 2}, "osmajorrelease": {"9": 7}},
        origin_seq=99,
        origin_at=1_700_000_000.25,
    )

    data = summary_mod.serialize(original)
    reconstructed = summary_mod.deserialize(data)

    assert reconstructed == original
    # And its path is a tuple again (NamedTuple contract).
    assert isinstance(reconstructed.path, tuple)


def test_deserialize_missing_field_raises_valueerror():
    """A dict missing a required field is a protocol error."""
    data = {
        "cluster_id": "east",
        "path": ["east"],
        "minion_count": 1,
        "up_count": 1,
        "grain_histograms": {},
        "origin_seq": 1,
        # origin_at omitted
    }
    with pytest.raises(ValueError):
        summary_mod.deserialize(data)


def test_deserialize_wrong_type_raises_valueerror():
    """Wrong field types are rejected without coercion."""
    data = {
        "cluster_id": "east",
        "path": ["east"],
        "minion_count": "not-an-int",
        "up_count": 1,
        "grain_histograms": {},
        "origin_seq": 1,
        "origin_at": 1_700_000_000.0,
    }
    with pytest.raises(ValueError):
        summary_mod.deserialize(data)


def test_deserialize_non_dict_raises_valueerror():
    """Non-dict input (e.g. list, None) is rejected."""
    with pytest.raises(ValueError):
        summary_mod.deserialize(["not", "a", "dict"])
    with pytest.raises(ValueError):
        summary_mod.deserialize(None)


# ---------------------------------------------------------------------------
# merge_into --- pure accumulator
# ---------------------------------------------------------------------------


def test_merge_into_accumulates_counts():
    """``merge_into`` folds a summary's counts into caller-owned totals."""
    s = ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=10,
        up_count=7,
        grain_histograms={},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )
    counts = {}
    histograms = {}

    summary_mod.merge_into(s, counts, histograms)

    assert counts["minion_count"] == 10
    assert counts["up_count"] == 7


def test_merge_into_accumulates_multiple_summaries():
    """Successive ``merge_into`` calls add to the running totals."""
    a = ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=10,
        up_count=7,
        grain_histograms={"os": {"Ubuntu": 5, "RHEL": 2}},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )
    b = ClusterSummary(
        cluster_id="west",
        path=("west",),
        minion_count=20,
        up_count=15,
        grain_histograms={"os": {"Ubuntu": 10, "Debian": 1}},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )
    counts = {}
    histograms = {}

    summary_mod.merge_into(a, counts, histograms)
    summary_mod.merge_into(b, counts, histograms)

    assert counts["minion_count"] == 30
    assert counts["up_count"] == 22
    assert histograms["os"] == {"Ubuntu": 15, "RHEL": 2, "Debian": 1}


def test_merge_into_does_not_mutate_summary():
    """``merge_into`` is pure --- the summary argument is unchanged."""
    s = ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=10,
        up_count=7,
        grain_histograms={"os": {"Ubuntu": 5}},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )
    counts = {}
    histograms = {}

    summary_mod.merge_into(s, counts, histograms)

    # NamedTuple equality on original value.
    assert s == ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=10,
        up_count=7,
        grain_histograms={"os": {"Ubuntu": 5}},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )


def test_merge_into_grain_histograms_shape_preserved():
    """Histogram values are added per inner key; shape is dict-of-dict."""
    s = ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=1,
        up_count=1,
        grain_histograms={"os": {"RHEL": 3}, "osmajorrelease": {"9": 3}},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )
    counts = {}
    histograms = {}

    summary_mod.merge_into(s, counts, histograms)

    assert histograms == {"os": {"RHEL": 3}, "osmajorrelease": {"9": 3}}
