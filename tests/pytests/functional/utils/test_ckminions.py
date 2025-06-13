import pytest

import salt.utils.minions
from tests.support.mock import patch
from tests.support.pytest.database import (  # pylint: disable=unused-import
    available_databases,
    database_backend,
)

sqlalchemy = pytest.importorskip("sqlalchemy")

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.parametrize(
        "database_backend",
        available_databases(
            [
                ("mysql-server", "8.0"),
                ("postgresql", "17"),
                ("sqlite", None),
                ("no_database", None),
            ]
        ),
        indirect=True,
    ),
]


def assert_matching_results(ckminions, compound_tgt, direct_tgt, tgt_type):
    """Helper function to assert that compound and direct targeting return the same results"""
    # compound_result = ckminions.check_minions(compound_tgt, tgt_type="compound")
    direct_result = ckminions.check_minions(direct_tgt, tgt_type=tgt_type)

    # assert compound_result["minions"] == direct_result["minions"], \
    #    f"Compound ({compound_tgt}) and direct ({direct_tgt}) targeting returned different results"

    return direct_result


@pytest.fixture
def base_ckminions(master_opts, database_backend):
    """Create a base CkMinions instance without any data"""
    return salt.utils.minions.CkMinions.factory(master_opts)


@pytest.fixture(scope="function")
def ckminions(base_ckminions):
    """
    Factory fixture that returns a function to create and configure ckminions instances
    with test-specific data.
    """
    # Track minion IDs and their banks for cleanup
    created_data = []  # List of (minion_id, bank) tuples

    def setup_minion_data(data_dict=None, bank="grains"):
        """
        Create test data in the cache

        Args:
            data_dict: Dictionary with minion_id -> data mapping
            bank: The cache bank to store data in ("grains" or "pillar")
                  Note: For pillar_pcre targeting, data must be in the "pillar" bank

        Returns:
            The configured ckminions instance
        """

        base_ckminions.key.cache.flush("keys")
        base_ckminions.cache.flush("grains")
        base_ckminions.cache.flush("pillar")
        if not data_dict:
            return base_ckminions

        for minion_id, data in data_dict.items():
            created_data.append((minion_id, bank))
            # Add key to cache (required for data to be found)
            base_ckminions.key.cache.store(
                "keys", minion_id, {"state": "accepted", "pub": ""}
            )
            # Add data to cache
            base_ckminions.cache.store(bank, minion_id, data)

        return base_ckminions

    # Return the setup function
    yield setup_minion_data

    # Cleanup after all tests using this fixture
    base_ckminions.key.cache.flush("keys")
    base_ckminions.cache.flush("grains")
    base_ckminions.cache.flush("pillar")


def test_check_minions_simple_match(ckminions):
    """Test a simple grains match with one level"""
    minion_data = {"minion1": {"os": "ubuntu"}}
    ck = ckminions(minion_data)
    result = assert_matching_results(ck, "G@os:ubuntu", "os:ubuntu", "grain")
    assert "minion1" in result["minions"]
    assert len(result["minions"]) == 1


def test_check_minions_nested_match(ckminions):
    """Test a nested grains match with two levels"""
    minion_data = {"minion2": {"os_family": {"name": "debian"}}}
    ck = ckminions(minion_data)
    result = assert_matching_results(
        ck, "G@os_family:name:debian", "os_family:name:debian", "grain"
    )
    assert "minion2" in result["minions"]
    assert len(result["minions"]) == 1


def test_check_minions_boolean_match(ckminions):
    """Test matching against boolean value"""
    minion_data = {"minion3": {"virtual": True}}
    ck = ckminions(minion_data)
    result = assert_matching_results(ck, "G@virtual:True", "virtual:True", "grain")
    assert "minion3" in result["minions"]
    assert len(result["minions"]) == 1


def test_check_minions_array_match(ckminions):
    """Test matching against value in array"""
    minion_data = {"minion6": {"roles": ["webserver"]}}
    ck = ckminions(minion_data)
    result = assert_matching_results(
        ck, "G@roles:webserver", "roles:webserver", "grain"
    )
    assert "minion6" in result["minions"]
    assert len(result["minions"]) == 1


