import salt.fileclient
from tests.support.mock import patch


class MockReqChannel:
    def factory(self, opts):
        return self

    def close(self):
        return True

    def send(self, load):
        return self


def test_fileclient_context_manager_closes(temp_salt_minion, temp_salt_master):
    """
    ensure fileclient channel closes
    when used with a context manager
    """
    opts = temp_salt_minion.config.copy()
    opts.update(
        {
            "id": "root",
            "transport": "zeromq",
            "auth_tries": 1,
            "auth_timeout": 5,
            "master_ip": "127.0.0.1",
            "master_port": temp_salt_master.config["ret_port"],
            "master_uri": "tcp://127.0.0.1:{}".format(
                temp_salt_master.config["ret_port"]
            ),
        }
    )
    master_uri = "tcp://{master_ip}:{master_port}".format(
        master_ip="localhost", master_port=opts["master_port"]
    )
    mock_reqchannel = MockReqChannel()
    patch_reqchannel = patch.object(
        salt.channel.client, "ReqChannel", return_value=mock_reqchannel
    )
    with patch_reqchannel:
        with salt.fileclient.get_file_client(opts) as client:
            client.master_opts()
            assert not client._closing

        assert client._closing
        assert client.channel.close.called
