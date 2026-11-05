"""
Authenticated event streaming for remote Salt clients.

This module provides network-based event delivery to remote clients using
client key authentication. Clients can subscribe to events over the network
instead of requiring access to local IPC sockets.

Architecture:
- Listens on configurable port (default: 4507)
- Requires client authentication via either:
    - a client PKI key signature (``action="auth"``), or
    - a Salt eauth token (``action="auth_token"``), validated against the
      master's standard tokens cache via :class:`salt.auth.LoadAuth`.
- Filters events based on client identity and job ownership
- Publishes events only to authorized clients
- Event payloads are encrypted with a per-session :class:`salt.crypt.Crypticle`
  key.  For PKI auth, the server mints a random key and wraps it with the
  client's RSA public key during the auth REP exchange.  For token auth,
  both sides derive the key from the Salt token via HKDF-SHA256 (so the
  token itself never travels on the REP channel outside the request).
"""

import base64
import logging
import os
import re
import secrets

import zmq
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

import salt.auth
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

# HKDF context tag -- bump the version suffix if the key schedule changes
# incompatibly so an old client doesn't silently misdecode new events.
_EVENTS_HKDF_INFO = b"salt-client-events-v1"
# Crypticle default key size: 192-bit AES key + 32-byte HMAC key = 56 bytes.
_EVENTS_KEY_BYTES = 24 + 32


