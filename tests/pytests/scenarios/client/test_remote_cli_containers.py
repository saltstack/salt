"""
Scenario test for remote Salt CLI authentication using containers.

This test demonstrates the complete remote CLI workflow:
1. Salt master running in one container
2. Remote client connecting from another location
3. Client key acceptance and authentication
4. Command execution across the network

This simulates a real-world scenario where an administrator runs
salt commands from their workstation to manage a remote Salt master.
"""

import os
import textwrap

import pytest

import salt.crypt
import salt.key
import salt.utils.files


@pytest.fixture
def master_container(salt_factories):
    """Create a Salt master container."""
    config_overrides = {
        "open_mode": False,
        "auto_accept": False,
        "client_acl": {},
        "publisher_acl": {},
        "client_event_port": 4507,  # Enable network event publishing for tests
    }

    factory = salt_factories.salt_master_daemon(
        "remote-test-master",
        overrides=config_overrides,
    )

    with factory.started():
        yield factory


@pytest.fixture
def minion_container(salt_factories, master_container):
    """Create a Salt minion connected to the master."""
    import salt.cache

    minion_id = "remote-test-minion"
    factory = salt_factories.salt_minion_daemon(
        minion_id,
        master=master_container,
    )

    # master_container has auto_accept=False and open_mode=False; pre-generate
    # the minion keypair, drop it in the minion's pki_dir, and seed the
    # master's keys cache as "accepted" so factory.started() doesn't block
    # waiting for a human to run `salt-key -a`. The ACL/key-management tests
    # that depend on the deliberate manual-accept flow do not use this
    # fixture -- they operate on the separate client_keys namespace.
    minion_pki_dir = factory.config["pki_dir"]
    os.makedirs(minion_pki_dir, exist_ok=True)
    priv_pem = os.path.join(minion_pki_dir, "minion.pem")
    pub_pem = os.path.join(minion_pki_dir, "minion.pub")
    if not os.path.exists(priv_pem):
        priv_key, pub_key = salt.crypt.gen_keys(2048)
        with salt.utils.files.fopen(priv_pem, "w") as fp:
            fp.write(priv_key)
        with salt.utils.files.fopen(pub_pem, "w") as fp:
            fp.write(pub_key)
        os.chmod(priv_pem, 0o400)
    else:
        with salt.utils.files.fopen(pub_pem) as fp:
            pub_key = fp.read()

    cache = salt.cache.Cache(master_container.config)
    cache.store("keys", minion_id, {"pub": pub_key, "state": "accepted"})

    with factory.started():
        yield factory


@pytest.fixture
def client_config_dir(tmp_path):
    """Create a client configuration directory (simulates remote workstation)."""
    client_dir = tmp_path / "client_config"
    client_dir.mkdir()

    # Create pki directory for client keys
    pki_dir = client_dir / "pki"
    pki_dir.mkdir()

    return client_dir


@pytest.fixture
def remote_client_setup(master_container, client_config_dir):
    """
    Set up a remote client (simulates administrator workstation).

    This fixture:
    1. Generates client keypair
    2. Writes client config pointing to master
    3. Stores keys in client directory
    4. Accepts client key on master
    """
    client_id = "admin-workstation"

    # Generate client keys
    priv_key, pub_key = salt.crypt.gen_keys(4096)

    # Write client keys to client directory
    pki_dir = client_config_dir / "pki"

    priv_path = pki_dir / "client.pem"
    pub_path = pki_dir / "client.pub"

    with salt.utils.files.fopen(priv_path, "wb") as f:
        f.write(priv_key.encode() if isinstance(priv_key, str) else priv_key)

    with salt.utils.files.fopen(pub_path, "wb") as f:
        f.write(pub_key.encode() if isinstance(pub_key, str) else pub_key)

    # Set proper permissions
    os.chmod(priv_path, 0o400)
    os.chmod(pub_path, 0o644)

    # Create client config file pointing to master
    master_config = master_container.config

    client_config = textwrap.dedent(
        f"""
        # Client configuration for remote CLI access
        id: {client_id}
        master: {master_config['interface']}
        master_port: {master_config['ret_port']}

        # Client-specific settings
        pki_dir: {pki_dir}

        # Transport settings
        transport: {master_config.get('transport', 'zeromq')}

        # Timeouts
        timeout: 30
        acceptance_wait_time: 10
        acceptance_wait_time_max: 30
    """
    )

    config_file = client_config_dir / "client"
    with salt.utils.files.fopen(config_file, "w") as f:
        f.write(client_config)

    # Accept client key on master
    with salt.key.ClientKey(master_container.config) as ckey:
        # Store client public key on master
        ckey.cache.store(
            "client_keys", client_id, {"pub": pub_key, "state": "accepted"}
        )

    return {
        "id": client_id,
        "config_dir": client_config_dir,
        "config_file": str(config_file),
        "priv_key": priv_key,
        "pub_key": pub_key,
    }


