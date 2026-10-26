"""
Unit tests for master-topology additions to Salt's global config
schema.

Asserts on the raw ``VALID_OPTS`` / ``DEFAULT_MASTER_OPTS`` /
``DEFAULT_MINION_OPTS`` dicts.  These are complementary to the
loader-level functional tests in
``tests/pytests/functional/topology/test_config_opts.py``: the
functional tests exercise YAML parsing + validator; the unit tests
guard the shape of the schema itself.

Covers:

* Every topology opt is declared in ``VALID_OPTS`` and
  ``DEFAULT_MASTER_OPTS`` (and the companion minion-side
  ``master_cluster_id``).
* Declared type in ``VALID_OPTS`` matches the type of the value in
  ``DEFAULT_MASTER_OPTS``.
* Default values are sensible (TCP port in range, intervals positive,
  cache sizes > 0, path is absolute).
"""

import pytest

import salt.config

# ---------------------------------------------------------------------------
# Reference tables -- mirror the functional-test module so a drift in
# the production schema surfaces in both test files.
# ---------------------------------------------------------------------------

EXPECTED_TOPOLOGY_OPTS = {
    "topology_enabled": (bool, False),
    "topology_config_file": (str, "/etc/salt/topology.conf"),
    "topology_link_port": (int, 4521),
    "topology_summary_interval": (int, 30),
    "topology_breadcrumb_grace": (int, 30),
    "topology_breadcrumb_max_age": (int, 600),
    "topology_push_cluster_grain": (bool, True),
    "auto_accept_masters": (bool, False),
    "topology_breadcrumb_cache_size": (int, 1_000_000),
    "topology_breadcrumb_cache_key_size": (int, 64),
    "topology_registry_cache_size": (int, 10_000),
    "topology_registry_cache_key_size": (int, 64),
    "topology_detach_quiesce": (int, 60),
    "topology_summary_grains": (list, []),
}


# ---------------------------------------------------------------------------
# Presence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("opt_name", list(EXPECTED_TOPOLOGY_OPTS))
def test_opt_declared_in_valid_opts(opt_name):
    """Every topology opt is declared in ``salt.config.VALID_OPTS``."""
    assert opt_name in salt.config.VALID_OPTS


@pytest.mark.parametrize("opt_name", list(EXPECTED_TOPOLOGY_OPTS))
def test_opt_has_default_in_master_opts(opt_name):
    """
    Every topology opt has an entry in
    ``salt.config.DEFAULT_MASTER_OPTS``.
    """
    assert opt_name in salt.config.DEFAULT_MASTER_OPTS


def test_master_cluster_id_declared_in_valid_opts():
    """
    ``master_cluster_id`` -- the minion-side grain populated by the
    master's auth-response hook -- is declared with ``str`` type.
    """
    assert "master_cluster_id" in salt.config.VALID_OPTS
    assert salt.config.VALID_OPTS["master_cluster_id"] is str


def test_master_cluster_id_defaults_to_empty_string():
    """
    ``master_cluster_id`` defaults to the empty string on minions.
    Empty is the "no cluster yet / standalone master" sentinel; the
    auth-response hook overwrites it when the minion attaches to a
    cluster.
    """
    assert "master_cluster_id" in salt.config.DEFAULT_MINION_OPTS
    assert salt.config.DEFAULT_MINION_OPTS["master_cluster_id"] == ""


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "opt_name,expected_type",
    [(name, t) for name, (t, _) in EXPECTED_TOPOLOGY_OPTS.items()],
)
def test_valid_opts_type_matches(opt_name, expected_type):
    """
    The type recorded in ``VALID_OPTS`` is exactly the expected type.
    """
    assert salt.config.VALID_OPTS[opt_name] is expected_type


