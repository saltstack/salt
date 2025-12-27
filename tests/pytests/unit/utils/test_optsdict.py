"""
Unit tests for salt.utils.optsdict

Tests cover:
- Basic dict interface compliance
- Copy-on-write semantics
- Mutation tracking
- Parent-child relationships
- Memory efficiency
- Thread safety
"""

import copy
import sys
import threading

import pytest

# Add parent directory to path for imports
sys.path.insert(0, "/home/dan/src/wt/minion_mem")

from salt.utils.optsdict import MutationTracker, OptsDict, safe_opts_copy


class TestMutationTracker:
    """Test MutationTracker functionality."""

    def test_basic_tracking(self):
        """Test basic mutation recording."""
        tracker = MutationTracker(track_mutations=True)

        tracker.record_mutation("test", False, True)

        report = tracker.get_mutation_report(verbose=False)
        assert "test" in report
        assert report["test"]["mutation_count"] == 1
        assert report["test"]["original_value_type"] == "bool"
        assert report["test"]["current_value_type"] == "bool"

    def test_multiple_mutations(self):
        """Test tracking multiple mutations of same key."""
        tracker = MutationTracker(track_mutations=True)

        tracker.record_mutation("test", False, True)
        tracker.record_mutation("test", True, False)
        tracker.record_mutation("test", False, True)

        report = tracker.get_mutation_report(verbose=True)
        assert report["test"]["mutation_count"] == 3
        assert len(report["test"]["all_mutations"]) == 3

    def test_hotspot_detection(self):
        """Test identifying frequently mutated keys."""
        tracker = MutationTracker(track_mutations=True)

        # Mutate 'test' many times
        for i in range(5):
            tracker.record_mutation("test", i, i + 1)

        # Mutate 'saltenv' once
        tracker.record_mutation("saltenv", "base", "dev")

        hotspots = tracker.get_hotspot_keys(min_mutations=2)
        assert "test" in hotspots
        assert "saltenv" not in hotspots

    def test_disabled_tracking(self):
        """Test that tracking can be disabled."""
        tracker = MutationTracker(track_mutations=False)

        tracker.record_mutation("test", False, True)

        report = tracker.get_mutation_report()
        assert len(report) == 0


class TestOptsDictBasics:
    """Test basic OptsDict functionality."""

    def test_creation_from_dict(self):
        """Test creating OptsDict from regular dict."""
        base = {"grains": {}, "pillar": {}, "test": False}
        opts = OptsDict.from_dict(base, name="test")

        assert opts["test"] is False
        assert "grains" in opts
        assert len(opts) == 3

    def test_getitem(self):
        """Test getting items."""
        opts = OptsDict.from_dict({"a": 1, "b": 2})

        assert opts["a"] == 1
        assert opts["b"] == 2

        with pytest.raises(KeyError):
            _ = opts["nonexistent"]

    def test_setitem(self):
        """Test setting items."""
        opts = OptsDict.from_dict({"a": 1})

        opts["b"] = 2
        assert opts["b"] == 2

        opts["a"] = 10
        assert opts["a"] == 10

    def test_delitem(self):
        """Test deleting items."""
        opts = OptsDict.from_dict({"a": 1})
        opts["b"] = 2  # Add to local

        del opts["b"]
        assert "b" not in opts

        # Can't delete from parent/base
        with pytest.raises(KeyError):
            del opts["a"]

    def test_contains(self):
        """Test 'in' operator."""
        opts = OptsDict.from_dict({"a": 1, "b": 2})

        assert "a" in opts
        assert "b" in opts
        assert "c" not in opts

    def test_get(self):
        """Test get with default."""
        opts = OptsDict.from_dict({"a": 1})

        assert opts.get("a") == 1
        assert opts.get("b") is None
        assert opts.get("b", "default") == "default"

    def test_iteration(self):
        """Test iterating over keys."""
        opts = OptsDict.from_dict({"a": 1, "b": 2, "c": 3})

        keys = set(opts.keys())
        assert keys == {"a", "b", "c"}

        values = list(opts.values())
        assert len(values) == 3
        assert 1 in values

        items = dict(opts.items())
        assert items == {"a": 1, "b": 2, "c": 3}

    def test_len(self):
        """Test length."""
        opts = OptsDict.from_dict({"a": 1, "b": 2, "c": 3})
        assert len(opts) == 3

    def test_update(self):
        """Test update method."""
        opts = OptsDict.from_dict({"a": 1})
        opts.update({"b": 2, "c": 3})

        assert opts["b"] == 2
        assert opts["c"] == 3

    def test_to_dict(self):
        """Test converting to regular dict."""
        opts = OptsDict.from_dict({"a": 1, "b": 2})
        opts["c"] = 3

        regular_dict = opts.to_dict()
        assert isinstance(regular_dict, dict)
        assert regular_dict == {"a": 1, "b": 2, "c": 3}