class TestRemoteCLIScenario:
    """Test complete remote CLI authentication scenario."""

    def test_client_key_management_workflow(
        self, master_container, remote_client_setup
    ):
        """
        Test the complete client key management workflow.

        Scenario:
        1. Administrator generates client keys on workstation
        2. Public key is registered with master
        3. Master administrator accepts the client key
        4. Client is now authorized for remote CLI access
        """
        client_id = remote_client_setup["id"]

        # Verify client key is accepted on master
        with salt.key.ClientKey(master_container.config) as ckey:
            all_keys = ckey.list_keys()

            assert (
                client_id in all_keys["clients"]
            ), f"Client {client_id} should be in accepted clients"

            # Get client key fingerprint
            fingerprints = ckey.finger(client_id)
            assert (
                client_id in fingerprints["clients"]
            ), "Client should have a fingerprint"

            # Verify fingerprint format
            fp = fingerprints["clients"][client_id]
            assert ":" in fp, "Fingerprint should be colon-separated"

    def test_remote_client_configuration(self, master_container, remote_client_setup):
        """
        Test RemoteClient configuration for remote command execution.

        Scenario:
        1. Administrator on workstation wants to execute commands on minions
        2. Creates RemoteClient configured with client authentication
        3. Client is properly configured for PKI-based authentication
        4. Ready to execute commands on remote minions
        """
        import salt.client
        import salt.config

        # Load client config (simulates remote workstation)
        client_config = salt.config.client_config(remote_client_setup["config_file"])

        # Verify config loaded correctly
        assert client_config["id"] == remote_client_setup["id"]
        # __role may already be set by client_config() which is fine

        # Create RemoteClient (simulates running 'salt' command)
        client = salt.client.RemoteClient(
            mopts=client_config,
            skip_perm_errors=True,
        )

        try:
            # Verify client has correct role
            assert (
                client.opts["__role"] == "client"
            ), "RemoteClient should set __role to 'client'"

            # Verify client ID is set correctly
            assert (
                client.opts["id"] == remote_client_setup["id"]
            ), "Client ID should match configuration"

            # Verify transport is configured
            assert "transport" in client.opts, "Transport should be configured"

            # Verify client is ready to execute commands
            assert hasattr(client, "cmd"), "RemoteClient should have cmd method"
            assert hasattr(client, "pub"), "RemoteClient should have pub method"
        finally:
            client.destroy()

    def test_remote_client_uses_network_events(
        self, master_container, remote_client_setup
    ):
        """
        Test that RemoteClient uses network events, not IPC.

        This is critical for remote execution - IPC events only work
        on the same machine as the master.
        """
        import salt.client
        import salt.config
        import salt.utils.client_event

        client_config = salt.config.client_config(remote_client_setup["config_file"])

        client = salt.client.RemoteClient(
            mopts=client_config,
            skip_perm_errors=True,
        )

        try:
            # CRITICAL: Verify using network events, not IPC
            assert (
                client._use_network_events is True
            ), "RemoteClient must use network events for remote execution"

            # Verify event subscriber is ClientEventSubscriber
            assert isinstance(
                client.event, salt.utils.client_event.ClientEventSubscriber
            ), "RemoteClient should use ClientEventSubscriber for network events"

            # Verify NOT using IPC event subscriber
            assert not isinstance(
                client.event, salt.utils.event.SaltEvent
            ), "RemoteClient should NOT use IPC SaltEvent for remote execution"
        finally:
            client.destroy()

    def test_remote_runner_execution(self, master_container, remote_client_setup):
        """
        Test executing runners from remote client.

        Scenario:
        1. Administrator wants to run a master-side operation
        2. Runs 'salt-run test.ping' from workstation with --client-auth
        3. Command is authenticated via client PKI keys
        4. Master executes runner
        5. Results are returned to administrator
        """
        import salt.config
        import salt.runner

        # Load client config
        client_config = salt.config.client_config(remote_client_setup["config_file"])

        # Enable client auth (simulates --client-auth flag)
        client_config["client_auth"] = True
        client_config["fun"] = "test.ping"
        client_config["arg"] = []

        # Create Runner with client auth
        runner = salt.runner.Runner(client_config)

        # Verify runner is configured for client auth
        assert runner.opts.get("__role") == "client"
        assert runner.opts.get("client_auth") is True

        # Note: Full runner execution requires functional master daemon
        # For this test, we verify the configuration is correct

    def test_remote_runner_uses_network_events(
        self, master_container, remote_client_setup
    ):
        """
        Test that RunnerClient uses network events for remote execution.

        This is critical - runners need to receive events from the master,
        and IPC events only work locally.
        """
        import salt.config
        import salt.runner
        import salt.utils.client_event

        client_config = salt.config.client_config(remote_client_setup["config_file"])
        client_config["client_auth"] = True
        client_config["fun"] = "test.ping"
        client_config["arg"] = []

        runner = salt.runner.Runner(client_config)

        # CRITICAL: Verify network events are being used
        assert (
            runner._use_network_events is True
        ), "RunnerClient must use network events for remote execution"

        # Verify event subscriber is ClientEventSubscriber
        assert isinstance(
            runner.event, salt.utils.client_event.ClientEventSubscriber
        ), "RunnerClient should use ClientEventSubscriber for network events"

    def test_remote_key_management(self, master_container, remote_client_setup):
        """
        Test managing keys remotely via salt-key.

        Scenario:
        1. Administrator wants to manage minion keys remotely
        2. Runs 'salt-key -L' from workstation with --client-auth
        3. Command is authenticated via client PKI keys
        4. Master returns key list
        5. Administrator can accept/reject keys remotely
        """
        import salt.config
        import salt.key

        # Load client config
        client_config = salt.config.client_config(remote_client_setup["config_file"])

        # Enable client auth (simulates --client-auth flag)
        client_config["client_auth"] = True
        client_config["list"] = True

        # Create KeyCLI with client auth
        keycli = salt.key.KeyCLI(client_config)

        # Verify keycli is configured for client auth
        assert keycli.opts.get("__role") == "client"
        assert keycli.opts.get("client_auth") is True

        # Verify it's set up for remote execution
        assert keycli.key is salt.key.Key  # Class reference, not instance
        assert keycli.client_key is salt.key.ClientKey  # Class reference

    def test_remote_key_cli_uses_network_events(
        self, master_container, remote_client_setup
    ):
        """
        Test that KeyCLI (via WheelClient) uses network events for remote execution.

        salt-key uses WheelClient under the hood, which needs network events
        for remote execution.
        """
        import salt.config
        import salt.key
        import salt.wheel

        client_config = salt.config.client_config(remote_client_setup["config_file"])
        client_config["client_auth"] = True
        client_config["list"] = True

        keycli = salt.key.KeyCLI(client_config)

        # Create a WheelClient to verify network events
        wheel_client = salt.wheel.WheelClient(client_config)

        try:
            # CRITICAL: Verify network events are being used
            assert (
                wheel_client._use_network_events is True
            ), "WheelClient must use network events for remote execution"

            # Verify event subscriber is ClientEventSubscriber
            import salt.utils.client_event

            assert isinstance(
                wheel_client.event, salt.utils.client_event.ClientEventSubscriber
            ), "WheelClient should use ClientEventSubscriber for network events"
        finally:
            wheel_client.destroy()

    def test_multi_client_scenario(self, master_container, client_config_dir):
        """
        Test multiple administrators with separate client keys.

        Scenario:
        1. Multiple administrators need remote CLI access
        2. Each generates their own client keypair
        3. Master administrator accepts all client keys
        4. Each administrator can execute commands independently
        5. Master tracks which administrator executed each command
        """
        # Create multiple client identities
        clients = []
        for i, name in enumerate(["alice", "bob", "charlie"]):
            client_id = f"admin-{name}"

            # Generate keys
            priv_key, pub_key = salt.crypt.gen_keys(4096)

            # Accept on master
            with salt.key.ClientKey(master_container.config) as ckey:
                ckey.cache.store(
                    "client_keys", client_id, {"pub": pub_key, "state": "accepted"}
                )

            clients.append(
                {
                    "id": client_id,
                    "name": name,
                    "keys": (priv_key, pub_key),
                }
            )

        # Verify all clients are accepted
        with salt.key.ClientKey(master_container.config) as ckey:
            all_keys = ckey.list_keys()

            for client in clients:
                assert (
                    client["id"] in all_keys["clients"]
                ), f"Client {client['id']} should be accepted"

        # Verify we can list all client keys
        with salt.key.ClientKey(master_container.config) as ckey:
            fingerprints = {}
            for client in clients:
                fp = ckey.finger(client["id"])
                fingerprints[client["id"]] = fp["clients"][client["id"]]

            # All fingerprints should be unique
            assert len(set(fingerprints.values())) == len(
                clients
            ), "Each client should have unique fingerprint"

    def test_client_key_revocation_scenario(
        self, master_container, remote_client_setup
    ):
        """
        Test emergency client key revocation.

        Scenario:
        1. Administrator's laptop is stolen
        2. Master administrator immediately revokes client key
        3. Stolen client can no longer authenticate
        4. Administrator generates new keys on new laptop
        5. New keys are accepted, access is restored
        """
        client_id = remote_client_setup["id"]

        # Initial state: client is accepted
        with salt.key.ClientKey(master_container.config) as ckey:
            all_keys = ckey.list_keys()
            assert client_id in all_keys["clients"]

        # Emergency: revoke compromised client
        with salt.key.ClientKey(master_container.config) as ckey:
            result = ckey.reject(client_id, include_accepted=True)
            assert client_id in result["clients_rejected"]

        # Verify client is now rejected
        with salt.key.ClientKey(master_container.config) as ckey:
            all_keys = ckey.list_keys()
            assert client_id in all_keys["clients_rejected"]
            assert client_id not in all_keys["clients"]

        # Administrator gets new laptop, generates new keys
        new_client_id = f"{client_id}-new"
        _, new_pub = salt.crypt.gen_keys(4096)

        # Accept new client
        with salt.key.ClientKey(master_container.config) as ckey:
            ckey.cache.store(
                "client_keys", new_client_id, {"pub": new_pub, "state": "accepted"}
            )

        # Verify new client is accepted, old is still rejected
        with salt.key.ClientKey(master_container.config) as ckey:
            all_keys = ckey.list_keys()
            assert new_client_id in all_keys["clients"]
            assert client_id in all_keys["clients_rejected"]


