"""
Package-level conftest for master-subprocess stress tests.

These tests spawn *only* one salt-master subprocess (EventPublisher,
MWorker, MWorkerQueue, PubServerChannel._publish_daemon, ...) against
fake peers so we can pin per-subprocess throughput floors, memory
ceilings, and correctness under backpressure / peer-drop / malformed
input without paying for the full-master saltfactories setup.

Kept intentionally minimal so parallel work on sibling subprocess
suites can co-exist.  Only add symbols here that are provably shared
by more than one sub-suite.

Registers a ``stress`` marker so runs can select or exclude the suite.
"""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "stress: Mark test as part of the isolated master-subprocess "
        "stress suite.  Spawns exactly one master subprocess against "
        "fake peers.",
    )
