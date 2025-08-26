import multiprocessing
import time

import salt.ext.tornado.gen
import salt.transport.tcp


async def test_pub_channel(master_opts, minion_opts, io_loop):
    def presence_callback(client):
        pass

    def remove_presence_callback(client):
        pass

    master_opts["transport"] = "tcp"
    minion_opts.update(master_ip="127.0.0.1", transport="tcp")

    server = salt.transport.tcp.TCPPublishServer(master_opts)

    client = salt.transport.tcp.TCPPubClient(minion_opts, io_loop)

    payloads = []

    publishes = []

    def publish_payload(payload, callback):
        server.publish_payload(payload)
        payloads.append(payload)

    def on_recv(message):
        publishes.append(message)

    proc = multiprocessing.Process(
        target=server.publish_daemon,
        args=(publish_payload, presence_callback, remove_presence_callback),
    )
    proc.start()

    # Wait for socket to bind.
    time.sleep(3)

    await client.connect(master_opts["publish_port"])
    client.on_recv(on_recv)

    server.publish({"meh": "bah"})

    start = time.monotonic()
    try:
        while not publishes:
            await salt.ext.tornado.gen.sleep(0.3)
            if time.monotonic() - start > 30:
                assert False, "Message not published after 30 seconds"
    finally:
        client.close()
        server.close()
        proc.terminate()
        proc.join()
