import salt.channel.client
from tests.support.mock import MagicMock, patch


async def test_async_pub_channel_connect_cb(minion_opts):
    """
    Validate connect_callback closes the request channel it creates.
    """
    minion_opts["master_uri"] = "tcp://127.0.0.1:4506"
    minion_opts["master_ip"] = "127.0.0.1"
    channel = salt.channel.client.AsyncPubChannel.factory(minion_opts)

    async def send_id(*args):
        return

    channel.send_id = send_id
    channel._reconnected = True

    mock = MagicMock(salt.channel.client.AsyncReqChannel)
    with patch("salt.channel.client.AsyncReqChannel.factory", return_value=mock):
        await channel.connect_callback(None)
        mock.send.assert_called_once()
        mock.close.assert_called_once()
