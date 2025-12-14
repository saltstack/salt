"""
OptsDict: Copy-on-write dictionary optimized for Salt's opts pattern.

This module provides a memory-efficient alternative to copy.deepcopy(opts)
by implementing true copy-on-write semantics at the key level, with full
mutation tracking for future unwinding.

Key Features:
- Only duplicates data for keys that are actually mutated
- Tracks all mutations with stack traces for auditing
- Provides reports to identify unwinding opportunities
- Maintains dict interface for backward compatibility
- Thread-safe for concurrent access

Example:
    >>> base_opts = {'grains': {...}, 'pillar': {...}, 'test': False}
    >>> child = OptsDict(base_opts)
    >>> child['test'] = True  # Only 'test' is copied, grains/pillar shared
    >>> child.get_mutation_report()
    {
        'test': {
            'mutated_by': ['salt.utils.state.get_sls_opts:211'],
            'mutation_count': 1,
            'original_value': False,
            'current_value': True
        }
    }
"""

import copy
import logging
import sys
import threading
import traceback
from collections.abc import MutableMapping
from typing import Any, Optional

log = logging.getLogger(__name__)


class DictProxy(dict):
    """
    Proxy for dict that triggers copy-on-write in parent OptsDict on mutation.

    Subclasses dict to pass isinstance checks while providing copy-on-write semantics.
    """

    def __init__(self, target: dict, parent_optsdict: "OptsDict", key: str):
        # Initialize underlying dict with target data AND keep _target
        # We need both: underlying dict for C code, _target for our logic
        super().__init__(target)
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_parent", parent_optsdict)
        object.__setattr__(self, "_key", key)
        object.__setattr__(self, "_copied", False)

    def _ensure_copied(self):
        """Copy target to parent's _local on first mutation."""
        if not object.__getattribute__(self, "_copied"):
            parent = object.__getattribute__(self, "_parent")
            key = object.__getattribute__(self, "_key")
            target = object.__getattribute__(self, "_target")

            with parent._lock:
                # Deep copy the entire dict to parent's _local
                copied = copy.deepcopy(target)
                parent._local[key] = copied
                object.__setattr__(self, "_target", copied)
                # Also update the underlying dict storage
                dict.clear(self)
                dict.update(self, copied)
                object.__setattr__(self, "_copied", True)

    def __getitem__(self, key):
        target = object.__getattribute__(self, "_target")
        value = target[key]
        # For nested mutable values, copy THIS dict first,
        # then return the value from the copied dict without further wrapping
        if isinstance(value, (dict, list)) and not object.__getattribute__(
            self, "_copied"
        ):
            # Trigger copy-on-access for nested mutables to prevent unwrapped references
            self._ensure_copied()
            # Return value from the now-copied target
            target = object.__getattribute__(self, "_target")
            return target[key]
        return value

    def __setitem__(self, key, value):
        self._ensure_copied()
        object.__getattribute__(self, "_target")[key] = value
        # Also update underlying dict
        dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        self._ensure_copied()
        del object.__getattribute__(self, "_target")[key]
        # Also update underlying dict
        dict.__delitem__(self, key)

    def __iter__(self):
        return iter(object.__getattribute__(self, "_target"))

    def __len__(self):
        return len(object.__getattribute__(self, "_target"))

    def __repr__(self):
        return repr(object.__getattribute__(self, "_target"))

    def __str__(self):
        return str(object.__getattribute__(self, "_target"))

    def __contains__(self, key):
        return key in object.__getattribute__(self, "_target")

    def keys(self):
        return object.__getattribute__(self, "_target").keys()

    def values(self):
        return object.__getattribute__(self, "_target").values()

    def items(self):
        return object.__getattribute__(self, "_target").items()

    def get(self, key, default=None):
        return object.__getattribute__(self, "_target").get(key, default)

    def pop(self, key, *args):
        self._ensure_copied()
        result = object.__getattribute__(self, "_target").pop(key, *args)
        # Also update underlying dict
        dict.pop(self, key, *args)
        return result

    def update(self, *args, **kwargs):
        self._ensure_copied()
        object.__getattribute__(self, "_target").update(*args, **kwargs)
        # Also update underlying dict
        dict.update(self, *args, **kwargs)

    def setdefault(self, key, default=None):
        self._ensure_copied()
        result = object.__getattribute__(self, "_target").setdefault(key, default)
        # Also update underlying dict
        dict.setdefault(self, key, default)
        return result

    def __deepcopy__(self, memo):
        """Return a deep copy of the underlying dict, not the proxy."""
        target = object.__getattribute__(self, "_target")
        return copy.deepcopy(target, memo)

    def __reduce_ex__(self, protocol):
        """For pickling, return the underlying dict, not the proxy."""
        target = object.__getattribute__(self, "_target")
        return (dict, (target,))


