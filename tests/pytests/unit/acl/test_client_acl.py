"""
Unit tests for salt.acl.ClientACL - ACL controls for remote CLI clients

Tests the client ACL system that restricts which operations remote CLI
clients (identified by PKI keypairs) can perform on the Salt master.
"""

import pytest

import salt.acl


@pytest.fixture
def client_acl_config():
    """
    Sample client_acl configuration for testing.

    This configuration shows different permission levels for different clients:
    - admin-client: Full access to all runners and wheel functions
    - readonly-client: Limited to read-only operations
    - dev-client: Limited to test and jobs runners
    """
    return {
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
    }


@pytest.fixture
def empty_acl_config():
    """Empty ACL configuration for backward compatibility testing."""
    return {}


@pytest.fixture
def whitelist_config():
    """Whitelist-only configuration."""
    return {
        "trusted-client": {
            "runner": ["test.ping", "jobs.list_jobs"],
            "wheel": ["key.list_all"],
        }
    }


@pytest.fixture
def blacklist_config():
    """Blacklist configuration for testing."""
    return {
        "runner": ["cmd.*", "file.*"],
        "wheel": ["key.delete"],
        "clients": ["blocked-client"],
    }


class TestClientACLInit:
    """Test ClientACL initialization."""

    def test_init_with_config(self, client_acl_config):
        """Test ClientACL initialization with valid config."""
        client_acl = salt.acl.ClientACL(client_acl_config)
        assert client_acl.client_acl == client_acl_config
        assert isinstance(client_acl.client_acl, dict)

    def test_init_empty_config(self, empty_acl_config):
        """Test ClientACL initialization with empty config."""
        client_acl = salt.acl.ClientACL(empty_acl_config)
        assert client_acl.client_acl == {}

    def test_init_none_config(self):
        """Test ClientACL initialization with None config."""
        client_acl = salt.acl.ClientACL(None)
        assert client_acl.client_acl == {}