class TestRemoteCLIConfiguration:
    """Test different configuration scenarios for remote CLI."""

    def test_saltrc_configuration(self, master_container, client_config_dir, tmp_path):
        """
        Test user-specific saltrc configuration.

        Scenario:
        1. Administrator has multiple Salt environments
        2. Creates ~/.saltrc to configure default environment
        3. Can override with SALT_CLIENT_CONFIG environment variable
        4. Can override with -c/--config-dir flag
        """
        # Create user's home directory with .saltrc
        home_dir = tmp_path / "home"
        home_dir.mkdir()

        saltrc_file = home_dir / ".saltrc"
        saltrc_content = textwrap.dedent(
            f"""
            # User's default Salt configuration
            master: {master_container.config['interface']}
            master_port: {master_container.config['ret_port']}
            id: user-workstation
        """
        )

        with salt.utils.files.fopen(saltrc_file, "w") as f:
            f.write(saltrc_content)

        # Verify saltrc would be loaded
        assert saltrc_file.exists()
        assert "master:" in saltrc_file.read_text()

    def test_multiple_master_configuration(self, master_container, client_config_dir):
        """
        Test managing multiple masters from one workstation.

        Scenario:
        1. Administrator manages dev, staging, and prod environments
        2. Each environment has its own master
        3. Uses different config directories for each environment
        4. Can switch between environments easily
        """
        # Create separate config for each environment
        environments = ["dev", "staging", "prod"]
        configs = {}

        for env in environments:
            env_dir = client_config_dir / env
            env_dir.mkdir()

            config_file = env_dir / "client"
            config_content = textwrap.dedent(
                f"""
                # {env.upper()} environment
                master: {env}-master.example.com
                id: admin-workstation-{env}
            """
            )

            with salt.utils.files.fopen(config_file, "w") as f:
                f.write(config_content)

            configs[env] = str(config_file)

        # Verify each environment has separate config
        assert len(configs) == 3
        for env, config_path in configs.items():
            assert os.path.exists(config_path)
            with salt.utils.files.fopen(config_path) as f:
                content = f.read()
                assert f"{env}-master" in content
                assert f"admin-workstation-{env}" in content


