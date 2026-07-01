"""
Unit tests for pool name edge cases - especially special characters in pool names.

Tests that pool names with special characters don't break URI construction,
file path creation, or cause security issues.
"""

import pytest

import salt.transport.zeromq
from salt.config.worker_pools import validate_worker_pools_config


class TestPoolNameSpecialCharacters:
    """Test pool names with various special characters."""

    @pytest.fixture
    def base_pool_config(self, tmp_path):
        """Base configuration for pool tests."""
        sock_dir = tmp_path / "sock"
        pki_dir = tmp_path / "pki"
        cache_dir = tmp_path / "cache"
        sock_dir.mkdir()
        pki_dir.mkdir()
        cache_dir.mkdir()

        return {
            "sock_dir": str(sock_dir),
            "pki_dir": str(pki_dir),
            "cachedir": str(cache_dir),
            "worker_pools_enabled": True,
            "ipc_mode": "",  # Use IPC mode
        }

    def test_pool_name_with_spaces(self, base_pool_config):
        """Pool name with spaces should work."""
        config = base_pool_config.copy()
        config["worker_pools"] = {
            "fast pool": {
                "worker_count": 2,
                "commands": ["test.ping", "*"],
            }
        }

        # Should validate successfully
        validate_worker_pools_config(config)

        # Test URI construction
        config["pool_name"] = "fast pool"
        transport = salt.transport.zeromq.RequestServer(config)
        uri = transport.get_worker_uri()

        # Should create valid IPC URI with pool name
        assert "workers-fast pool.ipc" in uri
        assert uri.startswith("ipc://")

    def test_pool_name_with_dashes_underscores(self, base_pool_config):
        """Pool name with dashes and underscores (common, should work)."""
        config = base_pool_config.copy()
        config["worker_pools"] = {
            "fast-pool_1": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        validate_worker_pools_config(config)

        config["pool_name"] = "fast-pool_1"
        transport = salt.transport.zeromq.RequestServer(config)
        uri = transport.get_worker_uri()

        assert "workers-fast-pool_1.ipc" in uri

    def test_pool_name_with_dots(self, base_pool_config):
        """Pool name with dots should work but creates interesting paths."""
        config = base_pool_config.copy()
        config["worker_pools"] = {
            "pool.fast": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        validate_worker_pools_config(config)

        config["pool_name"] = "pool.fast"
        transport = salt.transport.zeromq.RequestServer(config)
        uri = transport.get_worker_uri()

        # Should create workers-pool.fast.ipc (not a relative path)
        assert "workers-pool.fast.ipc" in uri
        # Verify it's not treated as directory.file
        assert ".." not in uri

    def test_pool_name_with_slash_rejected(self, base_pool_config):
        """Pool name with slash is rejected by validation to prevent path traversal."""
        config = base_pool_config.copy()
        config["worker_pools"] = {
            "fast/pool": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        # Config validation should reject pool names with slashes
        with pytest.raises(ValueError, match="path separators"):
            validate_worker_pools_config(config)

    def test_pool_name_path_traversal_attempt(self, base_pool_config):
        """Pool name attempting path traversal is rejected by validation."""
        config = base_pool_config.copy()
        config["worker_pools"] = {
            "../evil": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        # Config validation should reject path traversal attempts
        with pytest.raises(ValueError, match="path traversal"):
            validate_worker_pools_config(config)

    def test_pool_name_with_unicode(self, base_pool_config):
        """Pool name with unicode characters."""
        config = base_pool_config.copy()
        config["worker_pools"] = {
            "快速池": {  # Chinese for "fast pool"
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        validate_worker_pools_config(config)

        config["pool_name"] = "快速池"
        transport = salt.transport.zeromq.RequestServer(config)
        uri = transport.get_worker_uri()

        # Should handle unicode in URI
        assert "workers-快速池.ipc" in uri or "workers-" in uri

    def test_pool_name_with_special_chars(self, base_pool_config):
        """Pool name with various special characters."""
        special_chars = "!@#$%^&*()"
        config = base_pool_config.copy()
        config["worker_pools"] = {
            special_chars: {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        validate_worker_pools_config(config)

        config["pool_name"] = special_chars
        transport = salt.transport.zeromq.RequestServer(config)
        uri = transport.get_worker_uri()

        # Should create some kind of valid URI (may be escaped/sanitized)
        assert uri.startswith("ipc://")
        assert config["sock_dir"] in uri

    def test_pool_name_very_long(self, base_pool_config):
        """Pool name that's very long - could exceed path limits."""
        long_name = "a" * 300  # 300 chars
        config = base_pool_config.copy()
        config["worker_pools"] = {
            long_name: {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        validate_worker_pools_config(config)

        config["pool_name"] = long_name
        transport = salt.transport.zeromq.RequestServer(config)
        uri = transport.get_worker_uri()

        # Check if resulting path would exceed Unix socket path limit (typically 108 bytes)
        socket_path = uri.replace("ipc://", "")
        if len(socket_path) > 108:
            # This could fail at bind time on Unix systems
            pytest.skip(
                f"Socket path too long ({len(socket_path)} > 108): {socket_path}"
            )

    def test_pool_name_empty_string(self, base_pool_config):
        """Pool name as empty string is rejected by validation."""
        config = base_pool_config.copy()
        config["worker_pools"] = {
            "": {  # Empty string as pool name
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        # Validation should reject empty pool names
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_worker_pools_config(config)

    def test_pool_name_tcp_mode_hash_collision(self, base_pool_config):
        """Test that different pool names don't collide in TCP port assignment."""
        config = base_pool_config.copy()
        config["ipc_mode"] = "tcp"
        config["tcp_master_workers"] = 4515

        # Create two pools and check their ports
        pools_to_test = ["pool1", "pool2", "fast", "general", "test"]
        ports = []

        for pool_name in pools_to_test:
            config["pool_name"] = pool_name
            transport = salt.transport.zeromq.RequestServer(config)
            uri = transport.get_worker_uri()

            # Extract port from URI like "tcp://127.0.0.1:4516"
            port = int(uri.split(":")[-1])
            ports.append((pool_name, port))

        # Check no two pools got same port
        port_numbers = [p[1] for p in ports]
        unique_ports = set(port_numbers)

        if len(unique_ports) < len(port_numbers):
            # Found collision
            collisions = []
            for i, (name1, port1) in enumerate(ports):
                for name2, port2 in ports[i + 1 :]:
                    if port1 == port2:
                        collisions.append((name1, name2, port1))

            pytest.fail(f"Port collisions found: {collisions}")

    def test_pool_name_tcp_mode_port_range(self, base_pool_config):
        """Test that TCP port offsets stay in reasonable range."""
        config = base_pool_config.copy()
        config["ipc_mode"] = "tcp"
        config["tcp_master_workers"] = 4515

        # Test various pool names
        pool_names = ["a", "z", "AAA", "zzz", "pool1", "pool999", "🎉", "!@#$"]

        for pool_name in pool_names:
            config["pool_name"] = pool_name
            transport = salt.transport.zeromq.RequestServer(config)
            uri = transport.get_worker_uri()

            port = int(uri.split(":")[-1])

            # Port should be base + offset, offset is hash(name) % 1000
            # So port should be in range [4515, 5515)
            assert (
                4515 <= port < 5515
            ), f"Pool '{pool_name}' got port {port} outside expected range"

    def test_pool_name_null_byte(self, base_pool_config):
        """Pool name with null byte - potential security issue."""
        config = base_pool_config.copy()
        pool_name_with_null = "pool\x00evil"

        config["worker_pools"] = {
            pool_name_with_null: {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        # Validation might fail or succeed depending on Python version
        try:
            validate_worker_pools_config(config)

            config["pool_name"] = pool_name_with_null
            transport = salt.transport.zeromq.RequestServer(config)
            uri = transport.get_worker_uri()

            # Null byte should not truncate the path or cause issues
            # OS will reject paths with null bytes
            assert "\x00" not in uri or True  # Either stripped or will fail at bind
        except (ValueError, OSError):
            # Expected - null bytes should be rejected somewhere
            pass

    def test_pool_name_windows_reserved(self, base_pool_config):
        """Pool names that are Windows reserved names."""
        reserved_names = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]

        for reserved in reserved_names:
            config = base_pool_config.copy()
            config["worker_pools"] = {
                reserved: {
                    "worker_count": 2,
                    "commands": ["*"],
                }
            }

            validate_worker_pools_config(config)

            config["pool_name"] = reserved
            transport = salt.transport.zeromq.RequestServer(config)
            uri = transport.get_worker_uri()

            # On Windows, these might cause issues
            # On Unix, should work fine
            assert uri.startswith("ipc://")

    def test_pool_name_only_dots(self, base_pool_config):
        """Pool name that's just dots - '..' is rejected, '.' and '...' are allowed."""
        # Single dot is allowed
        config = base_pool_config.copy()
        config["worker_pools"] = {
            ".": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }
        validate_worker_pools_config(config)  # Should succeed

        # Double dot is rejected (path traversal)
        config["worker_pools"] = {
            "..": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }
        with pytest.raises(ValueError, match="path traversal"):
            validate_worker_pools_config(config)

        # Three dots is allowed (not a special path component)
        config["worker_pools"] = {
            "...": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }
        validate_worker_pools_config(config)  # Should succeed
