import asyncio
import multiprocessing
import socket
import threading
import time

import pytest

import salt.transport.tcp

pytestmark = [
    pytest.mark.core_test,
]


@pytest.mark.skip_on_fips_enabled_platform
def test_tcp_load_balancer_server(master_opts, io_loop):

    messages = []

    def handler(stream, message, header):
        messages.append(message)

    queue = multiprocessing.Queue()
    server = salt.transport.tcp.LoadBalancerServer(master_opts, queue)
    worker = salt.transport.tcp.LoadBalancerWorker(queue, handler, io_loop=io_loop)

    def run_loop():
        try:
            io_loop.start()
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Caught exeption {exc}")

    thread = threading.Thread(target=server.run)
    thread.start()

    # Wait for bind to happen.
    time.sleep(0.5)

    package = {"foo": "bar"}
    payload = salt.transport.frame.frame_msg(package)
    sock = socket.socket()
    sock.connect(("127.0.0.1", master_opts["ret_port"]))
    sock.send(payload)

    start = time.monotonic()

    async def check_test():
        while not messages:
            await asyncio.sleep(0.3)
            if time.monotonic() - start > 30:
                break

    io_loop.run_sync(lambda: check_test())  # pylint: disable=unnecessary-lambda

    try:
        if time.monotonic() - start > 30:
            assert False, "Took longer than 30 seconds to receive message"

        assert [package] == messages
    finally:
        server.close()
        thread.join()
        worker.close()
