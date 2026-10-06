"""
Smoke test: does the ``PubServerChannel._publish_daemon`` fixture actually
spawn a live publisher subprocess and expose bind-able endpoints?
"""

from __future__ import annotations

import socket
import time

import pytest


@pytest.mark.timeout(30)
def test_publisher_process_is_alive(publisher):
    assert publisher.is_alive(), "publisher subprocess died at startup"
    assert publisher.pid, "publisher has no pid"


@pytest.mark.timeout(30)
def test_publisher_pub_endpoint_accepts_tcp_connection(publisher):
    """Both zmq and tcp bind a TCP listener on ``publish_port``."""
    deadline = time.monotonic() + 5.0
    last_err = None
    while time.monotonic() < deadline:
        try:
            s = socket.create_connection(
                (publisher.pub_host, publisher.pub_port), timeout=1.0
            )
            s.close()
            return
        except OSError as exc:
            last_err = exc
            time.sleep(0.05)
    pytest.fail(f"pub endpoint never accepted a connection: {last_err!r}")
