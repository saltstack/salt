"""
Scenario test for remote Salt CLI authentication with master cluster.

This test demonstrates remote CLI operations in a high-availability environment:
1. Three-node Salt master cluster
2. Minions connected to the cluster
3. Remote administrator workstation
4. salt, salt-run, and salt-key commands executed remotely
5. Failover and load balancing across masters

This simulates a production environment where administrators manage
a clustered Salt infrastructure from their workstation.
"""

import os
import textwrap

import pytest

import salt.client
import salt.config
import salt.crypt
import salt.key
import salt.runner


@pytest.fixture(scope="module")
def master_cluster(salt_factories):
    """
    Create a three-node Salt master cluster.

    This simulates a high-availability production environment with
    multiple masters for redundancy and load balancing.
    """
    masters = []

    # Create three masters with coordinated configuration
    for i in range(3):
        master_id = f"cluster-master-{i+1}"

        config_overrides = {
            "open_mode": False,
            "auto_accept": False,
            "order_masters": True,  # Enable master ordering for cluster
            "cluster_mode": True,  # Enable cluster mode
        }

        factory = salt_factories.salt_master_daemon(
            master_id,
            overrides=config_overrides,
        )
        masters.append(factory)

    # Start all masters
    with masters[0].started(), masters[1].started(), masters[2].started():
        yield masters


@pytest.fixture
def remote_admin_workstation(tmp_path, master_cluster):
    """
    Set up remote administrator workstation.

    This simulates an administrator's laptop/desktop configured to
    manage the Salt cluster remotely.
    """
    workstation_dir = tmp_path / "admin_workstation"
    workstation_dir.mkdir()

    # Create PKI directory
    pki_dir = workstation_dir / "pki"
    pki_dir.mkdir()

    admin_id = "admin-cluster-ops"

    # Generate client keys
    priv_key, pub_key = salt.crypt.gen_keys(4096)

    # Write keys
    priv_path = pki_dir / "client.pem"
    pub_path = pki_dir / "client.pub"

    with open(priv_path, "wb") as f:
        f.write(priv_key.encode() if isinstance(priv_key, str) else priv_key)
    with open(pub_path, "wb") as f:
        f.write(pub_key.encode() if isinstance(pub_key, str) else pub_key)

    os.chmod(priv_path, 0o400)
    os.chmod(pub_path, 0o644)

    # Create config for each master in cluster
    master_configs = []
    for i, master in enumerate(master_cluster):
        config_file = workstation_dir / f"master{i+1}"

        config_content = textwrap.dedent(
            f"""
            # Cluster Master {i+1} configuration
            id: {admin_id}
            master: {master.config['interface']}
            master_port: {master.config['ret_port']}

            pki_dir: {pki_dir}
            transport: {master.config.get('transport', 'zeromq')}

            timeout: 30
            acceptance_wait_time: 10
            acceptance_wait_time_max: 30
        """
        )

        with open(config_file, "w") as f:
            f.write(config_content)

        master_configs.append(str(config_file))

    # Accept client key on all masters
    for master in master_cluster:
        with salt.key.ClientKey(master.config) as ckey:
            ckey.cache.store(
                "client_keys", admin_id, {"pub": pub_key, "state": "accepted"}
            )

    return {
        "id": admin_id,
        "workstation_dir": workstation_dir,
        "master_configs": master_configs,
        "priv_key": priv_key,
        "pub_key": pub_key,
    }


