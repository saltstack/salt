"""
Integration tests for remote Salt CLI client ACL enforcement.

Tests the complete ACL enforcement flow for remote CLI clients:
- ACL enforcement for runners (salt-run)
- ACL enforcement for wheel functions (salt-key)
- Proper error messages for denied access
- Backward compatibility (no ACL = full access)
"""

import pytest

import salt.acl
import salt.crypt
import salt.key


@pytest.fixture
def acl_enabled_master(salt_factories):
    """
    Create a Salt master with ACL configuration enabled.
    """
    client_acl_config = {
        "admin-client": {
            "runner": ["*"],
            "wheel": ["*"],
        },
        "readonly-client": {
            "runner": ["test.ping", "jobs.list_jobs", "jobs.lookup_jid"],
            "wheel": ["key.list_all", "key.finger"],
        },
        "dev-client": {
            "runner": ["test.*", "jobs.*"],
            "wheel": ["key.list_all"],
        },
        "restricted-client": {
            "runner": ["test.*", "jobs.*"],
            "wheel": ["key.list_all", "key.finger"],
        },
    }

    config_overrides = {
        "open_mode": False,
        "auto_accept": False,
        "client_acl": client_acl_config,
        "client_acl_verify": True,
    }

    factory = salt_factories.salt_master_daemon(
        "acl-test-master",
        overrides=config_overrides,
    )

    with factory.started():
        yield factory


@pytest.fixture
def no_acl_master(salt_factories):
    """
    Create a Salt master without ACL configuration (backward compatibility).
    """
    config_overrides = {
        "open_mode": False,
        "auto_accept": False,
        "client_acl": {},
        "client_acl_verify": False,
    }

    factory = salt_factories.salt_master_daemon(
        "no-acl-test-master",
        overrides=config_overrides,
    )

    with factory.started():
        yield factory


@pytest.fixture
def setup_test_clients(acl_enabled_master):
    """
    Set up multiple test clients with different permission levels.
    """
    clients = {}

    for client_name in [
        "admin-client",
        "readonly-client",
        "dev-client",
        "restricted-client",
    ]:
        # Generate keys
        priv_key, pub_key = salt.crypt.gen_keys(4096)

        # Accept client key on master
        with salt.key.ClientKey(acl_enabled_master.config) as ckey:
            ckey.cache.store(
                "client_keys", client_name, {"pub": pub_key, "state": "accepted"}
            )

        clients[client_name] = {
            "id": client_name,
            "priv_key": priv_key,
            "pub_key": pub_key,
        }

    yield clients

    # Cleanup
    with salt.key.ClientKey(acl_enabled_master.config) as ckey:
        for client_name in clients:
            try:
                ckey.delete_key(client_name)
            except (KeyError, OSError):
                pass


class TestRunnerACLEnforcement:
    """Test ACL enforcement for runner functions."""

    def test_runner_allowed_for_admin(self, acl_enabled_master, setup_test_clients):
        """Test that admin client can execute any runner."""
        # Get ACL instance
        client_acl = salt.acl.ClientACL(acl_enabled_master.config.get("client_acl", {}))

        # Admin should be allowed to run anything
        assert client_acl.client_is_allowed("admin-client", "test.ping", "runner")
        assert client_acl.client_is_allowed("admin-client", "jobs.list_jobs", "runner")
        assert client_acl.client_is_allowed("admin-client", "cmd.run", "runner")
        assert client_acl.client_is_allowed(
            "admin-client", "state.orchestrate", "runner"
        )

    def test_runner_allowed_for_readonly(self, acl_enabled_master, setup_test_clients):
        """Test that readonly client can only execute allowed runners."""
        client_acl = salt.acl.ClientACL(acl_enabled_master.config.get("client_acl", {}))

        # Readonly should be allowed specific runners
        assert client_acl.client_is_allowed("readonly-client", "test.ping", "runner")
        assert client_acl.client_is_allowed(
            "readonly-client", "jobs.list_jobs", "runner"
        )
        assert client_acl.client_is_allowed(
            "readonly-client", "jobs.lookup_jid", "runner"
        )

    def test_runner_denied_for_readonly(self, acl_enabled_master, setup_test_clients):
        """Test that readonly client cannot execute disallowed runners."""
        client_acl = salt.acl.ClientACL(acl_enabled_master.config.get("client_acl", {}))

        # Readonly should NOT be allowed these runners
        assert not client_acl.client_is_allowed("readonly-client", "cmd.run", "runner")
        assert not client_acl.client_is_allowed(
            "readonly-client", "state.orchestrate", "runner"
        )
        assert not client_acl.client_is_allowed(
            "readonly-client", "file.read", "runner"
        )

    def test_runner_pattern_matching(self, acl_enabled_master, setup_test_clients):
        """Test runner pattern matching with wildcards."""
        client_acl = salt.acl.ClientACL(acl_enabled_master.config.get("client_acl", {}))

        # Dev client can run test.* and jobs.*
        assert client_acl.client_is_allowed("dev-client", "test.ping", "runner")
        assert client_acl.client_is_allowed("dev-client", "test.version", "runner")
        assert client_acl.client_is_allowed("dev-client", "jobs.list_jobs", "runner")
        assert client_acl.client_is_allowed("dev-client", "jobs.lookup_jid", "runner")

        # But not others
        assert not client_acl.client_is_allowed(
            "dev-client", "state.orchestrate", "runner"
        )


