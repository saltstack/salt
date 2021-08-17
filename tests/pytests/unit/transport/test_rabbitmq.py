
import hashlib

import salt.config
import salt.exceptions
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.log.setup
import salt.transport.client
import salt.transport.server
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
from salt.ext import tornado
from salt.transport.rabbitmq import AsyncReqMessageClientPool
from tests.support.mock import MagicMock, call, patch


def test_async_req_message_client_pool_send():
    sock_pool_size = 5
    with patch(
        "salt.transport.rabbitmq.AsyncReqMessageClient.__init__",
        MagicMock(return_value=None),
    ):
        message_client_pool = AsyncReqMessageClientPool(
            {"sock_pool_size": sock_pool_size}, args=({}, "")
        )
        message_client_pool.message_clients = [
            MagicMock() for _ in range(sock_pool_size)
        ]
        for message_client_mock in message_client_pool.message_clients:
            message_client_mock.send_queue = [0, 0, 0]
            message_client_mock.send.return_value = []

        with message_client_pool:
            assert message_client_pool.send() == []

            message_client_pool.message_clients[2].send_queue = [0]
            message_client_pool.message_clients[2].send.return_value = [1]
            assert message_client_pool.send() == [1]


def test_clear_req_channel_master_uri_override(temp_salt_minion, temp_salt_master):
    """
    ensure master_uri kwarg is respected
    """
    opts = temp_salt_minion.config.copy()
    # minion_config should be 127.0.0.1, we want a different uri that still connects
    opts.update(
        {
            "id": "root",
            "transport": "rabbitmq",
            "auth_tries": 1,
            "auth_timeout": 5,
            "master_ip": "127.0.0.1",
            "master_port": temp_salt_master.config["ret_port"],
            "master_uri": "tcp://127.0.0.1:{}".format(
                temp_salt_master.config["ret_port"]
            ),
            "transport_rabbitmq_address": "localhost",
            "transport_rabbitmq_auth": {"username": "user", "password": "bitnami"},
        }
    )
    master_uri = "tcp://{master_ip}:{master_port}".format(
        master_ip="localhost", master_port=opts["master_port"]
    )
    with salt.transport.client.ReqChannel.factory(
        opts, master_uri=master_uri
    ) as channel:
        assert "localhost" in channel.master_uri


