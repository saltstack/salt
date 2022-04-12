"""
    :codeauthor: Thomas Jackson <jacksontj.89@gmail.com>
"""

import logging
import socket
import threading

import salt.config
import salt.exceptions
import salt.ext.tornado.concurrent
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.transport.client
import salt.transport.server
import salt.utils.platform
import salt.utils.process
from salt.ext.tornado.testing import AsyncTestCase, gen_test
from salt.transport.tcp import (
    SaltMessageClient,
    SaltMessageClientPool,
    TCPPubServerChannel,
)
from saltfactories.utils.ports import get_unused_localhost_port
from tests.support.helpers import flaky, slowTest
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.mock import MagicMock, create_autospec, patch
from tests.support.unit import TestCase, skipIf
from tests.unit.transport.mixins import (
    PubChannelMixin,
    ReqChannelMixin,
    run_loop_in_thread,
)

log = logging.getLogger(__name__)


class BaseTCPReqCase(TestCase, AdaptedConfigurationTestCaseMixin):
    """
    Test the req server/client pair
    """

    @classmethod
    def setUpClass(cls):
        if not hasattr(cls, "_handle_payload"):
            return
        ret_port = get_unused_localhost_port()
        publish_port = get_unused_localhost_port()
        tcp_master_pub_port = get_unused_localhost_port()
        tcp_master_pull_port = get_unused_localhost_port()
        tcp_master_publish_pull = get_unused_localhost_port()
        tcp_master_workers = get_unused_localhost_port()
        cls.master_config = cls.get_temp_config(
            "master",
            **{
                "transport": "tcp",
                "auto_accept": True,
                "ret_port": ret_port,
                "publish_port": publish_port,
                "tcp_master_pub_port": tcp_master_pub_port,
                "tcp_master_pull_port": tcp_master_pull_port,
                "tcp_master_publish_pull": tcp_master_publish_pull,
                "tcp_master_workers": tcp_master_workers,
            }
        )

        cls.minion_config = cls.get_temp_config(
            "minion",
            **{
                "transport": "tcp",
                "master_ip": "127.0.0.1",
                "master_port": ret_port,
                "master_uri": "tcp://127.0.0.1:{}".format(ret_port),
            }
        )

        cls.process_manager = salt.utils.process.ProcessManager(
            name="ReqServer_ProcessManager"
        )

        cls.server_channel = salt.transport.server.ReqServerChannel.factory(
            cls.master_config
        )
        cls.server_channel.pre_fork(cls.process_manager)
        cls.io_loop = salt.ext.tornado.ioloop.IOLoop()
        cls.stop = threading.Event()
        cls.server_channel.post_fork(cls._handle_payload, io_loop=cls.io_loop)
        cls.server_thread = threading.Thread(
            target=run_loop_in_thread, args=(cls.io_loop, cls.stop,),
        )
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server_channel.close()
        cls.stop.set()
        cls.server_thread.join()
        cls.process_manager.kill_children()
        del cls.server_channel

    @classmethod
    @salt.ext.tornado.gen.coroutine
    def _handle_payload(cls, payload):
        """
        TODO: something besides echo
        """
        raise salt.ext.tornado.gen.Return((payload, {"fun": "send_clear"}))


@skipIf(salt.utils.platform.is_darwin(), "hanging test suite on MacOS")
class ClearReqTestCases(BaseTCPReqCase, ReqChannelMixin):
    """
    Test all of the clear msg stuff
    """

    def setUp(self):
        self.channel = salt.transport.client.ReqChannel.factory(
            self.minion_config, crypt="clear"
        )

    def tearDown(self):
        self.channel.close()
        del self.channel

    @classmethod
    @salt.ext.tornado.gen.coroutine
    def _handle_payload(cls, payload):
        """
        TODO: something besides echo
        """
        raise salt.ext.tornado.gen.Return((payload, {"fun": "send_clear"}))


@skipIf(salt.utils.platform.is_darwin(), "hanging test suite on MacOS")
class AESReqTestCases(BaseTCPReqCase, ReqChannelMixin):
    def setUp(self):
        self.channel = salt.transport.client.ReqChannel.factory(self.minion_config)

    def tearDown(self):
        self.channel.close()
        del self.channel

    @classmethod
    @salt.ext.tornado.gen.coroutine
    def _handle_payload(cls, payload):
        """
        TODO: something besides echo
        """
        raise salt.ext.tornado.gen.Return((payload, {"fun": "send"}))

    # TODO: make failed returns have a specific framing so we can raise the same exception
    # on encrypted channels
    @flaky
    @slowTest
    def test_badload(self):
        """
        Test a variety of bad requests, make sure that we get some sort of error
        """
        msgs = ["", [], tuple()]
        for msg in msgs:
            with self.assertRaises(salt.exceptions.AuthenticationError):
                ret = self.channel.send(msg)


