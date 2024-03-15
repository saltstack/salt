import asyncio

import salt.transport
import salt.utils.process


async def test_request_server(
    io_loop, minion_opts, master_opts, transport, process_manager
):
    minion_opts["transport"] = master_opts["transport"] = transport

    # Needed by tcp transport's RequestClient
    minion_opts["master_uri"] = (
        f"tcp://{master_opts['interface']}:{master_opts['ret_port']}"
    )

    req_server = salt.transport.request_server(master_opts)
    req_server.pre_fork(process_manager)

    reqmsg = {"req": "test"}
    repmsg = {"result": "success"}

    requests = []

    async def handler(message):
        requests.append(message)
        return repmsg

    req_server.post_fork(handler, io_loop)
    req_client = salt.transport.request_client(minion_opts, io_loop)
    try:

        ret = await req_client.send({"req": "test"})
        assert [reqmsg] == requests
        assert repmsg == ret
    finally:
        req_client.close()
        req_server.close()

    # Yield to loop in order to allow background close methods to finish.
    await asyncio.sleep(0.3)
