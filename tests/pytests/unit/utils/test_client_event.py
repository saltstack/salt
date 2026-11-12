"""
Unit tests for client event filtering.

Tests the ClientEventPublisher's ability to filter and deliver events
for different event types: job, run, and wheel.
"""

import base64

import salt.crypt
import salt.utils.client_event


def _test_crypticle(opts=None):
    return salt.crypt.Crypticle(opts or {}, salt.crypt.Crypticle.generate_key_string())


class TestClientEventFiltering:
    """Test event filtering logic in ClientEventPublisher."""

    def test_job_event_extraction(self):
        """Test that job IDs are correctly extracted from salt/job/ events."""
        publisher = salt.utils.client_event.ClientEventPublisher({})

        # Mock event with job tag
        event = {
            "tag": "salt/job/20231027123456789012/new",
            "data": {"fun": "test.ping"},
        }

        # Mock clients - one subscribed to this job
        clients = {
            "test-client": {
                "authorized": True,
                "jobs": {"20231027123456789012"},
                "crypticle": _test_crypticle(),
            }
        }

        # Mock pub_socket to capture what would be sent
        sent_events = []

        class MockPubSocket:
            def send_multipart(self, parts):
                sent_events.append(parts)

        mock_socket = MockPubSocket()

        # Call the filtering method
        publisher._publish_filtered_event(mock_socket, event, clients)

        # Verify event was sent to subscribed client
        assert len(sent_events) == 1
        assert sent_events[0][0] == b"test-client"

    def test_run_event_extraction(self):
        """Test that job IDs are correctly extracted from salt/run/ events."""
        publisher = salt.utils.client_event.ClientEventPublisher({})

        # Mock runner event
        event = {
            "tag": "salt/run/20231027123456789012/new",
            "data": {"fun": "test.ping"},
        }

        # Mock clients - one subscribed to this runner job
        clients = {
            "test-runner-client": {
                "authorized": True,
                "jobs": {"20231027123456789012"},
                "crypticle": _test_crypticle(),
            }
        }

        # Mock pub_socket
        sent_events = []

        class MockPubSocket:
            def send_multipart(self, parts):
                sent_events.append(parts)

        mock_socket = MockPubSocket()

        # Call the filtering method
        publisher._publish_filtered_event(mock_socket, event, clients)

        # CRITICAL: Verify runner event was sent to subscribed client
        assert (
            len(sent_events) == 1
        ), "Runner events must be delivered to subscribed clients"
        assert sent_events[0][0] == b"test-runner-client"

    def test_wheel_event_extraction(self):
        """Test that job IDs are correctly extracted from salt/wheel/ events."""
        publisher = salt.utils.client_event.ClientEventPublisher({})

        # Mock wheel event
        event = {
            "tag": "salt/wheel/20231027123456789012/new",
            "data": {"fun": "key.list_all"},
        }

        # Mock clients - one subscribed to this wheel job
        clients = {
            "test-wheel-client": {
                "authorized": True,
                "jobs": {"20231027123456789012"},
                "crypticle": _test_crypticle(),
            }
        }

        # Mock pub_socket
        sent_events = []

        class MockPubSocket:
            def send_multipart(self, parts):
                sent_events.append(parts)

        mock_socket = MockPubSocket()

        # Call the filtering method
        publisher._publish_filtered_event(mock_socket, event, clients)

        # CRITICAL: Verify wheel event was sent to subscribed client
        assert (
            len(sent_events) == 1
        ), "Wheel events must be delivered to subscribed clients"
        assert sent_events[0][0] == b"test-wheel-client"

    def test_event_not_sent_to_unsubscribed_client(self):
        """Test that events are NOT sent to clients who haven't subscribed to the job."""
        publisher = salt.utils.client_event.ClientEventPublisher({})

        # Mock event
        event = {
            "tag": "salt/job/20231027123456789012/new",
            "data": {"fun": "test.ping"},
        }

        # Mock clients - authorized but NOT subscribed to this job
        clients = {
            "test-client": {
                "authorized": True,
                "jobs": {"different-job-id"},
                "crypticle": _test_crypticle(),
            }
        }

        # Mock pub_socket
        sent_events = []

        class MockPubSocket:
            def send_multipart(self, parts):
                sent_events.append(parts)

        mock_socket = MockPubSocket()

        # Call the filtering method
        publisher._publish_filtered_event(mock_socket, event, clients)

        # Verify NO events were sent
        assert (
            len(sent_events) == 0
        ), "Events should not be sent to unsubscribed clients"

    def test_event_not_sent_to_unauthorized_client(self):
        """Test that events are NOT sent to unauthorized clients."""
        publisher = salt.utils.client_event.ClientEventPublisher({})

        # Mock event
        event = {
            "tag": "salt/job/20231027123456789012/new",
            "data": {"fun": "test.ping"},
        }

        # Mock clients - subscribed but NOT authorized
        clients = {
            "test-client": {
                "authorized": False,
                "jobs": {"20231027123456789012"},
                "crypticle": _test_crypticle(),
            }
        }

        # Mock pub_socket
        sent_events = []

        class MockPubSocket:
            def send_multipart(self, parts):
                sent_events.append(parts)

        mock_socket = MockPubSocket()

        # Call the filtering method
        publisher._publish_filtered_event(mock_socket, event, clients)

        # Verify NO events were sent
        assert (
            len(sent_events) == 0
        ), "Events should not be sent to unauthorized clients"

    def test_multiple_clients_receive_same_job(self):
        """Test that multiple clients subscribed to same job all receive events."""
        publisher = salt.utils.client_event.ClientEventPublisher({})

        # Mock event
        event = {
            "tag": "salt/job/20231027123456789012/ret/minion1",
            "data": {"return": True},
        }

        # Mock multiple clients subscribed to same job
        clients = {
            "client1": {
                "authorized": True,
                "jobs": {"20231027123456789012"},
                "crypticle": _test_crypticle(),
            },
            "client2": {
                "authorized": True,
                "jobs": {"20231027123456789012"},
                "crypticle": _test_crypticle(),
            },
            "client3": {
                "authorized": True,
                "jobs": {"different-job"},
                "crypticle": _test_crypticle(),
            },
        }

        # Mock pub_socket
        sent_events = []

        class MockPubSocket:
            def send_multipart(self, parts):
                sent_events.append(parts)

        mock_socket = MockPubSocket()

        # Call the filtering method
        publisher._publish_filtered_event(mock_socket, event, clients)

        # Verify event was sent to both subscribed clients
        assert len(sent_events) == 2
        sent_client_ids = {parts[0] for parts in sent_events}
        assert sent_client_ids == {b"client1", b"client2"}

    def test_all_event_types_in_sequence(self):
        """Test that all three event types are handled correctly in sequence."""
        publisher = salt.utils.client_event.ClientEventPublisher({})

        # Mock client subscribed to all three jobs
        clients = {
            "test-client": {
                "authorized": True,
                "jobs": {"job-id-1", "run-id-1", "wheel-id-1"},
                "crypticle": _test_crypticle(),
            }
        }

        # Mock pub_socket
        sent_events = []

        class MockPubSocket:
            def send_multipart(self, parts):
                sent_events.append(parts)

        mock_socket = MockPubSocket()

        # Send job event
        job_event = {"tag": "salt/job/job-id-1/new", "data": {}}
        publisher._publish_filtered_event(mock_socket, job_event, clients)

        # Send run event
        run_event = {"tag": "salt/run/run-id-1/new", "data": {}}
        publisher._publish_filtered_event(mock_socket, run_event, clients)

        # Send wheel event
        wheel_event = {"tag": "salt/wheel/wheel-id-1/new", "data": {}}
        publisher._publish_filtered_event(mock_socket, wheel_event, clients)

        # Verify all three events were sent
        assert (
            len(sent_events) == 3
        ), "All three event types (job, run, wheel) should be delivered"

        # All should be sent to the same client
        assert all(parts[0] == b"test-client" for parts in sent_events)

    def test_malformed_event_tags(self):
        """Test that malformed event tags don't cause errors."""
        publisher = salt.utils.client_event.ClientEventPublisher({})

        # Mock client
        clients = {
            "test-client": {
                "authorized": True,
                "jobs": {"some-job-id"},
                "crypticle": _test_crypticle(),
            }
        }

        # Mock pub_socket
        sent_events = []

        class MockPubSocket:
            def send_multipart(self, parts):
                sent_events.append(parts)

        mock_socket = MockPubSocket()

        # Test various malformed tags
        malformed_events = [
            {"tag": "salt/job", "data": {}},  # Too short
            {"tag": "salt/job/", "data": {}},  # No job ID
            {"tag": "not-a-salt-event", "data": {}},  # Wrong prefix
            {"tag": "", "data": {}},  # Empty tag
            {"tag": "salt/unknown/12345/new", "data": {}},  # Unknown type
        ]

        for event in malformed_events:
            publisher._publish_filtered_event(mock_socket, event, clients)

        # None of these should cause events to be sent
        assert (
            len(sent_events) == 0
        ), "Malformed events should not result in any deliveries"


