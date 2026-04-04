"""
Worker pool routing at the channel layer - V2 Revised with RequestServer IPC.

This module provides transport-agnostic worker pool routing using Salt's
existing RequestClient/RequestServer infrastructure over IPC sockets.

V2 Revised Design:
- Each worker pool has its own RequestServer listening on IPC
- Routing channel uses RequestClient to forward messages to pool RequestServers
- No transport modifications needed
- Uses transport-native IPC (ZeroMQ/TCP/WS over IPC sockets)
"""

import logging
import os
import zlib

log = logging.getLogger(__name__)


class PoolRoutingChannelV2Revised:
    """
    Channel wrapper that routes requests to worker pools using RequestServer IPC.

    Architecture:
        External Transport → PoolRoutingChannel → RequestClient →
        Pool RequestServer (IPC) → Workers
    """

    def __init__(self, opts, transport, worker_pools):
        """
        Initialize the pool routing channel.

        Args:
            opts: Master configuration options
            transport: The external transport instance (port 4506)
            worker_pools: Dict of pool configurations {pool_name: config}
        """
        self.opts = opts
        self.transport = transport
        self.worker_pools = worker_pools
        self.pool_clients = {}  # RequestClient for each pool
        self.pool_servers = {}  # RequestServer for each pool

        log.info(
            "PoolRoutingChannelV2Revised initialized with pools: %s",
            list(worker_pools.keys()),
        )

    def pre_fork(self, process_manager):
        """
        Pre-fork setup - create RequestServer for each pool on IPC.

        Args:
            process_manager: The process manager instance
        """
        import salt.transport

        # Delegate external transport setup
        if hasattr(self.transport, "pre_fork"):
            self.transport.pre_fork(process_manager)

        # Create a RequestServer for each pool on IPC
        for pool_name, config in self.worker_pools.items():
            # Create pool-specific opts for IPC
            pool_opts = self.opts.copy()

            # Configure IPC mode and socket path
            if pool_opts.get("ipc_mode") == "tcp":
                # TCP IPC mode: use unique port per pool
                base_port = pool_opts.get("tcp_master_workers", 4515)
                port_offset = zlib.adler32(pool_name.encode()) % 1000
                pool_opts["ret_port"] = base_port + port_offset
                log.info(
                    "Pool '%s' RequestServer using TCP IPC on port %d",
                    pool_name,
                    pool_opts["ret_port"],
                )
            else:
                # Standard IPC mode: use unique socket per pool
                sock_dir = pool_opts.get("sock_dir", "/tmp/salt")
                os.makedirs(sock_dir, exist_ok=True)

                # Each pool gets its own IPC socket
                pool_opts["workers_ipc_name"] = f"workers-{pool_name}.ipc"
                

            # Create RequestServer for this pool using transport factory
            pool_server = salt.transport.request_server(pool_opts)

            # Pre-fork the pool server (this creates IPC listener)
            pool_server.pre_fork(process_manager)

            self.pool_servers[pool_name] = pool_server

        log.info("PoolRoutingChannelV2Revised pre_fork complete")

    def post_fork(self, payload_handler, io_loop):
        """
        Post-fork setup in routing process.

        Creates RequestClient connections to each pool's RequestServer.

        Args:
            payload_handler: Handler for processed payloads (not used)
            io_loop: The event loop to use
        """
        import salt.transport

        self.io_loop = io_loop

        # Build routing table from worker_pools config
        self.command_to_pool = {}
        self.default_pool = None

        for pool_name, config in self.worker_pools.items():
            for cmd in config.get('commands', []):
                if cmd == '*':
                    self.default_pool = pool_name
                else:
                    self.command_to_pool[cmd] = pool_name

        # Create RequestClient for each pool
        for pool_name in self.worker_pools.keys():
            # Create pool-specific opts matching the pool's RequestServer
            pool_opts = self.opts.copy()

            if pool_opts.get("ipc_mode") == "tcp":
                # TCP IPC: connect to pool's port
                base_port = pool_opts.get("tcp_master_workers", 4515)
                port_offset = zlib.adler32(pool_name.encode()) % 1000
                pool_opts["ret_port"] = base_port + port_offset
            else:
                # IPC socket: connect to pool's socket
                pool_opts["workers_ipc_name"] = f"workers-{pool_name}.ipc"
                
                sock_dir = pool_opts.get("sock_dir", "/tmp/salt")

            # Create RequestClient that connects to pool's IPC RequestServer
            client = salt.transport.request_client(pool_opts, io_loop=io_loop)
            self.pool_clients[pool_name] = client

        # Connect external transport to our routing handler
        if hasattr(self.transport, "post_fork"):
            self.transport.post_fork(self.handle_and_route_message, io_loop)

        log.info("PoolRoutingChannelV2Revised post_fork complete")

    def close(self):
        """
        Close the channel and all its pool clients/servers.
        """
        log.info("Closing PoolRoutingChannelV2Revised")

        # Close all pool clients
        for pool_name, client in self.pool_clients.items():
            try:
                client.close()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error closing client for pool '%s': %s", pool_name, exc)
        self.pool_clients.clear()

        # Close all pool servers
        for pool_name, server in self.pool_servers.items():
            try:
                server.close()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error closing server for pool '%s': %s", pool_name, exc)
        self.pool_servers.clear()

        # Close external transport
        if hasattr(self.transport, "close"):
            self.transport.close()

    async def handle_and_route_message(self, payload):
        """
        Handle incoming message and route to appropriate worker pool via RequestClient.

        Args:
            payload: The message payload from external transport

        Returns:
            Reply from the worker that processed the request
        """
        try:
            # Determine which pool
            cmd = payload.get("load", {}).get("cmd", "unknown")
            pool_name = self.command_to_pool.get(cmd, self.default_pool)

            if not pool_name:
                pool_name = self.default_pool or list(self.worker_pools.keys())[0]

            log.debug(
                "Routing request (cmd=%s) to pool '%s'",
                cmd,
                pool_name,
            )

            # Forward to pool via RequestClient
            client = self.pool_clients[pool_name]

            # RequestClient.send() sends payload to pool's RequestServer via IPC
            reply = await client.send(payload)

            return reply

        except Exception as exc:  # pylint: disable=broad-except
            log.error(
                "Error routing request to worker pool: %s",
                exc,
                exc_info=True,
            )
            return {"error": "Internal routing error"}
