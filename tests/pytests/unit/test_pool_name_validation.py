r"""
Unit tests for pool name validation.

Tests minimal security-focused validation:
- Blocks path traversal (/, \, ..)
- Blocks empty strings
- Blocks null bytes
- Allows everything else (spaces, dots, unicode, special chars)
"""

import pytest

from salt.config.worker_pools import validate_worker_pools_config


class TestPoolNameValidation:
    """Test pool name validation rules (Option A: Minimal security-focused)."""

    @pytest.fixture
    def base_config(self, tmp_path):
        """Base configuration for pool tests."""
        return {
            "sock_dir": str(tmp_path / "sock"),
            "pki_dir": str(tmp_path / "pki"),
            "cachedir": str(tmp_path / "cache"),
            "worker_pools_enabled": True,
        }

    def test_valid_pool_names_basic(self, base_config):
        """Valid pool names with various safe characters."""
        valid_names = [
            "fast",
            "general",
            "pool1",
            "pool2",
            "MyPool",
            "UPPERCASE",
            "lowercase",
            "Pool123",
            "123pool",
            "-fast",  # NOW ALLOWED - can start with hyphen
            "_general",  # NOW ALLOWED - can start with underscore
            "fast pool",  # NOW ALLOWED - spaces are fine
            "pool.fast",  # NOW ALLOWED - dots are fine
            "fast-pool_1",  # Mixed characters
            "my_pool-2",
            "快速池",  # NOW ALLOWED - unicode is fine
            "!@#$%^&*()",  # NOW ALLOWED - special chars (except / \ null)
            ".",  # NOW ALLOWED - single dot is fine
            "...",  # NOW ALLOWED - multiple dots fine (not at start as ../)
        ]

        for name in valid_names:
            config = base_config.copy()
            config["worker_pools"] = {
                name: {
                    "worker_count": 2,
                    "commands": ["*"],
                }
            }

            # Should not raise
            try:
                validate_worker_pools_config(config)
            except ValueError as e:
                pytest.fail(f"Pool name '{name}' should be valid but got error: {e}")

    def test_invalid_pool_name_with_forward_slash(self, base_config):
        """Pool name with forward slash is rejected (prevents path traversal)."""
        config = base_config.copy()
        config["worker_pools"] = {
            "fast/pool": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        with pytest.raises(ValueError, match="path separators"):
            validate_worker_pools_config(config)

    def test_invalid_pool_name_with_backslash(self, base_config):
        """Pool name with backslash is rejected (prevents path traversal on Windows)."""
        config = base_config.copy()
        config["worker_pools"] = {
            "fast\\pool": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        with pytest.raises(ValueError, match="path separators"):
            validate_worker_pools_config(config)

    def test_invalid_pool_name_dotdot_only(self, base_config):
        """Pool name that is exactly '..' is rejected."""
        config = base_config.copy()
        config["worker_pools"] = {
            "..": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        with pytest.raises(ValueError, match="path traversal"):
            validate_worker_pools_config(config)

    def test_invalid_pool_name_dotdot_slash_prefix(self, base_config):
        """Pool name starting with '../' is rejected."""
        config = base_config.copy()
        config["worker_pools"] = {
            "../evil": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        with pytest.raises(ValueError, match="path traversal"):
            validate_worker_pools_config(config)

    def test_invalid_pool_name_dotdot_backslash_prefix(self, base_config):
        """Pool name starting with '..\\' is rejected."""
        config = base_config.copy()
        config["worker_pools"] = {
            "..\\evil": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        with pytest.raises(ValueError, match="path traversal"):
            validate_worker_pools_config(config)

    def test_invalid_pool_name_empty_string(self, base_config):
        """Pool name as empty string is rejected."""
        config = base_config.copy()
        config["worker_pools"] = {
            "": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        with pytest.raises(ValueError, match="Pool name cannot be empty"):
            validate_worker_pools_config(config)

    def test_invalid_pool_name_null_byte(self, base_config):
        """Pool name with null byte is rejected."""
        config = base_config.copy()
        config["worker_pools"] = {
            "pool\x00evil": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        with pytest.raises(ValueError, match="null byte"):
            validate_worker_pools_config(config)

    def test_invalid_pool_name_not_string(self, base_config):
        """Pool name that's not a string is rejected."""
        # Note: can only test hashable types since dict keys must be hashable
        invalid_names = [
            123,
            12.5,
            None,
            True,
        ]

        for invalid_name in invalid_names:
            config = base_config.copy()
            config["worker_pools"] = {
                invalid_name: {
                    "worker_count": 2,
                    "commands": ["*"],
                }
            }

            with pytest.raises(ValueError, match="Pool name must be a string"):
                validate_worker_pools_config(config)

    def test_error_message_format_path_separator(self, base_config):
        """Verify error message for path separator is clear."""
        config = base_config.copy()
        config["worker_pools"] = {
            "bad/name": {
                "worker_count": 2,
                "commands": ["*"],
            }
        }

        with pytest.raises(ValueError) as exc_info:
            validate_worker_pools_config(config)

        error_msg = str(exc_info.value)
        # Should explain why it's rejected
        assert "path" in error_msg.lower() and (
            "separator" in error_msg.lower() or "traversal" in error_msg.lower()
        )
