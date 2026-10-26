"""
Unit tests for :mod:`salt.topology.summary` internals.

These exercise properties that are hard to assert cleanly in the
functional layer:

* ``origin_seq`` monotonicity across concurrent threads (the
  heartbeat task and an ad-hoc ``topology.status`` runner can race).
* The wire form emitted by :func:`serialize` is msgpack-encodable
  --- no NamedTuple instances leaking into the payload, no tuples
  masquerading as lists, no unhashable dict keys.
* :func:`with_path_extended` behaves on both the empty-path corner
  case (shouldn't happen in practice but should not blow up) and
  the typical non-empty path.
* Grain histograms with the nested-dict shape round-trip through
  serialize/deserialize unchanged, including nested value counts.
"""

import threading

import msgpack
import pytest

import salt.topology.summary as summary_mod
from salt.topology.summary import ClusterSummary

# ---------------------------------------------------------------------------
# origin_seq monotonicity (thread-safety)
# ---------------------------------------------------------------------------


def test_origin_seq_monotonic_direct():
    """Direct ``next(_SEQ_COUNTER)`` is strictly monotonic serially."""
    a = next(summary_mod._SEQ_COUNTER)
    b = next(summary_mod._SEQ_COUNTER)
    c = next(summary_mod._SEQ_COUNTER)
    assert a < b < c


def test_origin_seq_unique_under_thread_contention():
    """Concurrent threads calling ``next(_SEQ_COUNTER)`` get unique
    values --- no two threads can observe the same ``origin_seq``.

    ``itertools.count`` holds the CPython GIL during its ``__next__``
    so the increment is atomic.  We assert that invariant here so a
    future refactor that reaches for a non-atomic counter trips the
    test.
    """
    seen = []
    lock = threading.Lock()
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        local = []
        for _ in range(500):
            local.append(next(summary_mod._SEQ_COUNTER))
        with lock:
            seen.extend(local)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(seen) == 8 * 500
    assert len(set(seen)) == len(seen)  # all unique
    assert sorted(seen) == list(range(min(seen), max(seen) + 1))  # contiguous


# ---------------------------------------------------------------------------
# serialize output is msgpack-encodable
# ---------------------------------------------------------------------------


def test_serialize_output_is_msgpack_roundtrip():
    """``serialize(summary)`` emits only primitive types that msgpack
    can pack and unpack losslessly.  Guards against a future
    refactor that leaves a NamedTuple nested inside the payload
    (msgpack would silently pack it as a tuple, breaking the
    deserialize contract on the receiver)."""
    summary = ClusterSummary(
        cluster_id="east",
        path=("east", "mid", "west"),
        minion_count=10,
        up_count=7,
        grain_histograms={
            "os": {"Ubuntu": 5, "RHEL": 2},
            "osmajorrelease": {"9": 7},
        },
        origin_seq=99,
        origin_at=1_700_000_000.5,
    )

    data = summary_mod.serialize(summary)
    packed = msgpack.packb(data, use_bin_type=True)
    unpacked = msgpack.unpackb(packed, raw=False)

    # Round-trip through deserialize --- the ultimate on-wire test.
    reconstructed = summary_mod.deserialize(unpacked)
    assert reconstructed == summary


def test_serialize_output_has_no_namedtuple_leak():
    """No value in the wire dict is a ClusterSummary instance."""
    summary = ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=1,
        up_count=1,
        grain_histograms={"os": {"Ubuntu": 1}},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )
    data = summary_mod.serialize(summary)
    for key, value in data.items():
        assert not isinstance(value, ClusterSummary), key


def test_serialize_output_grain_histograms_are_plain_dicts():
    """Nested grain-histogram dicts are plain ``dict`` --- not an
    OrderedDict or any subclass that msgpack might stumble on."""
    summary = ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=0,
        up_count=0,
        grain_histograms={"os": {"RHEL": 1}},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )
    data = summary_mod.serialize(summary)
    assert (
        type(data["grain_histograms"]) is dict
    )  # pylint: disable=unidiomatic-typecheck
    for inner in data["grain_histograms"].values():
        assert type(inner) is dict  # pylint: disable=unidiomatic-typecheck


# ---------------------------------------------------------------------------
# with_path_extended corner cases
# ---------------------------------------------------------------------------