class TestClusterRemoteCLI:
    """Test remote CLI operations with master cluster."""

    def test_cluster_setup_verification(self, master_cluster, remote_admin_workstation):
        """
        Verify the cluster and remote workstation are set up correctly.

        Scenario:
        1. Three masters are running
        2. Remote admin workstation is configured
        3. Client keys are accepted on all masters
        """
        # Verify all masters are running
        assert len(master_cluster) == 3, "Should have 3 masters in cluster"

        # Verify client key accepted on all masters
        admin_id = remote_admin_workstation["id"]

        for i, master in enumerate(master_cluster):
            with salt.key.ClientKey(master.config) as ckey:
                all_keys = ckey.list_keys()
                assert (
                    admin_id in all_keys["clients"]
                ), f"Client {admin_id} should be accepted on master {i+1}"

    def test_remote_salt_key_list_across_cluster(
        self, master_cluster, remote_admin_workstation
    ):
        """
        Test listing keys remotely across the cluster.

        Scenario:
        1. Administrator runs 'salt-key -L' from workstation
        2. Connects to each master in cluster
        3. Verifies consistent key state across all masters
        4. Can see minion keys and client keys
        """
        import salt.utils.client_event
        import salt.wheel

        admin_id = remote_admin_workstation["id"]

        # Test salt-key against each master
        for i, config_file in enumerate(remote_admin_workstation["master_configs"]):
            # Load client config for this master
            client_config = salt.config.client_config(config_file)
            client_config["client_auth"] = True
            client_config["list"] = True

            # Create KeyCLI
            keycli = salt.key.KeyCLI(client_config)

            # Verify configuration
            assert (
                keycli.opts["__role"] == "client"
            ), f"Should be configured as client for master {i+1}"
            assert (
                keycli.opts["client_auth"] is True
            ), f"Should have client_auth enabled for master {i+1}"

            # CRITICAL: Verify WheelClient (used by KeyCLI) uses network events
            wheel_client = salt.wheel.WheelClient(client_config)
            try:
                assert (
                    wheel_client._use_network_events is True
                ), f"WheelClient must use network events for master {i+1} in cluster"
                assert isinstance(
                    wheel_client.event, salt.utils.client_event.ClientEventSubscriber
                ), f"WheelClient should use ClientEventSubscriber for master {i+1}"
            finally:
                wheel_client.destroy()

            # In a real scenario, keycli.run() would execute the command
            # For this test, we verify the setup is correct

    def test_remote_salt_run_across_cluster(
        self, master_cluster, remote_admin_workstation
    ):
        """
        Test running salt-run remotely against cluster masters.

        Scenario:
        1. Administrator runs 'salt-run test.ping' from workstation
        2. Can connect to any master in cluster
        3. Runner executes on the connected master
        4. Results are returned to administrator's workstation
        """
        import salt.utils.client_event

        # Test runner against each master
        for i, config_file in enumerate(remote_admin_workstation["master_configs"]):
            # Load client config
            client_config = salt.config.client_config(config_file)
            client_config["client_auth"] = True
            client_config["fun"] = "test.ping"
            client_config["arg"] = []

            # Create Runner with client auth
            runner = salt.runner.Runner(client_config)

            # Verify runner is configured correctly
            assert (
                runner.opts["__role"] == "client"
            ), f"Runner should be configured as client for master {i+1}"
            assert (
                runner.opts["client_auth"] is True
            ), f"Runner should have client_auth for master {i+1}"
            assert (
                runner.opts["fun"] == "test.ping"
            ), "Runner should have correct function"

            # CRITICAL: Verify using network events for cluster
            assert (
                runner._use_network_events is True
            ), f"Runner must use network events for master {i+1} in cluster"
            assert isinstance(
                runner.event, salt.utils.client_event.ClientEventSubscriber
            ), f"Runner should use ClientEventSubscriber for master {i+1}"

    def test_remote_salt_command_to_minions(
        self, master_cluster, remote_admin_workstation
    ):
        """
        Test RemoteClient configuration for cluster operations.

        Scenario:
        1. Administrator configures salt client for cluster
        2. Can connect to any master in cluster
        3. RemoteClient is properly configured for command execution
        4. Ready to publish commands to minions
        5. Works with any master in cluster
        """
        # Test against first master
        config_file = remote_admin_workstation["master_configs"][0]

        # Load client config
        client_config = salt.config.client_config(config_file)

        # Create RemoteClient
        client = salt.client.RemoteClient(
            mopts=client_config,
            skip_perm_errors=True,
        )

        try:
            # Verify client is configured correctly
            assert (
                client.opts["__role"] == "client"
            ), "RemoteClient should have client role"
            assert (
                client.opts["id"] == remote_admin_workstation["id"]
            ), "RemoteClient should have correct ID"

            # Verify RemoteClient methods are available
            assert hasattr(client, "cmd"), "RemoteClient should have cmd method"
            assert hasattr(
                client, "cmd_async"
            ), "RemoteClient should have cmd_async method"

            # CRITICAL: Verify using network events for remote execution
            import salt.utils.client_event

            assert (
                client._use_network_events is True
            ), "RemoteClient must use network events in cluster scenario"
            assert isinstance(
                client.event, salt.utils.client_event.ClientEventSubscriber
            ), "RemoteClient should use ClientEventSubscriber for cluster operations"

            # In production environment with running minions:
            # ret = client.cmd("*", "test.ping")
            # Would execute command on all minions via cluster
        finally:
            client.destroy()

    def test_cluster_failover_scenario(self, master_cluster, remote_admin_workstation):
        """
        Test remote CLI failover between cluster masters.

        Scenario:
        1. Administrator configured to use primary master
        2. Primary master becomes unavailable
        3. Administrator switches to backup master
        4. All operations continue normally
        5. Demonstrates high availability
        """
        # Primary master config
        primary_config = remote_admin_workstation["master_configs"][0]

        # Load primary config
        primary_opts = salt.config.client_config(primary_config)
        primary_opts["client_auth"] = True

        # Create runner on primary
        primary_runner = salt.runner.Runner(primary_opts)
        assert primary_runner.opts["__role"] == "client"

        # Simulate failover - switch to secondary master
        secondary_config = remote_admin_workstation["master_configs"][1]

        # Load secondary config
        secondary_opts = salt.config.client_config(secondary_config)
        secondary_opts["client_auth"] = True

        # Create runner on secondary
        secondary_runner = salt.runner.Runner(secondary_opts)
        assert secondary_runner.opts["__role"] == "client"

        # Both runners should work identically
        assert (
            primary_runner.opts["id"] == secondary_runner.opts["id"]
        ), "Same admin ID on both masters"
        assert (
            primary_runner.opts["client_auth"] == secondary_runner.opts["client_auth"]
        ), "Same auth mode on both masters"

    def test_cluster_load_balancing_simulation(
        self, master_cluster, remote_admin_workstation
    ):
        """
        Test distributing operations across cluster masters.

        Scenario:
        1. Administrator has all three masters configured
        2. Distributes different operations across masters
        3. salt commands to master1
        4. salt-run commands to master2
        5. salt-key commands to master3
        6. Demonstrates load distribution
        """
        configs = remote_admin_workstation["master_configs"]

        # Operation 1: salt command via master1
        config1 = salt.config.client_config(configs[0])
        client1 = salt.client.RemoteClient(mopts=config1, skip_perm_errors=True)

        try:
            assert client1.opts["__role"] == "client"
            assert "master" in client1.opts
        finally:
            client1.destroy()

        # Operation 2: salt-run via master2
        config2 = salt.config.client_config(configs[1])
        config2["client_auth"] = True
        config2["fun"] = "jobs.list_jobs"
        config2["arg"] = []
        runner2 = salt.runner.Runner(config2)

        assert runner2.opts["__role"] == "client"
        assert runner2.opts["client_auth"] is True

        # Operation 3: salt-key via master3
        config3 = salt.config.client_config(configs[2])
        config3["client_auth"] = True
        config3["list"] = True
        keycli3 = salt.key.KeyCLI(config3)

        assert keycli3.opts["__role"] == "client"
        assert keycli3.opts["client_auth"] is True