@pytest.mark.parametrize(
    "opt_name,expected_type",
    [(name, t) for name, (t, _) in EXPECTED_TOPOLOGY_OPTS.items()],
)
def test_default_master_opts_value_type_matches(opt_name, expected_type):
    """
    The actual Python type of the default value matches the declared
    type.  ``bool`` is matched exactly (``True``/``False`` -- not ``1``
    or ``0``) because ``_validate_opts`` treats bool as a distinct
    type.
    """
    value = salt.config.DEFAULT_MASTER_OPTS[opt_name]
    if expected_type is bool:
        assert value is True or value is False
    elif expected_type is list:
        # ``immutabletypes.freeze`` wraps list defaults in an
        # ``ImmutableList`` (a ``collections.abc.Sequence`` -- not a
        # ``list`` subclass).  Coerce before isinstance to assert on
        # shape, not wrapper identity.
        assert isinstance(list(value), expected_type)
    else:
        assert isinstance(value, expected_type)


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "opt_name,expected_default",
    [(name, d) for name, (_, d) in EXPECTED_TOPOLOGY_OPTS.items()],
)
def test_default_master_opts_value(opt_name, expected_default):
    """Each default value is exactly what the RFC specifies."""
    actual = salt.config.DEFAULT_MASTER_OPTS[opt_name]
    # ``immutabletypes.freeze`` wraps list defaults; normalize for
    # equality against the plain-list expectation.
    if isinstance(expected_default, list):
        actual = list(actual)
    assert actual == expected_default


def test_topology_link_port_in_valid_range():
    """Default TCP port lands in the unreserved user range (1024-65535)."""
    port = salt.config.DEFAULT_MASTER_OPTS["topology_link_port"]
    assert 1024 <= port <= 65535


@pytest.mark.parametrize(
    "opt_name",
    [
        "topology_summary_interval",
        "topology_breadcrumb_grace",
        "topology_breadcrumb_max_age",
        "topology_detach_quiesce",
    ],
)
def test_interval_default_positive(opt_name):
    """Every seconds-interval default is strictly positive."""
    assert salt.config.DEFAULT_MASTER_OPTS[opt_name] > 0


@pytest.mark.parametrize(
    "opt_name",
    [
        "topology_breadcrumb_cache_size",
        "topology_breadcrumb_cache_key_size",
        "topology_registry_cache_size",
        "topology_registry_cache_key_size",
    ],
)
def test_cache_sizing_default_positive(opt_name):
    """MmapCache sizing defaults are strictly positive."""
    assert salt.config.DEFAULT_MASTER_OPTS[opt_name] > 0


def test_breadcrumb_grace_le_max_age():
    """
    The grace window cannot exceed the max-age window -- otherwise
    breadcrumbs would be reaped before leaving the grace period.
    """
    grace = salt.config.DEFAULT_MASTER_OPTS["topology_breadcrumb_grace"]
    max_age = salt.config.DEFAULT_MASTER_OPTS["topology_breadcrumb_max_age"]
    assert grace <= max_age


def test_topology_config_file_absolute_path():
    """Default topology config path is absolute (not a relative path)."""
    import os

    path = salt.config.DEFAULT_MASTER_OPTS["topology_config_file"]
    assert os.path.isabs(path), f"not an absolute path: {path!r}"


def test_topology_enabled_defaults_off():
    """
    The feature is opt-in: ``topology_enabled`` defaults to False so
    existing masters are unaffected until an operator flips it on.
    """
    assert salt.config.DEFAULT_MASTER_OPTS["topology_enabled"] is False


def test_auto_accept_masters_defaults_off():
    """
    Mirrors the ``auto_accept`` posture: cross-master trust is NOT
    auto-granted by default.
    """
    assert salt.config.DEFAULT_MASTER_OPTS["auto_accept_masters"] is False


def test_topology_summary_grains_default_empty():
    """
    ``topology_summary_grains`` is an opt-in fan-out list; empty by
    default means the summary thread does not ship extra grains.
    """
    assert list(salt.config.DEFAULT_MASTER_OPTS["topology_summary_grains"]) == []


# ---------------------------------------------------------------------------
# Cross-check against functional reference
# ---------------------------------------------------------------------------


def test_reference_table_matches_functional_module():
    """
    The ``EXPECTED_TOPOLOGY_OPTS`` tables in the unit and functional
    modules are kept intentionally identical.  A drift in one and not
    the other means someone updated the schema in one place but not
    the other; this test turns that drift into a loud failure.
    """
    from tests.pytests.functional.topology import test_config_opts as functional_mod

    assert EXPECTED_TOPOLOGY_OPTS == functional_mod.EXPECTED_TOPOLOGY_OPTS