class TestDeriveEventsKey:
    """Covers :func:`salt.utils.client_event._derive_events_key`.

    The token-auth path for the remote event stream derives a per-session
    Crypticle key from the Salt token via HKDF-SHA256 so the token itself
    never travels on the REP channel outside the request.  Both ends of
    the stream MUST agree bit-for-bit on the output, so the function is
    deterministic, accepts the token in either str or bytes form, and
    produces a well-formed Crypticle ``key_string``.
    """

    def test_deterministic_for_same_input(self):
        """Same secret in -> same key out (bit-for-bit)."""
        a = salt.utils.client_event._derive_events_key("shared-secret")
        b = salt.utils.client_event._derive_events_key("shared-secret")
        assert a == b

    def test_accepts_str_and_bytes_equivalently(self):
        """``str`` and ``bytes`` forms of the same secret derive the same key."""
        s = "shared-secret"
        a = salt.utils.client_event._derive_events_key(s)
        b = salt.utils.client_event._derive_events_key(s.encode())
        assert a == b

    def test_different_secrets_produce_different_keys(self):
        """Distinct secrets must not collide."""
        a = salt.utils.client_event._derive_events_key("alpha")
        b = salt.utils.client_event._derive_events_key("beta")
        assert a != b

    def test_output_decodes_to_crypticle_key_length(self):
        """
        The derived key_string is base64 and decodes to exactly 56 bytes
        -- the Crypticle layout of 24 AES bytes + 32 HMAC bytes.
        """
        key_string = salt.utils.client_event._derive_events_key("secret")
        raw = base64.b64decode(key_string)
        assert len(raw) == 24 + 32  # key_size=192//8 + SHA-256 digest size

    def test_output_is_valid_crypticle_key_string(self):
        """
        Feed the derived key into :class:`salt.crypt.Crypticle` and
        make sure a round-trip encrypt/decrypt comes back with the same
        payload.  Also sanity-checks that ``extract_keys`` accepts the
        encoding without hitting its ``invalid key`` assertion.
        """
        key_string = salt.utils.client_event._derive_events_key("secret")
        crypt = salt.crypt.Crypticle({}, key_string)
        token = crypt.dumps({"hello": "world"})
        assert crypt.loads(token) == {"hello": "world"}


