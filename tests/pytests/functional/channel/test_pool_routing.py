"""
Integration test for worker pool routing functionality.

Tests that requests are routed to the correct pool based on command classification.
"""

import ctypes
import logging
import multiprocessing
import time

import pytest
import tornado.gen
import tornado.ioloop
from pytestshellutils.utils.processes import terminate_process

import salt.channel.server
import salt.config
import salt.crypt
import salt.master
import salt.payload
import salt.utils.process
import salt.utils.stringutils

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
]


class PoolReqServer(salt.utils.process.SignalHandlingProcess):
    """
    Test request server with pool routing enabled.
    """

    def __init__(self, config):
        super().__init__()
        self._closing = False
        self.config = config
        self.process_manager = salt.utils.process.ProcessManager(
            name="PoolReqServer-ProcessManager"
        )
        self.io_loop = None
        self.running = multiprocessing.Event()
        self.handled_requests = multiprocessing.Manager().dict()

    def run(self):
        """Run the pool-aware request server."""
        salt.master.SMaster.secrets["aes"] = {
            "secret": multiprocessing.Array(
                ctypes.c_char,
                salt.utils.stringutils.to_bytes(
                    salt.crypt.Crypticle.generate_key_string()
                ),
            ),
            "serial": multiprocessing.Value(ctypes.c_longlong, lock=False),
        }

        self.io_loop = tornado.ioloop.IOLoop()
        self.io_loop.make_current()

        # Set up pool-specific channels
        from salt.config.worker_pools import get_worker_pools_config

        worker_pools = get_worker_pools_config(self.config)

        # Create front-end channel
        from salt.utils.channel import iter_transport_opts

        frontend_channel = None
        for transport, opts in iter_transport_opts(self.config):
            frontend_channel = salt.channel.server.ReqServerChannel.factory(opts)
            frontend_channel.pre_fork(self.process_manager)
            break

        # Create pool-specific channels
        pool_channels = {}
        for pool_name in worker_pools.keys():
            pool_opts = self.config.copy()
            pool_opts["pool_name"] = pool_name

            for transport, opts in iter_transport_opts(pool_opts):
                chan = salt.channel.server.ReqServerChannel.factory(opts)
                chan.pre_fork(self.process_manager)
                pool_channels[pool_name] = chan
                break

        # Create dispatcher
        dispatcher = salt.channel.server.PoolDispatcherChannel(
            self.config, [frontend_channel], pool_channels
        )

        def start_dispatcher():
            """Start the dispatcher in the IO loop."""
            dispatcher.post_fork(self.io_loop)

        # Start dispatcher
        self.io_loop.add_callback(start_dispatcher)

        # Start workers for each pool
        for pool_name, pool_config in worker_pools.items():
            worker_count = pool_config.get("worker_count", 1)
            pool_chan = pool_channels[pool_name]

            for pool_index in range(worker_count):

                def worker_handler(payload, pname=pool_name, pidx=pool_index):
                    """Handler that tracks which pool handled the request."""
                    return self._handle_payload(payload, pname, pidx)

                # Start worker
                pool_chan.post_fork(worker_handler, self.io_loop)

        self.io_loop.add_callback(self.running.set)
        try:
            self.io_loop.start()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self.close()

    @tornado.gen.coroutine
    def _handle_payload(self, payload, pool_name, pool_index):
        """
        Handle a payload and track which pool handled it.

        :param payload: The request payload
        :param pool_name: Name of the pool handling this request
        :param pool_index: Index of the worker in the pool
        """
        try:
            # Extract the command from the payload
            if isinstance(payload, dict) and "load" in payload:
                cmd = payload["load"].get("cmd", "unknown")
            else:
                cmd = "unknown"

            # Track which pool handled this command
            key = f"{cmd}_{time.time()}"
            self.handled_requests[key] = {
                "cmd": cmd,
                "pool": pool_name,
                "pool_index": pool_index,
                "timestamp": time.time(),
            }

            log.info(
                "Pool '%s' worker %d handled command '%s'",
                pool_name,
                pool_index,
                cmd,
            )

            # Return response indicating which pool handled it
            response = {
                "handled_by_pool": pool_name,
                "handled_by_worker": pool_index,
                "original_payload": payload,
            }

            raise tornado.gen.Return((response, {"fun": "send_clear"}))
        except Exception as exc:
            log.error("Error in pool handler: %s", exc, exc_info=True)
            raise tornado.gen.Return(({"error": str(exc)}, {"fun": "send_clear"}))

    def _handle_signals(self, signum, sigframe):
        self.close()
        super()._handle_signals(signum, sigframe)

    def __enter__(self):
        self.start()
        self.running.wait()
        return self

    def __exit__(self, *args):
        self.close()
        self.terminate()

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self.process_manager is not None:
            self.process_manager.terminate()
            for pid in self.process_manager._process_map:
                terminate_process(pid=pid, kill_children=True, slow_stop=False)
            self.process_manager = None


