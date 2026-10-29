"""Salt request channels interoperate with the production WebSocket handler."""

import asyncio

import aiohttp.web
import pytest

import salt.channel.client
import salt.transport.ws
import salt.utils.asynchronous

pytestmark = [pytest.mark.core_test]


@pytest.fixture
def request_server(io_loop):
    state = {"received": [], "started": asyncio.Event(), "release": asyncio.Event()}
    server = salt.transport.ws.RequestServer({})

    async def application_handler(payload):
        assert payload["enc"] == "clear"
        load = payload["load"]
        state["received"].append(load)
        if load.get("block"):
            state["started"].set()
            await state["release"].wait()
        return {"request": load["id"], "result": load.get("value")}

    server.message_handler = application_handler

    async def start():
        # Exercise Salt's wire handler; the fixture owns the listener and runner.
        runner = aiohttp.web.ServerRunner(
            aiohttp.web.Server(server.handle_message), shutdown_timeout=1
        )
        await runner.setup()
        await aiohttp.web.TCPSite(runner, "127.0.0.1", 0).start()
        host, port = runner.addresses[0]
        state["opts"] = {"transport": "ws", "master_uri": f"http://{host}:{port}/ws"}
        state["runner"] = runner

    loop = salt.utils.asynchronous.aioloop(io_loop)
    loop.run_until_complete(start())
    yield state
    state["release"].set()
    loop.run_until_complete(state["runner"].cleanup())


async def test_async_channel_concurrent_requests_use_salt_server(request_server):
    async with salt.channel.client.AsyncReqChannel.factory(
        request_server["opts"], crypt="clear"
    ) as channel:
        loads = [{"id": index, "value": index * 2} for index in range(20)]
        results = await asyncio.gather(*(channel.send(load) for load in loads))
        assert results == [
            {"request": load["id"], "result": load["value"]} for load in loads
        ]
        assert request_server["received"] == loads
        assert len(request_server["runner"].server.connections) == 1
        transport = channel.transport
    assert transport._closed
    assert transport.close_task.done()
    assert not transport._operation_tasks


async def test_blocked_client_does_not_block_another_client(request_server):
    opts = request_server["opts"]
    async with salt.channel.client.AsyncReqChannel.factory(
        opts, crypt="clear"
    ) as first, salt.channel.client.AsyncReqChannel.factory(
        opts, crypt="clear"
    ) as second:
        active = asyncio.create_task(first.send({"id": 1, "block": True}))
        await request_server["started"].wait()
        try:
            assert await asyncio.wait_for(
                second.send({"id": 2, "value": False}), 2
            ) == {
                "request": 2,
                "result": False,
            }
            assert not active.done()
        finally:
            request_server["release"].set()
            result = await asyncio.wait_for(active, 2)
        assert result == {"request": 1, "result": None}


@pytest.mark.parametrize("context_manager", [False, True])
async def test_sync_channel_uses_salt_server_and_finishes_cleanup(
    request_server, context_manager
):
    def request():
        channel = salt.channel.client.ReqChannel.factory(
            request_server["opts"], crypt="clear"
        )
        transport = channel.obj.transport
        if context_manager:
            with channel:
                result = channel.send({"id": 7, "value": "sync"})
        else:
            try:
                result = channel.send({"id": 7, "value": "sync"})
            finally:
                channel.close()
        assert transport._closed
        assert transport.session is None
        assert transport.close_task.done()
        assert not transport.close_task.cancelled()
        return result

    # The synchronous API drives its own loop in this thread while the test's
    # loop continues serving real WebSocket traffic.
    result = await asyncio.wait_for(asyncio.to_thread(request), 5)
    assert result == {"request": 7, "result": "sync"}