def test_with_path_extended_empty_path():
    """Even if a (malformed) summary has an empty path, extending works."""
    s = ClusterSummary(
        cluster_id="east",
        path=(),
        minion_count=0,
        up_count=0,
        grain_histograms={},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )
    extended = summary_mod.with_path_extended(s, "west")
    assert extended.path == ("west",)
    assert s.path == ()  # original unchanged


def test_with_path_extended_non_empty_path():
    """Appending to a multi-hop path puts the new hop at the end."""
    s = ClusterSummary(
        cluster_id="east",
        path=("east", "mid"),
        minion_count=0,
        up_count=0,
        grain_histograms={},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )
    extended = summary_mod.with_path_extended(s, "west")
    assert extended.path == ("east", "mid", "west")


def test_with_path_extended_chained_calls():
    """Chaining ``with_path_extended`` builds the path left-to-right."""
    s = ClusterSummary(
        cluster_id="origin",
        path=("origin",),
        minion_count=0,
        up_count=0,
        grain_histograms={},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )
    s = summary_mod.with_path_extended(s, "hop1")
    s = summary_mod.with_path_extended(s, "hop2")
    s = summary_mod.with_path_extended(s, "hop3")
    assert s.path == ("origin", "hop1", "hop2", "hop3")


# ---------------------------------------------------------------------------
# grain_histograms with nested dict shapes
# ---------------------------------------------------------------------------


def test_grain_histograms_many_keys_round_trip():
    """A histogram with many top-level keys and many buckets each
    round-trips through serialize/deserialize intact."""
    histograms = {
        "os": {"Ubuntu": 100, "RHEL": 50, "Debian": 25, "Rocky": 10},
        "osmajorrelease": {"8": 50, "9": 60, "22": 100, "11": 25},
        "osarch": {"x86_64": 180, "aarch64": 55},
    }
    original = ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=235,
        up_count=200,
        grain_histograms=histograms,
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )
    data = summary_mod.serialize(original)
    reconstructed = summary_mod.deserialize(data)
    assert reconstructed.grain_histograms == histograms


def test_grain_histograms_empty_inner_dict_preserved():
    """A grain key with no observed values keeps its ``{}`` shape ---
    receivers can distinguish 'asked, nobody reports it' from
    'never asked'."""
    original = ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=0,
        up_count=0,
        grain_histograms={"os": {}, "osmajorrelease": {}},
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )
    data = summary_mod.serialize(original)
    reconstructed = summary_mod.deserialize(data)
    assert reconstructed.grain_histograms == {"os": {}, "osmajorrelease": {}}


def test_serialize_decouples_from_input_dict():
    """Mutating the summary's grain_histograms after serialize does
    not leak into the wire payload (serialize produces a copy)."""
    inner = {"RHEL": 3}
    outer = {"os": inner}
    summary = ClusterSummary(
        cluster_id="east",
        path=("east",),
        minion_count=1,
        up_count=1,
        grain_histograms=outer,
        origin_seq=1,
        origin_at=1_700_000_000.0,
    )
    data = summary_mod.serialize(summary)
    # Mutate the originals.
    inner["RHEL"] = 99
    outer["os2"] = {"X": 1}
    # Wire payload is untouched.
    assert data["grain_histograms"] == {"os": {"RHEL": 3}}


# ---------------------------------------------------------------------------
# deserialize strict-typing (unit-level complement to the functional set)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutation",
    [
        {"cluster_id": 123},
        {"path": "east"},  # str, not list
        {"path": [1, 2, 3]},  # non-str hops
        {"minion_count": True},  # bool rejected
        {"up_count": 1.5},  # float not accepted for int field
        {"grain_histograms": "nope"},
        {"grain_histograms": {"os": "nope"}},  # inner not dict
        {"origin_seq": "1"},
        {"origin_at": "now"},
    ],
)
def test_deserialize_rejects_type_errors(mutation):
    """Each field type is strictly enforced; coercion is not attempted."""
    base = {
        "cluster_id": "east",
        "path": ["east"],
        "minion_count": 1,
        "up_count": 1,
        "grain_histograms": {},
        "origin_seq": 1,
        "origin_at": 1_700_000_000.0,
    }
    base.update(mutation)
    with pytest.raises(ValueError):
        summary_mod.deserialize(base)
