import time

import pytest

import salt.utils.data
import salt.utils.minions
from tests.support.mock import patch
from tests.support.pytest.database import (
    available_databases,
    database_backend,
    master_opts,
)

__all__ = ["database_backend", "master_opts"]

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
    compound_result = ckminions.check_minions(compound_tgt, tgt_type="compound")
    direct_result = ckminions.check_minions(direct_tgt, tgt_type=tgt_type)
    assert set(compound_result["minions"]) == set(direct_result["minions"])
    return direct_result


@pytest.fixture
def base_ckminions(master_opts, database_backend):
    """Create a base CkMinions instance without any data"""
    instance = salt.utils.minions.CkMinions.factory(master_opts)
    assert isinstance(instance, salt.utils.minions.SQLAlchemyCkMinions) == (
        database_backend.name != "no_database"
    )
    return instance


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
    """Match a pillar regex through both compound and direct targeting."""
    minion_data = {
        "app-server-1": {"application": {"version": "1.2.3"}},
        "app-server-2": {"application": {"version": "2.0.1"}},
        "app-server-3": {"application": {"version": "3.4.5"}},
    }
    # For pillar_pcre targeting, data must be in the "pillar" bank
    ck = ckminions(minion_data, bank="pillar")
    result = assert_matching_results(
        ck,
        "J@application:version:2\\.[0-9]+\\.[0-9]+",
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
        message = f"Expression {expr} should be rejected or return no matches"
        assert len(result["minions"]) == 0, message


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


@pytest.mark.parametrize("greedy", [False, True])
@pytest.mark.parametrize(
    "data,expr,options,expected",
    [
        ({"os": "Ubuntu"}, "os:ubuntu", {}, {"target"}),
        ({"os": "Ubuntu"}, "'os':ubuntu", {}, {"target"}),
        ({"os": "Ubuntu"}, '"os":ubuntu', {}, {"target"}),
        ({"os": "Ubuntu"}, "!!str os:ubuntu", {}, {"target"}),
        ({"os": "Ubuntu"}, "&a os:ubuntu", {}, {"target"}),
        ({"'os'": "Ubuntu"}, "'os':ubuntu", {}, {"target"}),
        ({"os\0": "Ubuntu"}, '"os\\0":ubuntu', {}, {"target"}),
        ({"os": "Ubuntu"}, "os:ubuntu", {"exact_match": True}, {"target"}),
        ({"os": "ubuntu"}, "os:ubu", {"regex_match": True}, {"target"}),
        ({"role": "web1"}, "role:web?", {}, {"target"}),
        ({"role": "app"}, "role:[ab]*", {}, {"target"}),
        ({"ipv6": ["fe80::1"]}, "ipv6:fe80::1", {}, {"target"}),
        ({"url": "https://host/path"}, "url:https://host/path", {}, {"target"}),
        ({"value": 1.5}, "value:1.5", {}, {"target"}),
        ({"value": -2}, "value:-2", {}, {"target"}),
        ({"value": None}, "value:none", {}, {"target"}),
        ({100: "prod"}, "100:prod", {}, {"target"}),
        ({"env": {100: "prod"}}, "env:100:prod", {}, {"target"}),
        ({100: "prod", "os": "Ubuntu"}, "os:ubuntu", {}, {"target"}),
        (
            {"__salt_sqlalchemy__": "literal", "os": "Ubuntu"},
            "os:ubuntu",
            {},
            {"target"},
        ),
        ([{"os": "Ubuntu"}], "os:ubuntu", {}, {"target"}),
        ({"os": "Ubuntu"}, "*:os:ubuntu", {}, {"target"}),
        ({"os": "Ubuntu"}, "os|ubuntu", {"delimiter": "|"}, {"target"}),
        ({"os": "Ubuntu"}, "**", {"delimiter": "*"}, {"target", "other"}),
        ({"role": "web"}, "role", {}, set()),
        ({"os": "Debian"}, "os:ubuntu", {}, set()),
    ],
)
def test_cache_match_preserves_base_semantics(
    ckminions, data, expr, options, expected, greedy
):
    ck = ckminions({"target": data, "other": {"unrelated": True}})
    kwargs = {"delimiter": ":", "greedy": greedy, "search_type": "grains", **options}
    result = ck._check_cache_minions(expr, **kwargs)
    reference = salt.utils.minions.CkMinions._check_cache_minions(ck, expr, **kwargs)
    assert set(result["minions"]) == set(reference["minions"]) == expected


@pytest.mark.parametrize("bank,prefix", [("grains", "G"), ("pillar", "I")])
@pytest.mark.parametrize(
    "expr",
    [
        "{prefix}@os:ubuntu",
        "{prefix}@'os':ubuntu",
        '{prefix}@"os":ubuntu',
        "{prefix}@role:web or {prefix}*@**",
    ],
)
def test_cached_target_cannot_bypass_acl(ckminions, bank, prefix, expr):
    ck = ckminions(
        {
            "web": {"os": "Ubuntu", "role": "web"},
            "db": {"os": "Ubuntu", "role": "database"},
        },
        bank=bank,
    )
    target = expr.format(prefix=prefix)
    assert not ck.validate_tgt(f"{prefix}@role:web", target, "compound")


def test_pillar_exact_match_preserves_case_folding(ckminions):
    ck = ckminions({"target": {"environment": "Prod"}}, bank="pillar")
    result = ck.check_minions("environment:prod", tgt_type="pillar_exact")
    assert set(result["minions"]) == {"target"}


@pytest.mark.parametrize("greedy", [False, True])
def test_cache_match_excludes_missing_and_expired_data(ckminions, greedy):
    ck = ckminions({"live": {"os": "Ubuntu"}, "expired": {"os": "Ubuntu"}})
    ck.key.cache.store("keys", "missing", {"state": "accepted", "pub": ""})
    ck.cache.store("grains", "expired", {"os": "Ubuntu"}, expires=-1)
    result = ck._check_cache_minions("os:ubuntu", ":", greedy, "grains")
    assert set(result["minions"]) == {"live"}


@pytest.mark.parametrize("greedy,expected", [(False, {"cached"}), (True, set())])
def test_cached_minion_without_accepted_key(ckminions, greedy, expected):
    ck = ckminions({"cached": {"os": "Ubuntu"}})
    ck.key.cache.flush("keys", "cached")
    result = ck._check_cache_minions("os:ubuntu", ":", greedy, "grains")
    assert set(result["minions"]) == expected


def test_cache_match_honors_explicit_minion_subset(ckminions):
    ck = ckminions({"allowed": {"role": "web"}, "other": {"role": "web"}})
    result = ck._check_cache_minions(
        "role:web", ":", True, "grains", minions=["allowed"]
    )
    assert set(result["minions"]) == {"allowed"}


@pytest.mark.parametrize(
    "extra_grains", [{}, {100: "custom"}, {"__salt_sqlalchemy__": "literal"}]
)
def test_connected_ids_returns_first_matching_address_per_family(
    ckminions, extra_grains
):
    ipv4 = ["192.0.2.10", "192.0.2.11", "192.0.2.12"]
    ipv6 = ["2001:db8::10", "2001:db8::11", "2001:db8::12"]
    grains = {"ipv4": ipv4, "ipv6": ipv6, **extra_grains}
    ck = ckminions({"server": grains, "expired": grains})
    ck.cache.store("grains", "expired", grains, expires=-1)
    with patch(
        "salt.utils.network.local_port_tcp", return_value=set(ipv4[1:] + ipv6[1:])
    ):
        assert ck.connected_ids(show_ip=True) == {
            ("server", ipv4[1]),
            ("server", ipv6[1]),
        }


def test_large_minion_subset(ckminions):
    grains = {"role": "web", "ipv4": ["192.0.2.10"]}
    ck = ckminions({"target": grains, "outside": grains})
    if not isinstance(ck, salt.utils.minions.SQLAlchemyCkMinions):
        pytest.skip("Exercise database parameter limits without filesystem probes")
    subset = ["target", *(f"missing-{idx}" for idx in range(65_536))]
    result = ck._check_cache_minions("role:web", ":", True, "grains", minions=subset)
    assert set(result["minions"]) == {"target"}
    assert list(ck._iter_minion_grains_addresses(subset=subset)) == [
        ("target", "ipv4", "192.0.2.10")
    ]


def test_cache_match_across_streaming_batches(ckminions):
    ck = ckminions()
    if getattr(ck, "dialect_name", None) != "postgresql":
        pytest.skip("The streaming cache matcher is PostgreSQL-only")
    data = {f"minion-{idx}": {"os": "Ubuntu"} for idx in range(501)}
    ck = ckminions(data)
    result = ck._check_cache_minions("os:ubuntu", ":", True, "grains")
    assert set(result["minions"]) == set(data)


def _require_terms(ck):
    if getattr(ck, "dialect_name", None) != "postgresql":
        pytest.skip("Cache terms are PostgreSQL-only")


TERMS_DATA = {
    "ubuntu": {
        "os": "Ubuntu",
        "roles": ["web", "db"],
        "bb": {"bbcpu": {"rhsttag": True}},
        "systemd": {"version": "252"},
        "ipv4": ["10.0.0.1", "127.0.0.1"],
        "virtual": True,
        "osrelease": 22.04,
    },
    "centos": {
        "os": "CentOS",
        "roles": ["db"],
        "bb": {"bbcpu": "rhsttag"},
        "ipv6": "fe80::1",
        "nested": [{"name": "eth0"}],
    },
    "bare": {"os": "Debian", "bb": {"bbcpu": {"other": 1}}},
}

TERMS_TARGETS = [
    ("os:ubuntu", {}),
    ("OS:Ubuntu", {}),
    ("roles:web", {}),
    ("bb:bbcpu:rhsttag", {}),
    ("systemd:version", {}),
    ("virtual:True", {}),
    ("osrelease:22.04", {}),
    ("ipv6:fe80::1", {}),
    ("ipv4:1:127.0.0.1", {}),
    ("nested:name:eth0", {}),
    ("'os':ubuntu", {}),
    ("os:*", {}),
    ("os:cen*", {}),
    ("os:deb?an", {}),
    ("os:*buntu", {}),
    ("os:ubu.*", {"regex_match": True}),
    ("os:(ubu|deb).*", {"regex_match": True}),
    ("os:centos", {"exact_match": True}),
    ("*:bbcpu:rhsttag", {}),
    ("os", {}),
]


@pytest.mark.parametrize("greedy", [False, True])
@pytest.mark.parametrize("expr,options", TERMS_TARGETS)
def test_terms_match_python_matcher(ckminions, expr, options, greedy):
    ck = ckminions(TERMS_DATA)
    _require_terms(ck)
    kwargs = {"delimiter": ":", "greedy": greedy, "search_type": "grains", **options}
    result = ck._check_cache_minions(expr, **kwargs)
    reference = salt.utils.minions.CkMinions._check_cache_minions(ck, expr, **kwargs)
    assert set(result["minions"]) == set(reference["minions"])


@pytest.mark.parametrize(
    "expr,options",
    [
        target
        for target in TERMS_TARGETS
        if target[0] not in ("os:*buntu", "*:bbcpu:rhsttag")
    ],
)
def test_terms_targets_do_not_scan(ckminions, expr, options):
    ck = ckminions(TERMS_DATA)
    _require_terms(ck)
    with patch.object(ck, "_scan_statement", side_effect=AssertionError("scan")):
        ck._check_cache_minions(expr, ":", True, "grains", **options)


@pytest.mark.parametrize("greedy", [False, True])
def test_wildcard_root_targets_scan_documents(ckminions, greedy):
    ck = ckminions(TERMS_DATA)
    _require_terms(ck)
    expr = "*:bbcpu:rhsttag"
    reference = salt.utils.minions.CkMinions._check_cache_minions(
        ck, expr, ":", greedy, "grains"
    )
    # The base matcher fetches every minion separately, without the deadline.
    with patch.object(
        salt.utils.minions.CkMinions,
        "_check_cache_minions",
        side_effect=AssertionError("base matcher"),
    ):
        result = ck._check_cache_minions(expr, ":", greedy, "grains")
    assert set(result["minions"]) == set(reference["minions"]) == {"ubuntu", "centos"}


def test_terms_lookup_uses_gin_index(ckminions):
    ck = ckminions({f"minion-{idx}": {"os": f"os-{idx}"} for idx in range(500)})
    _require_terms(ck)
    engine = salt.sqlalchemy.ENGINE_REGISTRY["default"]["engine"]
    with engine.begin() as connection:
        connection.exec_driver_sql("ANALYZE cache_grains")
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if "@@" in statement:
            statements.append((statement, parameters))

    sqlalchemy.event.listen(engine, "before_cursor_execute", capture)
    try:
        ck._check_cache_minions("os:os-7", ":", True, "grains")
    finally:
        sqlalchemy.event.remove(engine, "before_cursor_execute", capture)
    statement, parameters = statements[-1]
    with engine.connect() as connection:
        plan = connection.exec_driver_sql(f"EXPLAIN {statement}", parameters).all()
    plan = "\n".join(row[0] for row in plan)
    assert "ix_cache_grains_terms" in plan, plan


@pytest.mark.parametrize(
    "update",
    [
        "terms = NULL, terms_config = NULL",
        # Terms built for other term paths are not trusted.
        "terms = '{}', terms_config = 'stale'",
    ],
)
def test_rows_without_current_terms_are_rechecked(ckminions, update):
    ck = ckminions(TERMS_DATA)
    _require_terms(ck)
    engine = salt.sqlalchemy.ENGINE_REGISTRY["default"]["engine"]
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"UPDATE cache SET {update} WHERE bank = 'grains' AND key = 'ubuntu'"
        )
    result = ck._check_cache_minions("os:ubuntu", ":", True, "grains")
    assert result["minions"] == ["ubuntu"]