class BaseTCPPubCase(AsyncTestCase, AdaptedConfigurationTestCaseMixin):
    """
    Test the req server/client pair
    """

    @classmethod
    def setUpClass(cls):
        ret_port = get_unused_localhost_port()
        publish_port = get_unused_localhost_port()
        tcp_master_pub_port = get_unused_localhost_port()
        tcp_master_pull_port = get_unused_localhost_port()
        tcp_master_publish_pull = get_unused_localhost_port()
        tcp_master_workers = get_unused_localhost_port()
        cls.master_config = cls.get_temp_config(
            "master",
            **{
                "transport": "tcp",
                "auto_accept": True,
                "ret_port": ret_port,
                "publish_port": publish_port,
                "tcp_master_pub_port": tcp_master_pub_port,
                "tcp_master_pull_port": tcp_master_pull_port,
                "tcp_master_publish_pull": tcp_master_publish_pull,
                "tcp_master_workers": tcp_master_workers,
            }
        )

        cls.minion_config = cls.get_temp_config(
            "minion",
            **{
                "transport": "tcp",
                "master_ip": "127.0.0.1",
                "auth_timeout": 1,
                "master_port": ret_port,
                "master_uri": "tcp://127.0.0.1:{}".format(ret_port),
            }
        )

        cls.process_manager = salt.utils.process.ProcessManager(
            name="ReqServer_ProcessManager"
        )

        cls.server_channel = salt.transport.server.PubServerChannel.factory(
            cls.master_config
        )
        cls.server_channel.pre_fork(cls.process_manager)

        # we also require req server for auth
        cls.req_server_channel = salt.transport.server.ReqServerChannel.factory(
            cls.master_config
        )
        cls.req_server_channel.pre_fork(cls.process_manager)
        cls.io_loop = salt.ext.tornado.ioloop.IOLoop()
        cls.stop = threading.Event()
        cls.req_server_channel.post_fork(cls._handle_payload, io_loop=cls.io_loop)
        cls.server_thread = threading.Thread(
            target=run_loop_in_thread, args=(cls.io_loop, cls.stop,),
        )
        cls.server_thread.start()

    @classmethod
    def _handle_payload(cls, payload):
        """
        TODO: something besides echo
        """
        return payload, {"fun": "send_clear"}

    @classmethod
    def tearDownClass(cls):
        cls.req_server_channel.close()
        cls.server_channel.close()
        cls.stop.set()
        cls.server_thread.join()
        cls.process_manager.kill_children()
        del cls.req_server_channel

    def setUp(self):
        super().setUp()
        self._start_handlers = dict(self.io_loop._handlers)

    def tearDown(self):
        super().tearDown()
        failures = []
        for k, v in self.io_loop._handlers.items():
            if self._start_handlers.get(k) != v:
                failures.append((k, v))
        if failures:
            raise Exception("FDs still attached to the IOLoop: {}".format(failures))
        del self.channel
        del self._start_handlers