class ListProxy(list):
    """
    Proxy for list that triggers copy-on-write in parent OptsDict on mutation.

    Subclasses list to pass isinstance checks while providing copy-on-write semantics.
    """

    def __init__(self, target: list, parent_optsdict: "OptsDict", key: str):
        # Initialize underlying list with target data AND keep _target
        # We need both: underlying list for C code, _target for our logic
        super().__init__(target)
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_parent", parent_optsdict)
        object.__setattr__(self, "_key", key)
        object.__setattr__(self, "_copied", False)

    def _ensure_copied(self):
        """Copy target to parent's _local on first mutation."""
        if not object.__getattribute__(self, "_copied"):
            parent = object.__getattribute__(self, "_parent")
            key = object.__getattribute__(self, "_key")
            target = object.__getattribute__(self, "_target")

            with parent._lock:
                # Deep copy the entire list to parent's _local
                copied = copy.deepcopy(target)
                parent._local[key] = copied
                object.__setattr__(self, "_target", copied)
                object.__setattr__(self, "_copied", True)

    def __getitem__(self, index):
        return object.__getattribute__(self, "_target")[index]

    def __setitem__(self, index, value):
        self._ensure_copied()
        object.__getattribute__(self, "_target")[index] = value

    def __delitem__(self, index):
        self._ensure_copied()
        del object.__getattribute__(self, "_target")[index]

    def __len__(self):
        return len(object.__getattribute__(self, "_target"))

    def __iter__(self):
        return iter(object.__getattribute__(self, "_target"))

    def __contains__(self, item):
        return item in object.__getattribute__(self, "_target")

    def insert(self, index, value):
        self._ensure_copied()
        object.__getattribute__(self, "_target").insert(index, value)

    def append(self, value):
        self._ensure_copied()
        object.__getattribute__(self, "_target").append(value)

    def extend(self, values):
        self._ensure_copied()
        object.__getattribute__(self, "_target").extend(values)

    def remove(self, value):
        self._ensure_copied()
        object.__getattribute__(self, "_target").remove(value)

    def pop(self, index=-1):
        self._ensure_copied()
        return object.__getattribute__(self, "_target").pop(index)

    def __deepcopy__(self, memo):
        """Return a deep copy of the underlying list, not the proxy."""
        return copy.deepcopy(object.__getattribute__(self, "_target"), memo)

    def __reduce_ex__(self, protocol):
        """For pickling, return the underlying list, not the proxy."""
        return (list, (object.__getattribute__(self, "_target"),))

    def clear(self):
        self._ensure_copied()
        object.__getattribute__(self, "_target").clear()

    def __repr__(self):
        return repr(object.__getattribute__(self, "_target"))

    def __str__(self):
        return str(object.__getattribute__(self, "_target"))

    def __eq__(self, other):
        target = object.__getattribute__(self, "_target")
        if isinstance(other, ListProxy):
            return target == object.__getattribute__(other, "_target")
        return target == other

    def index(self, value, *args):
        """Return first index of value."""
        return object.__getattribute__(self, "_target").index(value, *args)

    def count(self, value):
        """Return number of occurrences of value."""
        return object.__getattribute__(self, "_target").count(value)


# DictProxy and ListProxy now subclass dict and list respectively, so they pass
# isinstance checks. This ensures compatibility with Salt code that uses isinstance(x, dict).


