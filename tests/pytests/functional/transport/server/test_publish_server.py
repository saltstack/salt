import asyncio

import salt.transport


async def test_publsh_server(
    io_loop, minion_opts, master_opts, transport, process_manager
):
    minion_opts["transport"] = master_opts["transport"] = transport

    pub_server = salt.transport.publish_server(master_opts)
    pub_server.pre_fork(process_manager)
    await asyncio.sleep(3)

    pub_client = salt.transport.publish_client(
        minion_opts, io_loop, master_opts["interface"], master_opts["publish_port"]
    )
    await pub_client.connect()

    # Yield to loop in order to allow pub client to connect.
    event = asyncio.Event()

    messages = []

    async def handle_msg(msg):
        messages.append(msg)
        event.set()

    try:
        pub_client.on_recv(handle_msg)
        # TODO: Fix this inconsistancy.
        if transport == "zeromq":
            msg = b"meh"
        else:
            msg = {b"foo": b"bar"}
        await pub_server.publish(msg)
        await asyncio.wait_for(event.wait(), 1)
        assert [msg] == messages
    finally:
        pub_server.close()
        pub_client.close()

    # Yield to loop in order to allow background close methods to finish.
    await asyncio.sleep(0.3)
