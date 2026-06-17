import asyncio
import logging
import multiprocessing
import time

import pytest

try:
    import zmq

    import salt.transport.zeromq
except ImportError:
    zmq = None


log = logging.getLogger(__name__)


def clients(recieved):
    """
    Fire up 1000 publish socket clients and wait for a message.
    """
    log.debug("Clients start")
    context = zmq.asyncio.Context()
    sockets = {}
    for i in range(1000):
        socket = context.socket(zmq.SUB)
        socket.connect("tcp://127.0.0.1:5406")
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        sockets[i] = socket
    log.debug("Clients connected")

    async def check():
        start = time.time()
        while time.time() - start < 60:
            n = 0
            for i in list(sockets):
                if await sockets[i].poll():
                    msg = await sockets[i].recv()
                    n += 1
                    log.debug(
                        "Client %d got message %s total %d", i, msg, recieved.value
                    )
                    sockets[i].close(0)
                    sockets.pop(i)
            with recieved.get_lock():
                recieved.value += n
            await asyncio.sleep(0.3)

    asyncio.run(check())


@pytest.mark.skipif(not zmq, reason="Zeromq not installed")
def test_issue_regression_65265():
    """
    Regression test for 65265. This test will not fail 100% of the time prior
    to the fix for 65265. However, it does pass reliably with the issue fixed.
    """
    recieved = multiprocessing.Value("i", 0)
    process_manager = salt.utils.process.ProcessManager(wait_for_kill=5)
    opts = {"ipv6": False, "zmq_filtering": False, "zmq_backlog": 1000, "pub_hwm": 1000}
    process_manager.add_process(clients, args=(recieved,))
    process_manager.add_process(clients, args=(recieved,))
    process_manager.add_process(clients, args=(recieved,))
    # Give some time for all clients to start up before starting server.
    time.sleep(10)
    server = salt.transport.zeromq.PublishServer(
        opts, pub_host="127.0.0.1", pub_port=5406, pull_path="/tmp/pull.ipc"
    )
    process_manager.add_process(server.publish_daemon, args=(server.publish_payload,))
    # Wait some more for the server to start up completely.
    time.sleep(10)
    asyncio.run(server.publish(b"asdf"))
    log.debug("After publish")
    # Give time for clients to receive thier messages.
    time.sleep(10)
    try:
        with recieved.get_lock():
            total = recieved.value
        assert total == 3000
    finally:
        process_manager.kill_children(9)