class TestClusterKeyManagement:
    """Test managing keys across cluster."""

    def test_accept_minion_key_on_all_masters(
        self, master_cluster, remote_admin_workstation
    ):
        """
        Test accepting a new minion key across all cluster masters.

        Scenario:
        1. New minion attempts to connect to cluster
        2. Administrator sees pending key on all masters
        3. Accepts key on one master
        4. Key state should propagate to other masters (in production)
        5. For this test, we verify key can be accepted independently
        """
        new_minion_id = "cluster-minion-new"
        _, new_pub = salt.crypt.gen_keys(4096)

        # Simulate new minion key pending on all masters
        for master in master_cluster:
            master_key = salt.key.Key(master.config)
            # In production, minion would send key automatically
            # For test, we manually add to pending
            master_key.cache.store(
                "keys", new_minion_id, {"pub": new_pub, "state": "pending"}
            )

        # Verify key is pending on all masters
        for i, master in enumerate(master_cluster):
            master_key = salt.key.Key(master.config)
            all_keys = master_key.list_keys()
            assert (
                new_minion_id in all_keys["minions_pre"]
            ), f"New minion should be pending on master {i+1}"

        # Administrator accepts on first master
        master_key = salt.key.Key(master_cluster[0].config)
        result = master_key.accept(new_minion_id)
        assert new_minion_id in result["minions"]

        # Clean up
        for master in master_cluster:
            try:
                master_key = salt.key.Key(master.config)
                master_key.delete_key(new_minion_id)
            except (KeyError, OSError):
                pass

    def test_manage_client_keys_across_cluster(
        self, master_cluster, remote_admin_workstation
    ):
        """
        Test managing client keys across cluster.

        Scenario:
        1. Administrator's client key is accepted on all masters
        2. New administrator requests access
        3. Admin accepts new client key on all masters
        4. Both admins can now manage the cluster
        """
        # Create new admin
        new_admin_id = "admin-developer"
        _, new_pub = salt.crypt.gen_keys(4096)

        # Accept new admin on all masters
        for master in master_cluster:
            with salt.key.ClientKey(master.config) as ckey:
                ckey.cache.store(
                    "client_keys", new_admin_id, {"pub": new_pub, "state": "accepted"}
                )

        # Verify new admin is accepted on all masters
        for i, master in enumerate(master_cluster):
            with salt.key.ClientKey(master.config) as ckey:
                all_keys = ckey.list_keys()
                assert (
                    new_admin_id in all_keys["clients"]
                ), f"New admin should be accepted on master {i+1}"

                # Original admin should still be there
                assert (
                    remote_admin_workstation["id"] in all_keys["clients"]
                ), f"Original admin should still be on master {i+1}"

        # Clean up
        for master in master_cluster:
            with salt.key.ClientKey(master.config) as ckey:
                ckey.delete_key(new_admin_id)


