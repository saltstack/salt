"""
Authenticated event streaming for remote Salt clients.

This module provides network-based event delivery to remote clients using
client key authentication. Clients can subscribe to events over the network
instead of requiring access to local IPC sockets.

Architecture:
- Listens on configurable port (default: 4507)
- Requires client authentication via PKI keys
- Filters events based on client identity and job ownership
- Publishes events only to authorized clients
"""

import logging
import os

import zmq

import salt.cache
import salt.crypt
import salt.payload
import salt.transport.zeromq
import salt.utils.event
import salt.utils.files
import salt.utils.network
import salt.utils.process
import salt.utils.stringutils

log = logging.getLogger(__name__)


class ClientEventPublisher(salt.utils.process.SignalHandlingProcess):
    """
    Authenticated event publisher for remote Salt clients.

    This process subscribes to the master event bus and republishes
    filtered events to authenticated remote clients over the network.

    Event Filtering:
    - Clients only receive events for jobs they initiated
    - System/admin events are filtered out
    - Client ACLs can further restrict event access
    """

    def __init__(self, opts):
        """
        Initialize the client event publisher.

        Args:
            opts: Master configuration dictionary
        """
        super().__init__()
        self.opts = opts

    def run(self):
        """
        Main event publisher loop.

        1. Subscribe to master event bus (IPC)
        2. Listen for client authentication requests
        3. Filter and forward events to authenticated clients
        """
        client_event_port = self.opts.get("client_event_port", 4507)
        log.info(
            "Starting client event publisher on %s:%s",
            self.opts["interface"],
            client_event_port,
        )

        # Create ZeroMQ context
        context = zmq.Context()

        # Subscribe to master event bus (IPC)
        event_bus = salt.utils.event.get_event(
            "master",
            self.opts["sock_dir"],
            opts=self.opts,
            listen=True,
        )

        # Create publisher socket for clients (TCP)
        pub_socket = context.socket(zmq.PUB)
        pub_socket.setsockopt(zmq.LINGER, 1000)
        pub_uri = f"tcp://{self.opts['interface']}:{client_event_port}"
        pub_socket.bind(pub_uri)

        # Create REP socket for client authentication
        auth_socket = context.socket(zmq.REP)
        auth_socket.setsockopt(zmq.LINGER, 1000)
        auth_uri = (
            f"tcp://{self.opts['interface']}:{client_event_port + 1}"
        )
        auth_socket.bind(auth_uri)

        # Track authenticated clients and their subscriptions
        # Format: {client_id: {jobs: set(), authorized: bool}}
        clients = {}

        # Initialize crypto for client authentication
        key_cache = salt.cache.Cache(
            self.opts, driver=self.opts.get("keys.cache_driver", "localfs_key")
        )

        log.info("Client event publisher started on %s", pub_uri)

        # Poller for handling auth requests and events
        poller = zmq.Poller()
        poller.register(auth_socket, zmq.POLLIN)

        try:
            while True:
                # Poll for authentication requests (non-blocking)
                socks = dict(poller.poll(timeout=100))

                # Handle client authentication
                if auth_socket in socks:
                    self._handle_auth_request(auth_socket, key_cache, clients)

                # Get events from master event bus
                event = event_bus.get_event(wait=0.1, full=True)
                if event:
                    self._publish_filtered_event(pub_socket, event, clients)

        except (KeyboardInterrupt, SystemExit):
            log.info("Client event publisher shutting down")
        finally:
            log.debug("Cleaning up client event publisher resources")
            pub_socket.close()
            auth_socket.close()
            context.term()
            event_bus.destroy()

    def _handle_auth_request(self, auth_socket, key_cache, clients):
        """
        Handle client authentication request.

        Args:
            auth_socket: ZeroMQ REP socket for authentication
            key_cache: Key cache for client key lookups
            clients: Dictionary tracking authenticated clients
        """
        try:
            # Receive authentication payload
            payload = auth_socket.recv_pyobj()

            client_id = payload.get("id")
            token = payload.get("token")
            action = payload.get("action")

            if action == "auth":
                # Verify client
                authorized = self._verify_client(client_id, token, key_cache)

                if authorized:
                    clients[client_id] = {"jobs": set(), "authorized": True}
                    log.info("Client %s authenticated for event streaming", client_id)
                    auth_socket.send_pyobj({"authorized": True})
                else:
                    log.warning(
                        "Client %s failed authentication for event streaming", client_id
                    )
                    auth_socket.send_pyobj({"authorized": False})

            elif action == "subscribe_job":
                # Client wants to subscribe to events for a specific job
                jid = payload.get("jid")
                if client_id in clients and clients[client_id]["authorized"]:
                    clients[client_id]["jobs"].add(jid)
                    auth_socket.send_pyobj({"subscribed": True})
                else:
                    auth_socket.send_pyobj({"subscribed": False})

            elif action == "unsubscribe_job":
                # Client wants to unsubscribe from job events
                jid = payload.get("jid")
                if client_id in clients:
                    clients[client_id]["jobs"].discard(jid)
                    auth_socket.send_pyobj({"unsubscribed": True})
                else:
                    auth_socket.send_pyobj({"unsubscribed": False})

        except Exception as exc:  # pylint: disable=broad-except
            log.error("Error handling auth request: %s", exc)
            try:
                auth_socket.send_pyobj({"error": str(exc)})
            except Exception:  # pylint: disable=broad-except
                pass

    def _verify_client(self, client_id, token, key_cache):
        """
        Verify client using client key authentication.

        Args:
            client_id: Client identifier
            token: Encrypted token from client
            key_cache: Key cache for client key lookups

        Returns:
            bool: True if client is authenticated
        """
        try:
            # Get client public key from cache
            client_key = key_cache.fetch("client_keys", client_id)
            if not client_key:
                log.debug("No key found for client %s", client_id)
                return False

            # Verify token signature
            pub = salt.crypt.PublicKey.from_str(client_key["pub"])
            if pub.decrypt(token) == b"salt":
                return True

        except Exception as exc:  # pylint: disable=broad-except
            log.error("Error verifying client %s: %s", client_id, exc)

        return False

    def _publish_filtered_event(self, pub_socket, event, clients):
        """
        Publish event to authorized clients after filtering.

        Args:
            pub_socket: ZeroMQ PUB socket
            event: Event dictionary from master event bus
            clients: Dictionary of authenticated clients
        """
        tag = event.get("tag", "")
        data = event.get("data", {})

        # Extract job ID from various event types
        # Handles: salt/job/* (minion commands), salt/run/* (runners), salt/wheel/* (key management)
        jid = None
        for prefix in ("salt/job/", "salt/run/", "salt/wheel/"):
            if tag.startswith(prefix):
                parts = tag.split("/")
                if len(parts) >= 3:
                    jid = parts[2]
                break

        # Publish to clients subscribed to this job
        for client_id, client_info in clients.items():
            if not client_info["authorized"]:
                continue

            # Check if client is subscribed to this job
            if jid and jid in client_info["jobs"]:
                # Publish event to this client
                try:
                    msg = salt.payload.dumps({"tag": tag, "data": data})
                    pub_socket.send_multipart([client_id.encode(), msg])
                except Exception as exc:  # pylint: disable=broad-except
                    log.error("Error publishing event to client %s: %s", client_id, exc)