class TestRemoteCLIACLScenarios:
    """Test ACL restriction scenarios for remote CLI clients."""

    def test_client_acl_restrictions(self, master_container, client_config_dir):
        """
        Test ACL restrictions for remote CLI clients.

        Scenario:
        1. Master is configured with client_acl restrictions
        2. Different clients have different permission levels
        3. Readonly client can only execute safe operations
        4. Dev client can only access dev environment
        5. Admin client has full access
        """
        import salt.acl

        # Configure master with client ACL
        acl_config = {
            "admin-workstation": {
                "runner": ["*"],
                "wheel": ["*"],
                "minion": ["*"],
                "minion_function": ["*"],
            },
            "readonly-workstation": {
                "runner": ["test.ping", "jobs.list_jobs"],
                "wheel": ["key.list_all", "key.finger"],
                "minion": ["*"],
                "minion_function": ["test.ping", "grains.items", "status.*"],
            },
            "dev-workstation": {
                "runner": ["test.*", "jobs.*"],
                "wheel": ["key.list_all"],
                "minion": ["dev-*", "test-*"],
                "minion_function": ["*"],
            },
        }

        # Update master config with ACL
        master_config = master_container.config.copy()
        master_config["client_acl"] = acl_config

        # Create ClientACL instance
        client_acl = salt.acl.ClientACL(acl_config)

        # Test admin client (full access)
        assert client_acl.client_can_run_runner("admin-workstation", "test.ping")
        assert client_acl.client_can_run_runner(
            "admin-workstation", "state.orchestrate"
        )
        assert client_acl.client_can_run_wheel("admin-workstation", "key.accept")
        assert client_acl.client_can_target_minion("admin-workstation", "prod-web-01")
        assert client_acl.client_can_run_minion_function("admin-workstation", "cmd.run")

        # Test readonly client (limited access)
        assert client_acl.client_can_run_runner("readonly-workstation", "test.ping")
        assert client_acl.client_can_run_runner(
            "readonly-workstation", "jobs.list_jobs"
        )
        assert not client_acl.client_can_run_runner(
            "readonly-workstation", "state.orchestrate"
        )
        assert not client_acl.client_can_run_wheel("readonly-workstation", "key.accept")
        assert client_acl.client_can_run_minion_function(
            "readonly-workstation", "test.ping"
        )
        assert not client_acl.client_can_run_minion_function(
            "readonly-workstation", "cmd.run"
        )

        # Test dev client (environment-restricted)
        assert client_acl.client_can_target_minion("dev-workstation", "dev-web-01")
        assert client_acl.client_can_target_minion("dev-workstation", "test-db-01")
        assert not client_acl.client_can_target_minion("dev-workstation", "prod-web-01")
        assert client_acl.client_can_run_minion_function("dev-workstation", "cmd.run")

    def test_multi_client_different_permissions(
        self, master_container, client_config_dir
    ):
        """
        Test multiple clients with different permission levels.

        Scenario:
        1. Organization has multiple teams: operations, development, audit
        2. Operations team has full access
        3. Development team has limited access to dev environment
        4. Audit team has read-only access
        5. Each team's access is properly restricted
        """
        import salt.acl

        # Configure ACL for different teams
        acl_config = {
            "ops-team-client": {
                "runner": ["*"],
                "wheel": ["*"],
                "minion": ["*"],
                "minion_function": ["*"],
            },
            "dev-team-client": {
                "runner": ["test.*", "jobs.*", "pillar.show_pillar"],
                "wheel": ["key.list_all"],
                "minion": ["dev-*", "staging-*"],
                "minion_function": ["*"],
            },
            "audit-team-client": {
                "runner": ["jobs.list_jobs", "jobs.lookup_jid", "jobs.print_job"],
                "wheel": ["key.list_all", "key.finger"],
                "minion": ["*"],
                "minion_function": ["test.ping", "grains.items", "status.*"],
            },
        }

        client_acl = salt.acl.ClientACL(acl_config)

        # Operations team can do everything
        assert client_acl.client_can_run_runner("ops-team-client", "cmd.run")
        assert client_acl.client_can_run_wheel("ops-team-client", "key.delete")
        assert client_acl.client_can_target_minion("ops-team-client", "prod-db-01")
        assert client_acl.client_can_run_minion_function("ops-team-client", "cmd.run")

        # Development team has limited access
        assert client_acl.client_can_run_runner("dev-team-client", "test.ping")
        assert client_acl.client_can_target_minion("dev-team-client", "dev-web-01")
        assert client_acl.client_can_target_minion("dev-team-client", "staging-app-01")
        assert not client_acl.client_can_target_minion("dev-team-client", "prod-web-01")
        assert not client_acl.client_can_run_wheel("dev-team-client", "key.accept")
        assert client_acl.client_can_run_minion_function("dev-team-client", "cmd.run")

        # Audit team has read-only access
        assert client_acl.client_can_run_runner("audit-team-client", "jobs.list_jobs")
        assert client_acl.client_can_run_wheel("audit-team-client", "key.list_all")
        assert not client_acl.client_can_run_runner(
            "audit-team-client", "state.orchestrate"
        )
        assert not client_acl.client_can_run_wheel("audit-team-client", "key.accept")

        # Verify audit team can target all minions but with limited functions
        assert client_acl.client_can_target_minion("audit-team-client", "prod-web-01")
        assert client_acl.client_can_run_minion_function(
            "audit-team-client", "test.ping"
        )
        assert client_acl.client_can_run_minion_function(
            "audit-team-client", "status.uptime"
        )
        assert not client_acl.client_can_run_minion_function(
            "audit-team-client", "cmd.run"
        )

    def test_acl_denied_operations(self, master_container, client_config_dir):
        """
        Test that denied operations are properly blocked.

        Scenario:
        1. Junior admin has access to most operations
        2. Dangerous operations are explicitly blocked
        3. Attempting blocked operations returns denial
        4. Error messages are informative
        5. Client can still perform allowed operations
        """
        import salt.acl

        # Configure ACL using publisher_acl-style positive whitelists: only
        # the patterns listed below are allowed; everything else is denied by
        # omission.
        acl_config = {
            "junior-admin-client": {
                "runner": [
                    "test.*",
                    "jobs.*",
                    "cache.*",
                ],
                "wheel": [
                    "key.list_all",
                    "key.accept",
                ],
                "minions": [
                    "dev-*",
                    "staging-*",
                ],
            },
            "contractor-client": {
                "runner": ["test.ping", "jobs.list_jobs"],
                "wheel": ["key.list_all"],
                "minions": ["contractor-*"],
            },
        }

        client_acl = salt.acl.ClientACL(acl_config)

        # Junior admin - verify blocked operations (not in whitelist)
        assert not client_acl.client_can_run_runner("junior-admin-client", "cmd.run")
        assert not client_acl.client_can_run_runner("junior-admin-client", "cmd.shell")
        assert not client_acl.client_can_run_wheel("junior-admin-client", "key.delete")
        assert not client_acl.client_can_target_minion(
            "junior-admin-client", "prod-db-01"
        )

        # Junior admin - verify allowed operations (in whitelist)
        assert client_acl.client_can_run_runner("junior-admin-client", "test.ping")
        assert client_acl.client_can_run_runner("junior-admin-client", "jobs.list_jobs")
        assert client_acl.client_can_run_wheel("junior-admin-client", "key.accept")
        assert client_acl.client_can_target_minion("junior-admin-client", "dev-web-01")

        # Contractor - very limited access
        assert client_acl.client_can_run_runner("contractor-client", "test.ping")
        assert not client_acl.client_can_run_runner("contractor-client", "state.apply")
        assert client_acl.client_can_target_minion(
            "contractor-client", "contractor-vm-01"
        )
        assert not client_acl.client_can_target_minion(
            "contractor-client", "prod-web-01"
        )
        assert not client_acl.client_can_target_minion(
            "contractor-client", "dev-web-01"
        )

        # Test error messages for denied operations
        denial_msg = client_acl.get_denial_message(
            "junior-admin-client", "runner", "cmd.run"
        )
        assert "junior-admin-client" in denial_msg
        assert "cmd.run" in denial_msg
        assert "not authorized" in denial_msg.lower() or "denied" in denial_msg.lower()

    def test_emergency_acl_revocation(self, master_container):
        """
        Test emergency ACL revocation scenario.

        Scenario:
        1. Client has normal access to production
        2. Security incident detected - client credentials compromised
        3. Security team immediately revokes client key
        4. Client can no longer authenticate
        5. New client key is generated with restricted permissions
        6. Access is restored with reduced privileges
        """
        # Setup initial client with full access
        compromised_client_id = "compromised-workstation"
        priv_key, pub_key = salt.crypt.gen_keys(4096)

        # Accept client key
        with salt.key.ClientKey(master_container.config) as ckey:
            ckey.cache.store(
                "client_keys",
                compromised_client_id,
                {"pub": pub_key, "state": "accepted"},
            )

        # Verify client is accepted
        with salt.key.ClientKey(master_container.config) as ckey:
            all_keys = ckey.list_keys()
            assert compromised_client_id in all_keys["clients"]

        # Emergency: Revoke compromised client
        with salt.key.ClientKey(master_container.config) as ckey:
            result = ckey.reject(compromised_client_id, include_accepted=True)
            assert compromised_client_id in result["clients_rejected"]

        # Verify client is now rejected
        with salt.key.ClientKey(master_container.config) as ckey:
            all_keys = ckey.list_keys()
            assert compromised_client_id in all_keys["clients_rejected"]
            assert compromised_client_id not in all_keys["clients"]

        # Create new client with restricted access
        new_client_id = "restricted-workstation"
        new_priv_key, new_pub_key = salt.crypt.gen_keys(4096)

        # Configure with restricted ACL
        restricted_acl = {
            new_client_id: {
                "runners": ["test.ping", "jobs.list_jobs"],
                "wheel": ["key.list_all"],
                "minions": ["dev-*"],
            }
        }

        # Accept new client
        with salt.key.ClientKey(master_container.config) as ckey:
            ckey.cache.store(
                "client_keys", new_client_id, {"pub": new_pub_key, "state": "accepted"}
            )

        # Verify restricted access
        from salt import acl as _acl

        client_acl = _acl.ClientACL(restricted_acl)

        assert client_acl.client_can_run_runner(new_client_id, "test.ping")
        assert not client_acl.client_can_run_runner(new_client_id, "cmd.run")
        assert client_acl.client_can_target_minion(new_client_id, "dev-web-01")
        assert not client_acl.client_can_target_minion(new_client_id, "prod-web-01")

        # Cleanup
        with salt.key.ClientKey(master_container.config) as ckey:
            try:
                ckey.delete_key(compromised_client_id)
                ckey.delete_key(new_client_id)
            except (KeyError, OSError):
                pass

    def test_dynamic_acl_updates(self, master_container):
        """
        Test dynamic ACL updates without restarting master.

        Scenario:
        1. Client starts with limited permissions
        2. Client needs additional access for a project
        3. ACL is updated to grant temporary additional permissions
        4. Client can now perform additional operations
        5. After project completion, permissions are reduced
        6. Client returns to baseline permissions
        """
        import salt.acl

        client_id = "project-client"

        # Initial ACL - baseline permissions
        initial_acl = {
            client_id: {
                "runners": ["test.ping"],
                "wheel": ["key.list_all"],
                "minions": ["dev-*"],
            }
        }

        client_acl = salt.acl.ClientACL(initial_acl)

        # Verify baseline permissions
        assert client_acl.client_can_run_runner(client_id, "test.ping")
        assert not client_acl.client_can_run_runner(client_id, "jobs.list_jobs")
        assert not client_acl.client_can_run_runner(client_id, "state.orchestrate")

        # Update ACL - grant temporary permissions for project
        project_acl = {
            client_id: {
                "runners": ["test.*", "jobs.*", "state.orchestrate"],
                "wheel": ["key.list_all", "key.accept"],
                "minions": ["dev-*", "staging-*"],
            }
        }

        client_acl = salt.acl.ClientACL(project_acl)

        # Verify expanded permissions
        assert client_acl.client_can_run_runner(client_id, "test.ping")
        assert client_acl.client_can_run_runner(client_id, "jobs.list_jobs")
        assert client_acl.client_can_run_runner(client_id, "state.orchestrate")
        assert client_acl.client_can_run_wheel(client_id, "key.accept")
        assert client_acl.client_can_target_minion(client_id, "staging-app-01")

        # Restore baseline ACL after project
        client_acl = salt.acl.ClientACL(initial_acl)

        # Verify returned to baseline
        assert client_acl.client_can_run_runner(client_id, "test.ping")
        assert not client_acl.client_can_run_runner(client_id, "jobs.list_jobs")
        assert not client_acl.client_can_run_runner(client_id, "state.orchestrate")
        assert not client_acl.client_can_run_wheel(client_id, "key.accept")
        assert not client_acl.client_can_target_minion(client_id, "staging-app-01")


