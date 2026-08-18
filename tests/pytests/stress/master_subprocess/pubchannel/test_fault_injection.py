"""
Fault-injection: publisher must survive a variety of misbehaving peers
and misbehaving input.
"""

from __future__ import annotations

import socket
import struct
import time

import pytest
import zmq

from tests.pytests.stress.master_subprocess.pubchannel.helpers import (
    make_pusher,
    make_subscriber,
)


@pytest.mark.timeout(30)
def test_subscriber_rst_mid_stream_is_survived(publisher):
    """
    A subscriber that abruptly resets its TCP connection mid-stream must
    not crash the publisher, and the publisher must clean up its own
    ``clients`` set entry within a bounded time.
    """
    # A "clean" subscriber, running throughout, to confirm the publisher
    # keeps serving after the RST.
    clean = make_subscriber(publisher)
    clean.connect()
    clean.start_reader()
    time.sleep(0.3)

    # Second subscriber uses a raw TCP socket so we can RST it via
    # SO_LINGER=0+close.  For zmq this attaches at the wire level
    # (libzmq will still see FIN, not RST, unless SO_LINGER=0).
    victim = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    victim.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    victim.connect((publisher.pub_host, publisher.pub_port))
    time.sleep(0.3)

    try:
        with make_pusher(publisher) as pusher:
            # Publish a few events so both peers are in the write path.
            for i in range(20):
                pusher.send(f"before-rst-{i}".encode())
            time.sleep(0.3)
            # RST the victim.
            victim.close()
            # Publish more.
            for i in range(20):
                pusher.send(f"after-rst-{i}".encode())
            assert clean.wait_for_frames(
                40, timeout=10.0
            ), f"clean subscriber only got {len(clean.frames)}/40 after peer RST"
        assert publisher.is_alive()
    finally:
        clean.close()


@pytest.mark.timeout(30)
def test_publisher_survives_garbage_bytes_from_subscriber(publisher):
    """
    A subscriber that writes garbage bytes back on its receive socket
    must not kill the publisher.

    The tcp PubServer runs ``_stream_read`` per client that unpacks
    incoming bytes via ``msgpack.Unpacker`` and calls ``presence_callback``.
    Malformed / garbage input must be logged and the publisher must
    keep servicing everyone else.

    For zmq the SUB socket is unidirectional (server writes only), so
    this test is a no-op there.
    """
    if publisher.transport != "tcp":
        pytest.skip("tcp-only test — zmq SUB is receive-only")

    clean = make_subscriber(publisher)
    clean.connect()
    clean.start_reader()

    garbage_peer = socket.create_connection(
        (publisher.pub_host, publisher.pub_port), timeout=5.0
    )
    time.sleep(0.3)

    try:
        # Write bytes that don't msgpack-parse as ``{"body": ...}``.
        garbage_peer.sendall(b"\xff" * 4096 + b"not-msgpack" * 100)
        garbage_peer.sendall(b"\x00" * 8192)
        time.sleep(0.5)

        # The publisher must still be alive and serving the clean SUB.
        with make_pusher(publisher) as pusher:
            for i in range(20):
                pusher.send(f"after-garbage-{i}".encode())
        assert clean.wait_for_frames(
            20, timeout=10.0
        ), f"clean subscriber got only {len(clean.frames)}/20 after garbage input"
        assert publisher.is_alive()
    finally:
        try:
            garbage_peer.close()
        except OSError:
            pass
        clean.close()


@pytest.mark.timeout(30)
def test_publisher_survives_malformed_pull_input(publisher):
    """
    The pull socket ingests msgpack-framed payloads from
    ``PubServerChannel.publish_payload``.  If a caller pushes malformed
    bytes into that socket, the publisher must log-and-drop instead of
    dying.
    """
    clean = make_subscriber(publisher)
    clean.connect()
    clean.start_reader()
    time.sleep(0.3)

    try:
        if publisher.transport == "tcp":
            # Send bytes that DON'T parse as ``frame_msg_ipc`` output.
            # A silly 4-byte "length" claiming 4 GiB followed by junk
            # will make the puller wait for bytes it will never read,
            # but the puller catches ``OSError`` / ``StreamClosedError``
            # and just closes the client stream — it must NOT crash.
            bad = socket.create_connection(
                (publisher.pull_host, publisher.pull_port), timeout=5.0
            )
            bad.sendall(b"\xff\xff\xff\xff")  # length: 4 GiB
            bad.sendall(b"garbage-msgpack" * 100)
            bad.close()
        else:
            # zmq: push a raw non-msgpack payload.  The publisher's
            # ``publish_payload`` will forward it to SUBs verbatim in
            # unfiltered mode; there's no "malformed" from ZMQ's POV.
            # Instead push an empty message which some frames don't
            # tolerate.
            ctx = zmq.Context()
            sock = ctx.socket(zmq.PUSH)
            sock.setsockopt(zmq.LINGER, 1)
            sock.connect(f"tcp://{publisher.pull_host}:{publisher.pull_port}")
            sock.send(b"")
            sock.close(0)
            ctx.destroy(0)

        time.sleep(0.5)

        # Publisher must still serve real traffic.
        with make_pusher(publisher) as pusher:
            for i in range(20):
                pusher.send(f"after-malformed-{i}".encode())
        assert clean.wait_for_frames(
            20, timeout=10.0
        ), f"clean subscriber got {len(clean.frames)}/20 after malformed input"
        assert publisher.is_alive()
    finally:
        clean.close()


@pytest.mark.timeout(30)
def test_publisher_survives_immediate_client_disconnect(publisher):
    """
    Repeatedly connect + immediately close.  Publisher must not leak
    ``clients`` set entries indefinitely and must stay alive.
    """
    from tests.pytests.stress.master_subprocess.pubchannel.conftest import fd_count

    fd_before = fd_count(publisher.pid)
    for _ in range(200):
        s = socket.create_connection(
            (publisher.pub_host, publisher.pub_port), timeout=5.0
        )
        s.close()
    time.sleep(1.0)
    fd_after = fd_count(publisher.pid)

    # Publisher stayed alive.
    assert publisher.is_alive(), "publisher died after 200 connect+close cycles"
    # FD growth from 200 connect-and-drop cycles should be small.
    # Allow a generous slop for tornado's connect+cleanup timing.
    fd_growth = fd_after - fd_before
    assert (
        fd_growth < 50
    ), f"FD count grew by {fd_growth} across 200 connect+close cycles"
