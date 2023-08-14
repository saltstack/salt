import pytest

import salt.fileclient
from tests.support.mock import Mock, patch


class MockReqChannel:
    def factory(self, opts):
        return self

    def close(self):
        return True

    def send(self, load):
        return self


def test_fileclient_context_manager_closes(minion_opts, master_opts):
    """
    ensure fileclient channel closes
    when used with a context manager
    """
    minion_opts.update(
        {
            "id": "root",
            "transport": "zeromq",
            "auth_tries": 1,
            "auth_timeout": 5,
            "master_ip": "127.0.0.1",
            "master_port": master_opts["ret_port"],
            "master_uri": "tcp://127.0.0.1:{}".format(master_opts["ret_port"]),
            "request_channel_timeout": 1,
            "request_channel_tries": 1,
        }
    )
    master_uri = "tcp://{master_ip}:{master_port}".format(
        master_ip="localhost", master_port=minion_opts["master_port"]
    )
    mock_reqchannel = MockReqChannel()
    patch_reqchannel = patch.object(
        salt.channel.client, "ReqChannel", return_value=mock_reqchannel
    )
    with patch_reqchannel:
        with salt.fileclient.get_file_client(minion_opts) as client:
            client.master_opts()
            assert not client._closing

        assert client._closing
        assert client.channel.close.called


@pytest.mark.slow_test
def test_fileclient_timeout(minion_opts, master_opts):
    """
    ensure fileclient channel closes
    when used with a context manager
    """
    minion_opts.update(
        {
            "id": "root",
            "transport": "zeromq",
            "auth_tries": 1,
            "auth_timeout": 5,
            "master_ip": "127.0.0.1",
            "master_port": master_opts["ret_port"],
            "master_uri": "tcp://127.0.0.1:{}".format(master_opts["ret_port"]),
            "request_channel_timeout": 1,
            "request_channel_tries": 1,
        }
    )
    master_uri = "tcp://{master_ip}:{master_port}".format(
        master_ip="localhost", master_port=minion_opts["master_port"]
    )

    async def mock_auth():
        return True

    def mock_dumps(*args):
        return b"meh"

    with salt.fileclient.get_file_client(minion_opts) as client:
        # Authenticate must return true
        client.auth.authenticate = mock_auth
        # Crypticla must return bytes to pass to transport.RequestClient.send
        client.auth._crypticle = Mock()
        client.auth._crypticle.dumps = mock_dumps
        with pytest.raises(salt.exceptions.SaltClientError):
            client.file_list()