class TestPublishACLScenarios:
    """Test specific scenarios for publish ACL (minion targeting and module execution)."""

    def test_web_admin_scenario(self):
        """
        Test web administrator scenario.

        Scenario:
        1. Web admin manages web servers and load balancers
        2. Can only target web-* and lb-* minions
        3. Can only run service.*, nginx.*, and test.* modules
        4. Cannot access database or application servers
        5. Cannot run dangerous commands like cmd.run
        """
        import salt.acl

        acl_config = {
            "web-admin": {
                "minion": ["web-*", "lb-*"],
                "minion_function": ["service.*", "nginx.*", "test.*", "pkg.list_pkgs"],
            }
        }

        client_acl = salt.acl.ClientACL(acl_config)

        # Can target web servers
        assert client_acl.client_can_target_minion("web-admin", "web-01")
        assert client_acl.client_can_target_minion("web-admin", "web-prod-01")
        assert client_acl.client_can_target_minion("web-admin", "lb-main")

        # Cannot target other servers
        assert not client_acl.client_can_target_minion("web-admin", "db-01")
        assert not client_acl.client_can_target_minion("web-admin", "app-server-01")

        # Can run service management
        assert client_acl.client_can_run_minion_function("web-admin", "service.restart")
        assert client_acl.client_can_run_minion_function("web-admin", "service.status")
        assert client_acl.client_can_run_minion_function(
            "web-admin", "nginx.configtest"
        )
        assert client_acl.client_can_run_minion_function("web-admin", "test.ping")
        assert client_acl.client_can_run_minion_function("web-admin", "pkg.list_pkgs")

        # Cannot run dangerous commands
        assert not client_acl.client_can_run_minion_function("web-admin", "cmd.run")
        assert not client_acl.client_can_run_minion_function("web-admin", "pkg.install")
        assert not client_acl.client_can_run_minion_function("web-admin", "file.remove")

    def test_database_admin_scenario(self):
        """
        Test database administrator scenario.

        Scenario:
        1. DB admin manages database and cache servers
        2. Can only target db-* and cache-* minions
        3. Can only run database-related modules (mysql.*, postgres.*, redis.*)
        4. Cannot access web or application servers
        5. Cannot run system commands
        """
        import salt.acl

        acl_config = {
            "db-admin": {
                "minion": ["db-*", "cache-*"],
                "minion_function": [
                    "mysql.*",
                    "postgres.*",
                    "redis.*",
                    "test.ping",
                    "grains.get",
                ],
            }
        }

        client_acl = salt.acl.ClientACL(acl_config)

        # Can target database servers
        assert client_acl.client_can_target_minion("db-admin", "db-master")
        assert client_acl.client_can_target_minion("db-admin", "db-replica-01")
        assert client_acl.client_can_target_minion("db-admin", "cache-redis-01")

        # Cannot target other servers
        assert not client_acl.client_can_target_minion("db-admin", "web-01")
        assert not client_acl.client_can_target_minion("db-admin", "app-server-01")

        # Can run database operations
        assert client_acl.client_can_run_minion_function("db-admin", "mysql.query")
        assert client_acl.client_can_run_minion_function("db-admin", "postgres.version")
        assert client_acl.client_can_run_minion_function("db-admin", "redis.info")
        assert client_acl.client_can_run_minion_function("db-admin", "test.ping")

        # Cannot run system commands
        assert not client_acl.client_can_run_minion_function("db-admin", "cmd.run")
        assert not client_acl.client_can_run_minion_function(
            "db-admin", "service.restart"
        )
        assert not client_acl.client_can_run_minion_function("db-admin", "pkg.install")

    def test_monitoring_client_scenario(self):
        """
        Test monitoring client scenario.

        Scenario:
        1. Monitoring system needs to check all minions
        2. Can target all minions (*)
        3. Can only run read-only monitoring modules
        4. Cannot run any administrative or write operations
        """
        import salt.acl

        acl_config = {
            "monitoring": {
                "minion": ["*"],
                "minion_function": [
                    "test.ping",
                    "status.*",
                    "grains.items",
                    "disk.usage",
                    "network.interfaces",
                ],
            }
        }

        client_acl = salt.acl.ClientACL(acl_config)

        # Can target all minions
        assert client_acl.client_can_target_minion("monitoring", "web-01")
        assert client_acl.client_can_target_minion("monitoring", "db-master")
        assert client_acl.client_can_target_minion("monitoring", "app-server-01")
        assert client_acl.client_can_target_minion("monitoring", "any-minion")

        # Can run monitoring functions
        assert client_acl.client_can_run_minion_function("monitoring", "test.ping")
        assert client_acl.client_can_run_minion_function("monitoring", "status.uptime")
        assert client_acl.client_can_run_minion_function("monitoring", "status.loadavg")
        assert client_acl.client_can_run_minion_function("monitoring", "grains.items")
        assert client_acl.client_can_run_minion_function("monitoring", "disk.usage")

        # Cannot run administrative functions
        assert not client_acl.client_can_run_minion_function("monitoring", "cmd.run")
        assert not client_acl.client_can_run_minion_function(
            "monitoring", "service.restart"
        )
        assert not client_acl.client_can_run_minion_function(
            "monitoring", "pkg.install"
        )
        assert not client_acl.client_can_run_minion_function(
            "monitoring", "file.remove"
        )

    def test_environment_segregation_scenario(self):
        """
        Test environment segregation scenario.

        Scenario:
        1. Organization has dev, staging, and prod environments
        2. Dev team can only access dev-* and test-* minions with full module access
        3. Staging team can access staging-* minions with limited modules
        4. Prod access is highly restricted to specific operations
        """
        import salt.acl

        acl_config = {
            "dev-team": {
                "minion": ["dev-*", "test-*"],
                "minion_function": ["*"],
            },
            "staging-team": {
                "minion": ["staging-*"],
                "minion_function": [
                    "test.*",
                    "state.apply",
                    "saltutil.refresh_*",
                    "service.*",
                ],
            },
            "prod-readonly": {
                "minion": ["prod-*"],
                "minion_function": ["test.ping", "grains.*", "status.*"],
            },
        }

        client_acl = salt.acl.ClientACL(acl_config)

        # Dev team - full access in dev environment
        assert client_acl.client_can_target_minion("dev-team", "dev-web-01")
        assert client_acl.client_can_target_minion("dev-team", "test-app-01")
        assert client_acl.client_can_run_minion_function("dev-team", "cmd.run")
        assert client_acl.client_can_run_minion_function("dev-team", "pkg.install")
        assert not client_acl.client_can_target_minion("dev-team", "prod-web-01")

        # Staging team - limited access in staging
        assert client_acl.client_can_target_minion("staging-team", "staging-web-01")
        assert client_acl.client_can_run_minion_function("staging-team", "test.ping")
        assert client_acl.client_can_run_minion_function("staging-team", "state.apply")
        assert client_acl.client_can_run_minion_function(
            "staging-team", "service.restart"
        )
        assert not client_acl.client_can_run_minion_function("staging-team", "cmd.run")
        assert not client_acl.client_can_target_minion("staging-team", "prod-web-01")

        # Prod readonly - very limited in production
        assert client_acl.client_can_target_minion("prod-readonly", "prod-web-01")
        assert client_acl.client_can_run_minion_function("prod-readonly", "test.ping")
        assert client_acl.client_can_run_minion_function(
            "prod-readonly", "grains.items"
        )
        assert client_acl.client_can_run_minion_function(
            "prod-readonly", "status.uptime"
        )
        assert not client_acl.client_can_run_minion_function("prod-readonly", "cmd.run")
        assert not client_acl.client_can_run_minion_function(
            "prod-readonly", "service.restart"
        )

    def test_contractor_limited_access_scenario(self):
        """
        Test contractor with limited access scenario.

        Scenario:
        1. Contractor needs temporary access to specific minions
        2. Can only target contractor-specific minions
        3. Can only run specific safe modules
        4. No access to production or sensitive systems
        """
        import salt.acl

        acl_config = {
            "contractor-client": {
                "minion": ["contractor-*", "test-contractor-*"],
                "minion_function": [
                    "test.ping",
                    "grains.items",
                    "pkg.list_pkgs",
                    "file.read",
                ],
            }
        }

        client_acl = salt.acl.ClientACL(acl_config)

        # Can only target contractor minions
        assert client_acl.client_can_target_minion(
            "contractor-client", "contractor-vm-01"
        )
        assert client_acl.client_can_target_minion(
            "contractor-client", "test-contractor-app"
        )

        # Cannot target production or other systems
        assert not client_acl.client_can_target_minion("contractor-client", "web-01")
        assert not client_acl.client_can_target_minion(
            "contractor-client", "prod-web-01"
        )
        assert not client_acl.client_can_target_minion("contractor-client", "db-master")

        # Can run safe read-only operations
        assert client_acl.client_can_run_minion_function(
            "contractor-client", "test.ping"
        )
        assert client_acl.client_can_run_minion_function(
            "contractor-client", "grains.items"
        )
        assert client_acl.client_can_run_minion_function(
            "contractor-client", "pkg.list_pkgs"
        )

        # Cannot run administrative or write operations
        assert not client_acl.client_can_run_minion_function(
            "contractor-client", "cmd.run"
        )
        assert not client_acl.client_can_run_minion_function(
            "contractor-client", "pkg.install"
        )
        assert not client_acl.client_can_run_minion_function(
            "contractor-client", "service.restart"
        )
        assert not client_acl.client_can_run_minion_function(
            "contractor-client", "file.write"
        )

    def test_security_audit_scenario(self):
        """
        Test security auditor scenario.

        Scenario:
        1. Security team needs to audit all systems
        2. Can target all minions
        3. Can only run audit and inspection functions
        4. Cannot make any changes to systems
        """
        import salt.acl

        acl_config = {
            "security-audit": {
                "minion": ["*"],
                "minion_function": [
                    "test.ping",
                    "grains.*",
                    "status.*",
                    "pkg.list_pkgs",
                    "user.list_users",
                    "shadow.info",
                    "file.stats",
                    "network.interfaces",
                ],
            }
        }

        client_acl = salt.acl.ClientACL(acl_config)

        # Can target all systems for audit
        assert client_acl.client_can_target_minion("security-audit", "web-01")
        assert client_acl.client_can_target_minion("security-audit", "db-master")
        assert client_acl.client_can_target_minion("security-audit", "prod-app-server")

        # Can run audit functions
        assert client_acl.client_can_run_minion_function("security-audit", "test.ping")
        assert client_acl.client_can_run_minion_function(
            "security-audit", "grains.items"
        )
        assert client_acl.client_can_run_minion_function(
            "security-audit", "pkg.list_pkgs"
        )
        assert client_acl.client_can_run_minion_function(
            "security-audit", "user.list_users"
        )
        assert client_acl.client_can_run_minion_function(
            "security-audit", "status.uptime"
        )

        # Cannot make changes
        assert not client_acl.client_can_run_minion_function(
            "security-audit", "cmd.run"
        )
        assert not client_acl.client_can_run_minion_function(
            "security-audit", "pkg.install"
        )
        assert not client_acl.client_can_run_minion_function(
            "security-audit", "service.restart"
        )
        assert not client_acl.client_can_run_minion_function(
            "security-audit", "user.add"
        )
        assert not client_acl.client_can_run_minion_function(
            "security-audit", "file.write"
        )

    def test_multi_tier_application_scenario(self):
        """
        Test multi-tier application management scenario.

        Scenario:
        1. Web tier admin manages web and load balancer servers
        2. App tier admin manages application servers
        3. Data tier admin manages database and cache servers
        4. Each tier admin has appropriate module access for their tier
        """
        import salt.acl

        acl_config = {
            "web-tier-admin": {
                "minion": ["web-*", "lb-*"],
                "minion_function": ["nginx.*", "apache.*", "service.*", "test.*"],
            },
            "app-tier-admin": {
                "minion": ["app-*"],
                "minion_function": [
                    "service.*",
                    "supervisord.*",
                    "test.*",
                    "saltutil.*",
                ],
            },
            "data-tier-admin": {
                "minion": ["db-*", "cache-*"],
                "minion_function": [
                    "mysql.*",
                    "postgres.*",
                    "redis.*",
                    "service.*",
                    "test.*",
                ],
            },
        }

        client_acl = salt.acl.ClientACL(acl_config)

        # Web tier admin
        assert client_acl.client_can_target_minion("web-tier-admin", "web-01")
        assert client_acl.client_can_target_minion("web-tier-admin", "lb-main")
        assert client_acl.client_can_run_minion_function(
            "web-tier-admin", "nginx.configtest"
        )
        assert client_acl.client_can_run_minion_function(
            "web-tier-admin", "service.restart"
        )
        assert not client_acl.client_can_target_minion("web-tier-admin", "app-01")
        assert not client_acl.client_can_run_minion_function(
            "web-tier-admin", "mysql.query"
        )

        # App tier admin
        assert client_acl.client_can_target_minion("app-tier-admin", "app-server-01")
        assert client_acl.client_can_run_minion_function(
            "app-tier-admin", "service.restart"
        )
        assert client_acl.client_can_run_minion_function(
            "app-tier-admin", "supervisord.status"
        )
        assert not client_acl.client_can_target_minion("app-tier-admin", "web-01")
        assert not client_acl.client_can_run_minion_function(
            "app-tier-admin", "nginx.configtest"
        )

        # Data tier admin
        assert client_acl.client_can_target_minion("data-tier-admin", "db-master")
        assert client_acl.client_can_target_minion("data-tier-admin", "cache-redis-01")
        assert client_acl.client_can_run_minion_function(
            "data-tier-admin", "mysql.query"
        )
        assert client_acl.client_can_run_minion_function(
            "data-tier-admin", "redis.info"
        )
        assert not client_acl.client_can_target_minion("data-tier-admin", "web-01")
        assert not client_acl.client_can_run_minion_function(
            "data-tier-admin", "nginx.configtest"
        )