class TestWheelACLEnforcement:
    """Test ACL enforcement for wheel functions."""

    def test_wheel_allowed_for_admin(self, acl_enabled_master, setup_test_clients):
        """Test that admin client can execute any wheel function."""
        client_acl = salt.acl.ClientACL(acl_enabled_master.config.get("client_acl", {}))

        # Admin should be allowed to run anything
        assert client_acl.client_is_allowed("admin-client", "key.list_all", "wheel")
        assert client_acl.client_is_allowed("admin-client", "key.accept", "wheel")
        assert client_acl.client_is_allowed("admin-client", "key.delete", "wheel")
        assert client_acl.client_is_allowed("admin-client", "key.reject", "wheel")

    def test_wheel_allowed_for_readonly(self, acl_enabled_master, setup_test_clients):
        """Test that readonly client can only execute allowed wheel functions."""
        client_acl = salt.acl.ClientACL(acl_enabled_master.config.get("client_acl", {}))

        # Readonly should be allowed specific wheel functions
        assert client_acl.client_is_allowed("readonly-client", "key.list_all", "wheel")
        assert client_acl.client_is_allowed("readonly-client", "key.finger", "wheel")

    def test_wheel_denied_for_readonly(self, acl_enabled_master, setup_test_clients):
        """Test that readonly client cannot execute disallowed wheel functions."""
        client_acl = salt.acl.ClientACL(acl_enabled_master.config.get("client_acl", {}))

        # Readonly should NOT be allowed these wheel functions
        assert not client_acl.client_is_allowed(
            "readonly-client", "key.accept", "wheel"
        )
        assert not client_acl.client_is_allowed(
            "readonly-client", "key.delete", "wheel"
        )
        assert not client_acl.client_is_allowed(
            "readonly-client", "key.reject", "wheel"
        )


class TestACLErrorMessages:
    """Test that ACL denials return proper error messages."""

    def test_denied_runner_error_message(self, acl_enabled_master, setup_test_clients):
        """Test error message for denied runner execution."""
        client_acl = salt.acl.ClientACL(acl_enabled_master.config.get("client_acl", {}))

        # Check that permission is denied
        assert not client_acl.client_is_allowed("readonly-client", "cmd.run", "runner")

        # Get error message
        error_msg = client_acl.get_denial_message(
            "readonly-client", "runner", "cmd.run"
        )
        assert "readonly-client" in error_msg
        assert "cmd.run" in error_msg
        assert "not authorized" in error_msg.lower() or "denied" in error_msg.lower()

    def test_denied_wheel_error_message(self, acl_enabled_master, setup_test_clients):
        """Test error message for denied wheel execution."""
        client_acl = salt.acl.ClientACL(acl_enabled_master.config.get("client_acl", {}))

        # Check that permission is denied
        assert not client_acl.client_is_allowed(
            "readonly-client", "key.accept", "wheel"
        )

        # Error message should be informative
        error_msg = client_acl.get_denial_message(
            "readonly-client", "wheel", "key.accept"
        )
        assert "readonly-client" in error_msg
        assert "key.accept" in error_msg


