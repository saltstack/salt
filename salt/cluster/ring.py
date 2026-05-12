"""
Consistent hash ring with virtual nodes (VNodes).

The ring maps arbitrary keys (JIDs, minion IDs, cache bank names) to the
physical node that owns them.  Virtual nodes prevent hotspots by distributing
each physical node to ``vnodes`` evenly-spaced points around the ring before
any real nodes are added, and then placing each physical node's actual token
set through xxhash so the distribution is deterministic given the same node
set.

Ring position encoding
----------------------
Positions are 64-bit unsigned integers derived from
``xxhash.xxh3_64_intdigest``.  The ring is modelled as the integer range
``[0, 2**64)``, wrapping around.  A key is owned by the first node whose
position is ≥ the key's hash (clockwise successor), with wrap-around to the
lowest-position node when no successor exists.

VNode token derivation
----------------------
For physical node *n* and replica index *r* (0 … vnodes-1), the token is::

    xxhash.xxh3_64_intdigest(f"{n}#vnode{r}".encode())

This is deterministic, cheap, and produces good distribution.

Single-node fast-path
---------------------
When the ring contains exactly one physical node every key maps to that node
without any binary-search overhead.  This matches the roadmap goal of making
the single-node case a first-class citizen before multi-node Raft is wired up.

Thread safety
-------------
``HashRing`` uses an ``RLock``.  ``get_owner`` / ``get_replicas`` acquire only
a read-path (non-mutating) lock section; ``add_node`` / ``remove_node`` /
``rebuild`` hold the lock for the full mutation.
"""

import bisect
import logging
import threading

import xxhash

log = logging.getLogger(__name__)

# Default number of virtual nodes (tokens) per physical node.
# 150 tokens/node gives a coefficient of variation < 10 % for typical cluster
# sizes (1-20 nodes).
DEFAULT_VNODES = 150

_RING_SIZE = 1 << 64  # 2**64 — hash space


def _token(node_id: str, replica: int) -> int:
    """Return the ring position for *node_id* replica *replica*."""
    return xxhash.xxh3_64_intdigest(f"{node_id}#vnode{replica}".encode())


def _key_hash(key) -> int:
    """Hash an arbitrary key to a ring position."""
    if isinstance(key, str):
        key = key.encode()
    return xxhash.xxh3_64_intdigest(key)


