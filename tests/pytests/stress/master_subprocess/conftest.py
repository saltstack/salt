"""
Shared conftest for per-subprocess master stress tests.

Kept intentionally minimal so it can be safely merged with parallel work
on sibling subprocess suites (EventPublisher, MWorkerQueue,
PubServerChannel).  Only add symbols here that are provably shared by
more than one sub-suite.
"""