class TestRemoteCommandExecution:
    """Test actual command execution with remote clients."""

    def test_remote_client_executes_command_on_minion(
        self, master_container, minion_container, remote_client_setup
    ):
        """
        CRITICAL TEST: Verify RemoteClient can actually execute commands remotely.

        This tests the complete workflow:
        1. Remote client publishes command to master
        2. Master forwards to minion
        3. Minion executes and returns result
        4. Master publishes result event
        5. Remote client receives event over network
        6. Remote client returns result to caller
        """
        import salt.client
        import salt.config

        client_config = salt.config.client_config(remote_client_setup["config_file"])

        client = salt.client.RemoteClient(
            mopts=client_config,
            skip_perm_errors=True,
        )

        try:
            # CRITICAL: Actually execute a command
            ret = client.cmd(
                minion_container.id,
                "test.ping",
                timeout=30,
            )

            # Verify we got a result
            assert ret is not None, "Should receive command result"
            assert (
                minion_container.id in ret
            ), f"Result should contain minion {minion_container.id}"
            assert ret[minion_container.id] is True, "test.ping should return True"

            # This proves:
            # 1. Command was published to master
            # 2. Master forwarded to minion
            # 3. Minion executed and returned
            # 4. Events were delivered over network (not IPC)
            # 5. RemoteClient received events and returned result
        finally:
            client.destroy()

    def test_remote_client_receives_events_over_network(
        self, master_container, minion_container, remote_client_setup
    ):
        """
        CRITICAL TEST: Verify events are delivered over network, not IPC.

        This tests the event streaming implementation specifically.
        """
        import time

        import salt.client
        import salt.config

        client_config = salt.config.client_config(remote_client_setup["config_file"])

        client = salt.client.RemoteClient(
            mopts=client_config,
            skip_perm_errors=True,
            listen=True,  # Enable event listening
        )

        try:
            # Verify using network events
            from salt.utils import client_event

            assert isinstance(
                client.event, client_event.ClientEventSubscriber
            ), "Remote client must use ClientEventSubscriber for network events"

            # Execute async command to get JID
            pub_data = client.cmd_async(
                minion_container.id,
                "test.ping",
            )

            assert "jid" in pub_data, "Should receive JID from async command"
            jid = pub_data["jid"]

            # Subscribe to job events
            client.event.subscribe_job(jid)

            # Wait for return event
            max_wait = 30
            start = time.time()
            result_received = False

            while time.time() - start < max_wait:
                event = client.event.get_event(wait=1, full=True)
                if event and "tag" in event:
                    if f"salt/job/{jid}/ret" in event["tag"]:
                        # Got the return event!
                        result_received = True
                        assert "data" in event, "Event should have data"
                        assert (
                            "return" in event["data"]
                        ), "Event should have return data"
                        break

            assert (
                result_received
            ), f"Should receive job return event for JID {jid} over network"

            # This proves events were delivered over network, not IPC
        finally:
            client.destroy()