class TestBackwardCompatibility:
    """Test backward compatibility with no ACL configuration."""

    def test_no_acl_allows_all_runners(self, no_acl_master):
        """Test that empty ACL config allows all runner execution."""
        client_acl = salt.acl.ClientACL(no_acl_master.config.get("client_acl", {}))

        # With no ACL, all should be allowed
        assert client_acl.client_is_allowed("any-client", "test.ping", "runner")
        assert client_acl.client_is_allowed("any-client", "cmd.run", "runner")
        assert client_acl.client_is_allowed("any-client", "state.orchestrate", "runner")

    def test_no_acl_allows_all_wheel(self, no_acl_master):
        """Test that empty ACL config allows all wheel execution."""
        client_acl = salt.acl.ClientACL(no_acl_master.config.get("client_acl", {}))

        # With no ACL, all should be allowed
        assert client_acl.client_is_allowed("any-client", "key.list_all", "wheel")
        assert client_acl.client_is_allowed("any-client", "key.accept", "wheel")
        assert client_acl.client_is_allowed("any-client", "key.delete", "wheel")


class TestMultipleClients:
    """Test scenarios with multiple clients having different permissions."""

    def test_different_permissions_for_different_clients(
        self, acl_enabled_master, setup_test_clients
    ):
        """Test that different clients have different permission levels."""
        client_acl = salt.acl.ClientACL(acl_enabled_master.config.get("client_acl", {}))

        # Admin can do everything
        assert client_acl.client_is_allowed("admin-client", "cmd.run", "runner")
        assert client_acl.client_is_allowed("admin-client", "key.delete", "wheel")

        # Readonly cannot
        assert not client_acl.client_is_allowed("readonly-client", "cmd.run", "runner")
        assert not client_acl.client_is_allowed(
            "readonly-client", "key.delete", "wheel"
        )

        # Dev has specific access
        assert client_acl.client_is_allowed("dev-client", "test.ping", "runner")
        assert not client_acl.client_is_allowed("dev-client", "cmd.run", "runner")

    def test_simultaneous_client_access(self, acl_enabled_master, setup_test_clients):
        """Test that multiple clients can be checked simultaneously."""
        client_acl = salt.acl.ClientACL(acl_enabled_master.config.get("client_acl", {}))

        # Multiple clients accessing same resource
        runner_name = "test.ping"

        admin_allowed = client_acl.client_is_allowed(
            "admin-client", runner_name, "runner"
        )
        readonly_allowed = client_acl.client_is_allowed(
            "readonly-client", runner_name, "runner"
        )
        dev_allowed = client_acl.client_is_allowed("dev-client", runner_name, "runner")

        # All should be allowed for test.ping
        assert admin_allowed
        assert readonly_allowed
        assert dev_allowed


class TestACLRevocation:
    """Test emergency ACL revocation scenarios."""

    def test_remove_client_access(self, acl_enabled_master, setup_test_clients):
        """Test removing a client's access by rejecting their key."""
        client_id = "readonly-client"

        # Initially, client is accepted
        with salt.key.ClientKey(acl_enabled_master.config) as ckey:
            all_keys = ckey.list_keys()
            assert client_id in all_keys["clients"]

        # Reject the client key
        with salt.key.ClientKey(acl_enabled_master.config) as ckey:
            result = ckey.reject(client_id, include_accepted=True)
            assert client_id in result["clients_rejected"]

        # Verify client is now rejected
        with salt.key.ClientKey(acl_enabled_master.config) as ckey:
            all_keys = ckey.list_keys()
            assert client_id in all_keys["clients_rejected"]
            assert client_id not in all_keys["clients"]

    def test_update_client_permissions(self, acl_enabled_master):
        """Test updating a client's permissions by modifying ACL config."""
        # Initial ACL
        initial_acl = {
            "dynamic-client": {
                "runner": ["test.ping"],
            }
        }
        client_acl = salt.acl.ClientACL(initial_acl)

        # Client can only run test.ping
        assert client_acl.client_is_allowed("dynamic-client", "test.ping", "runner")
        assert not client_acl.client_is_allowed(
            "dynamic-client", "jobs.list_jobs", "runner"
        )

        # Update ACL (simulating config reload)
        updated_acl = {
            "dynamic-client": {
                "runner": ["test.ping", "jobs.*"],
            }
        }
        client_acl = salt.acl.ClientACL(updated_acl)

        # Client can now run additional functions
        assert client_acl.client_is_allowed("dynamic-client", "test.ping", "runner")
        assert client_acl.client_is_allowed(
            "dynamic-client", "jobs.list_jobs", "runner"
        )