@pytest.mark.parametrize("expr,options", TERMS_TARGETS)
def test_excluded_term_paths_match_python_matcher(ckminions, expr, options):
    config = salt.sqlalchemy.ENGINE_REGISTRY["default"]["config"]
    with patch.dict(config, {"term_exclude": ["bb", "nested"]}):
        ck = ckminions(TERMS_DATA)
        _require_terms(ck)
        kwargs = {"delimiter": ":", "greedy": True, "search_type": "grains"}
        kwargs.update(options)
        result = ck._check_cache_minions(expr, **kwargs)
    reference = salt.utils.minions.CkMinions._check_cache_minions(ck, expr, **kwargs)
    assert set(result["minions"]) == set(reference["minions"])


def test_untagged_data_updates_clear_terms(ckminions):
    ck = ckminions(TERMS_DATA)
    _require_terms(ck)
    engine = salt.sqlalchemy.ENGINE_REGISTRY["default"]["engine"]
    # A master without term support updates the data but not the terms.
    with engine.begin() as connection:
        connection.exec_driver_sql(
            'UPDATE cache SET data = \'{"os": "Gentoo"}\' '
            "WHERE bank = 'grains' AND key = 'ubuntu'"
        )
        stored = connection.exec_driver_sql(
            "SELECT terms, terms_config FROM cache "
            "WHERE bank = 'grains' AND key = 'ubuntu'"
        ).one()
    assert tuple(stored) == (None, None)
    assert ck._check_cache_minions("os:gentoo", ":", True, "grains")["minions"] == [
        "ubuntu"
    ]
    assert ck._check_cache_minions("os:ubuntu", ":", True, "grains")["minions"] == []
    # Stores through the cache keep the terms they wrote.
    ck.cache.store("grains", "ubuntu", {"os": "Arch"})
    with engine.connect() as connection:
        stored = connection.exec_driver_sql(
            "SELECT terms_config FROM cache WHERE bank = 'grains' AND key = 'ubuntu'"
        ).scalar()
    assert stored is not None