class AsyncTCPPubChannelTest(AsyncTestCase, AdaptedConfigurationTestCaseMixin):
    @slowTest
    def test_connect_publish_port(self):
        """
        test when publish_port is not 4506
        """
        opts = self.get_temp_config("master")
        opts["master_uri"] = ""
        opts["master_ip"] = "127.0.0.1"
        opts["publish_port"] = 1234
        channel = salt.transport.tcp.AsyncTCPPubChannel(opts)
        patch_auth = MagicMock(return_value=True)
        patch_client = MagicMock(spec=SaltMessageClientPool)
        with patch("salt.crypt.AsyncAuth.gen_token", patch_auth), patch(
            "salt.crypt.AsyncAuth.authenticated", patch_auth
        ), patch("salt.transport.tcp.SaltMessageClientPool", patch_client):
            channel.connect()
        assert patch_client.call_args[0][0]["publish_port"] == opts["publish_port"]

    def test_when_async_req_channel_with_syndic_role_should_use_syndic_master_pub_file_to_verify_master_sig(
        self,
    ):
        """
        test when publish_port is not 4506
        """

        @salt.ext.tornado.gen.coroutine
        def mocksend(msg, timeout=60, tries=3):
            raise salt.ext.tornado.gen.Return({"pillar": "data", "key": "value"})

        with patch(
            "salt.transport.tcp.PKCS1_OAEP", autospec=True, create=True
        ) as fake_crypto, patch("salt.crypt.AsyncAuth.get_keys", autospec=True):
            expected_pubkey_path = "/etc/salt/pki/minion/syndic_master.pub"
            fake_crypto.new.return_value.decrypt.return_value = "decrypted_return_value"
            mockloop = MagicMock()
            opts = {
                "master_uri": "tcp://127.0.0.1:4506",
                "interface": "127.0.0.1",
                "ret_port": 4506,
                "ipv6": False,
                "sock_dir": ".",
                "pki_dir": "/etc/salt/pki/minion",
                "id": "syndic",
                "__role": "syndic",
                "keysize": 4096,
            }
            client = salt.transport.tcp.AsyncTCPReqChannel(opts, io_loop=mockloop)

            dictkey = "pillar"
            target = "minion"

            # Mock auth and message client.
            client.auth._authenticate_future = MagicMock()
            client.auth._authenticate_future.done.return_value = True
            client.auth._authenticate_future.exception.return_value = None
            client.auth._crypticle = MagicMock()
            client.message_client = create_autospec(client.message_client)

            client.message_client.send = mocksend

            # Note the 'ver' value in 'load' does not represent the the 'version' sent
            # in the top level of the transport's message.
            load = {
                "id": target,
                "grains": {},
                "saltenv": "base",
                "pillarenv": "base",
                "pillar_override": True,
                "extra_minion_data": {},
                "ver": "2",
                "cmd": "_pillar",
            }
            fake_nonce = 42
            with patch("salt.crypt.Crypticle") as fake_crypticle:
                fake_crypticle.generate_key_string.return_value = "fakey fake"
                with patch(
                    "salt.crypt.verify_signature", autospec=True, return_value=True
                ) as fake_verify, patch(
                    "salt.payload.Serial.loads",
                    autospec=True,
                    return_value={
                        "key": "value",
                        "nonce": fake_nonce,
                        "pillar": "data",
                    },
                ), patch(
                    "uuid.uuid4", autospec=True
                ) as fake_uuid:
                    fake_uuid.return_value.hex = fake_nonce
                    ret = client.crypted_transfer_decode_dictentry(
                        load, dictkey="pillar",
                    )

                    assert fake_verify.mock_calls[0].args[0] == expected_pubkey_path


@skipIf(True, "Skip until we can devote time to fix this test")
class AsyncPubChannelTest(BaseTCPPubCase, PubChannelMixin):
    """
    Tests around the publish system
    """


class SaltMessageClientPoolTest(AsyncTestCase):
    def setUp(self):
        super().setUp()
        sock_pool_size = 5
        with patch(
            "salt.transport.tcp.SaltMessageClient.__init__",
            MagicMock(return_value=None),
        ):
            self.message_client_pool = SaltMessageClientPool(
                {"sock_pool_size": sock_pool_size}, args=({}, "", 0)
            )
        self.original_message_clients = self.message_client_pool.message_clients
        self.message_client_pool.message_clients = [
            MagicMock() for _ in range(sock_pool_size)
        ]

    def tearDown(self):
        with patch(
            "salt.transport.tcp.SaltMessageClient.close", MagicMock(return_value=None)
        ):
            del self.original_message_clients
        super().tearDown()

    def test_send(self):
        for message_client_mock in self.message_client_pool.message_clients:
            message_client_mock.send_queue = [0, 0, 0]
            message_client_mock.send.return_value = []
        # pylint: disable=E1120
        self.assertEqual([], self.message_client_pool.send())
        self.message_client_pool.message_clients[2].send_queue = [0]
        self.message_client_pool.message_clients[2].send.return_value = [1]
        self.assertEqual([1], self.message_client_pool.send())
        # pylint: enable=E1120

    def test_write_to_stream(self):
        for message_client_mock in self.message_client_pool.message_clients:
            message_client_mock.send_queue = [0, 0, 0]
            message_client_mock._stream.write.return_value = []
        self.assertEqual([], self.message_client_pool.write_to_stream(""))
        self.message_client_pool.message_clients[2].send_queue = [0]
        self.message_client_pool.message_clients[2]._stream.write.return_value = [1]
        self.assertEqual([1], self.message_client_pool.write_to_stream(""))

    def test_close(self):
        self.message_client_pool.close()
        self.assertEqual([], self.message_client_pool.message_clients)

    def test_on_recv(self):
        for message_client_mock in self.message_client_pool.message_clients:
            message_client_mock.on_recv.return_value = None
        self.message_client_pool.on_recv()
        for message_client_mock in self.message_client_pool.message_clients:
            self.assertTrue(message_client_mock.on_recv.called)

    def test_connect_all(self):
        @gen_test
        def test_connect(self):
            yield self.message_client_pool.connect()

        for message_client_mock in self.message_client_pool.message_clients:
            future = salt.ext.tornado.concurrent.Future()
            future.set_result("foo")
            message_client_mock.connect.return_value = future

        self.assertIsNone(test_connect(self))

    def test_connect_partial(self):
        @gen_test(timeout=0.1)
        def test_connect(self):
            yield self.message_client_pool.connect()

        for idx, message_client_mock in enumerate(
            self.message_client_pool.message_clients
        ):
            future = salt.ext.tornado.concurrent.Future()
            if idx % 2 == 0:
                future.set_result("foo")
            message_client_mock.connect.return_value = future

        with self.assertRaises(salt.ext.tornado.ioloop.TimeoutError):
            test_connect(self)