class MutationTracker:
    """
    Tracks mutations to OptsDict keys for auditing and future unwinding.

    For each mutated key, we track:
    - Where the mutation happened (file, line, function)
    - When it happened (order of mutations)
    - What the original value was
    - How many times it's been mutated
    """

    def __init__(self, track_mutations: bool = True, max_stack_depth: int = 10):
        self.track_mutations = track_mutations
        self.max_stack_depth = max_stack_depth
        self._mutations: dict[str, dict[str, Any]] = {}
        self._mutation_order: list[str] = []
        self._lock = threading.RLock()

    def record_mutation(self, key: str, original_value: Any, new_value: Any):
        """
        Record a mutation of a key with stack trace.

        Args:
            key: The opts key being mutated
            original_value: The original value before mutation
            new_value: The new value being set
        """
        if not self.track_mutations:
            return

        with self._lock:
            # Capture stack trace
            stack = traceback.extract_stack(limit=self.max_stack_depth)
            # Filter out frames from this file
            stack = [frame for frame in stack if "optsdict.py" not in frame.filename]

            # Format stack trace for readability
            caller_info = []
            for frame in stack[-3:]:  # Last 3 frames (most relevant)
                caller_info.append(f"{frame.filename}:{frame.lineno} in {frame.name}")

            if key not in self._mutations:
                # First mutation of this key
                self._mutations[key] = {
                    "original_value": original_value,
                    "current_value": new_value,
                    "mutation_count": 1,
                    "first_mutation_stack": caller_info,
                    "all_mutations": [caller_info],
                    "mutation_sequence": [new_value],
                }
                self._mutation_order.append(key)
            else:
                # Subsequent mutation
                self._mutations[key]["mutation_count"] += 1
                self._mutations[key]["current_value"] = new_value
                self._mutations[key]["all_mutations"].append(caller_info)
                self._mutations[key]["mutation_sequence"].append(new_value)

    def get_mutation_report(self, verbose: bool = False) -> dict[str, Any]:
        """
        Generate a report of all mutations.

        Args:
            verbose: If True, include full mutation history

        Returns:
            Dictionary containing mutation statistics and details
        """
        with self._lock:
            if not verbose:
                # Concise report
                return {
                    key: {
                        "mutation_count": info["mutation_count"],
                        "first_mutated_at": info["first_mutation_stack"],
                        "original_value_type": type(info["original_value"]).__name__,
                        "current_value_type": type(info["current_value"]).__name__,
                    }
                    for key, info in self._mutations.items()
                }
            else:
                # Full report with history
                return copy.deepcopy(self._mutations)

    def get_hotspot_keys(self, min_mutations: int = 2) -> list[str]:
        """
        Identify keys that are frequently mutated (hotspots).

        These are candidates for being designed as mutable from the start.

        Args:
            min_mutations: Minimum mutation count to be considered a hotspot

        Returns:
            List of keys sorted by mutation count (descending)
        """
        with self._lock:
            hotspots = [
                (key, info["mutation_count"])
                for key, info in self._mutations.items()
                if info["mutation_count"] >= min_mutations
            ]
            return [
                key for key, _ in sorted(hotspots, key=lambda x: x[1], reverse=True)
            ]

    def get_mutation_locations(self) -> dict[str, set[str]]:
        """
        Get all unique locations where mutations happen.

        Returns:
            Dict mapping location strings to set of keys mutated there
        """
        with self._lock:
            locations = {}
            for key, info in self._mutations.items():
                for stack in info["all_mutations"]:
                    # Use the most recent frame (actual mutation site)
                    location = stack[-1] if stack else "unknown"
                    if location not in locations:
                        locations[location] = set()
                    locations[location].add(key)
            return locations