@pytest.fixture
def pool_config(tmp_path):
    """Create a master config with worker pools enabled."""
    sock_dir = tmp_path / "sock"
    pki_dir = tmp_path / "pki"
    cache_dir = tmp_path / "cache"
    sock_dir.mkdir()
    pki_dir.mkdir()
    cache_dir.mkdir()

    return {
        "sock_dir": str(sock_dir),
        "pki_dir": str(pki_dir),
        "cachedir": str(cache_dir),
        "key_pass": "meh",
        "keysize": 2048,
        "cluster_id": None,
        "master_sign_pubkey": False,
        "pub_server_niceness": None,
        "con_cache": False,
        "zmq_monitor": False,
        "request_server_ttl": 60,
        "publish_session": 600,
        "keys.cache_driver": "localfs_key",
        "id": "master",
        "optimization_order": [0, 1, 2],
        "__role": "master",
        "master_sign_key_name": "master_sign",
        "permissive_pki_access": True,
        # Pool configuration
        "worker_pools_enabled": True,
        "worker_pools": {
            "fast": {
                "worker_count": 2,
                "commands": ["test.ping", "test.echo", "runner.test.arg"],
            },
            "general": {
                "worker_count": 3,
                "commands": ["*"],  # Catchall
            },
        },
    }


@pytest.fixture
def pool_req_server(pool_config):
    """Create and start a pool-aware request server."""
    server_process = PoolReqServer(pool_config)
    try:
        with server_process:
            yield server_process
    finally:
        terminate_process(pid=server_process.pid, kill_children=True, slow_stop=False)


def test_pool_routing_fast_commands(pool_req_server, pool_config):
    """
    Test that commands configured for the 'fast' pool are routed there.
    """
    # Create a simple request for a command in the fast pool
    test_commands = ["test.ping", "test.echo"]

    for cmd in test_commands:
        payload = {"load": {"cmd": cmd, "arg": ["test"]}}

        # In a real scenario, we'd send this via a ReqChannel
        # For this test, we'll simulate the routing
        from salt.master import RequestRouter

        router = RequestRouter(pool_config)
        routed_pool = router.route_request(payload)

        assert routed_pool == "fast", f"Command '{cmd}' should route to 'fast' pool"


def test_pool_routing_catchall_commands(pool_req_server, pool_config):
    """
    Test that commands not in any specific pool route to the catchall pool.
    """
    # Create a request for a command NOT in the fast pool
    test_commands = ["state.highstate", "cmd.run", "pkg.install"]

    for cmd in test_commands:
        payload = {"load": {"cmd": cmd, "arg": ["test"]}}

        from salt.master import RequestRouter

        router = RequestRouter(pool_config)
        routed_pool = router.route_request(payload)

        assert (
            routed_pool == "general"
        ), f"Command '{cmd}' should route to 'general' pool (catchall)"


def test_pool_routing_statistics(pool_config):
    """
    Test that the RequestRouter tracks routing statistics.
    """
    from salt.master import RequestRouter

    router = RequestRouter(pool_config)

    # Route some requests (pass dict, not serialized bytes)
    test_data = [
        ({"load": {"cmd": "test.ping"}}, "fast"),
        ({"load": {"cmd": "test.echo"}}, "fast"),
        ({"load": {"cmd": "state.highstate"}}, "general"),
        ({"load": {"cmd": "cmd.run"}}, "general"),
    ]

    for payload, expected_pool in test_data:
        routed_pool = router.route_request(payload)
        assert routed_pool == expected_pool

    # Check statistics (router.stats is a dict of pool_name -> count)
    assert router.stats["fast"] == 2
    assert router.stats["general"] == 2


def test_pool_config_validation(pool_config):
    """
    Test that pool configuration validation works correctly.
    """
    from salt.config.worker_pools import validate_worker_pools_config

    # Valid config should not raise
    validate_worker_pools_config(pool_config)

    # Invalid config: duplicate commands
    invalid_config = pool_config.copy()
    invalid_config["worker_pools"] = {
        "pool1": {"worker_count": 2, "commands": ["test.ping"]},
        "pool2": {
            "worker_count": 2,
            "commands": ["test.ping", "*"],
        },  # Duplicate! (but has catchall)
    }

    with pytest.raises(
        ValueError, match="Command 'test.ping' mapped to multiple pools"
    ):
        validate_worker_pools_config(invalid_config)


def test_pool_disabled_fallback(tmp_path):
    """
    Test that when worker_pools_enabled=False, system uses legacy behavior.
    """
    config = {
        "sock_dir": str(tmp_path / "sock"),
        "pki_dir": str(tmp_path / "pki"),
        "cachedir": str(tmp_path / "cache"),
        "worker_pools_enabled": False,
        "worker_threads": 5,
    }

    from salt.config.worker_pools import get_worker_pools_config

    # When disabled, should return None
    pools = get_worker_pools_config(config)
    assert pools is None or pools == {}
