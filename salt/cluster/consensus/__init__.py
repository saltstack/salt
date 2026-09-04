"""
Consensus primitives for Salt master clusters (Raft-based metadata).

Prefer asyncio for integration-layer I/O and orchestration. The
``salt.cluster.consensus.raft`` package keeps a callback-driven synchronous
core for testability; outer code bridges asyncio to that surface.
"""