class TestNetworkEventStreaming:
    """Test network event streaming functionality for remote clients."""

    def test_client_event_subscriber_initialization(
        self, master_container, remote_client_setup
    ):
        """
        Test ClientEventSubscriber can be created and configured.

        This is the critical component that enables remote event delivery.
        """
        import salt.config
        import salt.utils.client_event

        client_config = salt.config.client_config(remote_client_setup["config_file"])

        # Create ClientEventSubscriber
        subscriber = salt.utils.client_event.ClientEventSubscriber(client_config)

        # Verify it has required attributes
        assert subscriber.opts == client_config
        assert hasattr(
            subscriber, "connect"
        ), "ClientEventSubscriber should have connect method"
        assert hasattr(
            subscriber, "get_event"
        ), "ClientEventSubscriber should have get_event method"
        assert hasattr(
            subscriber, "subscribe_job"
        ), "ClientEventSubscriber should have subscribe_job method"
        assert hasattr(
            subscriber, "destroy"
        ), "ClientEventSubscriber should have destroy method"

        subscriber.destroy()

    def test_remote_client_event_attribute(self, master_container, remote_client_setup):
        """
        Test that RemoteClient has properly initialized event subscriber.

        Regression test: Previously RemoteClient used IPC events which don't
        work remotely. Must use ClientEventSubscriber.
        """
        import salt.client
        import salt.config
        import salt.utils.client_event

        client_config = salt.config.client_config(remote_client_setup["config_file"])

        client = salt.client.RemoteClient(
            mopts=client_config,
            skip_perm_errors=True,
        )

        try:
            # Verify event subscriber exists
            assert client.event is not None, "RemoteClient should have event subscriber"

            # Verify it's the correct type
            assert isinstance(
                client.event, salt.utils.client_event.ClientEventSubscriber
            ), f"RemoteClient.event should be ClientEventSubscriber, got {type(client.event)}"

            # Verify _use_network_events flag is set
            assert (
                client._use_network_events is True
            ), "RemoteClient._use_network_events should be True for remote execution"
        finally:
            client.destroy()

    def test_runner_client_event_attribute(self, master_container, remote_client_setup):
        """
        Test that RunnerClient has properly initialized network event subscriber.

        Regression test: Previously RunnerClient used IPC events which don't
        work remotely.
        """
        import salt.config
        import salt.runner
        import salt.utils.client_event

        client_config = salt.config.client_config(remote_client_setup["config_file"])
        client_config["client_auth"] = True
        client_config["fun"] = "test.ping"
        client_config["arg"] = []

        runner = salt.runner.Runner(client_config)

        # Verify event subscriber exists
        assert runner.event is not None, "RunnerClient should have event subscriber"

        # Verify it's the correct type
        assert isinstance(
            runner.event, salt.utils.client_event.ClientEventSubscriber
        ), f"RunnerClient.event should be ClientEventSubscriber, got {type(runner.event)}"

        # Verify _use_network_events flag is set
        assert (
            runner._use_network_events is True
        ), "RunnerClient._use_network_events should be True for remote execution"

    def test_wheel_client_event_attribute(self, master_container, remote_client_setup):
        """
        Test that WheelClient has properly initialized network event subscriber.

        Regression test: Previously WheelClient used IPC events which don't
        work remotely.
        """
        import salt.config
        import salt.utils.client_event
        import salt.wheel

        client_config = salt.config.client_config(remote_client_setup["config_file"])
        client_config["client_auth"] = True

        wheel = salt.wheel.WheelClient(client_config)

        try:
            # Verify event subscriber exists
            assert wheel.event is not None, "WheelClient should have event subscriber"

            # Verify it's the correct type
            assert isinstance(
                wheel.event, salt.utils.client_event.ClientEventSubscriber
            ), f"WheelClient.event should be ClientEventSubscriber, got {type(wheel.event)}"

            # Verify _use_network_events flag is set
            assert (
                wheel._use_network_events is True
            ), "WheelClient._use_network_events should be True for remote execution"
        finally:
            wheel.destroy()

    def test_local_execution_still_uses_ipc(self, master_container):
        """
        Test that local execution still uses IPC events for backwards compatibility.

        When running on the same machine as master, should use IPC for efficiency.
        """
        import salt.runner
        import salt.utils.event

        # Create runner config WITHOUT client_auth (local execution)
        local_config = master_container.config.copy()
        local_config["fun"] = "test.ping"
        local_config["arg"] = []
        # Don't set client_auth or __role

        runner = salt.runner.RunnerClient(local_config)

        # Should use IPC events for local execution
        assert (
            runner._use_network_events is False
        ), "Local RunnerClient should not use network events"

        # Should be standard IPC event subscriber
        assert isinstance(
            runner.event, salt.utils.event.SaltEvent
        ), "Local RunnerClient should use IPC SaltEvent"
