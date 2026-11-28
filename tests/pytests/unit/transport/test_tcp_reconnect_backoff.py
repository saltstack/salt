"""
Tests for the randomized exponential backoff a minion uses between failed
TCP connection attempts to its master.
"""

import asyncio

import pytest

import salt.transport.base
import salt.transport.tcp
from tests.support.mock import AsyncMock, MagicMock, patch

pytestmark = [
    pytest.mark.core_test,
]

MASTER_IP = "10.0.0.1"


def _opts(role="minion", **kwargs):
    opts = {
        "__role": role,
        "tcp_reconnect_backoff": 1,
        "recon_max": 10000,
        "recon_randomize": False,
    }
    opts.update(kwargs)
    return opts


@pytest.mark.parametrize(
    "opts,expected",
    [
        (_opts(), [1, 2, 4, 8, 10, 10]),
        (
            _opts(tcp_reconnect_backoff=0.5, recon_max=3000),
            [0.5, 1, 2, 3, 3, 3],
        ),
        # recon_max below tcp_reconnect_backoff never shortens the delay.
        (_opts(tcp_reconnect_backoff=5, recon_max=1000), [5, 5, 5, 5, 5, 5]),
    ],
)
def test_reconnect_delay_doubles_up_to_recon_max(opts, expected):
    delays = [
        salt.transport.tcp._reconnect_delay(opts, attempt, True)
        for attempt in range(1, len(expected) + 1)
    ]
    assert delays == expected


def test_reconnect_delay_defaults():
    """
    Without the options set, the delay starts at 1 second and stops at 10.
    """
    opts = {"__role": "minion", "recon_randomize": False}
    assert salt.transport.tcp._reconnect_delay(opts, 1, True) == 1
    assert salt.transport.tcp._reconnect_delay(opts, 5, True) == 10


def test_reconnect_delay_large_attempt_count():
    """
    A long outage does not overflow the doubling.
    """
    assert salt.transport.tcp._reconnect_delay(_opts(), 100000, True) == 10


@pytest.mark.parametrize("attempt,low,high", [(1, 0.5, 1), (3, 2, 4), (9, 5, 10)])
def test_reconnect_delay_randomized(attempt, low, high):
    """
    With recon_randomize, the delay is drawn between half the delay and the
    delay.
    """
    opts = _opts(recon_randomize=True)
    with patch.object(
        salt.transport.tcp.random, "uniform", return_value=1.25
    ) as uniform:
        assert salt.transport.tcp._reconnect_delay(opts, attempt, True) == 1.25
    uniform.assert_called_once_with(low, high)

    for _ in range(100):
        delay = salt.transport.tcp._reconnect_delay(opts, attempt, True)
        assert low <= delay <= high


def test_reconnect_delay_randomize_is_default():
    opts = _opts()
    del opts["recon_randomize"]
    with patch.object(salt.transport.tcp.random, "uniform", return_value=3) as uniform:
        salt.transport.tcp._reconnect_delay(opts, 3, True)
    uniform.assert_called_once_with(2, 4)


@pytest.mark.parametrize(
    "role,to_master",
    [
        ("minion", False),
        ("master", True),
        ("master", False),
        ("syndic", True),
    ],
)
def test_reconnect_delay_fixed_for_other_connections(role, to_master):
    """
    Connections other than a minion's to its master keep the fixed
    tcp_reconnect_backoff, without randomization.
    """
    opts = _opts(role=role, tcp_reconnect_backoff=2, recon_randomize=True)
    for attempt in (1, 2, 5, 50):
        assert salt.transport.tcp._reconnect_delay(opts, attempt, to_master) == 2


@pytest.fixture
def sleeps():
    """
    Record every asyncio.sleep in salt.transport.tcp without waiting.
    """
    calls = []
    real_sleep = asyncio.sleep

    async def fake_sleep(delay, *args, **kwargs):
        calls.append(delay)
        await real_sleep(0)

    with patch("salt.transport.tcp.asyncio.sleep", side_effect=fake_sleep):
        yield calls


def _stream(closed=False):
    stream = MagicMock()
    stream.closed.return_value = closed
    return stream


def _failing_connect(failures, *streams):
    return AsyncMock(side_effect=[OSError("refused")] * failures + list(streams))


async def test_request_client_backs_off_to_master(minion_opts, io_loop, sleeps):
    minion_opts.update(
        master_uri=f"tcp://{MASTER_IP}:4506", recon_randomize=False, recon_max=10000
    )
    client = salt.transport.tcp.RequestClient(minion_opts, io_loop)
    stream = _stream()
    try:
        with patch.object(
            client._tcp_client, "connect", _failing_connect(5, stream)
        ) as connect:
            assert await client.getstream() is stream
        assert connect.await_count == 6
        assert sleeps == [1, 2, 4, 8, 10]

        # The count starts again on the next connection.
        sleeps.clear()
        stream = _stream()
        with patch.object(client._tcp_client, "connect", _failing_connect(2, stream)):
            assert await client.getstream() is stream
        assert sleeps == [1, 2]
    finally:
        client.close()