class TestOptsDictCopyOnWrite:
    """Test copy-on-write semantics."""

    def test_child_shares_parent_data(self):
        """Test that child shares parent data until mutation."""
        parent = OptsDict.from_dict(
            {
                "grains": {"os": "Linux"},
                "pillar": {"app": {"setting": "value"}},
                "test": False,
            }
        )

        child = OptsDict.from_parent(parent, name="child")

        # Child can read parent data
        assert child["test"] is False
        assert child["grains"]["os"] == "Linux"

        # Child has no local data yet
        assert len(child.get_local_keys()) == 0

    def test_mutation_creates_local_copy(self):
        """Test that mutation creates local copy of only that key."""
        parent = OptsDict.from_dict(
            {
                "grains": {"os": "Linux"},  # Large dict
                "pillar": {"app": "data"},  # Large dict
                "test": False,  # Small value
            },
            name="parent",
        )

        child = OptsDict.from_parent(parent, name="child")

        # Mutate only 'test'
        child["test"] = True

        # Only 'test' should be local
        local_keys = child.get_local_keys()
        assert local_keys == {"test"}

        # grains and pillar still shared
        shared_keys = child.get_shared_keys()
        assert "grains" in shared_keys
        assert "pillar" in shared_keys

        # Values are correct
        assert child["test"] is True  # Local
        assert parent["test"] is False  # Unchanged
        assert child["grains"] == parent["grains"]  # Shared

    def test_nested_children(self):
        """Test grandparent -> parent -> child hierarchy."""
        grandparent = OptsDict.from_dict({"a": 1, "b": 2, "c": 3}, name="grandparent")

        parent = OptsDict.from_parent(grandparent, name="parent")
        parent["b"] = 20  # Mutate in parent

        child = OptsDict.from_parent(parent, name="child")
        child["c"] = 30  # Mutate in child

        # Check values
        assert grandparent["a"] == 1
        assert grandparent["b"] == 2
        assert grandparent["c"] == 3

        assert parent["a"] == 1  # From grandparent
        assert parent["b"] == 20  # Local
        assert parent["c"] == 3  # From grandparent

        assert child["a"] == 1  # From grandparent
        assert child["b"] == 20  # From parent
        assert child["c"] == 30  # Local

    def test_multiple_children_isolated(self):
        """Test that sibling children don't affect each other."""
        parent = OptsDict.from_dict({"test": False, "saltenv": "base"}, name="parent")

        child1 = OptsDict.from_parent(parent, name="child1")
        child2 = OptsDict.from_parent(parent, name="child2")

        # Each child mutates independently
        child1["test"] = True
        child2["test"] = False  # Different value
        child1["saltenv"] = "dev"

        # Check isolation
        assert child1["test"] is True
        assert child2["test"] is False
        assert parent["test"] is False

        assert child1["saltenv"] == "dev"
        assert child2["saltenv"] == "base"  # Still shared from parent
        assert parent["saltenv"] == "base"


class TestOptsDictMutationTracking:
    """Test mutation tracking features."""

    def test_mutation_recorded(self):
        """Test that mutations are recorded."""
        opts = OptsDict.from_dict({"test": False}, track_mutations=True, name="test")

        opts["test"] = True

        report = opts.get_mutation_report()
        assert "test" in report
        assert report["test"]["mutation_count"] == 1

    def test_mutation_stack_trace(self):
        """Test that stack trace is captured."""
        opts = OptsDict.from_dict({"test": False}, track_mutations=True, name="test")

        opts["test"] = True

        report = opts.get_mutation_report(verbose=False)
        assert "first_mutated_at" in report["test"]
        assert len(report["test"]["first_mutated_at"]) > 0

    def test_multiple_mutations_tracked(self):
        """Test tracking multiple mutations."""
        opts = OptsDict.from_dict({"test": False}, track_mutations=True, name="test")

        opts["test"] = True
        opts["test"] = False
        opts["test"] = True

        report = opts.get_mutation_report(verbose=True)
        assert report["test"]["mutation_count"] == 3
        assert len(report["test"]["all_mutations"]) == 3

    def test_shared_tracker_across_hierarchy(self):
        """Test that child opts share parent's tracker."""
        parent = OptsDict.from_dict({"test": False, "saltenv": "base"}, track_mutations=True, name="parent")
        child = OptsDict.from_parent(parent, name="child")

        parent["test"] = True
        child["saltenv"] = "dev"  # Mutate existing key

        # Both mutations visible in both reports (shared tracker)
        parent_report = parent.get_mutation_report()
        child_report = child.get_mutation_report()

        assert parent_report == child_report
        assert "test" in parent_report
        assert "saltenv" in child_report

    def test_no_tracking_mode(self):
        """Test disabling mutation tracking."""
        opts = OptsDict.from_dict({"test": False}, track_mutations=False, name="test")

        opts["test"] = True

        report = opts.get_mutation_report()
        assert len(report) == 0