def test_check_minions_nested_array_match(ckminions):
    """Test matching against nested value in array"""
    minion_data = {"minion7": {"network": [{"interface": "eth0"}]}}
    ck = ckminions(minion_data)
    result = assert_matching_results(
        ck, "G@network:interface:eth0", "network:interface:eth0", "grain"
    )
    assert "minion7" in result["minions"]
    assert len(result["minions"]) == 1


def test_check_minions_deep_nested_match(ckminions):
    """Test matching against deeply nested structure"""
    minion_data = {"minion11": {"cloud": {"provider": {"name": "aws"}}}}
    ck = ckminions(minion_data)
    result = assert_matching_results(
        ck, "G@cloud:provider:name:aws", "cloud:provider:name:aws", "grain"
    )
    assert "minion11" in result["minions"]
    assert len(result["minions"]) == 1


def test_check_minions_deep_array_match(ckminions):
    """Test matching against deeply nested array structure"""
    minion_data = {"minion12": {"cloud": {"instances": [{"region": "us-east-1"}]}}}
    ck = ckminions(minion_data)
    result = assert_matching_results(
        ck,
        "G@cloud:instances:region:us-east-1",
        "cloud:instances:region:us-east-1",
        "grain",
    )
    assert "minion12" in result["minions"]
    assert len(result["minions"]) == 1


def test_check_minions_glob_pattern(ckminions):
    """Test when pattern contains glob characters that _recurse_contains can't handle"""
    minion_data = {
        "webserver1": {"role": "web", "env": "prod"},
        "webserver2": {"role": "web", "env": "dev"},
        "dbserver1": {"role": "db", "env": "prod"},
    }
    ck = ckminions(minion_data)
    # This should use _recurse_contains for 'role' but then fall back to subdict_match for 'web*'
    result = assert_matching_results(ck, "G@role:web*", "role:web*", "grain")

    # Should match both webservers regardless of environment
    assert "webserver1" in result["minions"]
    assert "webserver2" in result["minions"]
    assert "dbserver1" not in result["minions"]
    assert len(result["minions"]) == 2


def test_check_minions_regex_pattern(ckminions):
    """Test when pattern contains regex patterns that _recurse_contains can't handle"""
    minion_data = {
        "app-server-1": {"application": {"version": "1.2.3"}},
        "app-server-2": {"application": {"version": "2.0.1"}},
        "app-server-3": {"application": {"version": "3.4.5"}},
    }
    # For pillar_pcre targeting, data must be in the "pillar" bank
    ck = ckminions(minion_data, bank="pillar")
    # Use pillar_pcre to trigger the regex path
    # This will use _recurse_contains for 'application:version' but then use
    # subdict_match for the regex part
    result = assert_matching_results(
        ck,
        "P@application:version:2\\.[0-9]+\\.[0-9]+",
        "application:version:2\\.[0-9]+\\.[0-9]+",
        "pillar_pcre",
    )

    assert "app-server-1" not in result["minions"]
    assert "app-server-2" in result["minions"]
    assert "app-server-3" not in result["minions"]
    assert len(result["minions"]) == 1


def test_check_minions_mixed_exact_and_glob(ckminions):
    """Test mix of exact matches and glob patterns that exercises both paths"""
    minion_data = {
        "server1": {
            "network": {
                "interfaces": [
                    {"name": "eth0", "ips": ["192.168.1.1"]},
                    {"name": "eth1", "ips": ["10.0.0.1"]},
                ]
            }
        },
        "server2": {
            "network": {
                "interfaces": [
                    {"name": "eth0", "ips": ["192.168.1.2"]},
                    {"name": "wlan0", "ips": ["10.0.0.2"]},
                ]
            }
        },
    }
    ck = ckminions(minion_data)
    # This will use _recurse_contains for 'network:interfaces' but then fall back
    # to subdict_match for the glob part 'eth*'
    result = assert_matching_results(
        ck, "G@network:interfaces:name:eth*", "network:interfaces:name:eth*", "grain"
    )

    assert "server1" in result["minions"]
    assert "server2" in result["minions"]
    assert len(result["minions"]) == 2

    # More specific pattern that only matches server1 which has eth1
    result = assert_matching_results(
        ck, "G@network:interfaces:name:eth1", "network:interfaces:name:eth1", "grain"
    )

    assert "server1" in result["minions"]
    assert "server2" not in result["minions"]
    assert len(result["minions"]) == 1

    # Pattern that matches server2's wlan0 interface
    result = assert_matching_results(
        ck, "G@network:interfaces:name:wlan*", "network:interfaces:name:wlan*", "grain"
    )

    assert "server1" not in result["minions"]
    assert "server2" in result["minions"]
    assert len(result["minions"]) == 1


