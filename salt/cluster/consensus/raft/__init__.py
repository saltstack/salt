"""
Portable Raft core: log, node, timers, and test helpers.

Public objects are re-exported here so callers can use
``salt.cluster.consensus.raft`` without reaching into submodules.

The core is synchronous and callback-oriented; use asyncio in callers
(see ``salt.cluster.consensus`` package docstring).
"""

from salt.cluster.consensus.raft.log import (
    BaseStateMachine,
    BaseStorage,
    CounterStateMachine,
    Log,
    LogEntry,
    LogEntryCommitStatus,
    LogEntryType,
)
from salt.cluster.consensus.raft.node import (
    NOOPLOCK,
    Candidacy,
    CandidacyError,
    LockingNode,
    ManualPeer,
    Node,
    NodeState,
    NoOpLock,
    NotLeader,
    Peer,
    Vote,
)
from salt.cluster.consensus.raft.scheduler import (
    AsyncTimeoutScheduler,
    ManualTimeoutScheduler,
    ThreadedTimeoutScheduler,
    TimeoutHandle,
    TimeoutScheduler,
)
from salt.cluster.consensus.raft.util import (
    gettimeout,
    is_socket_closed,
    load_class,
    log_exceptions,
    log_exceptions_async,
    log_generator,
)

__all__ = (
    "AsyncTimeoutScheduler",
    "BaseStateMachine",
    "BaseStorage",
    "Candidacy",
    "CandidacyError",
    "CounterStateMachine",
    "LockingNode",
    "Log",
    "LogEntry",
    "LogEntryCommitStatus",
    "LogEntryType",
    "ManualPeer",
    "ManualTimeoutScheduler",
    "NOOPLOCK",
    "Node",
    "NodeState",
    "NoOpLock",
    "NotLeader",
    "Peer",
    "ThreadedTimeoutScheduler",
    "TimeoutHandle",
    "TimeoutScheduler",
    "Vote",
    "gettimeout",
    "is_socket_closed",
    "load_class",
    "log_exceptions",
    "log_exceptions_async",
    "log_generator",
)
