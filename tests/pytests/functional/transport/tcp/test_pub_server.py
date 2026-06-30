import asyncio
import logging
import os
import socket
import time

import tornado.gen
import tornado.iostream

import salt.transport.tcp


async def test_publisher_close_during_connect_no_attribute_error_69187(
    io_loop, monkeypatch
):
    """
    Regression test for #69187.

    Drives ``_TCPPubServerPublisher`` through its real ``connect()``,
    ``_connect()``, and ``close()`` entry points on a real asyncio /
    tornado io_loop. The only piece we slow down is ``IOStream.connect``
    — we wrap it so the in-flight ``_connect()`` task is reliably parked
    on its ``await`` when ``publisher.close()`` runs, which is the race
    described in the issue.

    Without the fix the in-flight ``_connect()`` task raises
    ``AttributeError: 'NoneType' object has no attribute 'set_result'``
    (or ``set_exception``). The task is scheduled with
    ``io_loop.create_task()``; tornado's ``IOLoop._discard_future_result``
    callback consumes the exception and routes it through
    ``IOLoop.handle_callback_exception`` → ``tornado`` logger at ERROR.
    This test installs a logging handler on the ``tornado`` logger that
    captures records produced during the close-during-connect window and
    asserts none reference ``AttributeError``.
    """
    # Pause the IOStream connect handshake until the test releases it, so
    # _connect() is guaranteed to be awaiting when close() runs.
    release = asyncio.Event()
    started = asyncio.Event()
    real_connect = tornado.iostream.IOStream.connect

    async def slow_connect(self, address, *args, **kwargs):
        started.set()
        await release.wait()
        return await real_connect(self, address, *args, **kwargs)

    monkeypatch.setattr(tornado.iostream.IOStream, "connect", slow_connect)

    # tornado logs exceptions raised inside loop callbacks via the
    # ``tornado`` / ``tornado.application`` loggers; capture those records
    # for the duration of the test.
    captured_records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            captured_records.append(record)

    capture_handler = _Capture(level=logging.DEBUG)
    tornado_logger = logging.getLogger("tornado")
    tornado_logger.addHandler(capture_handler)
    prev_level = tornado_logger.level
    tornado_logger.setLevel(logging.DEBUG)

    try:
        # Bind a real listener so the eventual real connect, when it
        # resumes, completes cleanly rather than blocking.
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(5)
        host, port = listener.getsockname()
        try:
            publisher = salt.transport.tcp._TCPPubServerPublisher(
                host=host, port=port, path=None, io_loop=io_loop
            )

            # publisher.connect() schedules _connect() on the io_loop via
            # io_loop.create_task() and returns the connecting future.
            connect_future = publisher.connect(timeout=None)

            # Wait until _connect() has reached the slow IOStream.connect
            # await — _connecting_future is the live future at this point
            # and close() is about to null it.
            await asyncio.wait_for(started.wait(), timeout=5)

            # close() nulls _connecting_future while _connect() is parked;
            # without the fix the in-flight task crashes on the next line
            # of _connect() (set_result on success, set_exception on
            # failure).
            publisher.close()

            # Let IOStream.connect resume so _connect() unparks and walks
            # into the set_result / set_exception branch.
            release.set()

            # Drain the loop so the _connect() task either resolves or
            # raises into tornado's discard-future-result callback.
            try:
                await asyncio.wait_for(connect_future, timeout=2)
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                pass
            await asyncio.sleep(0.1)
        finally:
            listener.close()
    finally:
        tornado_logger.removeHandler(capture_handler)
        tornado_logger.setLevel(prev_level)

    matching = []
    for record in captured_records:
        message = record.getMessage()
        if record.exc_info:
            exc = record.exc_info[1]
            chain = []
            while exc is not None:
                chain.append(exc)
                exc = exc.__context__ or exc.__cause__
            if any(isinstance(e, AttributeError) for e in chain):
                matching.append(message)
                continue
        if "AttributeError" in message:
            matching.append(message)
    assert (
        not matching
    ), f"AttributeError leaked from _connect() after close(): {matching!r}"


async def test_pub_channel(master_opts, minion_opts, io_loop):
    def presence_callback(client):
        pass

    def remove_presence_callback(client):
        pass

    master_opts["transport"] = "tcp"
    minion_opts.update(master_ip="127.0.0.1", transport="tcp")

    server = salt.transport.tcp.PublishServer(
        master_opts,
        pub_host="127.0.0.1",
        pub_port=master_opts["publish_port"],
        pull_path=os.path.join(master_opts["sock_dir"], "publish_pull.ipc"),
    )

    client = salt.transport.tcp.PublishClient(
        minion_opts,
        io_loop,
        host="127.0.0.1",
        port=master_opts["publish_port"],
    )

    payloads = []

    publishes = []

    async def publish_payload(payload):
        await server.publish_payload(payload)
        payloads.append(payload)

    async def on_recv(message):
        publishes.append(message)

    io_loop.add_callback(
        server.publisher, publish_payload, presence_callback, remove_presence_callback
    )

    # Wait for socket to bind.
    await asyncio.sleep(3)

    await client.connect(master_opts["publish_port"])
    client.on_recv(on_recv)

    await server.publish({"meh": "bah"})

    start = time.monotonic()
    try:
        while not publishes:
            await tornado.gen.sleep(0.3)
            if time.monotonic() - start > 30:
                assert False, "Message not published after 30 seconds"
    finally:
        server.close()
        client.close()
