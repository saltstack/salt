"""
Regression test for FD leak from nested SyncWrapper in TCP transport (Fix #6).

Bug: PublishServer.connect() creates a SyncWrapper for pub_sock wrapping
_TCPPubServerPublisher. When PublishServer.close() was called, it called
pub_sock.close() through __getattr__ which didn't properly clean up the
nested SyncWrapper's event loop.

Fix: Explicitly call SyncWrapper.close() for pub_sock in
salt/transport/tcp.py PublishServer.close()

This test exercises TCP transport publish operations.
"""

import time

import pytest

pytestmark = [
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def salt_master_tcp(salt_factories):
    """Create master with TCP transport."""
    config_overrides = {
        "transport": "tcp",
    }
    factory = salt_factories.salt_master_daemon(
        "tcp-master",
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def salt_minion_tcp(salt_master_tcp):
    """Create minion with TCP transport."""
    config_overrides = {
        "transport": "tcp",
        "master": salt_master_tcp.config["interface"],
        "master_port": salt_master_tcp.config["ret_port"],
    }
    factory = salt_master_tcp.salt_minion_daemon(
        "tcp-minion",
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture
def salt_client_tcp(salt_master_tcp):
    """Create client for TCP master."""
    return salt_master_tcp.salt_client()


def test_tcp_publish_operations_no_fd_leak(
    salt_master_tcp, salt_minion_tcp, salt_client_tcp
):
    """
    Regression test: TCP transport publish operations with nested SyncWrapper cleanup.

    Before fix (salt/transport/tcp.py PublishServer.close()):
        if self.pub_sock:
            self.pub_sock.close()  # Through __getattr__ - doesn't clean up loop

    After fix:
        if self.pub_sock:
            if isinstance(self.pub_sock, SyncWrapper):
                SyncWrapper.close(self.pub_sock)  # Explicit - cleans up loop

    This test uses TCP transport which creates nested SyncWrapper instances.
    """
    import psutil

    master_pid = salt_master_tcp.pid
    if master_pid is None:
        pytest.skip("Cannot get master PID")

    try:
        process = psutil.Process(master_pid)
    except psutil.NoSuchProcess:
        pytest.skip("Master process not found")

    initial_fds = process.num_fds()

    # Run operations that exercise TCP publish operations
    # These create/use PublishServer with nested SyncWrapper
    operation_count = 25
    for i in range(operation_count):
        ret = salt_client_tcp.cmd(salt_minion_tcp.id, "test.ping")
        assert ret[salt_minion_tcp.id] is True
        time.sleep(0.1)

    # Aggressive garbage collection
    import gc

    for _ in range(10):
        gc.collect()
        time.sleep(0.5)

    final_fds = process.num_fds()
    leaked_fds = final_fds - initial_fds

    # With explicit SyncWrapper.close() for nested instances, leak should be minimal
    assert (
        leaked_fds <= 20
    ), f"FD leak from TCP nested SyncWrapper: {leaked_fds} FDs after {operation_count} operations"
