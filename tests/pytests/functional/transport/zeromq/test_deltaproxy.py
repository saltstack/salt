"""Real ZeroMQ subscriptions for children sharing a DeltaProxy connection."""

import asyncio
import hashlib

import zmq
import zmq.asyncio

import salt.payload
import salt.transport.zeromq


async def test_child_subscriptions(minion_opts, io_loop):
    opts = dict(
        minion_opts,
        id="controller",
        zmq_filtering=True,
        zmq_monitor=False,
        recon_randomize=False,
    )
    context = zmq.asyncio.Context()
    publisher = context.socket(zmq.XPUB)
    port = publisher.bind_to_random_port("tcp://127.0.0.1")
    children = ["child-one", "child-two"]
    topics = {
        child: hashlib.sha1(child.encode()).hexdigest().encode()
        for child in ["controller", *children]
    }
    try:
        with salt.transport.zeromq.PublishClient(
            opts, io_loop, host="127.0.0.1", port=port
        ) as client:
            await client.connect()
            # Register children after connecting, as post_master_init does.
            client.add_subscriptions(children)
            expected = {b"broadcast", *topics.values()}
            while expected:
                subscription = await asyncio.wait_for(publisher.recv(), timeout=5)
                if subscription[0] == 1:
                    expected.discard(subscription[1:])

            payload = {"enc": "aes", "load": "encrypted-job"}
            for topic in [b"broadcast", *topics.values()]:
                await publisher.send_multipart([topic, salt.payload.dumps(payload)])
                messages = await client.recv(timeout=5)
                assert messages == [topic, salt.payload.dumps(payload)]
                assert client._decode_messages(messages) == payload

            await publisher.send_multipart([b"unrelated", b"invalid"])
            assert await client.recv(timeout=0.1) is None
    finally:
        publisher.close(linger=0)
        context.destroy(linger=0)