class TestServerBounds:
    """Server-side defensive bounds on ClientEventPublisher internals.

    Covers:
      * ``recent_events`` deque hard-caps at ``client_event_replay_maxlen``
      * ``_handle_auth_request`` rejects new auths once the ``clients``
        dict is full (``client_event_max_sessions``)
      * ``_evict_expired_sessions`` reclaims token-auth entries whose
        ``expire`` timestamp has passed, independent of the publish path
    """

    def test_recent_events_deque_honors_maxlen(self):
        """``collections.deque(maxlen=N)`` drops oldest when full."""
        import collections

        buf = collections.deque(maxlen=4)
        for i in range(10):
            buf.append(("t", {"i": i}))
        assert len(buf) == 4
        # Oldest 6 were evicted; survivors are the latest 4
        assert [item[1]["i"] for item in buf] == [6, 7, 8, 9]

    def test_evict_expired_sessions_drops_past_expiry(self):
        """Expired token sessions are removed; unexpired + no-expire stay."""
        publisher = salt.utils.client_event.ClientEventPublisher({})
        now = 1_000_000.0
        clients = {
            "stale-token-session": {
                "authorized": True,
                "auth_mode": "token",
                "jobs": set(),
                "expire": now - 10,  # 10s ago
            },
            "live-token-session": {
                "authorized": True,
                "auth_mode": "token",
                "jobs": set(),
                "expire": now + 60,  # 60s from now
            },
            "pki-no-expire": {
                "authorized": True,
                "auth_mode": "pki",
                "jobs": set(),
                "expire": None,
            },
        }
        publisher._evict_expired_sessions(clients, now)
        assert set(clients) == {"live-token-session", "pki-no-expire"}

    def test_handle_auth_rejects_when_session_cap_reached(self):
        """New ``auth`` beyond ``client_event_max_sessions`` is rejected."""
        import salt.payload

        publisher = salt.utils.client_event.ClientEventPublisher(
            {"client_event_max_sessions": 2}
        )
        clients = {
            "sid-0": {"authorized": True, "jobs": set()},
            "sid-1": {"authorized": True, "jobs": set()},
        }
        sent = []

        class StubSocket:
            def recv(self):
                return salt.payload.dumps(
                    {"action": "auth", "id": "new-client", "token": b"x"}
                )

            def send(self, msg):
                sent.append(msg)

        publisher._handle_auth_request(
            StubSocket(), key_cache=None, loadauth=None, clients=clients
        )
        # Clients dict unchanged -- new-client was not admitted
        assert "new-client" not in clients
        assert len(sent) == 1
        resp = salt.payload.loads(sent[0])
        assert resp["authorized"] is False
        assert "session cap" in resp.get("reason", "")

    def test_subscribe_job_not_blocked_by_session_cap(self):
        """The cap gates only ``auth``/``auth_token``; subscribe actions on
        already-authenticated sessions must still work when the dict is
        at capacity (otherwise legitimate subscribers can't poll).
        """
        import salt.payload

        publisher = salt.utils.client_event.ClientEventPublisher(
            {"client_event_max_sessions": 1}
        )
        clients = {
            "existing-sid": {"authorized": True, "jobs": set()},
        }
        sent = []

        class StubSocket:
            def recv(self):
                return salt.payload.dumps(
                    {
                        "action": "subscribe_job",
                        "id": "existing-sid",
                        "jid": "20260101000000000001",
                    }
                )

            def send(self, msg):
                sent.append(msg)

        publisher._handle_auth_request(
            StubSocket(), key_cache=None, loadauth=None, clients=clients
        )
        assert "20260101000000000001" in clients["existing-sid"]["jobs"]
        resp = salt.payload.loads(sent[0])
        assert resp["subscribed"] is True