async def test_request_client_ipc_keeps_fixed_interval(
    minion_opts, io_loop, sleeps, tmp_path
):
    minion_opts.update(
        master_uri=f"ipc://{tmp_path / 'missing.ipc'}", recon_randomize=False
    )
    client = salt.transport.tcp.RequestClient(minion_opts, io_loop)
    try:

        async def stop_after_four(delay, *args, **kwargs):
            sleeps.append(delay)
            if len(sleeps) == 4:
                client._closing = True

        with patch("salt.transport.tcp.asyncio.sleep", side_effect=stop_after_four):
            assert await client.getstream() is None
        assert sleeps == [1, 1, 1, 1]
    finally:
        client.close()


async def test_request_client_on_master_keeps_fixed_interval(
    master_opts, io_loop, sleeps
):
    master_opts.update(
        master_uri=f"tcp://{MASTER_IP}:4506", recon_randomize=False, recon_max=10000
    )
    client = salt.transport.tcp.RequestClient(master_opts, io_loop)
    stream = _stream()
    try:
        with patch.object(client._tcp_client, "connect", _failing_connect(4, stream)):
            assert await client.getstream() is stream
        assert sleeps == [1, 1, 1, 1]
    finally:
        client.close()


def _pub_client(opts, io_loop, host, ssl=None):
    return salt.transport.tcp.PublishClient(
        opts, io_loop, host=host, port=4505, ssl=ssl
    )


async def test_publish_client_backs_off_to_master(minion_opts, io_loop, sleeps):
    minion_opts.update(master_ip=MASTER_IP, recon_randomize=False, recon_max=10000)
    client = _pub_client(minion_opts, io_loop, MASTER_IP)
    stream = _stream()
    try:
        with patch.object(
            salt.transport.tcp.TCPClientKeepAlive,
            "connect",
            _failing_connect(5, stream),
        ):
            assert await client.getstream() is stream
        assert sleeps == [1, 2, 4, 8, 10]
    finally:
        client.close()


async def test_publish_client_to_other_host_keeps_fixed_interval(
    minion_opts, io_loop, sleeps
):
    minion_opts.update(master_ip=MASTER_IP, recon_randomize=False, recon_max=10000)
    client = _pub_client(minion_opts, io_loop, "10.0.0.2")
    stream = _stream()
    try:
        with patch.object(
            salt.transport.tcp.TCPClientKeepAlive,
            "connect",
            _failing_connect(4, stream),
        ):
            assert await client.getstream() is stream
        assert sleeps == [1, 1, 1, 1]
    finally:
        client.close()


async def test_publish_client_waits_after_tls_close_from_master(
    minion_opts, io_loop, sleeps
):
    """
    A publish connection to the master that closes right after the TLS
    handshake waits the backoff delay before the next attempt.
    """
    minion_opts.update(master_ip=MASTER_IP, recon_randomize=False, recon_max=10000)
    client = _pub_client(
        minion_opts, io_loop, MASTER_IP, ssl={"cert_reqs": "CERT_NONE"}
    )
    good = _stream()
    streams = [_stream(closed=True), _stream(closed=True), good]
    try:
        with patch.object(
            salt.transport.tcp.TCPClientKeepAlive,
            "connect",
            AsyncMock(side_effect=streams),
        ), patch.object(salt.transport.base, "ssl_context"):
            assert await client.getstream() is good
        # 0.1 is the wait for the TLS handshake after each connection.
        assert sleeps == [0.1, 1, 0.1, 2, 0.1]
    finally:
        client.close()


async def test_publish_client_tls_close_from_other_host_retries_at_once(
    minion_opts, io_loop, sleeps
):
    minion_opts.update(master_ip=MASTER_IP, recon_randomize=False)
    client = _pub_client(
        minion_opts, io_loop, "10.0.0.2", ssl={"cert_reqs": "CERT_NONE"}
    )
    good = _stream()
    streams = [_stream(closed=True), _stream(closed=True), good]
    try:
        with patch.object(
            salt.transport.tcp.TCPClientKeepAlive,
            "connect",
            AsyncMock(side_effect=streams),
        ), patch.object(salt.transport.base, "ssl_context"):
            assert await client.getstream() is good
        assert sleeps == [0.1, 0.1, 0.1]
    finally:
        client.close()