def _derive_events_key(secret):
    """
    Derive a :class:`salt.crypt.Crypticle` ``key_string`` from a shared
    secret via HKDF-SHA256.  Used by the token-auth path where both the
    publisher and the client already share the Salt token and don't need
    to transport a separate events key.
    """
    if isinstance(secret, str):
        secret = secret.encode()
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=_EVENTS_KEY_BYTES,
        salt=None,
        info=_EVENTS_HKDF_INFO,
    ).derive(secret)
    return base64.b64encode(derived).decode("utf-8")


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

    def __init__(self, opts, **kwargs):
        """
        Initialize the client event publisher.

        Args:
            opts: Master configuration dictionary
            **kwargs: Forwarded to ``SignalHandlingProcess`` (e.g. ``name``
                passed by ``process_manager.add_process``).
        """
        super().__init__(**kwargs)
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
        auth_uri = f"tcp://{self.opts['interface']}:{client_event_port + 1}"
        auth_socket.bind(auth_uri)

        # Track authenticated clients and their subscriptions.
        # Entries from PKI-auth are keyed by the client_id string; entries
        # from token-auth are keyed by a per-session synthetic id so that
        # concurrent sessions for the same eauth user don't collide and
        # token values never land on the wire as a SUB prefix.
        # Format:
        #   {subscriber_id: {
        #        "jobs": set(),
        #        "authorized": bool,
        #        "auth_mode": "pki" | "token",
        #        "auth_list": list,       # populated only in token mode
        #        "expire": float | None,  # populated only in token mode
        #    }}
        clients = {}

        # Initialize crypto for client authentication (PKI path)
        key_cache = salt.cache.Cache(
            self.opts, driver=self.opts.get("keys.cache_driver", "localfs_key")
        )
        # LoadAuth for the token-auth path.  Shares the master's tokens
        # cache dir because this publisher is a child of the master
        # process and inherits opts["token_dir"] / cachedir.
        loadauth = salt.auth.LoadAuth(self.opts)

        log.info("Client event publisher started on %s", pub_uri)

        # Poller for handling auth requests and events
        poller = zmq.Poller()
        poller.register(auth_socket, zmq.POLLIN)

        # Short rolling buffer of recent events so a client that calls
        # ``subscribe_job`` right after dispatching a fast runner / wheel
        # job can still catch the ``/new`` and ``/ret`` events that fired
        # in the few hundred ms between dispatch and subscribe.  Keyed on
        # (timestamp, event).  Hard-capped so a burst of events on the
        # master's bus can't balloon memory even if the TTL loop lags.
        import collections
        import time

        recent_maxlen = int(self.opts.get("client_event_replay_maxlen", 1024))
        recent_events = collections.deque(maxlen=recent_maxlen)
        recent_ttl = self.opts.get("client_event_replay_ttl", 5.0)
        # Cadence (seconds) for sweeping expired token-auth sessions
        # from ``clients`` so the sweep still runs on an idle master
        # instead of only when a new event triggers the publish path.
        session_sweep_interval = 1.0
        last_session_sweep = time.time()

        try:
            while True:
                # Poll for authentication requests (non-blocking)
                socks = dict(poller.poll(timeout=100))

                # Handle client authentication
                if auth_socket in socks:
                    self._handle_auth_request(
                        auth_socket,
                        key_cache,
                        loadauth,
                        clients,
                        pub_socket=pub_socket,
                        recent_events=recent_events,
                    )

                # Periodic eviction of expired token sessions.  Running
                # here (rather than only inside ``_publish_filtered_event``)
                # means a quiet master still reclaims memory for sessions
                # whose Salt tokens have expired.
                now_wall = time.time()
                if now_wall - last_session_sweep >= session_sweep_interval:
                    self._evict_expired_sessions(clients, now_wall)
                    last_session_sweep = now_wall

                # Get events from master event bus
                event = event_bus.get_event(wait=0.1, full=True)
                if event:
                    # Buffer first (so late subscribers can replay), then
                    # forward to currently-subscribed clients.
                    now = time.time()
                    recent_events.append((now, event))
                    cutoff = now - recent_ttl
                    while recent_events and recent_events[0][0] < cutoff:
                        recent_events.popleft()
                    self._publish_filtered_event(pub_socket, event, clients, loadauth)

        except (KeyboardInterrupt, SystemExit):
            log.info("Client event publisher shutting down")
        finally:
            log.debug("Cleaning up client event publisher resources")
            pub_socket.close(linger=0)
            auth_socket.close(linger=0)
            context.destroy(linger=0)
            event_bus.destroy()

    def _handle_auth_request(
        self,
        auth_socket,
        key_cache,
        loadauth,
        clients,
        pub_socket=None,
        recent_events=None,
    ):
        """
        Handle client authentication request.

        Args:
            auth_socket: ZeroMQ REP socket for authentication
            key_cache: Key cache for client key lookups (PKI path)
            loadauth: LoadAuth for Salt token validation (token path)
            clients: Dictionary tracking authenticated clients
        """
        try:
            # Receive authentication payload
            payload = salt.payload.loads(auth_socket.recv())

            action = payload.get("action")

            # Server-side cap on concurrent subscriber sessions.  Only
            # applies to new ``auth`` / ``auth_token`` requests; existing
            # subscribe/unsubscribe actions on already-authenticated
            # entries don't grow the dict.  Rejecting here prevents a
            # token-auth attacker (who can mint fresh ``session_id``s per
            # connection) from exhausting server memory.
            max_sessions = int(self.opts.get("client_event_max_sessions", 1024))
            if action in ("auth", "auth_token") and len(clients) >= max_sessions:
                log.warning(
                    "Rejecting %s auth: event-stream session cap (%s) reached",
                    action,
                    max_sessions,
                )
                auth_socket.send(
                    salt.payload.dumps(
                        {
                            "authorized": False,
                            "reason": "server session cap reached",
                        }
                    )
                )
                return

            if action == "auth":
                client_id = payload.get("id")
                token = payload.get("token")
                # PKI client key authentication: subscriber_id == client_id.
                authorized = self._verify_client(client_id, token, key_cache)
                if authorized:
                    # Mint a fresh Crypticle key for this subscriber session
                    # and wrap it with the client's RSA public key so it
                    # can be delivered over the auth REP channel in
                    # confidentiality.  The client unwraps with its
                    # ``client.pem``.
                    key_string = salt.crypt.Crypticle.generate_key_string()
                    crypticle = salt.crypt.Crypticle(self.opts, key_string)
                    enc_algo = payload.get(
                        "enc_algo", getattr(salt.crypt, "OAEP_SHA1", "OAEP-SHA1")
                    )
                    client_key = key_cache.fetch("client_keys", client_id)
                    client_pub = salt.crypt.PublicKey.from_str(client_key["pub"])
                    wrapped = client_pub.encrypt(key_string.encode(), enc_algo)
                    clients[client_id] = {
                        "jobs": set(),
                        "authorized": True,
                        "auth_mode": "pki",
                        "auth_list": None,
                        "expire": None,
                        "crypticle": crypticle,
                    }
                    log.info("Client %s authenticated for event streaming", client_id)
                    auth_socket.send(
                        salt.payload.dumps({"authorized": True, "events_key": wrapped})
                    )
                else:
                    log.warning(
                        "Client %s failed authentication for event streaming",
                        client_id,
                    )
                    auth_socket.send(salt.payload.dumps({"authorized": False}))

            elif action == "auth_token":
                # Eauth token authentication.  Validate via LoadAuth
                # against the master's tokens cache; mint a session id so
                # the token itself never travels on the SUB prefix.
                salt_token = payload.get("token")
                eauth = payload.get("eauth")
                token_check = loadauth.check_authentication(
                    {"token": salt_token, "eauth": eauth}, "token"
                )
                if token_check.get("error"):
                    log.warning(
                        "Event-stream token auth failed: %s",
                        token_check["error"].get("message", "unknown"),
                    )
                    auth_socket.send(salt.payload.dumps({"authorized": False}))
                    return
                session_id = secrets.token_urlsafe(16)
                tok_data = loadauth.get_tok(salt_token) or {}
                # Derive the per-session Crypticle key from the Salt
                # token.  Both the publisher and the client already share
                # the token (the client just presented it on this very
                # request), so HKDF-SHA256 lets us produce an identical
                # key on both ends without transporting it over the REP
                # channel.  The ``_EVENTS_HKDF_INFO`` tag binds the key
                # to this specific protocol version.
                key_string = _derive_events_key(salt_token)
                crypticle = salt.crypt.Crypticle(self.opts, key_string)
                clients[session_id] = {
                    "jobs": set(),
                    "authorized": True,
                    "auth_mode": "token",
                    "auth_list": token_check.get("auth_list") or [],
                    "username": token_check.get("username"),
                    "expire": tok_data.get("expire"),
                    "crypticle": crypticle,
                }
                log.info(
                    "Eauth user %s authenticated for event streaming (session %s)",
                    token_check.get("username"),
                    session_id,
                )
                auth_socket.send(
                    salt.payload.dumps({"authorized": True, "session_id": session_id})
                )

            elif action == "subscribe_job":
                # Client wants to subscribe to events for a specific job.
                # Caller passes ``id`` (= client_id for PKI, = session_id
                # for token auth) alongside the jid.
                subscriber_id = payload.get("id")
                jid = payload.get("jid")
                if subscriber_id in clients and clients[subscriber_id]["authorized"]:
                    clients[subscriber_id]["jobs"].add(jid)
                    auth_socket.send(salt.payload.dumps({"subscribed": True}))
                    # Replay recent events for this jid so a late
                    # subscriber (dispatched a fast job then subscribed)
                    # doesn't miss ``/new`` or ``/ret``.  Scoped to just
                    # the subscribing client via a single-entry dict.
                    if pub_socket is not None and recent_events:
                        just_this = {subscriber_id: clients[subscriber_id]}
                        for _ts, buffered in list(recent_events):
                            btag = buffered.get("tag", "")
                            if jid and jid in btag:
                                self._publish_filtered_event(
                                    pub_socket, buffered, just_this, loadauth
                                )
                else:
                    auth_socket.send(salt.payload.dumps({"subscribed": False}))

            elif action == "unsubscribe_job":
                subscriber_id = payload.get("id")
                jid = payload.get("jid")
                if subscriber_id in clients:
                    clients[subscriber_id]["jobs"].discard(jid)
                    auth_socket.send(salt.payload.dumps({"unsubscribed": True}))
                else:
                    auth_socket.send(salt.payload.dumps({"unsubscribed": False}))

        except Exception as exc:  # pylint: disable=broad-except
            log.error("Error handling auth request: %s", exc)
            try:
                auth_socket.send(salt.payload.dumps({"error": str(exc)}))
            except Exception:  # pylint: disable=broad-except
                pass

    def _evict_expired_sessions(self, clients, now):
        """
        Drop token-auth sessions whose ``expire`` timestamp has passed.

        Called periodically from the publisher main loop so that an idle
        master still reclaims memory held by stale sessions, rather than
        waiting for the next event to drive eviction in
        ``_publish_filtered_event``.
        """
        expired = [
            sid
            for sid, info in clients.items()
            if info.get("expire") is not None and info["expire"] < now
        ]
        for sid in expired:
            clients.pop(sid, None)
            log.info("Evicted expired token session %s", sid)

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
        if not client_id:
            log.warning("Event-stream PKI auth: missing client_id in payload")
            return False
        if not token:
            log.warning(
                "Event-stream PKI auth for %s: missing token in payload",
                client_id,
            )
            return False
        try:
            # Get client public key from cache
            client_key = key_cache.fetch("client_keys", client_id)
        except Exception as exc:  # pylint: disable=broad-except
            log.error(
                "Event-stream PKI auth for %s: client_keys cache lookup "
                "raised %s: %s (expected pubkey in pki_dir/clients/)",
                client_id,
                type(exc).__name__,
                exc,
            )
            return False
        if not client_key:
            log.warning(
                "Event-stream PKI auth for %s: no entry in client_keys "
                "cache (expected a 'state: accepted' record stored via "
                "salt.key.ClientKey.cache.store).",
                client_id,
            )
            return False
        if client_key.get("state") != "accepted":
            log.warning(
                "Event-stream PKI auth for %s: client_keys entry is in "
                "state %r, not 'accepted'; master operator must accept "
                "the key first.",
                client_id,
                client_key.get("state"),
            )
            return False
        try:
            pub = salt.crypt.PublicKey.from_str(client_key["pub"])
        except Exception as exc:  # pylint: disable=broad-except
            log.error(
                "Event-stream PKI auth for %s: could not load stored "
                "pubkey as RSA PEM: %s: %s",
                client_id,
                type(exc).__name__,
                exc,
            )
            return False
        try:
            decrypted = pub.decrypt(token)
        except Exception as exc:  # pylint: disable=broad-except
            log.warning(
                "Event-stream PKI auth for %s: X9.31 signature verify "
                "failed (%s: %s).  Common causes: client sent a token "
                "signed with a different private key than the one "
                "accepted on the master; token bytes corrupted on the "
                "wire.",
                client_id,
                type(exc).__name__,
                exc,
            )
            return False
        if decrypted != b"salt":
            log.warning(
                "Event-stream PKI auth for %s: signature verified but "
                "payload was %r, expected b'salt' -- the client sent a "
                "signature of the wrong challenge string.",
                client_id,
                decrypted[:32],
            )
            return False
        return True

    def _publish_filtered_event(self, pub_socket, event, clients, loadauth=None):
        """
        Publish event to authorized clients after filtering.

        Args:
            pub_socket: ZeroMQ PUB socket
            event: Event dictionary from master event bus
            clients: Dictionary of authenticated clients
            loadauth: Optional :class:`salt.auth.LoadAuth` for the extra
                ``auth_check`` on token-mode sessions.  When omitted, the
                auth_list filter is skipped (PKI-only deployments).
        """
        import time

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

        # Publish to subscribers whose job filter matches.  Token-auth
        # sessions also pass through an auth_list check so the eauth
        # user's authorization applies to the stream.
        now = time.time()
        expired = []
        for subscriber_id, info in clients.items():
            if not info["authorized"]:
                continue

            # Evict expired token sessions lazily.
            expire = info.get("expire")
            if expire is not None and expire < now:
                expired.append(subscriber_id)
                continue

            # Must be subscribed to this specific job.
            if not (jid and jid in info["jobs"]):
                continue

            # Extra auth_list gate for token-auth sessions: the eauth user
            # must be authorized for the event's function.  Branch on the
            # event tag -- publish events use the minion matcher
            # (auth_check), runner/wheel events use the per-form matchers
            # (runner_check / wheel_check) which don't need tgt/tgt_type.
            # Fall through to deliver if the event does not carry enough
            # context for a check (e.g. non-job /ret events).
            if info.get("auth_mode") == "token" and loadauth is not None:
                auth_list = info.get("auth_list") or []
                if auth_list and isinstance(data, dict):
                    fun = data.get("fun")
                    if fun:
                        if tag.startswith("salt/run/"):
                            # Event data decorates the function name with
                            # the form prefix (``runner.<fun>``), but
                            # ckminions.runner_check / spec_check expects
                            # a plain ``mod.func`` -- strip the prefix.
                            check_fun = (
                                fun[len("runner.") :]
                                if fun.startswith("runner.")
                                else fun
                            )
                            allowed = loadauth.ckminions.runner_check(
                                auth_list, check_fun, data.get("arg") or []
                            )
                        elif tag.startswith("salt/wheel/"):
                            check_fun = (
                                fun[len("wheel.") :]
                                if fun.startswith("wheel.")
                                else fun
                            )
                            allowed = loadauth.ckminions.wheel_check(
                                auth_list, check_fun, data.get("arg") or []
                            )
                        else:
                            tgt = data.get("tgt", "")
                            tgt_type = data.get("tgt_type", "glob")
                            allowed = loadauth.ckminions.auth_check(
                                auth_list, fun, data.get("arg") or [], tgt, tgt_type
                            )
                        if isinstance(allowed, dict) or not allowed:
                            # Deny this event for this subscriber.
                            continue

            try:
                # Each subscriber has its own Crypticle (keyed off the
                # auth exchange), so one event delivered to N
                # subscribers is N independent AES-CBC+HMAC encryptions.
                # Both auth paths populate ``crypticle``; a missing one
                # here means a bug in auth setup, not a legacy client.
                # Fail loud rather than falling back to cleartext.
                crypticle = info["crypticle"]
                msg = crypticle.dumps({"tag": tag, "data": data})
                pub_socket.send_multipart([subscriber_id.encode(), msg])
            except Exception as exc:  # pylint: disable=broad-except
                log.error(
                    "Error publishing event to subscriber %s: %s", subscriber_id, exc
                )

        for sid in expired:
            clients.pop(sid, None)
            log.info("Evicted expired token session %s", sid)


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
        # Populated by token-auth path.  When set, the subscriber uses
        # this as its SUB filter prefix (not the opts["id"] client_id).
        self.session_id = None
        # Per-session :class:`salt.crypt.Crypticle` for decrypting
        # events on the SUB socket.  Populated during authentication:
        # the PKI path unwraps a server-minted key from the auth REP
        # response; the token path derives the same key both sides from
        # the Salt token.
        self.crypticle = None

    def connect(self, salt_token=None, eauth=None):
        """
        Connect to the event publisher and authenticate.

        Args:
            salt_token: Optional Salt eauth token.  When provided, the
                subscriber authenticates via the publisher's token-auth
                path (``action="auth_token"``) and uses the returned
                session_id as its SUB filter.  Without a token, the
                subscriber falls back to the PKI client-key signature
                path (``action="auth"``).
            eauth: Optional eauth driver name, carried alongside the
                token for logging on the server side.
        """
        master = self.opts.get("master", "localhost")
        port = self.opts.get("client_event_port", 4507)

        # Connect subscriber socket (filter set after auth)
        self.sub_socket = self.context.socket(zmq.SUB)
        sub_uri = f"tcp://{master}:{port}"
        self.sub_socket.connect(sub_uri)

        # Connect authentication socket
        self.auth_socket = self.context.socket(zmq.REQ)
        auth_uri = f"tcp://{master}:{port + 1}"
        self.auth_socket.connect(auth_uri)

        if salt_token:
            self._authenticate_token(salt_token, eauth)
            # Token path: subscribe on the session_id prefix.
            if self.session_id:
                self.sub_socket.setsockopt(zmq.SUBSCRIBE, self.session_id.encode())
        else:
            # PKI path: subscribe on the client's own ID.
            self._authenticate()
            client_id = self.opts.get("id", "client")
            self.sub_socket.setsockopt(zmq.SUBSCRIBE, client_id.encode())

        log.info("Connected to event publisher at %s", sub_uri)

    def _authenticate(self):
        """Authenticate with the event publisher using client keys."""
        client_id = self.opts.get("id", "client")

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
        auth_payload = {
            "id": client_id,
            "token": token,
            "action": "auth",
            "enc_algo": self.opts.get("encryption_algorithm", "OAEP-SHA1"),
        }

        self.auth_socket.send(salt.payload.dumps(auth_payload))
        response = salt.payload.loads(self.auth_socket.recv())

        if response.get("authorized"):
            self.authenticated = True
            # Unwrap the server-minted Crypticle key with our private
            # key.  The server encrypted it under our RSA public key
            # (which it has in ``client_keys`` cache from the sign-in
            # flow), so only we can read it.  Use the same
            # ``encryption_algorithm`` we advertised in the auth
            # payload above; the default ``OAEP-SHA1`` is rejected on
            # FIPS hosts.
            wrapped = response.get("events_key")
            if wrapped is not None:
                enc_algo = self.opts.get(
                    "encryption_algorithm",
                    getattr(salt.crypt, "OAEP_SHA1", "OAEP-SHA1"),
                )
                key_string_bytes = priv_key.decrypt(wrapped, algorithm=enc_algo)
                key_string = key_string_bytes.decode()
                self.crypticle = salt.crypt.Crypticle(self.opts, key_string)
            log.info("Successfully authenticated with event publisher")
        else:
            raise Exception("Failed to authenticate with event publisher")

    def _authenticate_token(self, salt_token, eauth=None):
        """
        Authenticate with the event publisher using a Salt eauth token.

        The server returns a per-session ``session_id`` which the
        subscriber uses as its SUB filter prefix.  The token value itself
        is never sent on the SUB channel.
        """
        auth_payload = {"action": "auth_token", "token": salt_token}
        if eauth:
            auth_payload["eauth"] = eauth

        self.auth_socket.send(salt.payload.dumps(auth_payload))
        response = salt.payload.loads(self.auth_socket.recv())

        if response.get("authorized"):
            self.authenticated = True
            self.session_id = response.get("session_id")
            # Derive the per-session Crypticle key from the Salt token
            # the same way the publisher did.  No key transport needed
            # because both sides already share the token value.
            key_string = _derive_events_key(salt_token)
            self.crypticle = salt.crypt.Crypticle(self.opts, key_string)
            log.info("Successfully authenticated with event publisher via token")
        else:
            raise Exception("Failed to authenticate with event publisher via token")

    @property
    def cpub(self):
        """
        True when the subscriber socket is open.

        Mirrors ``salt.utils.event.SaltEvent.cpub``: callers inspect this
        before issuing a listen=True publish so they can decide whether to
        call ``close_pub()`` afterwards.
        """
        return self.sub_socket is not None

    def connect_pub(self, timeout=None):
        """
        Connect the pub (subscriber) channel.

        Mirrors ``salt.utils.event.SaltEvent.connect_pub``: returns True on
        success, False on failure.  ``timeout`` is accepted for interface
        compatibility; the underlying ``connect()`` does not poll.
        """
        if self.cpub:
            return True
        try:
            self.connect()
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Failed to connect to event publisher: %s", exc)
            return False
        return self.cpub

    def close_pub(self):
        """
        Close the subscriber socket.

        Called by ``LocalClient`` after a ``listen=True`` publish to tear
        down a connection it opened just for that call.  Keep the auth
        socket and the ZMQ context alive so a subsequent ``connect_pub()``
        on the same subscriber instance works.
        """
        if self.sub_socket is not None:
            self.sub_socket.close(linger=0)
            self.sub_socket = None

    def subscribe(self, tag, match_type=None):
        """
        Subscribe to events with the given tag.

        Mirrors ``salt.utils.event.SaltEvent.subscribe``.  For the network
        subscriber the subscription is server-side (the publisher filters
        events by client-id + job-id); if ``tag`` contains a JID we treat
        it as a job subscribe request, otherwise the call is a no-op (the
        server already forwards all events authorised for this client).
        """
        jid = self._extract_jid(tag)
        if jid is not None:
            self.subscribe_job(jid)

    def unsubscribe(self, tag, match_type=None):
        """
        Unsubscribe from events with the given tag.  Symmetric with
        ``subscribe``.
        """
        jid = self._extract_jid(tag)
        if jid is not None:
            self.unsubscribe_job(jid)

    @staticmethod
    def _extract_jid(tag):
        """Return the 20-digit JID embedded in ``tag`` or None."""
        if not tag:
            return None
        match = re.search(r"\b(\d{20})\b", tag)
        return match.group(1) if match else None

    def subscribe_job(self, jid):
        """
        Subscribe to events for a specific job.

        Args:
            jid: Job ID to subscribe to
        """
        if not self.authenticated:
            raise Exception("Not authenticated with event publisher")

        # ``id`` is the session_id in token mode, the client_id in PKI
        # mode -- the publisher keys ``clients`` by whichever we sent on
        # the initial auth.
        subscribe_payload = {
            "id": self.session_id or self.opts.get("id", "client"),
            "action": "subscribe_job",
            "jid": jid,
        }

        self.auth_socket.send(salt.payload.dumps(subscribe_payload))
        response = salt.payload.loads(self.auth_socket.recv())

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
                "id": self.session_id or self.opts.get("id", "client"),
                "action": "unsubscribe_job",
                "jid": jid,
            }

            self.auth_socket.send(salt.payload.dumps(unsubscribe_payload))
            salt.payload.loads(self.auth_socket.recv())
            self.subscribed_jobs.discard(jid)

    def get_event(
        self,
        wait=5,
        tag="",
        full=False,
        no_block=False,
        match_type=None,
        auto_reconnect=False,
        **kwargs,
    ):
        """
        Get a single event from the event stream.

        Mirrors :meth:`salt.utils.event.SaltEvent.get_event` enough that
        :class:`salt.client.LocalClient`'s event loops can call this
        without caring whether ``self.event`` is an IPC bus or a
        :class:`ClientEventSubscriber`.  Extra kwargs (``match_type``,
        ``auto_reconnect``) are accepted for interface compatibility and
        ignored -- filtering is done server-side by the
        :class:`ClientEventPublisher` based on the subscriber's job
        subscriptions.

        Args:
            wait: Timeout in seconds
            tag: Event tag filter (applied client-side as a prefix match
                against the delivered tag so callers that filter on a
                specific tag still see only matching events)
            full: Return the full ``{tag, data}`` event dict
            no_block: Non-blocking mode (zero wait)

        Returns:
            dict | None: Event data or ``None`` on timeout
        """
        if not self.sub_socket:
            return None

        import time

        deadline = None if no_block else time.monotonic() + max(wait, 0)

        try:
            # A single job fires multiple event tags (``.../new``,
            # ``.../ret/<id>``), so when the caller asks for a specific
            # tag we have to keep reading past non-matching events until
            # either a match arrives or the overall wait expires.
            # Dropping on the first mismatch (which the pre-replay code
            # did) hid a latent bug: the replay buffer now delivers
            # ``/new`` ahead of ``/ret``, and the old behaviour would
            # treat ``/new`` as "no match -> timeout".
            while True:
                if no_block:
                    self.sub_socket.setsockopt(zmq.RCVTIMEO, 0)
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return None
                    self.sub_socket.setsockopt(zmq.RCVTIMEO, int(remaining * 1000))

                # Receive event (multipart: [subscriber_id, payload])
                parts = self.sub_socket.recv_multipart()

                if len(parts) < 2:
                    return None

                # Decrypt with the per-session Crypticle established
                # at auth time.  Both ``_authenticate`` and
                # ``_authenticate_token`` populate ``self.crypticle``
                # on success; a missing one here means we received an
                # event before auth completed, which is a bug.
                if self.crypticle is None:
                    raise salt.exceptions.AuthenticationError(
                        "Received event before Crypticle session was "
                        "negotiated with the publisher"
                    )
                event_data = self.crypticle.loads(parts[1])
                if tag:
                    event_tag = event_data.get("tag", "")
                    if not event_tag.startswith(tag):
                        # Not what the caller asked for -- keep reading.
                        if no_block:
                            return None
                        continue
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
        """Close connections and clean up.

        Uses ``linger=0`` for the socket closes and
        ``context.destroy(linger=0)`` instead of ``context.term()`` so this
        never blocks finalisation.  ``term()`` waits indefinitely for any
        pending socket operations to drain, which deadlocks the pytest
        process at teardown when ``__del__`` collects an orphan
        ``RemoteClient`` whose counterpart master/minion was already
        SIGTERMed and left ZMQ fds in a half-closed state.
        """
        if self.sub_socket is not None:
            self.sub_socket.close(linger=0)
            self.sub_socket = None
        if self.auth_socket is not None:
            self.auth_socket.close(linger=0)
            self.auth_socket = None
        if self.context is not None:
            self.context.destroy(linger=0)
            self.context = None
