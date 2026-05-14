"""
Regression test for FD leak from unclosed TCP client (Fix #7).

Bug: PublishClient.getstream() creates a TCPClientKeepAlive instance stored
in self._tcp_client. This TCP client holds file descriptors (sockets) but
wasn't being closed in PublishClient.close().

Fix: Added _tcp_client.close() in salt/transport/tcp.py PublishClient.close()

This test exercises TCP client connections.
"""

import time

import pytest
from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN

pytestmark = [
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def salt_master_tcp(salt_factories):
    """Create master with TCP transport."""
    config_overrides = {
        "transport": "tcp",
        "open_mode": True,
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        random_string("tcp-master-client-"),
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
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": ("PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"),
    }
    factory = salt_master_tcp.salt_minion_daemon(
        random_string("tcp-minion-client-"),
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture
def salt_client_tcp(salt_master_tcp):
    """Create client for TCP master."""
    return salt_master_tcp.salt_client()


def test_tcp_client_connections_no_fd_leak(
    salt_master_tcp, salt_minion_tcp, salt_client_tcp
):
    """
    Regression test: TCP client connections are properly closed.

    Before fix (salt/transport/tcp.py PublishClient.close()):
        if stream is not None:
            stream.close()
        # BUG: _tcp_client not closed - socket FDs leak

    After fix:
        if stream is not None:
            stream.close()
        if hasattr(self, '_tcp_client') and self._tcp_client is not None:
            self._tcp_client.close()  # Release socket FDs
            self._tcp_client = None

    This test creates many client connections to exercise TCP client cleanup.
    """
    import psutil

    minion_pid = salt_minion_tcp.pid
    if minion_pid is None:
        pytest.skip("Cannot get minion PID")

    try:
        process = psutil.Process(minion_pid)
    except psutil.NoSuchProcess:
        pytest.skip("Minion process not found")

    initial_fds = process.num_fds()

    # Run many operations that create TCP client connections
    # Each connection creates a _tcp_client that needs to be closed
    operation_count = 30
    for i in range(operation_count):
        # Various operations that use TCP client
        if i % 2 == 0:
            ret = salt_client_tcp.cmd(salt_minion_tcp.id, "test.ping")
            assert ret[salt_minion_tcp.id] is True
        else:
            ret = salt_client_tcp.cmd(
                salt_minion_tcp.id,
                "test.echo",
                [f"tcp_client_test_{i}"],
            )
        time.sleep(0.1)

    # Aggressive garbage collection
    import gc

    for _ in range(10):
        gc.collect()
        time.sleep(0.5)

    final_fds = process.num_fds()
    leaked_fds = final_fds - initial_fds

    # With _tcp_client.close(), socket FDs should be released
    assert (
        leaked_fds <= 20
    ), f"FD leak from TCP client: {leaked_fds} FDs after {operation_count} connections"