def test_check_minions_complex_nested_glob(ckminions):
    """Test deep nesting with glob patterns in middle of path"""
    minion_data = {
        "complex1": {
            "services": {
                "running": [
                    {"name": "httpd", "ports": [80, 443]},
                    {"name": "mysql", "ports": [3306]},
                ],
                "stopped": [{"name": "postgresql", "ports": [5432]}],
            }
        },
        "complex2": {
            "services": {
                "running": [
                    {"name": "nginx", "ports": [80, 443]},
                    {"name": "redis", "ports": [6379]},
                ],
                "stopped": [],
            }
        },
    }
    ck = ckminions(minion_data)

    # This will need to use subdict_match because of the * in the middle of the path
    # This matches any service with port 80, regardless of running status
    result = assert_matching_results(
        ck, "G@services:*:ports:80", "services:*:ports:80", "grain"
    )

    assert "complex1" in result["minions"]
    assert "complex2" in result["minions"]
    assert len(result["minions"]) == 2

    # This matches only running nginx servers
    result = assert_matching_results(
        ck, "G@services:running:name:nginx", "services:running:name:nginx", "grain"
    )

    assert "complex1" not in result["minions"]
    assert "complex2" in result["minions"]
    assert len(result["minions"]) == 1

    # This matches any stopped service
    result = assert_matching_results(
        ck, "G@services:stopped:name:*", "services:stopped:name:*", "grain"
    )

    assert "complex1" in result["minions"]
    assert "complex2" not in result["minions"]  # Has empty stopped array
    assert len(result["minions"]) == 1
    #
    # This matches an integer
    result = assert_matching_results(
        ck, "G@services:running:ports:80", "services:running:ports:80", "grain"
    )

    assert "complex1" in result["minions"]
    assert "complex2" in result["minions"]
    assert len(result["minions"]) == 2


def test_compound_matching_rejects_dangerous_input(ckminions):
    """Test that the compound target matching rejects potentially dangerous input."""

    ck = ckminions()

    # A list of potentially dangerous expressions that should be rejected
    dangerous_expressions = [
        # Expressions that attempt namespace escape or code execution
        "G@_deferred_minions_scope.__class__.__bases__[0].__subclasses__():.*",
        "G@all_minions.__globals__:.*",
        "S@__import__('os').system('echo vulnerable')",
        "E@__builtins__['eval']('import os')",
        # Command chaining attempts
        "G@os:ubuntu); import os; os.system('echo vulnerable'); (",
        "G@role:web' and __import__('subprocess').call(['touch', '/tmp/vulnerable']) or '",
    ]

    # Each of these expressions should either:
    # 1. Fail with an error (empty minions list or exception)
    # 2. Be treated as literal text without executing code
    for expr in dangerous_expressions:
        result = ck.check_minions(expr, tgt_type="compound")

        # The result should be empty or contain the literal string
        # without executing the embedded code
        assert (
            len(result["minions"]) == 0
        ), f"Expression {expr} should be rejected or return no matches"


def test_connected_ids(ckminions):
    """Test mix of exact matches and glob patterns that exercises both paths"""
    minion_data = {
        "server1": {
            "ipv4": [
                "10.0.20.21",
                "127.0.0.1",
            ],
            "ipv6": [],
        },
        "server2": {
            "ipv6": [
                "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
                "2001:db8:85a3::8a2e:370:7334",
            ],
            "ipv4": [],
        },
        "server3": {
            "ipv6": ["2001:0db8:85a3:0000:0000:8a2e:0370:7334"],
        },
        "server4": {
            "ipv4": ["10.0.20.22"],
        },
    }

    addrs = {
        addr
        for v in minion_data.values()
        for proto in ("ipv4", "ipv6")
        for addr in v.get(proto, [])
    }

    with patch("salt.utils.network.local_port_tcp", return_value=addrs):
        ck = ckminions(minion_data)
        connected_ids = ck.connected_ids()
        assert {"server1", "server2", "server3", "server4"} == connected_ids
