"""
    :codeauthor: Thomas Jackson <jacksontj.89@gmail.com>
"""

import logging
import threading

import pytest
from pytestshellutils.utils import ports

import salt.channel.client
import salt.channel.server
import salt.config
import salt.exceptions
import salt.ext.tornado.concurrent
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.utils.platform
import salt.utils.process
from salt.ext.tornado.testing import AsyncTestCase
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.unit.transport.mixins import run_loop_in_thread

pytestmark = [
    pytest.mark.skip_on_darwin,
    pytest.mark.skip_on_freebsd,
]

log = logging.getLogger(__name__)


@pytest.mark.skip(reason="Skip until we can devote time to fix this test")
class AsyncPubServerTest(AsyncTestCase, AdaptedConfigurationTestCaseMixin):
    """
    Tests around the publish system
    """

    @classmethod
    def setUpClass(cls):
        ret_port = ports.get_unused_localhost_port()
        publish_port = ports.get_unused_localhost_port()
        tcp_master_pub_port = ports.get_unused_localhost_port()
        tcp_master_pull_port = ports.get_unused_localhost_port()
        tcp_master_publish_pull = ports.get_unused_localhost_port()
        tcp_master_workers = ports.get_unused_localhost_port()
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
            },
        )

        cls.minion_config = cls.get_temp_config(
            "minion",
            **{
                "transport": "tcp",
                "master_ip": "127.0.0.1",
                "auth_timeout": 1,
                "master_port": ret_port,
                "master_uri": f"tcp://127.0.0.1:{ret_port}",
            },
        )

        cls.process_manager = salt.utils.process.ProcessManager(
            name="ReqServer_ProcessManager"
        )

        cls.server_channel = salt.channel.server.PubServerChannel.factory(
            cls.master_config
        )
        cls.server_channel.pre_fork(cls.process_manager)

        # we also require req server for auth
        cls.req_server_channel = salt.channel.server.ReqServerChannel.factory(
            cls.master_config
        )
        cls.req_server_channel.pre_fork(cls.process_manager)
        cls.io_loop = salt.ext.tornado.ioloop.IOLoop()
        cls.stop = threading.Event()
        cls.req_server_channel.post_fork(cls._handle_payload, io_loop=cls.io_loop)
        cls.server_thread = threading.Thread(
            target=run_loop_in_thread,
            args=(
                cls.io_loop,
                cls.stop,
            ),
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
        cls.process_manager.terminate()
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
            raise Exception(f"FDs still attached to the IOLoop: {failures}")
        del self.channel
        del self._start_handlers

    def test_basic(self):
        self.pub = None

        def handle_pub(ret):
            self.pub = ret
            self.stop()  # pylint: disable=not-callable

        self.pub_channel = salt.channel.client.AsyncPubChannel.factory(
            self.minion_opts, io_loop=self.io_loop
        )
        connect_future = self.pub_channel.connect()
        connect_future.add_done_callback(
            lambda f: self.stop()  # pylint: disable=not-callable
        )
        self.wait()
        connect_future.result()
        self.pub_channel.on_recv(handle_pub)
        load = {
            "fun": "f",
            "arg": "a",
            "tgt": "t",
            "jid": "j",
            "ret": "r",
            "tgt_type": "glob",
        }
        self.server_channel.publish(load)
        self.wait()
        self.assertEqual(self.pub["load"], load)
        self.pub_channel.on_recv(None)
        self.server_channel.publish(load)
        with self.assertRaises(self.failureException):
            self.wait(timeout=0.5)

        # close our pub_channel, to pass our FD checks
        self.pub_channel.close()
        del self.pub_channel