def test_accepted_minions_listed_once_per_request(ckminions):
    ck = ckminions({"web": {"role": "web"}, "db": {"role": "database"}})
    if not isinstance(ck, salt.utils.minions.SQLAlchemyCkMinions):
        pytest.skip("Memoization is part of the SQLAlchemy matcher")
    with patch.object(ck.key, "list_status", wraps=ck.key.list_status) as listed:
        ck.check_minions("G@role:web or G@role:database or web*", "compound")
    assert listed.call_count <= 1
    with patch.object(ck.key, "list_status", wraps=ck.key.list_status) as listed:
        assert ck.auth_check(
            [{"G@role:web": ["test.*"]}, {"web*": ["test.*"]}],
            "test.ping",
            [],
            "G@role:web",
            "compound",
        )
    assert listed.call_count <= 1
    # Outside a request every call lists the keys again.
    with patch.object(ck.key, "list_status", wraps=ck.key.list_status) as listed:
        ck._pki_minions()
        ck._pki_minions()
    assert listed.call_count == 2


class _Canceled(Exception):
    sqlstate = "57014"


class _Broken(Exception):
    sqlstate = "08006"


@pytest.mark.parametrize(
    "error",
    [
        salt.utils.minions._TargetingTimeout(),
        sqlalchemy.exc.OperationalError("SELECT", {}, _Canceled()),
    ],
)
def test_timed_out_targets_fail_whole_target(ckminions, caplog, error):
    ck = ckminions(TERMS_DATA)
    if not isinstance(ck, salt.utils.minions.SQLAlchemyCkMinions):
        pytest.skip("The time limit is part of the SQLAlchemy matcher")
    with patch.object(ck, "_match_cache", side_effect=error):
        with pytest.raises(salt.utils.minions.TargetingTimeout):
            ck._check_cache_minions("os:ubuntu", ":", True, "grains")
        with caplog.at_level("ERROR", logger="salt.utils.minions"):
            # An empty operand would make the negation match every minion,
            # and an empty requested set would pass ACL subset checks.
            for tgt, tgt_type in (
                ("not G@os:ubuntu", "compound"),
                ("G@os:debian or not G@os:ubuntu", "compound"),
                ("os:ubuntu", "grain"),
            ):
                with pytest.raises(salt.utils.minions.TargetingTimeout):
                    ck.check_minions(tgt, tgt_type)
            with pytest.raises(salt.utils.minions.TargetingTimeout):
                ck.auth_check(
                    [{"web": ["test.*"]}], "test.ping", [], "os:ubuntu", "grain"
                )
            with pytest.raises(salt.utils.minions.TargetingTimeout):
                ck.validate_tgt("web", "os:ubuntu", "grain")
    assert "sqlalchemy.targeting_timeout" in caplog.text


