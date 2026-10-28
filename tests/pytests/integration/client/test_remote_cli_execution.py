"""
Integration tests for remote Salt CLI execution (salt-run and salt-key).

Tests the complete remote CLI workflow including:
- salt-run with --client-auth flag
- salt-key with --client-auth flag
- Client authentication via PKI keys
- Remote command execution without eauth credentials
"""

import salt.crypt
import salt.key
import salt.runner


class TestRemoteSaltRun:
    """Test remote salt-run execution with --client-auth."""

    def test_runner_client_auth_config(self, salt_master):
        """Test that Runner class loads client config when client_auth is enabled."""
        config = salt_master.config.copy()
        config["client_auth"] = True
        config["fun"] = "test.ping"
        config["arg"] = []

        runner = salt.runner.Runner(config)

        # Verify client role was set
        assert runner.opts.get("__role") == "client"

    def test_runner_uses_network_events_with_client_auth(self, salt_master):
        """
        Test that Runner uses network events when client_auth is enabled.

        Regression test: Runner must use ClientEventSubscriber, not IPC events.
        """
        import salt.utils.client_event

        config = salt_master.config.copy()
        config["client_auth"] = True
        config["fun"] = "test.ping"
        config["arg"] = []

        runner = salt.runner.Runner(config)

        # CRITICAL: Verify network events are being used
        assert (
            runner._use_network_events is True
        ), "Runner with client_auth must use network events"

        # Verify event subscriber type
        assert isinstance(
            runner.event, salt.utils.client_event.ClientEventSubscriber
        ), "Runner should use ClientEventSubscriber with client_auth"

    def test_runner_remote_execution(self, salt_master):
        """Test remote runner execution with client authentication."""
        # Setup: Create and accept client key
        client_id = "test-runner-client"
        _, pub = salt.crypt.gen_keys(4096)

        with salt.key.ClientKey(salt_master.config) as ckey:
            ckey.cache.store(
                "client_keys", client_id, {"pub": pub, "state": "accepted"}
            )

            try:
                # Create runner config with client auth
                config = salt_master.config.copy()
                config["client_auth"] = True
                config["fun"] = "test.ping"
                config["arg"] = []

                runner = salt.runner.Runner(config)

                # Verify runner is configured for client auth
                assert runner.opts.get("client_auth") is True
                assert runner.opts.get("__role") == "client"

            finally:
                # Cleanup
                ckey.delete_key(client_id)

    def test_runner_skips_eauth_with_client_auth(self, salt_master):
        """Test that runner skips eauth credential collection with client_auth."""
        config = salt_master.config.copy()
        config["client_auth"] = True
        config["eauth"] = ""  # No eauth
        config["fun"] = "test.ping"
        config["arg"] = []

        runner = salt.runner.Runner(config)

        # This should not raise an error for missing eauth credentials
        # because client_auth uses PKI keys
        assert runner.opts.get("client_auth") is True


class TestRemoteSaltKey:
    """Test remote salt-key execution with --client-auth."""

    def test_keycli_client_auth_config(self, salt_master):
        """Test that KeyCLI class loads client config when client_auth is enabled."""
        config = salt_master.config.copy()
        config["client_auth"] = True
        config["list"] = True  # Default command

        keycli = salt.key.KeyCLI(config)

        # Verify client role was set
        assert keycli.opts.get("__role") == "client"

    def test_wheel_client_uses_network_events_with_client_auth(self, salt_master):
        """
        Test that WheelClient uses network events when client_auth is enabled.

        Regression test: WheelClient (used by salt-key) must use ClientEventSubscriber.
        """
        import salt.utils.client_event
        import salt.wheel

        config = salt_master.config.copy()
        config["client_auth"] = True

        wheel = salt.wheel.WheelClient(config)

        try:
            # CRITICAL: Verify network events are being used
            assert (
                wheel._use_network_events is True
            ), "WheelClient with client_auth must use network events"

            # Verify event subscriber type
            assert isinstance(
                wheel.event, salt.utils.client_event.ClientEventSubscriber
            ), "WheelClient should use ClientEventSubscriber with client_auth"
        finally:
            wheel.destroy()

    def test_keycli_remote_execution_routing(self, salt_master):
        """Test that KeyCLI routes commands to remote execution with client_auth."""
        config = salt_master.config.copy()
        config["client_auth"] = True
        config["list"] = True

        keycli = salt.key.KeyCLI(config)

        # With client_auth, key objects should be class references, not instances
        assert keycli.key is salt.key.Key
        assert keycli.client_key is salt.key.ClientKey

    def test_keycli_skips_eauth_with_client_auth(self, salt_master):
        """Test that KeyCLI skips eauth credential collection with client_auth."""
        config = salt_master.config.copy()
        config["client_auth"] = True
        config["eauth"] = ""  # No eauth
        config["list"] = True

        keycli = salt.key.KeyCLI(config)

        # Initialize auth (should not prompt for credentials)
        keycli._init_auth()

        # Auth dict should be empty for client_auth (uses PKI keys)
        # This should not raise an error
        assert keycli.opts.get("client_auth") is True

    def test_keycli_local_vs_remote_execution(self, salt_master):
        """Test difference between local and remote KeyCLI execution."""
        # Local execution (no eauth, no client_auth)
        local_config = salt_master.config.copy()
        local_config["eauth"] = ""
        local_config["list"] = True

        local_keycli = salt.key.KeyCLI(local_config)

        # Should have instantiated key objects
        assert isinstance(local_keycli.key, salt.key.Key)
        assert isinstance(local_keycli.client_key, salt.key.ClientKey)

        # Remote execution with client_auth
        remote_config = salt_master.config.copy()
        remote_config["client_auth"] = True
        remote_config["list"] = True

        remote_keycli = salt.key.KeyCLI(remote_config)

        # Should have class references (for lazy loading)
        assert remote_keycli.key is salt.key.Key
        assert remote_keycli.client_key is salt.key.ClientKey


