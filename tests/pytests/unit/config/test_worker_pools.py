"""
Unit tests for worker pools configuration
"""

import pytest

from salt.config.worker_pools import (
    DEFAULT_WORKER_POOLS,
    OPTIMIZED_WORKER_POOLS,
    get_worker_pools_config,
    validate_worker_pools_config,
)


class TestWorkerPoolsConfig:
    """Test worker pools configuration functions"""

    def test_default_worker_pools_structure(self):
        """Test that DEFAULT_WORKER_POOLS has correct structure"""
        assert isinstance(DEFAULT_WORKER_POOLS, dict)
        assert "default" in DEFAULT_WORKER_POOLS
        assert DEFAULT_WORKER_POOLS["default"]["worker_count"] == 5
        assert DEFAULT_WORKER_POOLS["default"]["commands"] == ["*"]

    def test_optimized_worker_pools_structure(self):
        """Test that OPTIMIZED_WORKER_POOLS has correct structure"""
        assert isinstance(OPTIMIZED_WORKER_POOLS, dict)
        assert "lightweight" in OPTIMIZED_WORKER_POOLS
        assert "medium" in OPTIMIZED_WORKER_POOLS
        assert "heavy" in OPTIMIZED_WORKER_POOLS

    def test_get_worker_pools_config_default(self):
        """Test get_worker_pools_config with default config"""
        opts = {"worker_pools_enabled": True, "worker_pools": {}}
        result = get_worker_pools_config(opts)
        assert result == DEFAULT_WORKER_POOLS

    def test_get_worker_pools_config_disabled(self):
        """Test get_worker_pools_config when pools are disabled"""
        opts = {"worker_pools_enabled": False}
        result = get_worker_pools_config(opts)
        assert result is None

    def test_get_worker_pools_config_worker_threads_compat(self):
        """Test backward compatibility with worker_threads"""
        opts = {"worker_pools_enabled": True, "worker_threads": 10, "worker_pools": {}}
        result = get_worker_pools_config(opts)
        assert result == {"default": {"worker_count": 10, "commands": ["*"]}}

    def test_get_worker_pools_config_custom(self):
        """Test get_worker_pools_config with custom pools"""
        custom_pools = {
            "fast": {"worker_count": 2, "commands": ["ping"]},
            "slow": {"worker_count": 3, "commands": ["*"]},
        }
        opts = {"worker_pools_enabled": True, "worker_pools": custom_pools}
        result = get_worker_pools_config(opts)
        assert result == custom_pools

    def test_get_worker_pools_config_optimized(self):
        """Test get_worker_pools_config with optimized flag"""
        opts = {"worker_pools_enabled": True, "worker_pools_optimized": True}
        result = get_worker_pools_config(opts)
        assert result == OPTIMIZED_WORKER_POOLS

    def test_validate_worker_pools_config_valid_default(self):
        """Test validation with valid default config"""
        opts = {"worker_pools_enabled": True, "worker_pools": DEFAULT_WORKER_POOLS}
        assert validate_worker_pools_config(opts) is True

    def test_validate_worker_pools_config_valid_catchall(self):
        """Test validation with valid catchall pool"""
        opts = {
            "worker_pools_enabled": True,
            "worker_pools": {
                "fast": {"worker_count": 2, "commands": ["ping"]},
                "slow": {"worker_count": 3, "commands": ["*"]},
            },
        }
        assert validate_worker_pools_config(opts) is True

    def test_validate_worker_pools_config_valid_default_pool(self):
        """Test validation with valid explicit default pool"""
        opts = {
            "worker_pools_enabled": True,
            "worker_pools": {
                "pool1": {"worker_count": 2, "commands": ["ping"]},
                "pool2": {"worker_count": 3, "commands": ["_pillar"]},
            },
            "worker_pool_default": "pool2",
        }
        assert validate_worker_pools_config(opts) is True

    def test_validate_worker_pools_config_duplicate_catchall(self):
        """Test validation catches duplicate catchall"""
        opts = {
            "worker_pools_enabled": True,
            "worker_pools": {
                "pool1": {"worker_count": 2, "commands": ["*"]},
                "pool2": {"worker_count": 3, "commands": ["*"]},
            },
        }
        with pytest.raises(ValueError, match="Multiple pools have catchall"):
            validate_worker_pools_config(opts)

    def test_validate_worker_pools_config_duplicate_command(self):
        """Test validation catches duplicate commands"""
        opts = {
            "worker_pools_enabled": True,
            "worker_pools": {
                "pool1": {"worker_count": 2, "commands": ["ping"]},
                "pool2": {"worker_count": 3, "commands": ["ping"]},
            },
            "worker_pool_default": "pool1",
        }
        with pytest.raises(ValueError, match="Command 'ping' mapped to multiple pools"):
            validate_worker_pools_config(opts)

    def test_validate_worker_pools_config_invalid_worker_count(self):
        """Test validation catches invalid worker_count"""
        opts = {
            "worker_pools_enabled": True,
            "worker_pools": {
                "pool1": {"worker_count": 0, "commands": ["*"]},
            },
        }
        with pytest.raises(ValueError, match="worker_count must be integer >= 1"):
            validate_worker_pools_config(opts)

    def test_validate_worker_pools_config_missing_default_pool(self):
        """Test validation catches missing default pool"""
        opts = {
            "worker_pools_enabled": True,
            "worker_pools": {
                "pool1": {"worker_count": 2, "commands": ["ping"]},
            },
            "worker_pool_default": "nonexistent",
        }
        with pytest.raises(ValueError, match="not found in worker_pools"):
            validate_worker_pools_config(opts)

    def test_validate_worker_pools_config_no_catchall_no_default(self):
        """Test validation requires either catchall or default pool"""
        opts = {
            "worker_pools_enabled": True,
            "worker_pools": {
                "pool1": {"worker_count": 2, "commands": ["ping"]},
            },
            "worker_pool_default": None,
        }
        with pytest.raises(ValueError, match="Either use a catchall pool"):
            validate_worker_pools_config(opts)

    def test_validate_worker_pools_config_disabled(self):
        """Test validation passes when pools are disabled"""
        opts = {"worker_pools_enabled": False}
        assert validate_worker_pools_config(opts) is True