def test_other_database_errors_are_raised(ckminions):
    ck = ckminions(TERMS_DATA)
    if not isinstance(ck, salt.utils.minions.SQLAlchemyCkMinions):
        pytest.skip("The time limit is part of the SQLAlchemy matcher")
    error = sqlalchemy.exc.OperationalError("SELECT", {}, _Broken())
    with patch.object(ck, "_match_cache", side_effect=error):
        with pytest.raises(salt.utils.minions.TargetingError) as raised:
            ck._check_cache_minions("os:ubuntu", ":", True, "grains")
        assert raised.value.__cause__ is error
        assert not isinstance(raised.value, salt.utils.minions.TargetingTimeout)
        with pytest.raises(salt.utils.minions.TargetingError):
            ck.check_minions("not G@os:ubuntu", "compound")


@pytest.mark.parametrize(
    "expr",
    [
        "os:deb?an",  # rechecked candidates
        "os:*:x",  # wildcard segment, matched by scanning
        "*:os:x",  # wildcard root, matched by scanning whole documents
    ],
)
def test_targeting_deadline_stops_slow_matching(ckminions, expr):
    ck = ckminions(TERMS_DATA)
    _require_terms(ck)
    config = salt.sqlalchemy.ENGINE_REGISTRY["default"]["config"]
    real = salt.utils.data.subdict_match

    def slow(*args, **kwargs):
        time.sleep(0.05)
        return real(*args, **kwargs)

    with patch.dict(config, {"targeting_timeout": 10}), patch.object(
        salt.utils.data, "subdict_match", side_effect=slow
    ):
        with pytest.raises(salt.utils.minions.TargetingTimeout):
            ck._check_cache_minions(expr, ":", True, "grains")


