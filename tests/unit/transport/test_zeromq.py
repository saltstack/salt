"""
    :codeauthor: Thomas Jackson <jacksontj.89@gmail.com>
"""

import ctypes
import multiprocessing
import os
import threading
import time
from concurrent.futures.thread import ThreadPoolExecutor

import salt.config
import salt.exceptions
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.log.setup
import salt.transport.client
import salt.transport.server
import salt.utils.platform
import salt.utils.process
import zmq.eventloop.ioloop
from salt.ext import six
from salt.ext.six.moves import range
from salt.ext.tornado.testing import AsyncTestCase
from salt.transport.zeromq import AsyncReqMessageClientPool
from saltfactories.utils.ports import get_unused_localhost_port
from tests.support.helpers import flaky, not_runs_on, slowTest
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf
from tests.unit.transport.mixins import (
    PubChannelMixin,
    ReqChannelMixin,
    run_loop_in_thread,
)

x = "fix pre"

# support pyzmq 13.0.x, TODO: remove once we force people to 14.0.x
if not hasattr(zmq.eventloop.ioloop, "ZMQIOLoop"):
    zmq.eventloop.ioloop.ZMQIOLoop = zmq.eventloop.ioloop.IOLoop


class BaseZMQReqCase(TestCase, AdaptedConfigurationTestCaseMixin):
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
                "transport": "zeromq",
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
                "transport": "zeromq",
                "master_ip": "127.0.0.1",
                "master_port": ret_port,
                "auth_timeout": 5,
                "auth_tries": 1,
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
        cls.evt = threading.Event()
        cls.server_channel.post_fork(cls._handle_payload, io_loop=cls.io_loop)
        cls.server_thread = threading.Thread(
            target=run_loop_in_thread, args=(cls.io_loop, cls.evt)
        )
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, "_handle_payload"):
            return
        # Attempting to kill the children hangs the test suite.
        # Let the test suite handle this instead.
        cls.process_manager.stop_restarting()
        cls.process_manager.kill_children()
        cls.evt.set()
        cls.server_thread.join()
        time.sleep(
            2
        )  # Give the procs a chance to fully close before we stop the io_loop
        cls.server_channel.close()
        del cls.server_channel
        del cls.io_loop
        del cls.process_manager
        del cls.server_thread
        del cls.master_config
        del cls.minion_config

    @classmethod
    def _handle_payload(cls, payload):
        """
        TODO: something besides echo
        """
        return payload, {"fun": "send_clear"}


class ClearReqTestCases(BaseZMQReqCase, ReqChannelMixin):
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

    @slowTest
    def test_master_uri_override(self):
        """
        ensure master_uri kwarg is respected
        """
        # minion_config should be 127.0.0.1, we want a different uri that still connects
        uri = "tcp://{master_ip}:{master_port}".format(
            master_ip="localhost", master_port=self.minion_config["master_port"]
        )

        channel = salt.transport.client.ReqChannel.factory(
            self.minion_config, master_uri=uri
        )
        self.assertIn("localhost", channel.master_uri)
        del channel


@flaky
@not_runs_on(
    kernel="linux",
    os_familiy="Suse",
    reason="Skipping until https://github.com/saltstack/salt/issues/32902 gets fixed",
)
class AESReqTestCases(BaseZMQReqCase, ReqChannelMixin):
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
    #
    #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    #
    # WARNING: This test will fail randomly on any system with > 1 CPU core!!!
    #
    #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    @slowTest
    def test_badload(self):
        """
        Test a variety of bad requests, make sure that we get some sort of error
        """
        # TODO: This test should be re-enabled when Jenkins moves to C7.
        # Once the version of salt-testing is increased to something newer than the September
        # release of salt-testing, the @flaky decorator should be applied to this test.
        msgs = ["", [], tuple()]
        for msg in msgs:
            with self.assertRaises(salt.exceptions.AuthenticationError):
                ret = self.channel.send(msg, timeout=5)