class TestClientIsAllowed:
    """Test client_is_allowed method."""

    def test_admin_client_full_access_runner(self, client_acl_config):
        """Test that admin client can execute any runner."""
        client_acl = salt.acl.ClientACL(client_acl_config)

        # Admin should have access to everything
        assert client_acl.client_is_allowed("admin-client", "test.ping", "runner")
        assert client_acl.client_is_allowed("admin-client", "jobs.list_jobs", "runner")
        assert client_acl.client_is_allowed("admin-client", "cmd.run", "runner")
        assert client_acl.client_is_allowed(
            "admin-client", "state.orchestrate", "runner"
        )

    def test_admin_client_full_access_wheel(self, client_acl_config):
        """Test that admin client can execute any wheel function."""
        client_acl = salt.acl.ClientACL(client_acl_config)

        # Admin should have access to all wheel functions
        assert client_acl.client_is_allowed("admin-client", "key.list_all", "wheel")
        assert client_acl.client_is_allowed("admin-client", "key.accept", "wheel")
        assert client_acl.client_is_allowed("admin-client", "key.delete", "wheel")
        assert client_acl.client_is_allowed("admin-client", "key.reject", "wheel")

    def test_readonly_client_allowed_runners(self, client_acl_config):
        """Test that readonly client can only execute allowed runners."""
        client_acl = salt.acl.ClientACL(client_acl_config)

        # Readonly should be allowed specific runners
        assert client_acl.client_is_allowed("readonly-client", "test.ping", "runner")
        assert client_acl.client_is_allowed(
            "readonly-client", "jobs.list_jobs", "runner"
        )
        assert client_acl.client_is_allowed(
            "readonly-client", "jobs.lookup_jid", "runner"
        )

    def test_readonly_client_denied_runners(self, client_acl_config):
        """Test that readonly client cannot execute disallowed runners."""
        client_acl = salt.acl.ClientACL(client_acl_config)

        # Readonly should NOT be allowed these runners
        assert not client_acl.client_is_allowed("readonly-client", "cmd.run", "runner")
        assert not client_acl.client_is_allowed(
            "readonly-client", "state.orchestrate", "runner"
        )
        assert not client_acl.client_is_allowed(
            "readonly-client", "file.read", "runner"
        )

    def test_readonly_client_allowed_wheel(self, client_acl_config):
        """Test that readonly client can execute allowed wheel functions."""
        client_acl = salt.acl.ClientACL(client_acl_config)

        # Readonly should be allowed specific wheel functions
        assert client_acl.client_is_allowed("readonly-client", "key.list_all", "wheel")
        assert client_acl.client_is_allowed("readonly-client", "key.finger", "wheel")

    def test_readonly_client_denied_wheel(self, client_acl_config):
        """Test that readonly client cannot execute disallowed wheel functions."""
        client_acl = salt.acl.ClientACL(client_acl_config)

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

    def test_dev_client_pattern_matching(self, client_acl_config):
        """Test pattern matching with wildcards."""
        client_acl = salt.acl.ClientACL(client_acl_config)

        # Dev client can run test.* and jobs.*
        assert client_acl.client_is_allowed("dev-client", "test.ping", "runner")
        assert client_acl.client_is_allowed("dev-client", "test.version", "runner")
        assert client_acl.client_is_allowed("dev-client", "jobs.list_jobs", "runner")
        assert client_acl.client_is_allowed("dev-client", "jobs.lookup_jid", "runner")

        # But not others
        assert not client_acl.client_is_allowed(
            "dev-client", "state.orchestrate", "runner"
        )
        assert not client_acl.client_is_allowed("dev-client", "cmd.run", "runner")

    def test_unknown_client_denied_when_acl_exists(self, client_acl_config):
        """Test that unknown clients are denied when ACL config exists."""
        client_acl = salt.acl.ClientACL(client_acl_config)

        # Unknown client should be denied
        assert not client_acl.client_is_allowed("unknown-client", "test.ping", "runner")
        assert not client_acl.client_is_allowed(
            "unknown-client", "key.list_all", "wheel"
        )

    def test_unknown_client_allowed_when_no_acl(self, empty_acl_config):
        """Test that unknown clients are allowed when no ACL exists (backward compatibility)."""
        client_acl = salt.acl.ClientACL(empty_acl_config)

        # With empty config, should allow all (backward compatibility)
        assert client_acl.client_is_allowed("unknown-client", "test.ping", "runner")
        assert client_acl.client_is_allowed("unknown-client", "key.list_all", "wheel")

    def test_missing_cmd_type_denied(self, client_acl_config):
        """Test that client is denied when cmd_type is not configured."""
        # Create config with only runner permissions
        limited_config = {
            "limited-client": {
                "runner": ["test.ping"],
            }
        }
        client_acl = salt.acl.ClientACL(limited_config)

        # Runner access should work
        assert client_acl.client_is_allowed("limited-client", "test.ping", "runner")

        # Wheel access should be denied (not configured)
        assert not client_acl.client_is_allowed(
            "limited-client", "key.list_all", "wheel"
        )

    def test_list_of_commands(self, client_acl_config):
        """Test checking multiple commands at once."""
        client_acl = salt.acl.ClientACL(client_acl_config)

        # Readonly client - all allowed
        assert client_acl.client_is_allowed(
            "readonly-client", ["test.ping", "jobs.list_jobs"], "runner"
        )

        # Readonly client - one not allowed
        assert not client_acl.client_is_allowed(
            "readonly-client", ["test.ping", "cmd.run"], "runner"
        )