STORAGE_DATA = {
    "floats": {
        "neg_zero": -0.0,
        "big": 1e20,
        "small": 1.5e-07,
        "release": 22.04,
        "members": [-0.0, 2.5],
    },
    "ints": {"neg_zero": 0, "big": 100000000000000000000, "release": "22.04"},
}


@pytest.mark.parametrize(
    "expr",
    [
        "neg_zero:0.0",
        "neg_zero:-0.0",
        "neg_zero:0",
        "big:1e+20",
        "big:100000000000000000000",
        "small:1.5e-07",
        "release:22.04",
        "members:0.0",
        "members:-0.0",
    ],
)
def test_terms_match_values_as_stored(ckminions, expr):
    # The reference matcher reads documents back from the database, so it
    # sees values after JSONB normalized them.
    ck = ckminions(STORAGE_DATA)
    _require_terms(ck)
    kwargs = {"delimiter": ":", "greedy": True, "search_type": "grains"}
    result = ck._check_cache_minions(expr, **kwargs)
    reference = salt.utils.minions.CkMinions._check_cache_minions(ck, expr, **kwargs)
    assert set(result["minions"]) == set(reference["minions"])


@pytest.mark.parametrize(
    "limit,bulk,lists_all",
    [
        (10000, True, False),
        (0, True, True),
        (10000, False, False),
        (0, False, True),
    ],
)
def test_greedy_targets_check_only_matched_keys(ckminions, limit, bulk, lists_all):
    ck = ckminions(TERMS_DATA)
    _require_terms(ck)
    # A deleted minion's grains stay cached and must not match.
    ck.key.cache.flush("keys", "centos")
    limit_name = "BULK_ACCEPTED_LOOKUP_LIMIT" if bulk else "ACCEPTED_LOOKUP_LIMIT"
    with patch.object(ck, limit_name, limit), patch.object(
        ck, "_bulk_key_lookup", return_value=bulk
    ), patch.object(
        ck.key, "list_status", wraps=ck.key.list_status
    ) as listed, patch.object(
        ck.key, "list_match", wraps=ck.key.list_match
    ) as looked:
        for expr in ("os:centos", "nested:*:eth0"):  # indexed, then scanned
            assert ck._check_cache_minions(expr, ":", True, "grains")["minions"] == []
        result = ck._check_cache_minions("roles:db", ":", True, "grains")
    assert result["minions"] == ["ubuntu"]
    assert bool(listed.call_count) is lists_all
    assert bool(looked.call_count) is not lists_all