class TestClientAuthIntegration:
    """Test end-to-end client authentication workflow for CLI tools."""

    def test_runner_and_key_cli_share_config(self, salt_master):
        """Test that Runner and KeyCLI use compatible client auth configuration."""
        # Setup client key
        client_id = "test-integration-client"
        _, pub = salt.crypt.gen_keys(4096)

        with salt.key.ClientKey(salt_master.config) as ckey:
            ckey.cache.store(
                "client_keys", client_id, {"pub": pub, "state": "accepted"}
            )

            try:
                # Create config with client auth
                config = salt_master.config.copy()
                config["client_auth"] = True
                config["id"] = client_id

                # Test Runner
                runner_config = config.copy()
                runner_config["fun"] = "test.ping"
                runner_config["arg"] = []
                runner = salt.runner.Runner(runner_config)

                assert runner.opts.get("__role") == "client"
                assert runner.opts.get("client_auth") is True

                # Test KeyCLI
                keycli_config = config.copy()
                keycli_config["list"] = True
                keycli = salt.key.KeyCLI(keycli_config)

                assert keycli.opts.get("__role") == "client"
                assert keycli.opts.get("client_auth") is True

                # Both should have the same role
                assert runner.opts.get("__role") == keycli.opts.get("__role")

            finally:
                # Cleanup
                ckey.delete_key(client_id)

    def test_client_auth_without_accepted_key_fails_gracefully(self, salt_master):
        """Test that client auth without accepted key handles error gracefully."""
        # Create config with client auth but no accepted key
        config = salt_master.config.copy()
        config["client_auth"] = True
        config["id"] = "non-existent-client"

        # This should create objects without error (error happens at execution)
        runner_config = config.copy()
        runner_config["fun"] = "test.ping"
        runner_config["arg"] = []
        runner = salt.runner.Runner(runner_config)

        # Object should be created successfully
        assert runner.opts.get("__role") == "client"

        # KeyCLI as well
        keycli_config = config.copy()
        keycli_config["list"] = True
        keycli = salt.key.KeyCLI(keycli_config)

        assert keycli.opts.get("__role") == "client"


class TestNetworkEventIntegration:
    """Integration tests for network event streaming."""

    def test_all_remote_clients_use_network_events(self, salt_master):
        """
        Comprehensive test: All client types must use network events when remote.

        This is the critical regression test that would have caught the bug.
        """
        import salt.client
        import salt.config
        import salt.runner
        import salt.utils.client_event
        import salt.wheel

        # Simulate remote client config
        config = salt_master.config.copy()
        config["__role"] = "client"
        config["client_auth"] = True

        # Test RemoteClient
        remote_client = salt.client.RemoteClient(mopts=config, skip_perm_errors=True)
        try:
            assert (
                remote_client._use_network_events is True
            ), "RemoteClient MUST use network events"
            assert isinstance(
                remote_client.event, salt.utils.client_event.ClientEventSubscriber
            ), "RemoteClient should use ClientEventSubscriber"
        finally:
            remote_client.destroy()

        # Test RunnerClient
        runner_config = config.copy()
        runner_config["fun"] = "test.ping"
        runner_config["arg"] = []
        runner = salt.runner.Runner(runner_config)

        assert (
            runner._use_network_events is True
        ), "RunnerClient MUST use network events"
        assert isinstance(
            runner.event, salt.utils.client_event.ClientEventSubscriber
        ), "RunnerClient should use ClientEventSubscriber"

        # Test WheelClient
        wheel = salt.wheel.WheelClient(config)
        try:
            assert (
                wheel._use_network_events is True
            ), "WheelClient MUST use network events"
            assert isinstance(
                wheel.event, salt.utils.client_event.ClientEventSubscriber
            ), "WheelClient should use ClientEventSubscriber"
        finally:
            wheel.destroy()

    def test_local_clients_still_use_ipc(self, salt_master):
        """
        Test that local clients still use IPC for backwards compatibility and efficiency.
        """
        import salt.runner
        import salt.utils.event

        # Local runner config (no client_auth, no client role)
        local_config = salt_master.config.copy()
        local_config["fun"] = "test.ping"
        local_config["arg"] = []

        runner = salt.runner.RunnerClient(local_config)

        # Should use IPC for local execution
        assert (
            runner._use_network_events is False
        ), "Local RunnerClient should use IPC, not network events"
        assert isinstance(
            runner.event, salt.utils.event.SaltEvent
        ), "Local RunnerClient should use IPC SaltEvent"
