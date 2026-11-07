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
    "topology_peers": (list, []),
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


# Opts documented in doc/topics/master-topology/index.md "Master config
# opts" table.  Pin name + default so a rename or default flip in
# ``salt/config/__init__.py`` breaks this test loudly and the doc
# table is updated in the same change.  Entries intentionally mirror
# the doc rows one-for-one.
DOCUMENTED_INDEX_MD_OPTS = {
    # name: (type, default)  --- matches "Master config opts" table in
    # doc/topics/master-topology/index.md (around line 100 onward).
    "topology_enabled": (bool, False),
    # ``cluster_id`` is declared as ``str`` in VALID_OPTS but defaults
    # to None; the loader treats None as "unset" and
    # ``validate_topology_config`` rejects a None value when
    # ``topology_enabled`` is True.
    "cluster_id": (str, None),
    "topology_peers": (list, []),
    "topology_event_subscriptions": ((type(None), list), None),
    "topology_link_port": (int, 4521),
    "topology_summary_interval": (int, 30),
    "topology_breadcrumb_grace": (int, 30),
    "topology_breadcrumb_max_age": (int, 600),
    "topology_push_cluster_grain": (bool, True),
    "topology_detach_quiesce": (int, 60),
    "topology_summary_grains": (list, []),
    "topology_breadcrumb_cache_size": (int, 1_000_000),
    "topology_breadcrumb_cache_key_size": (int, 64),
    "topology_registry_cache_size": (int, 10_000),
    "topology_registry_cache_key_size": (int, 64),
    "auto_accept_masters": (bool, False),
}


# pub-ack / pub-complete opts land in salt.config but are documented
# in doc/topics/master-topology/pub-ack-complete.md rather than the
# main index.md table.  Pin them here so a rename/default flip on
# that surface also breaks the test.
DOCUMENTED_PUB_ACK_OPTS = {
    "topology_pub_ack": (bool, True),
    "topology_pub_ack_consumer": (bool, True),
    "topology_pub_complete_enabled": (bool, True),
    "topology_pub_complete_timeout": (float, 60.0),
    "topology_pub_complete_max_inflight": (int, 1024),
    "topology_wait": (float, 2.0),
}

# ``topology_event_subscriptions`` is declared with
# ``(type(None), list)`` because the None default means
# "use DEFAULT_EVENT_SUBSCRIPTIONS from salt.config.topology"
# rather than an empty subscription set.  Asserted separately.


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


def test_topology_peers_defaults_empty():
    """
    ``topology_peers`` defaults to an empty list on an opt-in
    feature; operators add peer entries only when they switch
    topology on.
    """
    assert list(salt.config.DEFAULT_MASTER_OPTS["topology_peers"]) == []


def test_topology_event_subscriptions_defaults_none():
    """
    ``topology_event_subscriptions`` defaults to ``None`` as a
    sentinel.  ``load_topology_config`` interprets None as "use
    :data:`DEFAULT_EVENT_SUBSCRIPTIONS` from salt.config.topology".
    An empty list would be a different, operator-chosen setting
    (nothing forwarded).
    """
    assert salt.config.DEFAULT_MASTER_OPTS["topology_event_subscriptions"] is None


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


# ---------------------------------------------------------------------------
# Documentation pinning: doc/topics/master-topology/index.md table
# ---------------------------------------------------------------------------
#
# The user-facing doc tables are the public API surface.  These tests
# pin every documented opt's name + default against ``salt.config`` so
# a rename or default flip breaks the test and forces the doc table
# to be updated in the same change.


@pytest.mark.parametrize(
    "opt_name,expected_type,expected_default",
    [(n, t, d) for n, (t, d) in DOCUMENTED_INDEX_MD_OPTS.items()],
)
def test_index_md_documented_opt_matches_schema(
    opt_name, expected_type, expected_default
):
    """
    Every row in ``doc/topics/master-topology/index.md`` "Master
    config opts" table pins to the real ``VALID_OPTS`` type and
    ``DEFAULT_MASTER_OPTS`` default.
    """
    assert opt_name in salt.config.VALID_OPTS, (
        f"{opt_name!r} is documented in index.md but missing from "
        "salt.config.VALID_OPTS -- doc table and schema drifted."
    )
    assert salt.config.VALID_OPTS[opt_name] == expected_type, (
        f"{opt_name!r} VALID_OPTS type drifted from the documented "
        f"type {expected_type!r}."
    )
    assert opt_name in salt.config.DEFAULT_MASTER_OPTS, (
        f"{opt_name!r} is documented in index.md but has no default "
        "in salt.config.DEFAULT_MASTER_OPTS."
    )
    actual_default = salt.config.DEFAULT_MASTER_OPTS[opt_name]
    # Normalize immutabletypes.freeze wrapping around list defaults.
    if isinstance(expected_default, list):
        actual_default = list(actual_default)
    assert actual_default == expected_default, (
        f"{opt_name!r} default drifted from the documented "
        f"{expected_default!r} to {actual_default!r} -- doc row and "
        "schema are out of sync."
    )


@pytest.mark.parametrize(
    "opt_name,expected_type,expected_default",
    [(n, t, d) for n, (t, d) in DOCUMENTED_PUB_ACK_OPTS.items()],
)
def test_pub_ack_documented_opt_matches_schema(
    opt_name, expected_type, expected_default
):
    """
    Every pub-ack / pub-complete opt documented in
    ``doc/topics/master-topology/pub-ack-complete.md`` pins to the
    real ``VALID_OPTS`` type and ``DEFAULT_MASTER_OPTS`` default.
    """
    assert opt_name in salt.config.VALID_OPTS
    assert salt.config.VALID_OPTS[opt_name] is expected_type
    assert opt_name in salt.config.DEFAULT_MASTER_OPTS
    assert salt.config.DEFAULT_MASTER_OPTS[opt_name] == expected_default


def test_no_undocumented_operator_facing_topology_opts():
    """
    Catch a new ``topology_*`` opt that lands in schema but misses
    both doc tables (index.md and pub-ack-complete.md).  Anything
    added to the schema is either documented or explicitly listed
    here as internal.
    """
    # Known-internal / handshake tunables (declared but intentionally
    # not surfaced in the operator docs -- see index.md "Treat them as
    # internal tunables.").  Add to this set only with a comment
    # explaining why the opt is operator-invisible.
    INTERNAL_NOT_DOCUMENTED = frozenset(
        {
            # Handshake knobs read with .get() defaults from
            # salt/topology/link.py; not in VALID_OPTS at all today.
        }
    )
    documented = (
        set(DOCUMENTED_INDEX_MD_OPTS)
        | set(DOCUMENTED_PUB_ACK_OPTS)
        | INTERNAL_NOT_DOCUMENTED
    )
    schema_topology_opts = {
        name for name in salt.config.VALID_OPTS if name.startswith("topology_")
    }
    undocumented = schema_topology_opts - documented
    assert not undocumented, (
        f"Undocumented operator-facing topology opts: {sorted(undocumented)!r}. "
        "Add them to doc/topics/master-topology/index.md or the "
        "pub-ack-complete.md table (and the matching DOCUMENTED_* "
        "dict in this file), or add them to INTERNAL_NOT_DOCUMENTED "
        "with a comment explaining why."
    )
