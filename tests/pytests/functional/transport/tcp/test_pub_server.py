import os
import stat
import time

import tornado.gen

import salt.transport.tcp


async def test_pub_channel_ipc(master_opts, minion_opts, io_loop):
    def presence_callback(client):
        pass

    def remove_presence_callback(client):
        pass

    master_opts = master_opts.copy()
    master_opts.update(transport="tcp")
    minion_opts.update(transport="tcp")

    pub_path = os.path.join(master_opts["sock_dir"], "master_event_pub.ipc")
    pull_path = os.path.join(master_opts["sock_dir"], "master_event_pull.ipc")

    if os.path.exists(pub_path):
        os.path.unlink(pub_path)

    server = salt.transport.tcp.PublishServer(
        master_opts,
        pub_path=pub_path,
        pull_path=pull_path,
    )

    client = salt.transport.tcp.PublishClient(
        minion_opts,
        io_loop,
        path=pub_path,
    )

    payloads = []

    publishes = []

    async def publish_payload(payload, callback):
        await server.publish_payload(payload)
        payloads.append(payload)

    async def on_recv(message):
        publishes.append(message)

    io_loop.add_callback(
        server.publisher,
        publish_payload,
        presence_callback,
        remove_presence_callback,
        io_loop=io_loop,
    )

    # Wait for socket to bind.
    await tornado.gen.sleep(3)

    perms = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP
    assert (os.stat(pub_path).st_mode & perms) == perms

    await client.connect()
    client.on_recv(on_recv)

    await server.publish({"meh": "bah"})

    start = time.monotonic()
    try:
        while not publishes:
            await tornado.gen.sleep(0.3)
            if time.monotonic() - start > 30:
                assert False, "Message not published after 30 seconds"
        assert payloads
    finally:
        server.close()
        server.pub_server.close()
        client.close()


async def test_pub_channel(master_opts, minion_opts, io_loop):
    def presence_callback(client):
        pass

    def remove_presence_callback(client):
        pass

    master_opts = master_opts.copy()
    master_opts.update(transport="tcp", ipc_mode="tcp")
    minion_opts.update(master_ip="127.0.0.1", transport="tcp")

    server = salt.transport.tcp.PublishServer(
        master_opts,
        pub_host="127.0.0.1",
        pub_port=master_opts["publish_port"],
        pull_host="127.0.0.1",
        pull_port=master_opts["tcp_master_publish_pull"],
    )

    client = salt.transport.tcp.PublishClient(
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
        server.publisher,
        publish_payload,
        presence_callback,
        remove_presence_callback,
        io_loop=io_loop,
    )

    # Wait for socket to bind.
    await tornado.gen.sleep(3)

    await client.connect()
    client.on_recv(on_recv)

    await server.publish({"meh": "bah"})

    start = time.monotonic()
    try:
        while not publishes:
            await tornado.gen.sleep(0.3)
            if time.monotonic() - start > 30:
                assert False, "Message not published after 30 seconds"
        assert payloads
    finally:
        server.close()
        server.pub_server.close()
        client.close()