class BaseZMQPubCase(AsyncTestCase, AdaptedConfigurationTestCaseMixin):
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
                "transport": "zeromq",
                "auto_accept": True,
                "ret_port": ret_port,
                "publish_port": publish_port,
                "tcp_master_pub_port": tcp_master_pub_port,
                "tcp_master_pull_port": tcp_master_pull_port,
                "tcp_master_publish_pull": tcp_master_publish_pull,
                "tcp_master_workers": tcp_master_workers,
            }
        )

        cls.minion_config = salt.config.minion_config(
            os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "minion")
        )
        cls.minion_config = cls.get_temp_config(
            "minion",
            **{
                "transport": "zeromq",
                "master_ip": "127.0.0.1",
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

        cls._server_io_loop = salt.ext.tornado.ioloop.IOLoop()
        cls.evt = threading.Event()
        cls.req_server_channel.post_fork(
            cls._handle_payload, io_loop=cls._server_io_loop
        )
        cls.server_thread = threading.Thread(
            target=run_loop_in_thread, args=(cls._server_io_loop, cls.evt)
        )
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.process_manager.kill_children()
        cls.process_manager.stop_restarting()
        time.sleep(
            2
        )  # Give the procs a chance to fully close before we stop the io_loop
        cls.evt.set()
        cls.server_thread.join()
        cls.req_server_channel.close()
        cls.server_channel.close()
        cls._server_io_loop.stop()
        del cls.server_channel
        del cls._server_io_loop
        del cls.process_manager
        del cls.server_thread
        del cls.master_config
        del cls.minion_config

    @classmethod
    def _handle_payload(cls, payload):
        """
        TODO: something besides echo
        """
        return payload, {"fun": "send_clear"}

    def setUp(self):
        super().setUp()
        self._start_handlers = dict(self.io_loop._handlers)

    def tearDown(self):
        super().tearDown()
        failures = []
        for k, v in self.io_loop._handlers.items():
            if self._start_handlers.get(k) != v:
                failures.append((k, v))
        del self._start_handlers
        if len(failures) > 0:
            raise Exception("FDs still attached to the IOLoop: {}".format(failures))


@skipIf(True, "Skip until we can devote time to fix this test")
class AsyncPubChannelTest(BaseZMQPubCase, PubChannelMixin):
    """
    Tests around the publish system
    """

    def get_new_ioloop(self):
        return salt.ext.tornado.ioloop.IOLoop()


class AsyncReqMessageClientPoolTest(TestCase):
    def setUp(self):
        super().setUp()
        sock_pool_size = 5
        with patch(
            "salt.transport.zeromq.AsyncReqMessageClient.__init__",
            MagicMock(return_value=None),
        ):
            self.message_client_pool = AsyncReqMessageClientPool(
                {"sock_pool_size": sock_pool_size}, args=({}, "")
            )
        self.original_message_clients = self.message_client_pool.message_clients
        self.message_client_pool.message_clients = [
            MagicMock() for _ in range(sock_pool_size)
        ]

    def tearDown(self):
        del self.original_message_clients
        super().tearDown()

    def test_send(self):
        for message_client_mock in self.message_client_pool.message_clients:
            message_client_mock.send_queue = [0, 0, 0]
            message_client_mock.send.return_value = []

        self.assertEqual([], self.message_client_pool.send())

        self.message_client_pool.message_clients[2].send_queue = [0]
        self.message_client_pool.message_clients[2].send.return_value = [1]
        self.assertEqual([1], self.message_client_pool.send())


class ZMQConfigTest(TestCase):
    def test_master_uri(self):
        """
        test _get_master_uri method
        """

        m_ip = "127.0.0.1"
        m_port = 4505
        s_ip = "111.1.0.1"
        s_port = 4058

        m_ip6 = "1234:5678::9abc"
        s_ip6 = "1234:5678::1:9abc"

        with patch("salt.transport.zeromq.LIBZMQ_VERSION_INFO", (4, 1, 6)), patch(
            "salt.transport.zeromq.ZMQ_VERSION_INFO", (16, 0, 1)
        ):
            # pass in both source_ip and source_port
            assert salt.transport.zeromq._get_master_uri(
                master_ip=m_ip, master_port=m_port, source_ip=s_ip, source_port=s_port
            ) == "tcp://{}:{};{}:{}".format(s_ip, s_port, m_ip, m_port)

            assert salt.transport.zeromq._get_master_uri(
                master_ip=m_ip6, master_port=m_port, source_ip=s_ip6, source_port=s_port
            ) == "tcp://[{}]:{};[{}]:{}".format(s_ip6, s_port, m_ip6, m_port)

            # source ip and source_port empty
            assert salt.transport.zeromq._get_master_uri(
                master_ip=m_ip, master_port=m_port
            ) == "tcp://{}:{}".format(m_ip, m_port)

            assert salt.transport.zeromq._get_master_uri(
                master_ip=m_ip6, master_port=m_port
            ) == "tcp://[{}]:{}".format(m_ip6, m_port)

            # pass in only source_ip
            assert salt.transport.zeromq._get_master_uri(
                master_ip=m_ip, master_port=m_port, source_ip=s_ip
            ) == "tcp://{}:0;{}:{}".format(s_ip, m_ip, m_port)

            assert salt.transport.zeromq._get_master_uri(
                master_ip=m_ip6, master_port=m_port, source_ip=s_ip6
            ) == "tcp://[{}]:0;[{}]:{}".format(s_ip6, m_ip6, m_port)

            # pass in only source_port
            assert salt.transport.zeromq._get_master_uri(
                master_ip=m_ip, master_port=m_port, source_port=s_port
            ) == "tcp://0.0.0.0:{};{}:{}".format(s_port, m_ip, m_port)


class PubServerChannel(TestCase, AdaptedConfigurationTestCaseMixin):
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
                "transport": "zeromq",
                "auto_accept": True,
                "ret_port": ret_port,
                "publish_port": publish_port,
                "tcp_master_pub_port": tcp_master_pub_port,
                "tcp_master_pull_port": tcp_master_pull_port,
                "tcp_master_publish_pull": tcp_master_publish_pull,
                "tcp_master_workers": tcp_master_workers,
                "sign_pub_messages": False,
            }
        )
        salt.master.SMaster.secrets["aes"] = {
            "secret": multiprocessing.Array(
                ctypes.c_char, six.b(salt.crypt.Crypticle.generate_key_string()),
            ),
        }
        cls.minion_config = cls.get_temp_config(
            "minion",
            **{
                "transport": "zeromq",
                "master_ip": "127.0.0.1",
                "master_port": ret_port,
                "auth_timeout": 5,
                "auth_tries": 1,
                "master_uri": "tcp://127.0.0.1:{}".format(ret_port),
            }
        )

    @classmethod
    def tearDownClass(cls):
        del cls.minion_config
        del cls.master_config

    def setUp(self):
        # Start the event loop, even though we don't directly use this with
        # ZeroMQPubServerChannel, having it running seems to increase the
        # likely hood of dropped messages.
        self.io_loop = salt.ext.tornado.ioloop.IOLoop()
        self.io_loop.make_current()
        self.io_loop_thread = threading.Thread(target=self.io_loop.start)
        self.io_loop_thread.start()
        self.process_manager = salt.utils.process.ProcessManager(
            name="PubServer_ProcessManager"
        )

    def tearDown(self):
        self.io_loop.add_callback(self.io_loop.stop)
        self.io_loop_thread.join()
        self.process_manager.stop_restarting()
        self.process_manager.kill_children()
        del self.io_loop
        del self.io_loop_thread
        del self.process_manager

    @staticmethod
    def _gather_results(opts, pub_uri, results, timeout=120, messages=None):
        """
        Gather results until then number of seconds specified by timeout passes
        without reveiving a message
        """
        ctx = zmq.Context()
        sock = ctx.socket(zmq.SUB)
        sock.setsockopt(zmq.LINGER, -1)
        sock.setsockopt(zmq.SUBSCRIBE, b"")
        sock.connect(pub_uri)
        last_msg = time.time()
        serial = salt.payload.Serial(opts)
        crypticle = salt.crypt.Crypticle(
            opts, salt.master.SMaster.secrets["aes"]["secret"].value
        )
        while time.time() - last_msg < timeout:
            try:
                payload = sock.recv(zmq.NOBLOCK)
            except zmq.ZMQError:
                time.sleep(0.01)
            else:
                if messages:
                    if messages != 1:
                        messages -= 1
                        continue
                payload = crypticle.loads(serial.loads(payload)["load"])
                if "stop" in payload:
                    break
                last_msg = time.time()
                results.append(payload["jid"])

    @skipIf(salt.utils.platform.is_windows(), "Skip on Windows OS")
    @slowTest
    def test_publish_to_pubserv_ipc(self):
        """
        Test sending 10K messags to ZeroMQPubServerChannel using IPC transport

        ZMQ's ipc transport not supported on Windows
        """
        opts = dict(self.master_config, ipc_mode="ipc", pub_hwm=0)
        server_channel = salt.transport.zeromq.ZeroMQPubServerChannel(opts)
        server_channel.pre_fork(
            self.process_manager,
            kwargs={"log_queue": salt.log.setup.get_multiprocessing_logging_queue()},
        )
        pub_uri = "tcp://{interface}:{publish_port}".format(**server_channel.opts)
        send_num = 10000
        expect = []
        results = []
        gather = threading.Thread(
            target=self._gather_results, args=(self.minion_config, pub_uri, results,)
        )
        gather.start()
        # Allow time for server channel to start, especially on windows
        time.sleep(2)
        for i in range(send_num):
            expect.append(i)
            load = {"tgt_type": "glob", "tgt": "*", "jid": i}
            server_channel.publish(load)
        server_channel.publish({"tgt_type": "glob", "tgt": "*", "stop": True})
        gather.join()
        server_channel.pub_close()
        assert len(results) == send_num, (len(results), set(expect).difference(results))

    @skipIf(salt.utils.platform.is_linux(), "Skip on Linux")
    @slowTest
    def test_zeromq_publish_port(self):
        """
        test when connecting that we
        use the publish_port set in opts
        when its not 4506
        """
        opts = dict(
            self.master_config,
            ipc_mode="ipc",
            pub_hwm=0,
            recon_randomize=False,
            publish_port=455505,
            recon_default=1,
            recon_max=2,
            master_ip="127.0.0.1",
            acceptance_wait_time=5,
            acceptance_wait_time_max=5,
        )
        opts["master_uri"] = "tcp://{interface}:{publish_port}".format(**opts)

        channel = salt.transport.zeromq.AsyncZeroMQPubChannel(opts)
        patch_socket = MagicMock(return_value=True)
        patch_auth = MagicMock(return_value=True)
        with patch.object(channel, "_socket", patch_socket), patch.object(
            channel, "auth", patch_auth
        ):
            channel.connect()
        assert str(opts["publish_port"]) in patch_socket.mock_calls[0][1][0]

    @skipIf(salt.utils.platform.is_linux(), "Skip on Linux")
    def test_zeromq_zeromq_filtering_decode_message_no_match(self):
        """
        test AsyncZeroMQPubChannel _decode_messages when
        zmq_filtering enabled and minion does not match
        """
        message = [
            b"4f26aeafdb2367620a393c973eddbe8f8b846eb",
            b"\x82\xa3enc\xa3aes\xa4load\xda\x00`\xeeR\xcf"
            b"\x0eaI#V\x17if\xcf\xae\x05\xa7\xb3bN\xf7\xb2\xe2"
            b'\xd0sF\xd1\xd4\xecB\xe8\xaf"/*ml\x80Q3\xdb\xaexg'
            b"\x8e\x8a\x8c\xd3l\x03\\,J\xa7\x01i\xd1:]\xe3\x8d"
            b"\xf4\x03\x88K\x84\n`\xe8\x9a\xad\xad\xc6\x8ea\x15>"
            b"\x92m\x9e\xc7aM\x11?\x18;\xbd\x04c\x07\x85\x99\xa3\xea[\x00D",
        ]

        opts = dict(
            self.master_config,
            ipc_mode="ipc",
            pub_hwm=0,
            zmq_filtering=True,
            recon_randomize=False,
            recon_default=1,
            recon_max=2,
            master_ip="127.0.0.1",
            acceptance_wait_time=5,
            acceptance_wait_time_max=5,
        )
        opts["master_uri"] = "tcp://{interface}:{publish_port}".format(**opts)

        server_channel = salt.transport.zeromq.AsyncZeroMQPubChannel(opts)
        with patch(
            "salt.crypt.AsyncAuth.crypticle",
            MagicMock(return_value={"tgt_type": "glob", "tgt": "*", "jid": 1}),
        ) as mock_test:
            res = server_channel._decode_messages(message)
        assert res.result() is None

    @skipIf(salt.utils.platform.is_linux(), "Skip on Linux")
    def test_zeromq_zeromq_filtering_decode_message(self):
        """
        test AsyncZeroMQPubChannel _decode_messages
        when zmq_filtered enabled
        """
        message = [
            b"4f26aeafdb2367620a393c973eddbe8f8b846ebd",
            b"\x82\xa3enc\xa3aes\xa4load\xda\x00`\xeeR\xcf"
            b"\x0eaI#V\x17if\xcf\xae\x05\xa7\xb3bN\xf7\xb2\xe2"
            b'\xd0sF\xd1\xd4\xecB\xe8\xaf"/*ml\x80Q3\xdb\xaexg'
            b"\x8e\x8a\x8c\xd3l\x03\\,J\xa7\x01i\xd1:]\xe3\x8d"
            b"\xf4\x03\x88K\x84\n`\xe8\x9a\xad\xad\xc6\x8ea\x15>"
            b"\x92m\x9e\xc7aM\x11?\x18;\xbd\x04c\x07\x85\x99\xa3\xea[\x00D",
        ]

        opts = dict(
            self.master_config,
            ipc_mode="ipc",
            pub_hwm=0,
            zmq_filtering=True,
            recon_randomize=False,
            recon_default=1,
            recon_max=2,
            master_ip="127.0.0.1",
            acceptance_wait_time=5,
            acceptance_wait_time_max=5,
        )
        opts["master_uri"] = "tcp://{interface}:{publish_port}".format(**opts)

        server_channel = salt.transport.zeromq.AsyncZeroMQPubChannel(opts)
        with patch(
            "salt.crypt.AsyncAuth.crypticle",
            MagicMock(return_value={"tgt_type": "glob", "tgt": "*", "jid": 1}),
        ) as mock_test:
            res = server_channel._decode_messages(message)

        assert res.result()["enc"] == "aes"

    @skipIf(salt.utils.platform.is_windows(), "Skip on Windows OS")
    @slowTest
    def test_zeromq_filtering(self):
        """
        Test sending messags to publisher using UDP
        with zeromq_filtering enabled
        """
        opts = dict(
            self.master_config,
            ipc_mode="ipc",
            pub_hwm=0,
            zmq_filtering=True,
            acceptance_wait_time=5,
        )
        server_channel = salt.transport.zeromq.ZeroMQPubServerChannel(opts)
        server_channel.pre_fork(
            self.process_manager,
            kwargs={"log_queue": salt.log.setup.get_multiprocessing_logging_queue()},
        )
        pub_uri = "tcp://{interface}:{publish_port}".format(**server_channel.opts)
        send_num = 1
        expect = []
        results = []
        gather = threading.Thread(
            target=self._gather_results,
            args=(self.minion_config, pub_uri, results,),
            kwargs={"messages": 2},
        )
        gather.start()
        # Allow time for server channel to start, especially on windows
        time.sleep(2)
        expect.append(send_num)
        load = {"tgt_type": "glob", "tgt": "*", "jid": send_num}
        with patch(
            "salt.utils.minions.CkMinions.check_minions",
            MagicMock(
                return_value={
                    "minions": ["minion"],
                    "missing": [],
                    "ssh_minions": False,
                }
            ),
        ):
            server_channel.publish(load)
        server_channel.publish({"tgt_type": "glob", "tgt": "*", "stop": True})
        gather.join()
        server_channel.pub_close()
        assert len(results) == send_num, (len(results), set(expect).difference(results))

    @slowTest
    def test_publish_to_pubserv_tcp(self):
        """
        Test sending 10K messags to ZeroMQPubServerChannel using TCP transport
        """
        opts = dict(self.master_config, ipc_mode="tcp", pub_hwm=0)
        server_channel = salt.transport.zeromq.ZeroMQPubServerChannel(opts)
        server_channel.pre_fork(
            self.process_manager,
            kwargs={"log_queue": salt.log.setup.get_multiprocessing_logging_queue()},
        )
        pub_uri = "tcp://{interface}:{publish_port}".format(**server_channel.opts)
        send_num = 10000
        expect = []
        results = []
        gather = threading.Thread(
            target=self._gather_results, args=(self.minion_config, pub_uri, results,)
        )
        gather.start()
        # Allow time for server channel to start, especially on windows
        time.sleep(2)
        for i in range(send_num):
            expect.append(i)
            load = {"tgt_type": "glob", "tgt": "*", "jid": i}
            server_channel.publish(load)
        gather.join()
        server_channel.pub_close()
        assert len(results) == send_num, (len(results), set(expect).difference(results))

    @staticmethod
    def _send_small(opts, sid, num=10):
        server_channel = salt.transport.zeromq.ZeroMQPubServerChannel(opts)
        for i in range(num):
            load = {"tgt_type": "glob", "tgt": "*", "jid": "{}-{}".format(sid, i)}
            server_channel.publish(load)
        server_channel.pub_close()

    @staticmethod
    def _send_large(opts, sid, num=10, size=250000 * 3):
        server_channel = salt.transport.zeromq.ZeroMQPubServerChannel(opts)
        for i in range(num):
            load = {
                "tgt_type": "glob",
                "tgt": "*",
                "jid": "{}-{}".format(sid, i),
                "xdata": "0" * size,
            }
            server_channel.publish(load)
        server_channel.pub_close()

    @skipIf(salt.utils.platform.is_freebsd(), "Skip on FreeBSD")
    @slowTest
    def test_issue_36469_tcp(self):
        """
        Test sending both large and small messags to publisher using TCP

        https://github.com/saltstack/salt/issues/36469
        """
        opts = dict(self.master_config, ipc_mode="tcp", pub_hwm=0)
        server_channel = salt.transport.zeromq.ZeroMQPubServerChannel(opts)
        server_channel.pre_fork(
            self.process_manager,
            kwargs={"log_queue": salt.log.setup.get_multiprocessing_logging_queue()},
        )
        send_num = 10 * 4
        expect = []
        results = []
        pub_uri = "tcp://{interface}:{publish_port}".format(**opts)
        # Allow time for server channel to start, especially on windows
        time.sleep(2)
        gather = threading.Thread(
            target=self._gather_results, args=(self.minion_config, pub_uri, results,)
        )
        gather.start()
        with ThreadPoolExecutor(max_workers=4) as executor:
            executor.submit(self._send_small, opts, 1)
            executor.submit(self._send_small, opts, 2)
            executor.submit(self._send_small, opts, 3)
            executor.submit(self._send_large, opts, 4)
        expect = ["{}-{}".format(a, b) for a in range(10) for b in (1, 2, 3, 4)]
        time.sleep(0.1)
        server_channel.publish({"tgt_type": "glob", "tgt": "*", "stop": True})
        gather.join()
        server_channel.pub_close()
        assert len(results) == send_num, (len(results), set(expect).difference(results))


class AsyncZeroMQReqChannelTests(TestCase):
    def test_force_close_all_instances(self):
        zmq1 = MagicMock()
        zmq2 = MagicMock()
        zmq3 = MagicMock()
        zmq_objects = {"zmq": {"1": zmq1, "2": zmq2}, "other_zmq": {"3": zmq3}}

        with patch(
            "salt.transport.zeromq.AsyncZeroMQReqChannel.instance_map", zmq_objects
        ):
            salt.transport.zeromq.AsyncZeroMQReqChannel.force_close_all_instances()

            self.assertEqual(zmq1.mock_calls, [call.close()])
            self.assertEqual(zmq2.mock_calls, [call.close()])
            self.assertEqual(zmq3.mock_calls, [call.close()])

            # check if instance map changed
            self.assertIs(
                zmq_objects, salt.transport.zeromq.AsyncZeroMQReqChannel.instance_map
            )