class TestUnknownClient:
    """Test behavior with unknown/unconfigured clients."""

    def test_unknown_client_denied_when_acl_exists(
        self, acl_enabled_master, setup_test_clients
    ):
        """Test that unknown clients are denied when ACL config exists."""
        client_acl = salt.acl.ClientACL(acl_enabled_master.config.get("client_acl", {}))

        # Unknown client should be denied
        assert not client_acl.client_is_allowed("unknown-client", "test.ping", "runner")
        assert not client_acl.client_is_allowed(
            "unknown-client", "key.list_all", "wheel"
        )

    def test_unknown_client_allowed_when_no_acl(self, no_acl_master):
        """Test that unknown clients are allowed when no ACL exists."""
        client_acl = salt.acl.ClientACL(no_acl_master.config.get("client_acl", {}))

        # Unknown client should be allowed (backward compatibility)
        assert client_acl.client_is_allowed("unknown-client", "test.ping", "runner")
        assert client_acl.client_is_allowed("unknown-client", "key.list_all", "wheel")


class TestPublishACLEnforcement:
    """Test ACL enforcement for publish operations (minion targeting and module execution)."""

    @pytest.fixture
    def publish_acl_master(self, salt_factories):
        """
        Create a Salt master with publish ACL configuration.
        """
        client_acl_config = {
            "admin-client": {
                "minion": ["*"],
                "minion_function": ["*"],
            },
            "web-admin-client": {
                "minion": ["web-*", "lb-*"],
                "minion_function": ["service.*", "nginx.*", "test.ping"],
            },
            "db-admin-client": {
                "minion": ["db-*", "cache-*"],
                "minion_function": ["mysql.*", "postgres.*", "test.ping"],
            },
            "monitoring-client": {
                "minion": ["*"],
                "minion_function": ["test.ping", "status.*", "grains.items"],
            },
            "dev-client": {
                "minion": ["dev-*", "test-*"],
                "minion_function": ["*"],
            },
        }

        config_overrides = {
            "open_mode": False,
            "auto_accept": False,
            "client_acl": client_acl_config,
            "client_acl_verify": True,
        }

        factory = salt_factories.salt_master_daemon(
            "publish-acl-master",
            overrides=config_overrides,
        )

        with factory.started():
            yield factory

    def test_admin_can_target_all_minions(self, publish_acl_master):
        """Test that admin client can target all minions."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # Admin should be able to target any minion
        assert client_acl.client_can_target_minion("admin-client", "web-01")
        assert client_acl.client_can_target_minion("admin-client", "db-master")
        assert client_acl.client_can_target_minion("admin-client", "any-minion-id")
        assert client_acl.client_can_target_minion("admin-client", "prod-app-server-01")

    def test_admin_can_run_all_modules(self, publish_acl_master):
        """Test that admin client can run all modules."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # Admin should be able to run any module
        assert client_acl.client_can_run_minion_function("admin-client", "test.ping")
        assert client_acl.client_can_run_minion_function("admin-client", "cmd.run")
        assert client_acl.client_can_run_minion_function("admin-client", "pkg.install")
        assert client_acl.client_can_run_minion_function("admin-client", "any.function")

    def test_web_admin_allowed_minion_targeting(self, publish_acl_master):
        """Test that web admin can only target web servers."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # Web admin should be able to target web and lb servers
        assert client_acl.client_can_target_minion("web-admin-client", "web-01")
        assert client_acl.client_can_target_minion("web-admin-client", "web-02")
        assert client_acl.client_can_target_minion("web-admin-client", "web-prod-01")
        assert client_acl.client_can_target_minion("web-admin-client", "lb-01")
        assert client_acl.client_can_target_minion("web-admin-client", "lb-main")

    def test_web_admin_denied_minion_targeting(self, publish_acl_master):
        """Test that web admin cannot target non-web servers."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # Web admin should NOT be able to target other servers
        assert not client_acl.client_can_target_minion("web-admin-client", "db-01")
        assert not client_acl.client_can_target_minion("web-admin-client", "db-master")
        assert not client_acl.client_can_target_minion(
            "web-admin-client", "cache-redis-01"
        )
        assert not client_acl.client_can_target_minion(
            "web-admin-client", "app-server-01"
        )

    def test_web_admin_allowed_module_execution(self, publish_acl_master):
        """Test that web admin can only run allowed modules."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # Web admin should be able to run service and nginx modules
        assert client_acl.client_can_run_minion_function(
            "web-admin-client", "service.restart"
        )
        assert client_acl.client_can_run_minion_function(
            "web-admin-client", "service.status"
        )
        assert client_acl.client_can_run_minion_function(
            "web-admin-client", "nginx.configtest"
        )
        assert client_acl.client_can_run_minion_function(
            "web-admin-client", "test.ping"
        )

    def test_web_admin_denied_module_execution(self, publish_acl_master):
        """Test that web admin cannot run disallowed modules."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # Web admin should NOT be able to run other modules
        assert not client_acl.client_can_run_minion_function(
            "web-admin-client", "cmd.run"
        )
        assert not client_acl.client_can_run_minion_function(
            "web-admin-client", "pkg.install"
        )
        assert not client_acl.client_can_run_minion_function(
            "web-admin-client", "mysql.query"
        )

    def test_db_admin_allowed_minion_targeting(self, publish_acl_master):
        """Test that db admin can only target database servers."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # DB admin should be able to target db and cache servers
        assert client_acl.client_can_target_minion("db-admin-client", "db-01")
        assert client_acl.client_can_target_minion("db-admin-client", "db-master")
        assert client_acl.client_can_target_minion("db-admin-client", "db-replica-01")
        assert client_acl.client_can_target_minion("db-admin-client", "cache-redis-01")
        assert client_acl.client_can_target_minion("db-admin-client", "cache-memcached")

    def test_db_admin_denied_minion_targeting(self, publish_acl_master):
        """Test that db admin cannot target non-database servers."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # DB admin should NOT be able to target other servers
        assert not client_acl.client_can_target_minion("db-admin-client", "web-01")
        assert not client_acl.client_can_target_minion("db-admin-client", "lb-01")
        assert not client_acl.client_can_target_minion(
            "db-admin-client", "app-server-01"
        )

    def test_db_admin_allowed_module_execution(self, publish_acl_master):
        """Test that db admin can only run database modules."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # DB admin should be able to run database modules
        assert client_acl.client_can_run_minion_function(
            "db-admin-client", "mysql.query"
        )
        assert client_acl.client_can_run_minion_function(
            "db-admin-client", "postgres.version"
        )
        assert client_acl.client_can_run_minion_function("db-admin-client", "test.ping")

    def test_db_admin_denied_module_execution(self, publish_acl_master):
        """Test that db admin cannot run non-database modules."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # DB admin should NOT be able to run other modules
        assert not client_acl.client_can_run_minion_function(
            "db-admin-client", "cmd.run"
        )
        assert not client_acl.client_can_run_minion_function(
            "db-admin-client", "service.restart"
        )
        assert not client_acl.client_can_run_minion_function(
            "db-admin-client", "nginx.configtest"
        )

    def test_monitoring_all_minions_limited_modules(self, publish_acl_master):
        """Test monitoring client can target all minions but with limited modules."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # Monitoring should be able to target any minion
        assert client_acl.client_can_target_minion("monitoring-client", "web-01")
        assert client_acl.client_can_target_minion("monitoring-client", "db-master")
        assert client_acl.client_can_target_minion("monitoring-client", "any-server")

        # But only run monitoring modules
        assert client_acl.client_can_run_minion_function(
            "monitoring-client", "test.ping"
        )
        assert client_acl.client_can_run_minion_function(
            "monitoring-client", "status.uptime"
        )
        assert client_acl.client_can_run_minion_function(
            "monitoring-client", "status.loadavg"
        )
        assert client_acl.client_can_run_minion_function(
            "monitoring-client", "grains.items"
        )

        # Should NOT be able to run administrative modules
        assert not client_acl.client_can_run_minion_function(
            "monitoring-client", "cmd.run"
        )
        assert not client_acl.client_can_run_minion_function(
            "monitoring-client", "service.restart"
        )
        assert not client_acl.client_can_run_minion_function(
            "monitoring-client", "pkg.install"
        )

    def test_dev_client_environment_restrictions(self, publish_acl_master):
        """Test dev client is restricted to dev environment."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # Dev client should be able to target dev and test servers
        assert client_acl.client_can_target_minion("dev-client", "dev-web-01")
        assert client_acl.client_can_target_minion("dev-client", "dev-db-01")
        assert client_acl.client_can_target_minion("dev-client", "test-app-01")

        # Should NOT be able to target production
        assert not client_acl.client_can_target_minion("dev-client", "prod-web-01")
        assert not client_acl.client_can_target_minion("dev-client", "web-01")
        assert not client_acl.client_can_target_minion("dev-client", "db-master")

        # But has full module access in dev environment
        assert client_acl.client_can_run_minion_function("dev-client", "test.ping")
        assert client_acl.client_can_run_minion_function("dev-client", "cmd.run")
        assert client_acl.client_can_run_minion_function("dev-client", "pkg.install")

    def test_combined_minion_and_module_restriction(self, publish_acl_master):
        """Test that both minion AND module restrictions must match."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # Web admin targeting web server with allowed module - should succeed
        assert client_acl.client_can_target_minion("web-admin-client", "web-01")
        assert client_acl.client_can_run_minion_function(
            "web-admin-client", "service.restart"
        )

        # Web admin targeting web server with disallowed module - minion OK, module denied
        assert client_acl.client_can_target_minion("web-admin-client", "web-01")
        assert not client_acl.client_can_run_minion_function(
            "web-admin-client", "cmd.run"
        )

        # Web admin targeting db server with allowed module - minion denied, module OK
        assert not client_acl.client_can_target_minion("web-admin-client", "db-01")
        assert client_acl.client_can_run_minion_function(
            "web-admin-client", "service.restart"
        )

        # Both must be allowed for publish to succeed

    def test_unknown_client_publish_denied(self, publish_acl_master):
        """Test that unknown clients cannot publish when ACL exists."""
        client_acl = salt.acl.ClientACL(publish_acl_master.config.get("client_acl", {}))

        # Unknown client should be denied for both minion targeting and module execution
        assert not client_acl.client_can_target_minion("unknown-client", "web-01")
        assert not client_acl.client_can_run_minion_function(
            "unknown-client", "test.ping"
        )

    def test_publish_acl_backward_compatibility(self, no_acl_master):
        """Test that empty ACL allows all publish operations (backward compatibility)."""
        client_acl = salt.acl.ClientACL(no_acl_master.config.get("client_acl", {}))

        # With no ACL, all publish operations should be allowed
        assert client_acl.client_can_target_minion("any-client", "web-01")
        assert client_acl.client_can_target_minion("any-client", "db-master")
        assert client_acl.client_can_run_minion_function("any-client", "cmd.run")
        assert client_acl.client_can_run_minion_function("any-client", "pkg.install")

    def test_publish_acl_pattern_matching(self, publish_acl_master):
        """Test complex pattern matching for publish ACL."""
        # Create client with complex patterns
        complex_config = {
            "complex-client": {
                "minion": ["prod-web-*", "prod-app-*", "staging-*"],
                "minion_function": ["test.*", "grains.get", "status.load*"],
            }
        }
        client_acl = salt.acl.ClientACL(complex_config)

        # Test complex minion patterns
        assert client_acl.client_can_target_minion("complex-client", "prod-web-01")
        assert client_acl.client_can_target_minion(
            "complex-client", "prod-app-server-01"
        )
        assert client_acl.client_can_target_minion("complex-client", "staging-db-01")
        assert not client_acl.client_can_target_minion("complex-client", "dev-web-01")

        # Test complex module patterns
        assert client_acl.client_can_run_minion_function("complex-client", "test.ping")
        assert client_acl.client_can_run_minion_function(
            "complex-client", "test.version"
        )
        assert client_acl.client_can_run_minion_function("complex-client", "grains.get")
        assert client_acl.client_can_run_minion_function(
            "complex-client", "status.loadavg"
        )
        assert not client_acl.client_can_run_minion_function(
            "complex-client", "grains.items"
        )
        assert not client_acl.client_can_run_minion_function(
            "complex-client", "cmd.run"
        )


class TestPublishACLErrorMessages:
    """Test proper error messages for publish ACL denials."""

    def test_minion_targeting_denial_message(self, acl_enabled_master):
        """Test error message for denied minion targeting."""
        config = {
            "restricted-client": {
                "minion": ["web-*"],
                "minion_function": ["test.ping"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Check that permission is denied
        assert not client_acl.client_can_target_minion("restricted-client", "db-01")

        # Get error message
        error_msg = client_acl.get_denial_message(
            "restricted-client", "minion", "db-01"
        )
        assert "restricted-client" in error_msg
        assert "db-01" in error_msg
        assert "not authorized" in error_msg.lower() or "denied" in error_msg.lower()

    def test_module_execution_denial_message(self, acl_enabled_master):
        """Test error message for denied module execution."""
        config = {
            "restricted-client": {
                "minion": ["web-*"],
                "minion_function": ["test.ping"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Check that permission is denied
        assert not client_acl.client_can_run_minion_function(
            "restricted-client", "cmd.run"
        )

        # Get error message
        error_msg = client_acl.get_denial_message(
            "restricted-client", "minion_function", "cmd.run"
        )
        assert "restricted-client" in error_msg
        assert "cmd.run" in error_msg
        assert "not authorized" in error_msg.lower() or "denied" in error_msg.lower()