class HashRing:
    """
    Consistent hash ring.

    :param nodes:   Initial iterable of node ID strings.
    :param vnodes:  Number of virtual nodes (tokens) per physical node.
                    Higher values improve distribution at the cost of memory
                    (``len(nodes) * vnodes * ~50 bytes``).
    :param replicas: Number of distinct owners returned by ``get_replicas``.
                    Must be ≤ number of physical nodes in the ring.
    """

    def __init__(self, nodes=(), vnodes=DEFAULT_VNODES, replicas=1):
        if vnodes < 1:
            raise ValueError(f"vnodes must be ≥ 1, got {vnodes}")
        if replicas < 1:
            raise ValueError(f"replicas must be ≥ 1, got {replicas}")
        self._vnodes = vnodes
        self._replicas = replicas
        self._lock = threading.RLock()

        # Sorted list of token positions (int).
        self._ring: list[int] = []
        # token position → physical node ID
        self._token_map: dict[int, str] = {}
        # set of physical node IDs currently in the ring
        self._nodes: set[str] = set()

        for node in nodes:
            self._add_node_locked(node)

    # ------------------------------------------------------------------
    # Internal helpers (call under lock)
    # ------------------------------------------------------------------

    def _add_node_locked(self, node_id: str) -> None:
        if node_id in self._nodes:
            return
        self._nodes.add(node_id)
        for r in range(self._vnodes):
            tok = _token(node_id, r)
            if tok not in self._token_map:
                bisect.insort(self._ring, tok)
                self._token_map[tok] = node_id
            else:
                # Collision: walk forward until a free slot is found.
                # Collisions are astronomically rare with xxh3-64.
                shifted = (tok + 1) % _RING_SIZE
                while shifted in self._token_map and shifted != tok:
                    shifted = (shifted + 1) % _RING_SIZE
                if shifted != tok:
                    bisect.insort(self._ring, shifted)
                    self._token_map[shifted] = node_id

    def _remove_node_locked(self, node_id: str) -> None:
        if node_id not in self._nodes:
            return
        self._nodes.discard(node_id)
        dead_tokens = [t for t, n in self._token_map.items() if n == node_id]
        for tok in dead_tokens:
            del self._token_map[tok]
            idx = bisect.bisect_left(self._ring, tok)
            if idx < len(self._ring) and self._ring[idx] == tok:
                del self._ring[idx]

    def _find_owner_locked(self, key_hash: int) -> str | None:
        """Return the node ID of the clockwise successor of *key_hash*."""
        if not self._ring:
            return None
        idx = bisect.bisect(self._ring, key_hash)
        if idx == len(self._ring):
            idx = 0  # wrap around
        return self._token_map[self._ring[idx]]

    # ------------------------------------------------------------------
    # Public mutation API
    # ------------------------------------------------------------------

    def add_node(self, node_id: str) -> None:
        """Add *node_id* to the ring."""
        with self._lock:
            self._add_node_locked(node_id)
        log.debug(
            "HashRing: added node %s (%d physical nodes)", node_id, len(self._nodes)
        )

    def remove_node(self, node_id: str) -> None:
        """Remove *node_id* from the ring."""
        with self._lock:
            self._remove_node_locked(node_id)
        log.debug(
            "HashRing: removed node %s (%d physical nodes)", node_id, len(self._nodes)
        )

    def rebuild(self, nodes) -> None:
        """
        Atomically replace the ring contents with *nodes*.

        This is the primary hook called from ``MembershipStateMachine.on_change``
        whenever a Raft CONFIG entry is committed.
        """
        new_nodes = set(nodes)
        with self._lock:
            old_nodes = set(self._nodes)
            for n in old_nodes - new_nodes:
                self._remove_node_locked(n)
            for n in new_nodes - old_nodes:
                self._add_node_locked(n)
        log.info(
            "HashRing: rebuilt with %d node(s): %s",
            len(new_nodes),
            sorted(new_nodes),
        )

    # ------------------------------------------------------------------
    # Public query API
    # ------------------------------------------------------------------

    @property
    def is_clustered(self) -> bool:
        """
        Return ``True`` if the ring has been populated via :meth:`rebuild`.

        A standalone (non-clustered) master never calls ``rebuild()``, so its
        ring stays empty and ``is_clustered`` remains ``False``.

        Use this to short-circuit routing logic that must not fire when Raft
        is not running::

            if ring.is_clustered and ring.get_owner(jid) != my_id:
                # shunt to cluster bus

        Or use :meth:`owns` which handles both cases in one call.
        """
        with self._lock:
            return bool(self._nodes)

    def owns(self, key, node_id: str) -> bool:
        """
        Return ``True`` if *node_id* should process *key*.

        * **Standalone master** (ring empty, Raft not running): always ``True``
          — every master owns all of its own keys.
        * **Clustered master** (ring populated via :meth:`rebuild`): ``True``
          only when *node_id* is the consistent-hash owner of *key*.

        This is the intended call site for ``master.py``::

            if not ring.owns(load["jid"], self.opts["id"]):
                # shunt to cluster bus
        """
        with self._lock:
            if not self._nodes:
                return True
            n = len(self._nodes)
            if n == 1:
                return next(iter(self._nodes)) == node_id
            return self._find_owner_locked(_key_hash(key)) == node_id

    def get_owner(self, key) -> str | None:
        """
        Return the node ID that owns *key*.

        *key* may be a ``str`` or ``bytes``.  Returns ``None`` if the ring is
        empty.

        Single-node fast-path: if only one physical node is present the lock
        is acquired once and the node is returned immediately without any
        bisect.
        """
        with self._lock:
            n = len(self._nodes)
            if n == 0:
                return None
            if n == 1:
                return next(iter(self._nodes))
            return self._find_owner_locked(_key_hash(key))

    def get_replicas(self, key, count: int | None = None) -> list[str]:
        """
        Return up to *count* distinct physical nodes starting from the owner
        of *key* and walking clockwise.

        *count* defaults to ``self._replicas``.  If fewer physical nodes exist
        than requested, all nodes are returned.

        The first element is always the primary owner (same as ``get_owner``).
        """
        n_want = count if count is not None else self._replicas
        with self._lock:
            n_phys = len(self._nodes)
            if n_phys == 0:
                return []
            n_want = min(n_want, n_phys)
            if n_phys == 1:
                return [next(iter(self._nodes))]

            h = _key_hash(key)
            idx = bisect.bisect(self._ring, h)
            if idx == len(self._ring):
                idx = 0

            seen: set[str] = set()
            result: list[str] = []
            ring_len = len(self._ring)
            steps = 0
            while len(result) < n_want and steps < ring_len:
                node = self._token_map[self._ring[(idx + steps) % ring_len]]
                if node not in seen:
                    seen.add(node)
                    result.append(node)
                steps += 1
            return result

    def node_count(self) -> int:
        """Return the number of physical nodes currently in the ring."""
        with self._lock:
            return len(self._nodes)

    def nodes(self) -> list[str]:
        """Return a sorted list of physical node IDs."""
        with self._lock:
            return sorted(self._nodes)

    def token_count(self) -> int:
        """Return the total number of tokens (vnodes * physical nodes, approx)."""
        with self._lock:
            return len(self._ring)

    def distribution(self) -> dict[str, int]:
        """
        Return a dict mapping each physical node to its token count.

        Useful for verifying VNode distribution balance in tests and
        diagnostics.
        """
        with self._lock:
            result: dict[str, int] = {n: 0 for n in self._nodes}
            for node in self._token_map.values():
                result[node] = result.get(node, 0) + 1
            return result

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return self.node_count()

    def __contains__(self, node_id: str) -> bool:
        with self._lock:
            return node_id in self._nodes

    def __repr__(self) -> str:
        return (
            f"HashRing(nodes={self.nodes()!r}, vnodes={self._vnodes}, "
            f"replicas={self._replicas})"
        )
