import os
import time

import tornado.gen

import salt.transport.tcp


async def test_pub_channel(master_opts, minion_opts, io_loop):
    def presence_callback(client):
        pass

    def remove_presence_callback(client):
        pass

    master_opts["transport"] = "tcp"
    minion_opts.update(master_ip="127.0.0.1", transport="tcp")

    server = salt.transport.tcp.TCPPublishServer(
        master_opts,
        pub_host="127.0.0.1",
        pub_port=master_opts["publish_port"],
        pull_path=os.path.join(master_opts["sock_dir"], "publish_pull.ipc"),
    )

    client = salt.transport.tcp.TCPPubClient(
        minion_opts,
        io_loop,
        host="127.0.0.1",
        port=master_opts["publish_port"],
    )

    payloads = []

    publishes = []

    async def publish_payload(payload, callback):
        await server.publish_payload(payload)
        payloads.append(payload)

    async def on_recv(message):
        publishes.append(message)

    io_loop.add_callback(
        server.publisher, publish_payload, presence_callback, remove_presence_callback
    )

    # Wait for socket to bind.
    await tornado.gen.sleep(3)

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
        server.pub_server.close()
        client.close()