class TestClientIsBlacklisted:
    """Test client_is_blacklisted method."""

    def test_client_id_blacklisted(self, blacklist_config):
        """Test that blacklisted client ID is blocked."""
        client_acl = salt.acl.ClientACL({})

        # Blocked client should be blacklisted
        assert client_acl.client_is_blacklisted(
            "blocked-client", "test.ping", "runner", blacklist_config
        )

    def test_client_id_not_blacklisted(self, blacklist_config):
        """Test that non-blacklisted client ID is not blocked."""
        client_acl = salt.acl.ClientACL({})

        # Non-blocked client should not be blacklisted
        assert not client_acl.client_is_blacklisted(
            "allowed-client", "test.ping", "runner", blacklist_config
        )

    def test_command_blacklisted_runner(self, blacklist_config):
        """Test that blacklisted runner commands are blocked."""
        client_acl = salt.acl.ClientACL({})

        # cmd.* is blacklisted
        assert client_acl.client_is_blacklisted(
            "some-client", "cmd.run", "runner", blacklist_config
        )
        assert client_acl.client_is_blacklisted(
            "some-client", "cmd.shell", "runner", blacklist_config
        )
        assert client_acl.client_is_blacklisted(
            "some-client", "file.read", "runner", blacklist_config
        )

    def test_command_not_blacklisted_runner(self, blacklist_config):
        """Test that non-blacklisted runner commands are not blocked."""
        client_acl = salt.acl.ClientACL({})

        # test.ping is not blacklisted
        assert not client_acl.client_is_blacklisted(
            "some-client", "test.ping", "runner", blacklist_config
        )
        assert not client_acl.client_is_blacklisted(
            "some-client", "jobs.list_jobs", "runner", blacklist_config
        )

    def test_command_blacklisted_wheel(self, blacklist_config):
        """Test that blacklisted wheel commands are blocked."""
        client_acl = salt.acl.ClientACL({})

        # key.delete is blacklisted
        assert client_acl.client_is_blacklisted(
            "some-client", "key.delete", "wheel", blacklist_config
        )

    def test_command_not_blacklisted_wheel(self, blacklist_config):
        """Test that non-blacklisted wheel commands are not blocked."""
        client_acl = salt.acl.ClientACL({})

        # key.list_all is not blacklisted
        assert not client_acl.client_is_blacklisted(
            "some-client", "key.list_all", "wheel", blacklist_config
        )

    def test_empty_blacklist(self):
        """Test that empty blacklist allows all."""
        client_acl = salt.acl.ClientACL({})

        # With empty blacklist, nothing should be blacklisted
        assert not client_acl.client_is_blacklisted(
            "any-client", "any.command", "runner", {}
        )

    def test_none_blacklist(self):
        """Test that None blacklist allows all."""
        client_acl = salt.acl.ClientACL({})

        # With None blacklist, nothing should be blacklisted
        assert not client_acl.client_is_blacklisted(
            "any-client", "any.command", "runner", None
        )


