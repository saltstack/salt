"""
Fault-injection helpers for Raft tests (partitions, drop rate, latency).
"""

import logging
import random
import time

log = logging.getLogger(__name__)


class ChaosController:
    """Controls the chaos rules for a cluster of nodes."""

    def __init__(self):
        """Initialize with no active partitions or drops."""
        self.partitions = (
            set()
        )  # Set of (addr1, addr2) tuples representing blocked links
        self.drop_rate = 0.0  # Global packet drop probability (0.0 to 1.0)
        self.latency_min = 0  # Minimum latency in ms
        self.latency_max = 0  # Maximum latency in ms

    def partition(self, addr1, addr2):
        """Block communication between two addresses."""
        # Always store in sorted order to represent an undirected link
        link = tuple(sorted([addr1, addr2]))
        self.partitions.add(link)
        log.info("CHAOS: Partitioned link %s <-> %s", addr1, addr2)

    def heal(self, addr1, addr2):
        """Restore communication between two addresses."""
        link = tuple(sorted([addr1, addr2]))
        self.partitions.discard(link)
        log.info("CHAOS: Healed link %s <-> %s", addr1, addr2)

    def heal_all(self):
        """Restore all communications."""
        self.partitions.clear()
        log.info("CHAOS: Healed all partitions")

    def should_drop(self, src, dst):
        """Check if a message between two nodes should be dropped."""
        # Check partitions
        link = tuple(sorted([src, dst]))
        if link in self.partitions:
            return True

        # Check random loss
        if self.drop_rate > 0 and random.random() < self.drop_rate:
            return True

        return False

    def get_latency(self):
        """Calculate a random latency based on current rules."""
        if self.latency_max <= 0:
            return 0
        return random.randint(self.latency_min, self.latency_max) / 1000.0


class ChaosPeer:
    """A wrapper for a Peer that injects failures based on a ChaosController."""

    def __init__(self, real_peer, controller, local_address):
        """Initialize the chaos wrapper around a real peer."""
        self.real_peer = real_peer
        self.controller = controller
        self.local_address = local_address
        # Mirror real peer attributes
        self.address = real_peer.address
        self.voting = getattr(real_peer, "voting", True)

    def __getattr__(self, name):
        """Delegate attribute access to the underlying real peer."""
        # Delegate everything else to the real peer
        return getattr(self.real_peer, name)

    def _wrap_rpc(self, method, callback, *args, **kwargs):
        """Intercept RPC calls to apply chaos rules."""
        if self.controller.should_drop(self.local_address, self.address):
            log.debug(
                "CHAOS: Dropping %s from %s to %s",
                method.__name__,
                self.local_address,
                self.address,
            )
            return

        latency = self.controller.get_latency()
        if latency > 0:
            # For simplicity in this implementation, we just sleep.
            # In a real async/threaded runtime, we'd use the scheduler.
            time.sleep(latency)

        return method(callback, *args, **kwargs)

    def request_vote(self, callback, *args, **kwargs):
        """Issue a RequestVote RPC with potential chaos effects."""
        return self._wrap_rpc(self.real_peer.request_vote, callback, *args, **kwargs)

    def pre_request_vote(self, callback, *args, **kwargs):
        """Issue a Pre-RequestVote RPC with potential chaos effects."""
        return self._wrap_rpc(
            self.real_peer.pre_request_vote, callback, *args, **kwargs
        )

    def append_entries(self, callback, *args, **kwargs):
        """Issue an AppendEntries RPC with potential chaos effects."""
        return self._wrap_rpc(self.real_peer.append_entries, callback, *args, **kwargs)

    def install_snapshot(self, callback, *args, **kwargs):
        """Issue an InstallSnapshot RPC with potential chaos effects."""
        return self._wrap_rpc(
            self.real_peer.install_snapshot, callback, *args, **kwargs
        )