def test_key_lookup_errors_fail_target(ckminions):
    ck = ckminions(TERMS_DATA)
    _require_terms(ck)
    with patch.object(ck.key, "list_match", side_effect=OSError("unreadable")):
        for tgt, tgt_type in (("not G@os:ubuntu", "compound"), ("os:ubuntu", "grain")):
            with pytest.raises(salt.utils.minions.TargetingError):
                ck.check_minions(tgt, tgt_type)


def test_oversized_documents_still_match(ckminions):
    # Terms past the tsvector size limit; only the recheck marker is stored.
    data = {"a" * 90: {"b" * 70: {f"k{i:05}": "x" for i in range(3200)}}}
    ck = ckminions({"big": data, "small": {"os": "Ubuntu"}})
    _require_terms(ck)
    for key in ("k03000", "k03199", "k00000"):
        expr = ":".join(("a" * 90, "b" * 70, key, "x"))
        assert ck._check_cache_minions(expr, ":", True, "grains")["minions"] == ["big"]


def test_deadline_checked_for_certain_rows(ckminions):
    ck = ckminions(TERMS_DATA)
    _require_terms(ck)
    config = salt.sqlalchemy.ENGINE_REGISTRY["default"]["config"]
    # The clock stands still until the rows stream, so the statement gets the
    # whole budget and only the deadline checks while streaming can fire.
    ticks = iter([0, 0])

    def clock():
        return next(ticks, 60)

    with patch.dict(config, {"targeting_timeout": 1000}), patch.object(
        salt.utils.minions.time, "monotonic", side_effect=clock
    ):
        # os:ubuntu is answered by certain rows only, with no rechecks.
        with pytest.raises(salt.utils.minions.TargetingTimeout):
            ck._check_cache_minions("os:ubuntu", ":", False, "grains")


def test_compound_operands_with_unusual_ids(ckminions):
    ck = ckminions(
        {
            "o'brien": {"role": "web"},
            'x{y}"z': {"role": "web"},
            "plain": {"role": "db"},
        }
    )
    result = ck.check_minions("G@role:web and not L@plain", "compound")
    assert sorted(result["minions"]) == sorted(["o'brien", 'x{y}"z'])
    result = ck.check_minions("G@role:web and not L@o'brien", "compound")
    assert result["minions"] == ['x{y}"z']


def test_grain_trie_index_follows_cache_writes(ckminions):
    ck = ckminions({"m1": {"os": "a"}, "m2": {"os": "b"}})
    with patch.dict(
        ck.opts, {"enable_grain_trie_index": True, "grain_trie_mmap_size": 5000}
    ):
        # Repeat so a trie, where one is used, is built and then reused.
        for _ in range(3):
            assert ck.check_minions("os:a", "grain")["minions"] == ["m1"]
        ck.cache.store("grains", "m1", {"os": "b"})
        assert ck.check_minions("os:a", "grain")["minions"] == []
        assert sorted(ck.check_minions("os:b", "grain")["minions"]) == ["m1", "m2"]
