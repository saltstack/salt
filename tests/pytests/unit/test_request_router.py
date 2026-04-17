"""
Unit tests for RequestRouter class
"""

import pytest

from salt.master import RequestRouter


class TestRequestRouter:
    """Test RequestRouter request classification and routing"""

    def test_router_initialization_with_catchall(self):
        """Test router initializes correctly with catchall pool"""
        opts = {
            "worker_pools": {
                "fast": {"worker_count": 2, "commands": ["ping", "verify_minion"]},
                "default": {"worker_count": 3, "commands": ["*"]},
            }
        }
        router = RequestRouter(opts)
        assert router.default_pool == "default"
        assert "ping" in router.cmd_to_pool
        assert router.cmd_to_pool["ping"] == "fast"

    def test_router_initialization_with_explicit_default(self):
        """Test router initializes correctly with explicit default pool"""
        opts = {
            "worker_pools": {
                "pool1": {"worker_count": 2, "commands": ["ping"]},
                "pool2": {"worker_count": 3, "commands": ["_pillar"]},
            },
            "worker_pool_default": "pool2",
        }
        router = RequestRouter(opts)
        assert router.default_pool == "pool2"

    def test_router_route_to_specific_pool(self):
        """Test routing to specific pool based on command"""
        opts = {
            "worker_pools": {
                "fast": {"worker_count": 2, "commands": ["ping", "verify_minion"]},
                "slow": {"worker_count": 3, "commands": ["_pillar", "_return"]},
                "default": {"worker_count": 2, "commands": ["*"]},
            }
        }
        router = RequestRouter(opts)

        # Test explicit mappings
        assert router.route_request({"load": {"cmd": "ping"}}) == "fast"
        assert router.route_request({"load": {"cmd": "verify_minion"}}) == "fast"
        assert router.route_request({"load": {"cmd": "_pillar"}}) == "slow"
        assert router.route_request({"load": {"cmd": "_return"}}) == "slow"

    def test_router_route_to_catchall(self):
        """Test routing unmapped commands to catchall pool"""
        opts = {
            "worker_pools": {
                "fast": {"worker_count": 2, "commands": ["ping"]},
                "default": {"worker_count": 3, "commands": ["*"]},
            }
        }
        router = RequestRouter(opts)

        # Unmapped command should go to catchall
        assert router.route_request({"load": {"cmd": "unknown_command"}}) == "default"
        assert router.route_request({"load": {"cmd": "_pillar"}}) == "default"

    def test_router_route_to_explicit_default(self):
        """Test routing unmapped commands to explicit default pool"""
        opts = {
            "worker_pools": {
                "pool1": {"worker_count": 2, "commands": ["ping"]},
                "pool2": {"worker_count": 3, "commands": ["_pillar"]},
            },
            "worker_pool_default": "pool2",
        }
        router = RequestRouter(opts)

        # Unmapped command should go to default
        assert router.route_request({"load": {"cmd": "unknown"}}) == "pool2"

    def test_router_extract_command_from_payload(self):
        """Test command extraction from various payload formats"""
        opts = {"worker_pools": {"default": {"worker_count": 5, "commands": ["*"]}}}
        router = RequestRouter(opts)

        # Normal payload
        assert router._extract_command({"load": {"cmd": "ping"}}) == "ping"

        # Missing cmd
        assert router._extract_command({"load": {}}) == ""

        # Missing load
        assert router._extract_command({}) == ""

        # Invalid payload
        assert router._extract_command(None) == ""

    def test_router_statistics_tracking(self):
        """Test that router tracks statistics per pool"""
        opts = {
            "worker_pools": {
                "fast": {"worker_count": 2, "commands": ["ping"]},
                "slow": {"worker_count": 3, "commands": ["_pillar"]},
                "default": {"worker_count": 2, "commands": ["*"]},
            }
        }
        router = RequestRouter(opts)

        # Initial stats should be zero
        assert router.stats["fast"] == 0
        assert router.stats["slow"] == 0
        assert router.stats["default"] == 0

        # Route some requests
        router.route_request({"load": {"cmd": "ping"}})
        router.route_request({"load": {"cmd": "ping"}})
        router.route_request({"load": {"cmd": "_pillar"}})
        router.route_request({"load": {"cmd": "unknown"}})

        # Check stats
        assert router.stats["fast"] == 2
        assert router.stats["slow"] == 1
        assert router.stats["default"] == 1

    def test_router_fails_duplicate_catchall(self):
        """Test router fails to initialize with duplicate catchall"""
        opts = {
            "worker_pools": {
                "pool1": {"worker_count": 2, "commands": ["*"]},
                "pool2": {"worker_count": 3, "commands": ["*"]},
            }
        }
        with pytest.raises(ValueError, match="Multiple pools have catchall"):
            RequestRouter(opts)

    def test_router_fails_duplicate_command(self):
        """Test router fails to initialize with duplicate command mapping"""
        opts = {
            "worker_pools": {
                "pool1": {"worker_count": 2, "commands": ["ping"]},
                "pool2": {"worker_count": 3, "commands": ["ping"]},
            },
            "worker_pool_default": "pool1",
        }
        with pytest.raises(ValueError, match="Command 'ping' mapped to multiple pools"):
            RequestRouter(opts)

    def test_router_fails_no_default(self):
        """Test router fails without catchall or explicit default"""
        opts = {
            "worker_pools": {
                "pool1": {"worker_count": 2, "commands": ["ping"]},
            },
            "worker_pool_default": None,
        }
        with pytest.raises(
            ValueError, match="Configuration must have either.*catchall.*default"
        ):
            RequestRouter(opts)
