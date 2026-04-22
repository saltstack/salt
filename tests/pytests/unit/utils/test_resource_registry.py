"""
Unit tests for :mod:`salt.utils.resource_registry`.
"""

import pytest

import salt.utils.resource_registry as rr


class _FakeCache:
    """In-memory stand-in for ``salt.cache.factory`` output."""

    def __init__(self):
        self.banks = {}

    def fetch(self, bank, key):
        return self.banks.get(bank, {}).get(key)

    def store(self, bank, key, value):
        self.banks.setdefault(bank, {})[key] = value


@pytest.fixture
def registry(tmp_path):
    opts = {"cachedir": str(tmp_path)}
    cache = _FakeCache()
    return rr.ResourceRegistry(opts, cache=cache)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expr, expected",
    [
        ("vcf_host", {"type": "vcf_host", "id": None}),
        ("vcf_host:esxi-01", {"type": "vcf_host", "id": "esxi-01"}),
        ("", {"type": None, "id": None}),
        (None, {"type": None, "id": None}),
        (":orphan", {"type": None, "id": "orphan"}),
        ("type_only:", {"type": "type_only", "id": None}),
    ],
)
def test_parse_srn(expr, expected):
    assert rr.parse_srn(expr) == expected


def test_resource_index_srn_key():
    assert rr.resource_index_srn_key("ssh", "web-01") == "ssh:web-01"


def test_encode_decode_by_id_roundtrip():
    blob = rr._encode_by_id_value("vcenter-1", "vcf_host")
    out = rr._decode_by_id_value(blob)
    assert out == {"minion": "vcenter-1", "type": "vcf_host"}


def test_decode_by_id_handles_garbage():
    assert rr._decode_by_id_value(None) is None
    assert rr._decode_by_id_value(True) is None
    assert rr._decode_by_id_value("not-json") is None
    assert rr._decode_by_id_value("[1,2]") is None


# ---------------------------------------------------------------------------
# Registry end-to-end
# ---------------------------------------------------------------------------


def test_register_minion_and_read_back(registry):
    registry.register_minion(
        "vcenter-1",
        {
            "vcf_host": ["esxi-01", "esxi-02"],
            "vm": ["vm-a"],
        },
    )

    assert registry.has_resource("vcenter-1", "vcf_host", "esxi-01") is True
    assert registry.has_resource("vcenter-1", "vcf_host", "nope") is False
    assert registry.has_resource_type("vcenter-1", "vm") is True
    assert registry.has_resource_type("vcenter-1", "bogus") is False

    rs = registry.get_resources_for_minion("vcenter-1")
    assert set(rs.keys()) == {"vcf_host", "vm"}
    assert sorted(rs["vcf_host"]) == ["esxi-01", "esxi-02"]

    assert registry.get_managing_minions_for_srn("vcf_host", "esxi-01") == ["vcenter-1"]
    assert registry.get_managing_minions_for_srn("vcf_host", "nope") == []


def test_register_minion_diff_removes_stale(registry):
    registry.register_minion("m1", {"ssh": ["a", "b", "c"], "vm": ["v1"]})
    # Now a smaller inventory: drop "b" and all vms.
    registry.register_minion("m1", {"ssh": ["a", "c"]})

    rs = registry.get_resources_for_minion("m1")
    assert sorted(rs["ssh"]) == ["a", "c"]
    assert "vm" not in rs
    assert registry.has_resource("m1", "ssh", "b") is False
    assert registry.has_resource("m1", "vm", "v1") is False


def test_cross_type_collisions_are_not_ambiguous(registry):
    """Composite SRN keys: same bare id on different types resolves distinctly."""
    registry.register_minion("m1", {"ssh": ["web-01"]})
    registry.register_minion("m2", {"vm": ["web-01"]})

    assert registry.get_managing_minions_for_srn("ssh", "web-01") == ["m1"]
    assert registry.get_managing_minions_for_srn("vm", "web-01") == ["m2"]


def test_managing_minions_by_type(registry):
    registry.register_minion("m1", {"ssh": ["a"]})
    registry.register_minion("m2", {"ssh": ["b"], "vm": ["v"]})
    registry.register_minion("m3", {"vm": ["v2"]})

    got = registry.get_managing_minions_by_type("ssh")
    assert got == {"minions": ["m1", "m2"], "missing": []}

    got = registry.get_managing_minions_by_type("vm")
    assert got == {"minions": ["m2", "m3"], "missing": []}

    got = registry.get_managing_minions_by_type("bogus")
    assert got == {"minions": [], "missing": []}


def test_unregister_minion(registry):
    registry.register_minion("m1", {"ssh": ["a", "b"]})
    registry.register_minion("m2", {"ssh": ["c"]})

    n = registry.unregister_minion("m1")
    assert n == 2

    assert registry.get_resources_for_minion("m1") == {}
    assert registry.get_managing_minions_by_type("ssh") == {
        "minions": ["m2"],
        "missing": [],
    }


def test_compact_preserves_contents(registry):
    registry.register_minion("m1", {"ssh": [f"h{i}" for i in range(50)]})
    registry.register_minion("m2", {"vm": ["v1", "v2"]})

    stats_before = registry.stats()["primary"]
    assert stats_before["occupied"] == 52

    before, after = registry.compact()
    assert before == after == 52

    # Reads still work after swap.
    assert registry.has_resource("m1", "ssh", "h7") is True
    assert registry.get_managing_minions_for_srn("vm", "v2") == ["m2"]


