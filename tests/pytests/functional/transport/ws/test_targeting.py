"""Live WebSocket publication delivery to a shared controller connection."""

import aiohttp.web
import pytest
from pytestshellutils.utils import ports

import salt.payload
import salt.transport.ws


@pytest.mark.parametrize("topics", [None, ["child-one"], ["child-one", "child-two"]])
async def test_child_topics_reach_controller(master_opts, minion_opts, io_loop, topics):
    server = salt.transport.ws.PublishServer(master_opts)
    app = aiohttp.web.Application()
    app.router.add_get("/ws", server.handle_request)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    port = ports.get_unused_localhost_port()
    site = aiohttp.web.TCPSite(runner, "127.0.0.1", port)
    client = salt.transport.ws.PublishClient(
        dict(minion_opts, id="controller", transport="ws"),
        io_loop,
        host="127.0.0.1",
        port=port,
    )
    try:
        await site.start()
        await client.connect()
        assert len(server.clients) == 1
        payload = {"enc": "aes", "load": "encrypted-job"}
        await server.publish_payload(salt.payload.dumps(payload), topic_list=topics)
        received = await client.recv(timeout=5)
        assert client._decode_messages(received) == payload
    finally:
        await client._async_cleanup()
        client.close()
        await runner.cleanup()
        server.close()