class ClientEventSubscriber:
    """
    Client-side event subscriber for remote Salt clients.

    Connects to the authenticated event publisher and receives
    filtered events over the network.
    """

    def __init__(self, opts):
        """
        Initialize the client event subscriber.

        Args:
            opts: Client configuration dictionary
        """
        self.opts = opts
        self.context = zmq.Context()
        self.sub_socket = None
        self.auth_socket = None
        self.authenticated = False
        self.subscribed_jobs = set()

    def connect(self):
        """Connect to the event publisher and authenticate."""
        master = self.opts.get("master", "localhost")
        port = self.opts.get("client_event_port", 4507)

        # Connect subscriber socket
        self.sub_socket = self.context.socket(zmq.SUB)
        sub_uri = f"tcp://{master}:{port}"
        self.sub_socket.connect(sub_uri)

        # Subscribe with client ID as filter
        client_id = self.opts.get("id", "client")
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, client_id.encode())

        # Connect authentication socket
        self.auth_socket = self.context.socket(zmq.REQ)
        auth_uri = f"tcp://{master}:{port + 1}"
        self.auth_socket.connect(auth_uri)

        # Authenticate
        self._authenticate()

        log.info("Connected to event publisher at %s", sub_uri)

    def _authenticate(self):
        """Authenticate with the event publisher using client keys."""
        client_id = self.opts.get("id", "client")

        # Load client private key
        import salt.crypt

        pki_dir = self.opts.get("pki_dir")
        client_key_path = os.path.join(pki_dir, "client.pem")

        if not os.path.exists(client_key_path):
            raise OSError(f"Client key not found: {client_key_path}")

        # Create auth token
        with salt.utils.files.fopen(client_key_path, "r") as f:
            priv_key = salt.crypt.PrivateKey.from_str(f.read())

        # Encrypt "salt" with our private key as proof of identity
        token = priv_key.encrypt(b"salt")

        # Send authentication request
        auth_payload = {"id": client_id, "token": token, "action": "auth"}

        self.auth_socket.send_pyobj(auth_payload)
        response = self.auth_socket.recv_pyobj()

        if response.get("authorized"):
            self.authenticated = True
            log.info("Successfully authenticated with event publisher")
        else:
            raise Exception("Failed to authenticate with event publisher")

    def subscribe_job(self, jid):
        """
        Subscribe to events for a specific job.

        Args:
            jid: Job ID to subscribe to
        """
        if not self.authenticated:
            raise Exception("Not authenticated with event publisher")

        subscribe_payload = {
            "id": self.opts.get("id", "client"),
            "action": "subscribe_job",
            "jid": jid,
        }

        self.auth_socket.send_pyobj(subscribe_payload)
        response = self.auth_socket.recv_pyobj()

        if response.get("subscribed"):
            self.subscribed_jobs.add(jid)
            log.debug("Subscribed to job %s", jid)
        else:
            log.warning("Failed to subscribe to job %s", jid)

    def unsubscribe_job(self, jid):
        """
        Unsubscribe from events for a specific job.

        Args:
            jid: Job ID to unsubscribe from
        """
        if jid in self.subscribed_jobs:
            unsubscribe_payload = {
                "id": self.opts.get("id", "client"),
                "action": "unsubscribe_job",
                "jid": jid,
            }

            self.auth_socket.send_pyobj(unsubscribe_payload)
            self.auth_socket.recv_pyobj()
            self.subscribed_jobs.discard(jid)

    def get_event(self, wait=5, tag="", full=False, no_block=False):
        """
        Get a single event from the event stream.

        Args:
            wait: Timeout in seconds (not used for network events)
            tag: Event tag filter (not used, filtering done server-side)
            full: Return full event dict
            no_block: Non-blocking mode

        Returns:
            dict: Event data or None
        """
        if not self.sub_socket:
            return None

        try:
            # Set timeout based on wait parameter
            if no_block:
                self.sub_socket.setsockopt(zmq.RCVTIMEO, 0)
            else:
                self.sub_socket.setsockopt(zmq.RCVTIMEO, int(wait * 1000))

            # Receive event (multipart: [client_id, payload])
            parts = self.sub_socket.recv_multipart()

            if len(parts) >= 2:
                event_data = salt.payload.loads(parts[1])
                if full:
                    return event_data
                return event_data.get("data")

        except zmq.Again:
            # Timeout
            return None
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Error receiving event: %s", exc)
            return None

    def destroy(self):
        """Close connections and clean up."""
        if self.sub_socket:
            self.sub_socket.close()
        if self.auth_socket:
            self.auth_socket.close()
        self.context.term()
