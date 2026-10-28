"""
Unit tests for client event filtering.

Tests the ClientEventPublisher's ability to filter and deliver events
for different event types: job, run, and wheel.
"""

import salt.utils.client_event


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
            },
            "client2": {
                "authorized": True,
                "jobs": {"20231027123456789012"},
            },
            "client3": {
                "authorized": True,
                "jobs": {"different-job"},
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
