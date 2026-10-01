import salt.channel.client
from tests.support.mock import AsyncMock, MagicMock, patch


async def test_async_pub_channel_connect_cb(minion_opts):
    """
    Validate connect_callback closes the request channel it creates.

    ``connect_callback`` uses ``async with AsyncReqChannel.factory(...)``
    (switched from sync ``with`` as part of the VCOPS-90587 close-async
    audit), so the mock has to expose ``__aenter__`` / ``__aexit__``,
    not ``__enter__`` / ``__exit__``.
    """
    minion_opts["master_uri"] = "tcp://127.0.0.1:4506"
    minion_opts["master_ip"] = "127.0.0.1"
    with salt.channel.client.AsyncPubChannel.factory(minion_opts) as channel:

        async def send_id(*args):
            return

        channel.send_id = send_id
        channel._reconnected = True

        mock = MagicMock(salt.channel.client.AsyncReqChannel)
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=None)

        with patch("salt.channel.client.AsyncReqChannel.factory", return_value=mock):
            await channel.connect_callback(None)
            mock.send.assert_called_once()
            mock.__aexit__.assert_called_once()