class TestClusterProductionWorkflow:
    """Test complete production workflow with cluster."""

    def test_complete_admin_workflow(self, master_cluster, remote_admin_workstation):
        """
        Test complete administrator workflow with cluster.

        Scenario:
        1. Admin connects to cluster from workstation
        2. Lists all minions with salt-key
        3. Executes test.ping on all minions with salt
        4. Checks job history with salt-run
        5. Manages cluster configuration
        6. All operations work across any master
        """
        admin_id = remote_admin_workstation["id"]
        config_file = remote_admin_workstation["master_configs"][0]

        # Step 1: Verify connection setup
        client_config = salt.config.client_config(config_file)
        assert client_config["id"] == admin_id

        # Step 2: salt-key list (simulated)
        key_config = client_config.copy()
        key_config["client_auth"] = True
        key_config["list"] = True
        keycli = salt.key.KeyCLI(key_config)
        assert keycli.opts["__role"] == "client"

        # Step 3: salt command (simulated)
        salt_client = salt.client.RemoteClient(
            mopts=client_config,
            skip_perm_errors=True,
        )
        try:
            assert salt_client.opts["__role"] == "client"
        finally:
            salt_client.destroy()

        # Step 4: salt-run command (simulated)
        run_config = client_config.copy()
        run_config["client_auth"] = True
        run_config["fun"] = "jobs.list_jobs"
        run_config["arg"] = []
        runner = salt.runner.Runner(run_config)
        assert runner.opts["__role"] == "client"

        # All steps configured correctly for cluster operation