def test_compact_reclaims_tombstones(registry):
    registry.register_minion("m1", {"ssh": [f"h{i}" for i in range(40)]})
    registry.register_minion("m1", {"ssh": [f"h{i}" for i in range(0, 40, 2)]})

    stats_before = registry.stats()["primary"]
    # 40 originals - 20 survivors = 20 deletions; 20 occupied + 20 deleted.
    assert stats_before["occupied"] == 20
    assert stats_before["deleted"] == 20

    before, after = registry.compact()
    assert before == after == 20

    stats_after = registry.stats()["primary"]
    assert stats_after["occupied"] == 20
    assert stats_after["deleted"] == 0


def test_get_resource_uses_resources_bank(registry):
    # The ResourceRegistry uses the fake cache we injected; seed the bank.
    fake_cache = registry._cache
    fake_cache.store(rr.RESOURCE_BANK, "esxi-01", {"managing_minions": ["vcenter-1"]})
    assert registry.get_resource("esxi-01") == {"managing_minions": ["vcenter-1"]}
    assert registry.get_resource("missing") is None


def test_get_managing_minions_for_id_legacy(registry):
    registry._cache.store(
        rr.RESOURCE_BANK, "shared-id", {"managing_minions": ["m1", "m2"]}
    )
    assert registry.get_managing_minions_for_id("shared-id") == ["m1", "m2"]
    assert registry.get_managing_minions_for_id("missing") == []


def test_stats_shape(registry):
    registry.register_minion("m1", {"ssh": ["a"]})
    s = registry.stats()
    assert "primary" in s
    assert "derived_version" in s
    assert "derived_by_type_count" in s
    assert "derived_by_minion_count" in s
    assert "path" in s
    assert s["primary"]["occupied"] == 1


def test_missing_cachedir_raises():
    with pytest.raises(ValueError):
        rr.ResourceRegistry({}, cache=_FakeCache())


# ---------------------------------------------------------------------------
# maybe_compact — policy-driven automatic compaction
# ---------------------------------------------------------------------------


def _make_registry(tmp_path, **overrides):
    opts = {"cachedir": str(tmp_path)}
    opts.update(overrides)
    return rr.ResourceRegistry(opts, cache=_FakeCache())


def test_maybe_compact_throttled_by_default(tmp_path):
    reg = _make_registry(tmp_path)
    # No writes yet, no file either. First call goes through the throttle
    # (because _last_compact_check starts at 0). Second should be throttled.
    first, _ = reg.maybe_compact()
    second, _ = reg.maybe_compact()
    assert first is False  # no file / nothing above threshold
    assert second is False  # throttled


def test_maybe_compact_force_check_bypasses_throttle(tmp_path):
    reg = _make_registry(tmp_path)
    reg.register_minion("m1", {"ssh": ["a", "b", "c"]})
    # Force two back-to-back reads; both should run (no side-effect since
    # nothing is above threshold, but the stats read happens).
    _, s1 = reg.maybe_compact(force_check=True)
    _, s2 = reg.maybe_compact(force_check=True)
    assert s1 is not None
    assert s2 is not None


def test_maybe_compact_triggers_on_tombstone_ratio(tmp_path):
    # Very large interval during setup so register_minion's in-line
    # maybe_compact is suppressed; we drive compaction explicitly.
    reg = _make_registry(
        tmp_path,
        resource_registry_compact_min_interval=3600,
        resource_registry_compact_tombstone_ratio=0.1,
    )
    reg.register_minion("m1", {"ssh": [f"h{i}" for i in range(20)]})
    reg.register_minion("m1", {"ssh": [f"h{i}" for i in range(0, 20, 4)]})

    stats_pre = reg.stats()["primary"]
    assert stats_pre["deleted"] > 0

    compacted, _ = reg.maybe_compact(force_check=True)
    assert compacted is True

    stats_post = reg.stats()["primary"]
    assert stats_post["deleted"] == 0
    assert reg.has_resource("m1", "ssh", "h0") is True
    assert reg.has_resource("m1", "ssh", "h3") is False


def test_maybe_compact_triggers_on_load_factor(tmp_path):
    reg = _make_registry(
        tmp_path,
        resource_index_primary_capacity=128,
        resource_index_primary_slot_size=32,
        resource_registry_compact_load_factor=0.1,
        # Suppress the in-line compact so the test sees an un-compacted file.
        resource_registry_compact_min_interval=3600,
    )
    reg.register_minion("m1", {"ssh": [f"h{i}" for i in range(20)]})
    compacted, stats = reg.maybe_compact(force_check=True)
    # Occupied/total = 20/128 = 0.156 which exceeds 0.1.
    assert compacted is True


def test_maybe_compact_no_trigger_when_healthy(tmp_path):
    reg = _make_registry(
        tmp_path,
        resource_registry_compact_min_interval=0,
    )
    reg.register_minion("m1", {"ssh": ["a", "b"]})
    compacted, stats = reg.maybe_compact(force_check=True)
    assert compacted is False
    assert stats["occupied"] == 2
    assert stats["deleted"] == 0


def test_register_minion_triggers_auto_compact(tmp_path):
    """register_minion invokes maybe_compact inline; when thresholds are met
    on the second call, the tombstones from the delta must be reclaimed."""
    reg = _make_registry(
        tmp_path,
        resource_registry_compact_min_interval=0,
        resource_registry_compact_tombstone_ratio=0.1,
    )
    reg.register_minion("m1", {"ssh": [f"h{i}" for i in range(20)]})
    # The second register_minion deletes 15 entries, tombstone_ratio
    # becomes 15/5 = 3.0 >> 0.1, and the inline maybe_compact reclaims.
    reg.register_minion("m1", {"ssh": [f"h{i}" for i in range(0, 20, 4)]})
    stats = reg.stats()["primary"]
    assert stats["deleted"] == 0
    assert stats["occupied"] == 5
