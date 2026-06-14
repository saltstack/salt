import psutil
import pytest


@pytest.fixture(autouse=True)
def _skip_syndic_under_memory_pressure():
    """
    Skip syndic scenario tests when system memory is critically constrained.

    Syndic tests start a master, syndic-master, syndic-minion, and minion
    (4+ daemons). By the time syndic tests run, earlier test suites
    (multimaster, swarm) have already consumed significant memory.
    Starting additional daemons on a near-OOM host causes the OOM killer to
    terminate the test runner mid-test.
    """
    mem = psutil.virtual_memory()
    if mem.percent >= 90:
        pytest.skip(f"Skipping syndic tests: system memory at {mem.percent:.1f}%")