class OptsDict(MutableMapping):
    """
    Copy-on-write dictionary for Salt opts.

    This class implements true copy-on-write semantics at the key level:
    - Keys are only copied when first mutated
    - Nested structures are handled properly (deep COW)
    - Parent data is shared until modification
    - Full mutation tracking for auditing

    Thread-safe for concurrent reads; writes are serialized per instance.

    Example:
        >>> parent_opts = {'grains': {...}, 'pillar': {...}, 'test': False}
        >>> child = OptsDict.from_parent(parent_opts)
        >>> child['test'] = True  # Only copies 'test', not grains/pillar
        >>> 'grains' in child  # True (shared from parent)
        >>> child['test']  # True (local mutation)
    """

    def __init__(
        self,
        base_dict: dict[str, Any] | None = None,
        parent: Optional["OptsDict"] = None,
        track_mutations: bool = True,
        name: str | None = None,
    ):
        """
        Initialize OptsDict.

        Args:
            base_dict: Initial dictionary (for root instance)
            parent: Parent OptsDict to inherit from (for child instances)
            track_mutations: Enable mutation tracking
            name: Optional name for debugging (e.g., "loader:states", "state:highstate")
        """
        self._parent = parent
        self._local = {}  # Keys that have been copied/mutated locally
        self._base = base_dict if base_dict is not None else {}
        self._name = name or f"OptsDict@{id(self)}"
        self._lock = threading.RLock()

        # Mutation tracking
        if parent and parent._tracker:
            # Inherit parent's tracker
            self._tracker = parent._tracker
        else:
            # Root instance - create new tracker
            self._tracker = MutationTracker(track_mutations=track_mutations)

    @classmethod
    def from_parent(cls, parent: "OptsDict", name: str | None = None) -> "OptsDict":
        """
        Create a child OptsDict that shares parent's data.

        Args:
            parent: Parent OptsDict to inherit from
            name: Optional name for debugging

        Returns:
            New OptsDict instance sharing parent's data
        """
        return cls(parent=parent, name=name)

    @classmethod
    def from_dict(
        cls,
        base_dict: dict[str, Any],
        track_mutations: bool = True,
        name: str | None = None,
    ) -> "OptsDict":
        """
        Create a root OptsDict from a regular dictionary.

        Args:
            base_dict: Dictionary to wrap
            track_mutations: Enable mutation tracking
            name: Optional name for debugging

        Returns:
            New root OptsDict instance
        """
        return cls(base_dict=base_dict, track_mutations=track_mutations, name=name)

    def _get_from_parent_chain(self, key: str) -> tuple[bool, Any]:
        """
        Walk up the parent chain to find a key.

        Returns:
            (found, value) tuple
        """
        current = self._parent
        while current is not None:
            # Check local dict first
            if key in current._local:
                return True, current._local[key]
            # Check base dict if this is a root node
            if current._parent is None and key in current._base:
                return True, current._base[key]
            current = current._parent

        return False, None

    def __getitem__(self, key: str) -> Any:
        """
        Get item with proxy-based copy-on-write for mutable values.

        When accessing mutable values from parent/base, we return a proxy object
        that triggers copy-on-write on first mutation. This provides isolation
        without copying until actually needed.
        """
        with self._lock:
            # Check local first - if already copied, return direct reference
            if key in self._local:
                return self._local[key]

            # Check parent chain
            if self._parent is not None:
                found, value = self._get_from_parent_chain(key)
                if found:
                    # Wrap mutable values in proxies to catch mutations
                    if isinstance(value, dict) and not isinstance(value, OptsDict):
                        return DictProxy(value, self, key)
                    elif isinstance(value, list):
                        return ListProxy(value, self, key)
                    # Immutable values can be returned directly
                    return value

            # Check base (root level only)
            if self._parent is None and key in self._base:
                value = self._base[key]
                # Even root instances need proxies to track when values are mutated
                # This allows us to know when a key has been accessed/modified
                if isinstance(value, dict) and not isinstance(value, OptsDict):
                    return DictProxy(value, self, key)
                elif isinstance(value, list):
                    return ListProxy(value, self, key)
                return value

            raise KeyError(key)

    def __setitem__(self, key: str, value: Any):
        """
        Set item with copy-on-write semantics.

        On first write to a key:
        1. Record the mutation
        2. Copy only that key's value to local dict
        3. Store new value
        """
        with self._lock:
            # Get original value for tracking
            try:
                original_value = self[key]
                is_mutation = True
            except KeyError:
                original_value = None
                is_mutation = False

            # Check if this is the first mutation of this key
            if is_mutation and key not in self._local:
                # First mutation - record it
                self._tracker.record_mutation(key, original_value, value)
                log.debug(
                    "OptsDict[%s]: First mutation of key '%s' (original type: %s, new type: %s)",
                    self._name,
                    key,
                    type(original_value).__name__,
                    type(value).__name__,
                )
            elif key in self._local:
                # Subsequent mutation of already-local key
                self._tracker.record_mutation(key, original_value, value)

            # Store the value locally
            self._local[key] = value

    def __delitem__(self, key: str):
        """Delete item (only from local dict)."""
        with self._lock:
            if key in self._local:
                del self._local[key]
            else:
                # Can't delete from parent - record as mutation to None?
                # For now, raise error
                raise KeyError(f"Cannot delete key '{key}' (not in local dict)")

    def __iter__(self):
        """Iterate over all keys (local + parent chain + base)."""
        with self._lock:
            # Collect all keys from the chain
            keys = set(self._local.keys())

            # Add parent chain keys
            if self._parent is not None:
                current = self._parent
                while current is not None:
                    keys.update(current._local.keys())
                    # Add base keys if this is a root node
                    if current._parent is None:
                        keys.update(current._base.keys())
                    current = current._parent
            else:
                # This is a root node, add base keys
                keys.update(self._base.keys())

            return iter(keys)

    def __len__(self) -> int:
        """Return total number of keys."""
        with self._lock:
            return len(set(self))

    def __contains__(self, key: str) -> bool:
        """Check if key exists in local, parent chain, or base."""
        with self._lock:
            if key in self._local:
                return True

            if self._parent is not None:
                found, _ = self._get_from_parent_chain(key)
                if found:
                    return True

            if self._parent is None and key in self._base:
                return True

            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get with default value."""
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        """Return all keys."""
        return iter(self)

    def values(self):
        """Return all values."""
        with self._lock:
            return [self[k] for k in self]

    def items(self):
        """Return all items."""
        with self._lock:
            return [(k, self[k]) for k in self]

    def copy(self) -> dict[str, Any]:
        """Return a regular dict copy of all data."""
        with self._lock:
            return {k: v for k, v in self.items()}

    def to_dict(self) -> dict[str, Any]:
        """Alias for copy() - return regular dict."""
        return self.copy()

    def update(self, other=None, /, **kwargs: Any):  # pylint: disable=arguments-differ
        """Update with another dict.

        Compatible with MutableMapping.update() signature.
        """
        with self._lock:
            if other:
                for key, value in other.items():
                    self[key] = value
            for key, value in kwargs.items():
                self[key] = value

    # OptsDict-specific methods

    def get_mutation_report(self, verbose: bool = False) -> dict[str, Any]:
        """
        Get report of all mutations across this OptsDict hierarchy.

        Args:
            verbose: Include full mutation history

        Returns:
            Dictionary with mutation statistics
        """
        return self._tracker.get_mutation_report(verbose=verbose)

    def get_local_keys(self) -> set[str]:
        """Return set of keys that have been mutated locally."""
        with self._lock:
            return set(self._local.keys())

    def get_shared_keys(self) -> set[str]:
        """Return set of keys that are shared from parent/base."""
        with self._lock:
            all_keys = set(self)
            local_keys = self.get_local_keys()
            return all_keys - local_keys

    def get_memory_stats(self) -> dict[str, Any]:
        """
        Estimate memory usage statistics.

        Returns:
            Dict with local size, shared size, etc.
        """
        with self._lock:
            import sys

            local_size = sum(
                sys.getsizeof(k) + sys.getsizeof(v) for k, v in self._local.items()
            )

            return {
                "name": self._name,
                "local_keys_count": len(self._local),
                "shared_keys_count": len(self.get_shared_keys()),
                "total_keys_count": len(self),
                "local_size_bytes": local_size,
                "local_size_mb": local_size / (1024 * 1024),
            }

    def log_mutation_summary(self, logger: logging.Logger | None = None):
        """
        Log a summary of mutations for debugging.

        Args:
            logger: Logger to use (defaults to module logger)
        """
        logger = logger or log
        stats = self.get_memory_stats()

        logger.info(
            "OptsDict[%s] memory stats: %d local keys (%.2f MB), %d shared keys",
            self._name,
            stats["local_keys_count"],
            stats["local_size_mb"],
            stats["shared_keys_count"],
        )

        if self._tracker.track_mutations:
            report = self.get_mutation_report(verbose=False)
            if report:
                logger.info("OptsDict[%s] mutations:", self._name)
                for key, info in report.items():
                    logger.info(
                        "  - %s: %d mutations, first at %s",
                        key,
                        info["mutation_count"],
                        (
                            info["first_mutated_at"][-1]
                            if info["first_mutated_at"]
                            else "unknown"
                        ),
                    )

    def __deepcopy__(self, memo):
        """
        Support for copy.deepcopy().

        When deepcopied, we return a regular dict to avoid issues with
        unpicklable locks. This matches the behavior expected by code
        that does copy.deepcopy(opts).
        """
        with self._lock:
            # Return a deep copy as a regular dict
            return copy.deepcopy(dict(self), memo)

    def __getstate__(self):
        """
        Support for pickling.

        Excludes the lock since it can't be pickled.
        """
        state = self.__dict__.copy()
        # Remove the unpicklable lock
        state.pop("_lock", None)
        # Also remove the tracker's lock
        if "_tracker" in state and hasattr(state["_tracker"], "_lock"):
            tracker_state = state["_tracker"].__dict__.copy()
            tracker_state.pop("_lock", None)
            state["_tracker"] = tracker_state
        return state

    def __setstate__(self, state):
        """
        Support for unpickling.

        Recreates the lock after unpickling.
        """
        self.__dict__.update(state)
        # Recreate the lock
        self._lock = threading.RLock()
        # Recreate the tracker's lock if it has one
        if hasattr(self, "_tracker") and not hasattr(self._tracker, "_lock"):
            self._tracker._lock = threading.RLock()

    def __repr__(self) -> str:
        """String representation."""
        with self._lock:
            return (
                f"OptsDict(name={self._name!r}, "
                f"local_keys={len(self._local)}, "
                f"total_keys={len(self)})"
            )


def generate_global_mutation_report(include_locations: bool = True) -> str:
    """
    Generate a global report of all mutations across all OptsDict instances.

    This is useful for identifying patterns and unwinding opportunities.

    Args:
        include_locations: Include mutation location analysis

    Returns:
        Formatted report string
    """
    # Note: This would require tracking all OptsDict instances globally
    # For now, this is a placeholder for the concept
    # Could be implemented with a global registry

    report_lines = [
        "=" * 80,
        "OptsDict Global Mutation Report",
        "=" * 80,
        "",
        "This report shows all opts mutations across the Salt minion instance.",
        "Use this to identify unwinding opportunities and refactoring targets.",
        "",
    ]

    # TODO: Implement global tracking
    report_lines.append(
        "(Not implemented yet - call get_mutation_report() on individual instances)"
    )

    return "\n".join(report_lines)


# Global mapping from source dict id() to its OptsDict root
# Keyed by id(source_dict), value is the root OptsDict that wraps it
_dict_to_root = {}


# Convenience function for backward compatibility
def safe_opts_copy(opts: Any, name: str | None = None) -> OptsDict:
    """
    Create an OptsDict from opts (dict or existing OptsDict).

    This function provides a migration path from copy.deepcopy(opts).

    Args:
        opts: Existing opts (dict or OptsDict)
        name: Optional name for debugging

    Returns:
        OptsDict instance

    Example:
        # OLD:
        opts = copy.deepcopy(opts)

        # NEW:
        from salt.utils.optsdict import safe_opts_copy
        opts = safe_opts_copy(opts, name="loader:states")
    """
    if isinstance(opts, OptsDict):
        # Find the root of this OptsDict tree
        root = opts
        while root._parent is not None:
            root = root._parent

        # Always create children from the root to ensure all children are siblings
        # This allows them to see each other's mutations through the root's _local
        return OptsDict.from_parent(root, name=name)

    # Converting from regular dict
    # Check if we've already created a root for this specific dict object
    global _dict_to_root  # pylint: disable=global-variable-not-assigned
    opts_id = id(opts)
    if opts_id in _dict_to_root:
        # Reuse existing root - this ensures all OptsDict instances
        # from the same source dict share the same base and see mutations
        root = _dict_to_root[opts_id]
        return OptsDict.from_parent(root, name=name)

    # First time seeing this dict - create a new root that wraps it
    root = OptsDict.from_dict(opts, name=name or f"root@{opts_id}")
    _dict_to_root[opts_id] = root
    return root