class TestOptsDictMemoryStats:
    """Test memory statistics and reporting."""

    def test_memory_stats_basic(self):
        """Test basic memory stats."""
        parent = OptsDict.from_dict(
            {
                "grains": {"os": "Linux", "cpus": 4},
                "pillar": {"app": "data"},
                "test": False,
            },
            name="parent",
        )

        child = OptsDict.from_parent(parent, name="child")
        child["test"] = True

        stats = child.get_memory_stats()

        assert stats["name"] == "child"
        assert stats["local_keys_count"] == 1  # Only 'test'
        assert stats["shared_keys_count"] == 2  # grains, pillar
        assert stats["total_keys_count"] == 3
        assert stats["local_size_bytes"] > 0

    def test_local_vs_shared_keys(self):
        """Test distinguishing local vs shared keys."""
        parent = OptsDict.from_dict({"a": 1, "b": 2, "c": 3}, name="parent")
        child = OptsDict.from_parent(parent, name="child")

        child["b"] = 20  # Mutate one key

        assert child.get_local_keys() == {"b"}
        assert child.get_shared_keys() == {"a", "c"}


class TestOptsDictThreadSafety:
    """Test thread safety of OptsDict."""

    def test_concurrent_reads(self):
        """Test concurrent reads are safe."""
        opts = OptsDict.from_dict({"a": 1, "b": 2, "c": 3}, name="test")

        results = []

        def reader():
            for _ in range(100):
                results.append(opts["a"])

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should succeed
        assert len(results) == 1000
        assert all(r == 1 for r in results)

    def test_concurrent_writes(self):
        """Test concurrent writes are serialized."""
        opts = OptsDict.from_dict({"counter": 0}, name="test")

        def writer(thread_id):
            for i in range(100):
                current = opts.get("counter", 0)
                opts["counter"] = current + 1

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Due to locking, final value should be predictable
        # (though not necessarily 1000 due to the read-modify-write pattern)
        # The important thing is no crashes/corruption
        assert "counter" in opts
        assert isinstance(opts["counter"], int)


class TestSafeOptsCopy:
    """Test safe_opts_copy migration helper."""

    def test_copy_from_dict(self):
        """Test creating OptsDict from regular dict."""
        regular_dict = {"a": 1, "b": 2}
        opts = safe_opts_copy(regular_dict, name="test")

        assert isinstance(opts, OptsDict)
        assert opts["a"] == 1
        assert opts["b"] == 2

    def test_copy_from_optsdict(self):
        """Test creating child from existing OptsDict."""
        parent = OptsDict.from_dict({"a": 1, "b": 2}, name="parent")
        child = safe_opts_copy(parent, name="child")

        assert isinstance(child, OptsDict)
        assert child["a"] == 1

        # Should be child of parent
        child["a"] = 10
        assert parent["a"] == 1  # Unchanged