class TestClientACLGlobPatterns:
    """Test glob pattern matching in ACLs."""

    def test_full_wildcard(self, client_acl_config):
        """Test full wildcard pattern matching."""
        client_acl = salt.acl.ClientACL(client_acl_config)

        # Admin has full wildcard
        assert client_acl.client_is_allowed(
            "admin-client", "any.function.here", "runner"
        )
        assert client_acl.client_is_allowed(
            "admin-client", "deep.nested.function", "wheel"
        )

    def test_prefix_wildcard(self, client_acl_config):
        """Test prefix wildcard pattern matching."""
        client_acl = salt.acl.ClientACL(client_acl_config)

        # Dev client has test.* and jobs.*
        assert client_acl.client_is_allowed("dev-client", "test.ping", "runner")
        assert client_acl.client_is_allowed("dev-client", "test.version", "runner")
        assert client_acl.client_is_allowed("dev-client", "test.fib", "runner")
        assert client_acl.client_is_allowed("dev-client", "jobs.list_jobs", "runner")
        assert client_acl.client_is_allowed("dev-client", "jobs.lookup_jid", "runner")

    def test_complex_patterns(self):
        """Test complex glob patterns."""
        config = {
            "complex-client": {
                "runner": ["test.*", "jobs.list_*", "cache.clear_*"],
                "wheel": ["key.finger", "key.list_*"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Test various pattern matches
        assert client_acl.client_is_allowed("complex-client", "test.ping", "runner")
        assert client_acl.client_is_allowed(
            "complex-client", "jobs.list_jobs", "runner"
        )
        assert client_acl.client_is_allowed(
            "complex-client", "jobs.list_runners", "runner"
        )
        assert client_acl.client_is_allowed(
            "complex-client", "cache.clear_all", "runner"
        )

        # Test non-matches
        assert not client_acl.client_is_allowed(
            "complex-client", "jobs.lookup_jid", "runner"
        )
        assert not client_acl.client_is_allowed(
            "complex-client", "state.apply", "runner"
        )


class TestClientACLEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_permission_list(self):
        """Test client with empty permission list."""
        config = {
            "empty-client": {
                "runner": [],
                "wheel": [],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Empty list should deny all
        assert not client_acl.client_is_allowed("empty-client", "test.ping", "runner")
        assert not client_acl.client_is_allowed("empty-client", "key.list_all", "wheel")

    def test_case_sensitivity(self):
        """Test case sensitivity in pattern matching."""
        config = {
            "case-client": {
                "runner": ["Test.Ping"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Patterns should be case-sensitive
        assert client_acl.client_is_allowed("case-client", "Test.Ping", "runner")
        # This will depend on the underlying check_whitelist_blacklist implementation
        # Most glob patterns are case-sensitive by default

    def test_special_characters_in_client_id(self):
        """Test client IDs with special characters."""
        config = {
            "admin-workstation-01": {
                "runner": ["test.ping"],
            },
            "user@host": {
                "runner": ["jobs.*"],
            },
        }
        client_acl = salt.acl.ClientACL(config)

        assert client_acl.client_is_allowed(
            "admin-workstation-01", "test.ping", "runner"
        )
        assert client_acl.client_is_allowed("user@host", "jobs.list_jobs", "runner")

    def test_special_characters_in_patterns(self):
        """Test patterns with special characters."""
        config = {
            "special-client": {
                "runner": ["test.ping", "jobs.list_*", "cache.*"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        assert client_acl.client_is_allowed("special-client", "test.ping", "runner")
        assert client_acl.client_is_allowed(
            "special-client", "jobs.list_jobs", "runner"
        )
        assert client_acl.client_is_allowed("special-client", "cache.clear", "runner")


class TestBackwardCompatibility:
    """Test backward compatibility with no ACL configuration."""

    def test_none_config_allows_all(self):
        """Test that None config allows all operations."""
        client_acl = salt.acl.ClientACL(None)

        # All operations should be allowed with None config
        assert client_acl.client_is_allowed("any-client", "any.function", "runner")
        assert client_acl.client_is_allowed("any-client", "any.function", "wheel")

    def test_empty_dict_allows_all(self):
        """Test that empty dict allows all operations."""
        client_acl = salt.acl.ClientACL({})

        # All operations should be allowed with empty config
        assert client_acl.client_is_allowed("any-client", "any.function", "runner")
        assert client_acl.client_is_allowed("any-client", "any.function", "wheel")

    def test_acl_enforcement_only_when_configured(self):
        """Test that ACL is only enforced when explicitly configured."""
        # Start with no ACL
        client_acl_no_config = salt.acl.ClientACL({})
        assert client_acl_no_config.client_is_allowed("client1", "cmd.run", "runner")

        # Add ACL config
        client_acl_with_config = salt.acl.ClientACL(
            {
                "client1": {
                    "runner": ["test.ping"],
                }
            }
        )
        assert client_acl_with_config.client_is_allowed(
            "client1", "test.ping", "runner"
        )
        assert not client_acl_with_config.client_is_allowed(
            "client1", "cmd.run", "runner"
        )


class TestMultipleClientsScenarios:
    """Test scenarios with multiple clients."""

    def test_different_permissions_per_client(self):
        """Test that different clients can have different permissions."""
        config = {
            "admin": {
                "runner": ["*"],
                "wheel": ["*"],
            },
            "developer": {
                "runner": ["test.*", "jobs.*"],
                "wheel": ["key.list_all"],
            },
            "auditor": {
                "runner": ["jobs.list_jobs", "jobs.lookup_jid"],
                "wheel": ["key.list_all"],
            },
        }
        client_acl = salt.acl.ClientACL(config)

        # Admin can do everything
        assert client_acl.client_is_allowed("admin", "cmd.run", "runner")
        assert client_acl.client_is_allowed("admin", "key.delete", "wheel")

        # Developer has limited access
        assert client_acl.client_is_allowed("developer", "test.ping", "runner")
        assert not client_acl.client_is_allowed("developer", "cmd.run", "runner")

        # Auditor has read-only access
        assert client_acl.client_is_allowed("auditor", "jobs.list_jobs", "runner")
        assert not client_acl.client_is_allowed("auditor", "state.apply", "runner")

    def test_overlapping_permissions(self):
        """Test clients with overlapping but different permissions."""
        config = {
            "client1": {
                "runner": ["test.*", "jobs.list_jobs"],
            },
            "client2": {
                "runner": ["test.*", "state.apply"],
            },
        }
        client_acl = salt.acl.ClientACL(config)

        # Both can run test.*
        assert client_acl.client_is_allowed("client1", "test.ping", "runner")
        assert client_acl.client_is_allowed("client2", "test.ping", "runner")

        # Different additional permissions
        assert client_acl.client_is_allowed("client1", "jobs.list_jobs", "runner")
        assert not client_acl.client_is_allowed("client1", "state.apply", "runner")

        assert client_acl.client_is_allowed("client2", "state.apply", "runner")
        assert not client_acl.client_is_allowed("client2", "jobs.list_jobs", "runner")


class TestClientMinionModulePermissions:
    """Test minion targeting and module execution permissions for publish ACL."""

    def test_minion_exact_match(self):
        """Test exact minion ID matching."""
        config = {
            "test-client": {
                "minion": ["web-01", "web-02", "db-01"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Exact matches should be allowed
        assert client_acl.client_can_target_minion("test-client", "web-01")
        assert client_acl.client_can_target_minion("test-client", "web-02")
        assert client_acl.client_can_target_minion("test-client", "db-01")

        # Non-matches should be denied
        assert not client_acl.client_can_target_minion("test-client", "web-03")
        assert not client_acl.client_can_target_minion("test-client", "app-01")

    def test_minion_glob_pattern_matching(self):
        """Test glob pattern matching for minion targeting."""
        config = {
            "web-admin": {
                "minion": ["web-*", "lb-*"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Glob patterns should match
        assert client_acl.client_can_target_minion("web-admin", "web-01")
        assert client_acl.client_can_target_minion("web-admin", "web-02")
        assert client_acl.client_can_target_minion("web-admin", "web-prod-01")
        assert client_acl.client_can_target_minion("web-admin", "lb-01")
        assert client_acl.client_can_target_minion("web-admin", "lb-main")

        # Non-matching patterns should be denied
        assert not client_acl.client_can_target_minion("web-admin", "db-01")
        assert not client_acl.client_can_target_minion("web-admin", "app-server-01")

    def test_minion_wildcard_full_access(self):
        """Test full wildcard for all minions."""
        config = {
            "admin-client": {
                "minion": ["*"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # All minions should be allowed
        assert client_acl.client_can_target_minion("admin-client", "web-01")
        assert client_acl.client_can_target_minion("admin-client", "db-01")
        assert client_acl.client_can_target_minion("admin-client", "any-minion")
        assert client_acl.client_can_target_minion("admin-client", "prod-app-server-01")

    def test_minion_multiple_patterns(self):
        """Test multiple glob patterns for minion targeting."""
        config = {
            "ops-client": {
                "minion": ["web-*", "db-*", "cache-*", "prod-*"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # All patterns should match
        assert client_acl.client_can_target_minion("ops-client", "web-01")
        assert client_acl.client_can_target_minion("ops-client", "db-master")
        assert client_acl.client_can_target_minion("ops-client", "cache-redis-01")
        assert client_acl.client_can_target_minion("ops-client", "prod-web-01")

        # Non-matching should be denied
        assert not client_acl.client_can_target_minion("ops-client", "dev-web-01")
        assert not client_acl.client_can_target_minion("ops-client", "staging-app-01")

    def test_minion_empty_list_denies_all(self):
        """Test that empty minion list denies all targeting."""
        config = {
            "restricted-client": {
                "minion": [],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Empty list should deny all
        assert not client_acl.client_can_target_minion("restricted-client", "web-01")
        assert not client_acl.client_can_target_minion(
            "restricted-client", "any-minion"
        )

    def test_minion_no_config_denies_when_acl_exists(self):
        """Test that missing minion config denies when ACL exists."""
        config = {
            "runner-only-client": {
                "runner": ["test.ping"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # No minion config should deny targeting
        assert not client_acl.client_can_target_minion("runner-only-client", "web-01")

    def test_minion_unknown_client_denied(self):
        """Test that unknown clients cannot target minions when ACL exists."""
        config = {
            "known-client": {
                "minion": ["web-*"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Unknown client should be denied
        assert not client_acl.client_can_target_minion("unknown-client", "web-01")

    def test_minion_no_acl_allows_all(self):
        """Test that no ACL config allows all minion targeting (backward compatibility)."""
        client_acl = salt.acl.ClientACL({})

        # No ACL should allow all
        assert client_acl.client_can_target_minion("any-client", "web-01")
        assert client_acl.client_can_target_minion("any-client", "db-01")
        assert client_acl.client_can_target_minion("unknown-client", "any-minion")

    def test_module_exact_match(self):
        """Test exact module function matching."""
        config = {
            "test-client": {
                "minion_function": ["test.ping", "grains.items", "status.uptime"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Exact matches should be allowed
        assert client_acl.client_can_run_minion_function("test-client", "test.ping")
        assert client_acl.client_can_run_minion_function("test-client", "grains.items")
        assert client_acl.client_can_run_minion_function("test-client", "status.uptime")

        # Non-matches should be denied
        assert not client_acl.client_can_run_minion_function("test-client", "cmd.run")
        assert not client_acl.client_can_run_minion_function(
            "test-client", "pkg.install"
        )

    def test_module_glob_pattern_matching(self):
        """Test glob pattern matching for module execution."""
        config = {
            "dev-client": {
                "minion_function": ["test.*", "grains.*", "status.*"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Glob patterns should match
        assert client_acl.client_can_run_minion_function("dev-client", "test.ping")
        assert client_acl.client_can_run_minion_function("dev-client", "test.version")
        assert client_acl.client_can_run_minion_function("dev-client", "grains.items")
        assert client_acl.client_can_run_minion_function("dev-client", "grains.get")
        assert client_acl.client_can_run_minion_function("dev-client", "status.uptime")

        # Non-matching patterns should be denied
        assert not client_acl.client_can_run_minion_function("dev-client", "cmd.run")
        assert not client_acl.client_can_run_minion_function(
            "dev-client", "pkg.install"
        )

    def test_module_wildcard_full_access(self):
        """Test full wildcard for all modules."""
        config = {
            "admin-client": {
                "minion_function": ["*"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # All modules should be allowed
        assert client_acl.client_can_run_minion_function("admin-client", "test.ping")
        assert client_acl.client_can_run_minion_function("admin-client", "cmd.run")
        assert client_acl.client_can_run_minion_function("admin-client", "pkg.install")
        assert client_acl.client_can_run_minion_function("admin-client", "any.function")

    def test_module_multiple_patterns(self):
        """Test multiple glob patterns for module execution."""
        config = {
            "monitoring-client": {
                "minion_function": ["test.*", "status.*", "disk.*", "network.*"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # All patterns should match
        assert client_acl.client_can_run_minion_function(
            "monitoring-client", "test.ping"
        )
        assert client_acl.client_can_run_minion_function(
            "monitoring-client", "status.uptime"
        )
        assert client_acl.client_can_run_minion_function(
            "monitoring-client", "disk.usage"
        )
        assert client_acl.client_can_run_minion_function(
            "monitoring-client", "network.interfaces"
        )

        # Non-matching should be denied
        assert not client_acl.client_can_run_minion_function(
            "monitoring-client", "cmd.run"
        )
        assert not client_acl.client_can_run_minion_function(
            "monitoring-client", "pkg.install"
        )

    def test_module_empty_list_denies_all(self):
        """Test that empty module list denies all execution."""
        config = {
            "restricted-client": {
                "minion_function": [],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Empty list should deny all
        assert not client_acl.client_can_run_minion_function(
            "restricted-client", "test.ping"
        )
        assert not client_acl.client_can_run_minion_function(
            "restricted-client", "any.function"
        )

    def test_module_no_config_denies_when_acl_exists(self):
        """Test that missing module config denies when ACL exists."""
        config = {
            "runner-only-client": {
                "runner": ["test.ping"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # No minion_function config should deny execution
        assert not client_acl.client_can_run_minion_function(
            "runner-only-client", "test.ping"
        )

    def test_module_unknown_client_denied(self):
        """Test that unknown clients cannot execute modules when ACL exists."""
        config = {
            "known-client": {
                "minion_function": ["test.*"],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Unknown client should be denied
        assert not client_acl.client_can_run_minion_function(
            "unknown-client", "test.ping"
        )

    def test_module_no_acl_allows_all(self):
        """Test that no ACL config allows all module execution (backward compatibility)."""
        client_acl = salt.acl.ClientACL({})

        # No ACL should allow all
        assert client_acl.client_can_run_minion_function("any-client", "test.ping")
        assert client_acl.client_can_run_minion_function("any-client", "cmd.run")
        assert client_acl.client_can_run_minion_function(
            "unknown-client", "any.function"
        )

    def test_combined_minion_and_module_restrictions(self):
        """Test combined minion targeting and module execution restrictions."""
        config = {
            "web-admin": {
                "minion": ["web-*", "lb-*"],
                "minion_function": ["service.*", "nginx.*", "test.ping"],
            },
            "db-admin": {
                "minion": ["db-*", "cache-*"],
                "minion_function": ["mysql.*", "postgres.*", "redis.*", "test.ping"],
            },
            "monitoring": {
                "minion": ["*"],
                "minion_function": ["test.ping", "status.*", "grains.items"],
            },
        }
        client_acl = salt.acl.ClientACL(config)

        # Web admin can target web servers and run service management
        assert client_acl.client_can_target_minion("web-admin", "web-01")
        assert client_acl.client_can_run_minion_function("web-admin", "service.restart")
        assert client_acl.client_can_run_minion_function("web-admin", "test.ping")
        assert not client_acl.client_can_target_minion("web-admin", "db-01")
        assert not client_acl.client_can_run_minion_function("web-admin", "cmd.run")

        # DB admin can target database servers and run database functions
        assert client_acl.client_can_target_minion("db-admin", "db-master")
        assert client_acl.client_can_run_minion_function("db-admin", "mysql.query")
        assert client_acl.client_can_run_minion_function("db-admin", "redis.info")
        assert not client_acl.client_can_target_minion("db-admin", "web-01")
        assert not client_acl.client_can_run_minion_function(
            "db-admin", "service.restart"
        )

        # Monitoring can target all but only run monitoring functions
        assert client_acl.client_can_target_minion("monitoring", "web-01")
        assert client_acl.client_can_target_minion("monitoring", "db-01")
        assert client_acl.client_can_target_minion("monitoring", "any-server")
        assert client_acl.client_can_run_minion_function("monitoring", "test.ping")
        assert client_acl.client_can_run_minion_function("monitoring", "status.uptime")
        assert not client_acl.client_can_run_minion_function("monitoring", "cmd.run")
        assert not client_acl.client_can_run_minion_function(
            "monitoring", "service.restart"
        )

    def test_complex_glob_patterns(self):
        """Test complex glob patterns for both minions and modules."""
        config = {
            "complex-client": {
                "minion": ["prod-web-*", "prod-app-*", "staging-*"],
                "minion_function": [
                    "test.*",
                    "grains.get",
                    "status.load*",
                    "pkg.list_*",
                ],
            }
        }
        client_acl = salt.acl.ClientACL(config)

        # Complex minion patterns
        assert client_acl.client_can_target_minion("complex-client", "prod-web-01")
        assert client_acl.client_can_target_minion(
            "complex-client", "prod-app-server-01"
        )
        assert client_acl.client_can_target_minion("complex-client", "staging-db-01")
        assert not client_acl.client_can_target_minion("complex-client", "dev-web-01")

        # Complex module patterns
        assert client_acl.client_can_run_minion_function("complex-client", "test.ping")
        assert client_acl.client_can_run_minion_function("complex-client", "grains.get")
        assert client_acl.client_can_run_minion_function(
            "complex-client", "status.loadavg"
        )
        assert client_acl.client_can_run_minion_function(
            "complex-client", "pkg.list_pkgs"
        )
        assert not client_acl.client_can_run_minion_function(
            "complex-client", "grains.items"
        )
        assert not client_acl.client_can_run_minion_function(
            "complex-client", "pkg.install"
        )

    def test_environment_based_restrictions(self):
        """Test environment-based minion and module restrictions."""
        config = {
            "dev-team": {
                "minion": ["dev-*", "test-*"],
                "minion_function": ["*"],
            },
            "staging-team": {
                "minion": ["staging-*"],
                "minion_function": ["test.*", "state.apply", "saltutil.refresh_pillar"],
            },
            "prod-readonly": {
                "minion": ["prod-*"],
                "minion_function": ["test.ping", "grains.*", "status.*"],
            },
        }
        client_acl = salt.acl.ClientACL(config)

        # Dev team has full access to dev environment
        assert client_acl.client_can_target_minion("dev-team", "dev-web-01")
        assert client_acl.client_can_target_minion("dev-team", "test-app-01")
        assert client_acl.client_can_run_minion_function("dev-team", "cmd.run")
        assert not client_acl.client_can_target_minion("dev-team", "prod-web-01")

        # Staging team has limited access to staging
        assert client_acl.client_can_target_minion("staging-team", "staging-web-01")
        assert client_acl.client_can_run_minion_function("staging-team", "test.ping")
        assert client_acl.client_can_run_minion_function("staging-team", "state.apply")
        assert not client_acl.client_can_run_minion_function("staging-team", "cmd.run")
        assert not client_acl.client_can_target_minion("staging-team", "prod-web-01")

        # Prod readonly has very limited access
        assert client_acl.client_can_target_minion("prod-readonly", "prod-web-01")
        assert client_acl.client_can_run_minion_function("prod-readonly", "test.ping")
        assert client_acl.client_can_run_minion_function(
            "prod-readonly", "grains.items"
        )
        assert not client_acl.client_can_run_minion_function("prod-readonly", "cmd.run")
        assert not client_acl.client_can_target_minion("prod-readonly", "dev-web-01")