class SaltMessageClientCleanupTest(TestCase, AdaptedConfigurationTestCaseMixin):
    def setUp(self):
        self.listen_on = "127.0.0.1"
        self.port = get_unused_localhost_port()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.listen_on, self.port))
        self.sock.listen(1)

    def tearDown(self):
        self.sock.close()
        del self.sock

    def test_message_client(self):
        """
        test message client cleanup on close
        """
        orig_loop = salt.ext.tornado.ioloop.IOLoop()
        orig_loop.make_current()
        opts = self.get_temp_config("master")
        client = SaltMessageClient(opts, self.listen_on, self.port)

        # Mock the io_loop's stop method so we know when it has been called.
        orig_loop.real_stop = orig_loop.stop
        orig_loop.stop_called = False

        def stop(*args, **kwargs):
            orig_loop.stop_called = True
            orig_loop.real_stop()

        orig_loop.stop = stop
        try:
            assert client.io_loop == orig_loop
            client.io_loop.run_sync(client.connect)

            # Ensure we are testing the _read_until_future and io_loop teardown
            assert client._stream is not None
            assert client._read_until_future is not None
            assert orig_loop.stop_called is True

            # The run_sync call will set stop_called, reset it
            orig_loop.stop_called = False
            client.close()

            # Stop should be called again, client's io_loop should be None
            assert orig_loop.stop_called is True
            assert client.io_loop is None
        finally:
            orig_loop.stop = orig_loop.real_stop
            del orig_loop.real_stop
            del orig_loop.stop_called


class TCPPubServerChannelTest(TestCase, AdaptedConfigurationTestCaseMixin):
    @patch("salt.master.SMaster.secrets")
    @patch("salt.crypt.Crypticle")
    def test_publish_filtering(self, crypticle, secrets):
        opts = self.get_temp_config("master")
        opts["sign_pub_messages"] = False
        channel = TCPPubServerChannel(opts)

        crypt = MagicMock()
        crypt.dumps.return_value = {"test": "value"}

        secrets.return_value = {"aes": {"secret": None}}
        crypticle.return_value = crypt

        # try simple publish with glob tgt_type
        payload = channel.pack_publish(
            {"test": "value", "tgt_type": "glob", "tgt": "*"}
        )

        # verify we send it without any specific topic
        assert "topic_lst" not in payload

        # try simple publish with list tgt_type
        payload = channel.pack_publish(
            {"test": "value", "tgt_type": "list", "tgt": ["minion01"]}
        )

        # verify we send it with correct topic
        assert "topic_lst" in payload
        self.assertEqual(payload["topic_lst"], ["minion01"])

        # try with syndic settings
        opts["order_masters"] = True
        payload = channel.pack_publish(
            {"test": "value", "tgt_type": "list", "tgt": ["minion01"]}
        )

        # verify we send it without topic for syndics
        assert "topic_lst" not in payload

    @patch("salt.utils.minions.CkMinions.check_minions")
    @patch("salt.master.SMaster.secrets")
    @patch("salt.crypt.Crypticle")
    def test_publish_filtering_str_list(self, crypticle, secrets, check_minions):
        opts = self.get_temp_config("master")
        opts["sign_pub_messages"] = False
        channel = TCPPubServerChannel(opts)

        crypt = MagicMock()
        crypt.dumps.return_value = {"test": "value"}

        secrets.return_value = {"aes": {"secret": None}}
        crypticle.return_value = crypt
        check_minions.return_value = {"minions": ["minion02"]}

        # try simple publish with list tgt_type
        payload = channel.pack_publish(
            {"test": "value", "tgt_type": "list", "tgt": "minion02"}
        )

        # verify we send it with correct topic
        assert "topic_lst" in payload
        self.assertEqual(payload["topic_lst"], ["minion02"])

        # verify it was correctly calling check_minions
        check_minions.assert_called_with("minion02", tgt_type="list")