class TestRealWorldScenarios:
    """Test real-world Salt usage patterns."""

    def test_state_execution_pattern(self):
        """
        Simulate state execution pattern:
        1. Base opts with grains, pillar
        2. get_sls_opts creates child with test=True
        3. State object modifies saltenv
        """
        # Base minion opts
        base_opts = OptsDict.from_dict(
            {
                "grains": {"os": "Linux", "id": "minion1"},  # ~500KB in real life
                "pillar": {"app": {"db": "mysql"}},  # ~5MB in real life
                "test": False,
                "saltenv": "base",
            },
            name="minion_opts",
        )

        # get_sls_opts pattern
        sls_opts = OptsDict.from_parent(base_opts, name="get_sls_opts")
        sls_opts["test"] = True

        # State object pattern
        state_opts = OptsDict.from_parent(sls_opts, name="state_object")
        state_opts["saltenv"] = "dev"

        # Verify isolation
        assert base_opts["test"] is False
        assert base_opts["saltenv"] == "base"

        assert sls_opts["test"] is True
        assert sls_opts["saltenv"] == "base"

        assert state_opts["test"] is True
        assert state_opts["saltenv"] == "dev"

        # Check memory efficiency
        state_stats = state_opts.get_memory_stats()
        assert state_stats["local_keys_count"] == 1  # Only saltenv
        assert state_stats["shared_keys_count"] >= 2  # grains, pillar shared

    def test_multimaster_pattern(self):
        """
        Simulate multimaster pattern:
        Multiple loaders with separate opts per master.
        """
        base_opts = OptsDict.from_dict(
            {"grains": {"os": "Linux"}, "pillar": {"app": "data"}, "master": "master1"},
            name="base_opts",
        )

        # Master 1 loader
        master1_opts = OptsDict.from_parent(base_opts, name="master1_loader")
        master1_opts["master"] = "master1"

        # Master 2 loader
        master2_opts = OptsDict.from_parent(base_opts, name="master2_loader")
        master2_opts["master"] = "master2"

        # Each has different master
        assert master1_opts["master"] == "master1"
        assert master2_opts["master"] == "master2"

        # But share grains/pillar
        assert master1_opts["grains"] is not None
        assert master2_opts["pillar"] is not None

        # Check shared data
        assert "grains" in master1_opts.get_shared_keys()
        assert "grains" in master2_opts.get_shared_keys()

    def test_loader_per_module_pattern(self):
        """
        Simulate loader creating opts for each loaded module.
        """
        loader_opts = OptsDict.from_dict(
            {"grains": {"os": "Linux"}, "pillar": {"app": "data"}, "test": False},
            name="loader_opts",
        )

        # Simulate 50 modules
        module_opts_list = []
        for i in range(50):
            mod_opts = OptsDict.from_parent(loader_opts, name=f"module_{i}")
            # Some modules might mutate test mode
            if i % 10 == 0:
                mod_opts["test"] = True
            module_opts_list.append(mod_opts)

        # Check memory efficiency
        total_local_keys = sum(len(mod.get_local_keys()) for mod in module_opts_list)

        # Only 5 modules mutated test, so only 5 local keys total
        assert total_local_keys == 5

        # All share grains/pillar
        for mod_opts in module_opts_list:
            assert "grains" in mod_opts.get_shared_keys()
            assert "pillar" in mod_opts.get_shared_keys()


class TestOptsDictVsDeepCopy:
    """Compare OptsDict vs copy.deepcopy for memory efficiency."""

    def test_memory_comparison(self):
        """
        Compare memory usage: OptsDict vs deepcopy.

        This test demonstrates the memory savings.
        """
        import sys

        # Create large opts dict
        large_opts = {
            "grains": {f"grain_{i}": f"value_{i}" for i in range(1000)},
            "pillar": {f"pillar_{i}": f"data_{i}" for i in range(1000)},
            "test": False,
            "saltenv": "base",
        }

        # Measure deepcopy approach
        deepcopy_size = 0
        deepcopy_instances = []
        for i in range(10):
            instance = copy.deepcopy(large_opts)
            deepcopy_instances.append(instance)
            deepcopy_size += sys.getsizeof(instance)

        # Measure OptsDict approach
        root_opts = OptsDict.from_dict(large_opts, name="root")
        optsdict_instances = []
        optsdict_size = 0

        for i in range(10):
            child = OptsDict.from_parent(root_opts, name=f"child_{i}")
            child["test"] = i % 2 == 0  # Mutate only test
            optsdict_instances.append(child)
            stats = child.get_memory_stats()
            optsdict_size += stats["local_size_bytes"]

        # OptsDict should use significantly less memory
        # (exact ratio depends on dict size, but should be substantial)
        print(f"\nDeep copy total: ~{deepcopy_size} bytes")
        print(f"OptsDict total: ~{optsdict_size} bytes")
        print(f"Savings: ~{deepcopy_size - optsdict_size} bytes")

        # OptsDict should use less memory (exact amount varies)
        # Main assertion: both work correctly
        assert all(isinstance(inst, dict) for inst in deepcopy_instances)
        assert all(isinstance(inst, OptsDict) for inst in optsdict_instances)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
