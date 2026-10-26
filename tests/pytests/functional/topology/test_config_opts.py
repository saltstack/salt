"""
Functional tests for the master-topology option set in Salt's global
master config schema (``salt/config/__init__.py``).

Scope
-----
These tests cover the integration between a ``topology_*`` /
``auto_accept_masters`` option declaration (in ``VALID_OPTS`` +
``DEFAULT_MASTER_OPTS``) and the master config loader
(``salt.config.master_config``).  Tests are intentionally
loader-level: no master daemon is started.

The companion unit tests in
``tests/pytests/unit/topology/test_config_opts.py`` assert the raw
contents of the two dicts; here we exercise end-to-end YAML parsing +
``_validate_opts`` on real files on disk.

The complementary module ``test_config.py`` in the same directory
covers the standalone ``salt.config.topology`` loader (which reads
``/etc/salt/topology.conf``); this file is about the master-opts
plumbing only.
"""

import logging

import pytest

import salt.config

pytestmark = [
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# Reference tables -- single source of truth for every expected opt.
# ---------------------------------------------------------------------------
#
# Each entry maps the opt name to (expected_type, expected_default).
#
# Keep this list in sync with the ``VALID_OPTS`` / ``DEFAULT_MASTER_OPTS``
# additions made for master topology (RFC: rfcs/master-topology.md,
# section "New config options").  The unit tests re-use the same
# constants via a module-level import so a drift in one place
# surfaces as test failures in both.
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def master_conf_path(tmp_path):
    """Path to a per-test master config (file may or may not exist)."""
    return tmp_path / "master"


@pytest.fixture
def minimal_master_conf(master_conf_path):
    """
    Write a trivially-valid master config with no topology_* keys.

    Returns the path.  Used by backward-compat and default-loading
    tests.
    """
    master_conf_path.write_text(
        "# minimal master config -- no topology_* keys\nuser: root\n"
    )
    return str(master_conf_path)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_defaults_loaded_from_fresh_master_config(minimal_master_conf):
    """
    A master config file with no topology_* keys loads cleanly, and
    every topology opt is present in the returned opts with its
    documented default.
    """
    opts = salt.config.master_config(minimal_master_conf)

    for name, (expected_type, expected_default) in EXPECTED_TOPOLOGY_OPTS.items():
        assert name in opts, f"missing opt: {name!r}"
        assert isinstance(opts[name], expected_type), (
            f"{name!r}: expected {expected_type.__name__}, "
            f"got {type(opts[name]).__name__} ({opts[name]!r})"
        )
        assert (
            opts[name] == expected_default
        ), f"{name!r}: expected default {expected_default!r}, got {opts[name]!r}"


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------


def test_explicit_overrides_are_honored(master_conf_path):
    """
    Values set in the master config file override defaults for every
    topology opt (one override per opt, covers every type: bool, int,
    str, list).
    """
    master_conf_path.write_text(
        """\
topology_enabled: true
topology_config_file: /etc/salt/custom-topology.conf
topology_link_port: 4600
topology_summary_interval: 15
topology_breadcrumb_grace: 45
topology_breadcrumb_max_age: 1200
topology_push_cluster_grain: false
auto_accept_masters: true
topology_breadcrumb_cache_size: 2000000
topology_breadcrumb_cache_key_size: 128
topology_registry_cache_size: 20000
topology_registry_cache_key_size: 128
topology_detach_quiesce: 90
topology_summary_grains:
  - os
  - os_family
  - saltversion
"""
    )
    opts = salt.config.master_config(str(master_conf_path))

    assert opts["topology_enabled"] is True
    assert opts["topology_config_file"] == "/etc/salt/custom-topology.conf"
    assert opts["topology_link_port"] == 4600
    assert opts["topology_summary_interval"] == 15
    assert opts["topology_breadcrumb_grace"] == 45
    assert opts["topology_breadcrumb_max_age"] == 1200
    assert opts["topology_push_cluster_grain"] is False
    assert opts["auto_accept_masters"] is True
    assert opts["topology_breadcrumb_cache_size"] == 2_000_000
    assert opts["topology_breadcrumb_cache_key_size"] == 128
    assert opts["topology_registry_cache_size"] == 20_000
    assert opts["topology_registry_cache_key_size"] == 128
    assert opts["topology_detach_quiesce"] == 90
    assert opts["topology_summary_grains"] == ["os", "os_family", "saltversion"]


@pytest.mark.parametrize(
    "override_key,override_value,expected",
    [
        ("topology_enabled", "true", True),
        ("topology_enabled", "false", False),
        ("topology_push_cluster_grain", "false", False),
        ("auto_accept_masters", "true", True),
        ("topology_link_port", "4700", 4700),
        ("topology_summary_grains", "[os, kernel]", ["os", "kernel"]),
    ],
)
def test_single_override_honored(
    master_conf_path, override_key, override_value, expected
):
    """
    Each topology opt can be overridden individually without
    disturbing the others.
    """
    master_conf_path.write_text(f"{override_key}: {override_value}\n")
    opts = salt.config.master_config(str(master_conf_path))
    assert opts[override_key] == expected

    # Spot-check: other topology opts still at their defaults.
    for name, (_, default) in EXPECTED_TOPOLOGY_OPTS.items():
        if name == override_key:
            continue
        assert (
            opts[name] == default
        ), f"override of {override_key!r} unexpectedly changed {name!r}"


# ---------------------------------------------------------------------------
# Validation of invalid types
# ---------------------------------------------------------------------------


def test_invalid_int_type_rejected(master_conf_path, caplog):
    """
    A quoted non-numeric string in ``topology_link_port`` is rejected
    by ``_validate_opts`` with a warning that names the offending key.

    ``_validate_opts`` logs at WARNING and sets a return of False; it
    does not raise.  The daemon treats this as a non-fatal
    configuration error and continues to boot, so from the loader's
    perspective we assert on the warning record.
    """
    master_conf_path.write_text('topology_link_port: "not a number"\n')
    with caplog.at_level(logging.WARNING, logger="salt.config"):
        salt.config.master_config(str(master_conf_path))

    messages = [rec.getMessage() for rec in caplog.records]
    assert any(
        "topology_link_port" in m and "invalid type" in m for m in messages
    ), f"expected validation warning naming topology_link_port, got: {messages!r}"


def test_invalid_bool_type_rejected(master_conf_path, caplog):
    """
    An integer where a bool is required (``auto_accept_masters: 1``)
    triggers a validation warning naming the key.
    """
    master_conf_path.write_text("auto_accept_masters: 1\n")
    with caplog.at_level(logging.WARNING, logger="salt.config"):
        salt.config.master_config(str(master_conf_path))

    messages = [rec.getMessage() for rec in caplog.records]
    assert any(
        "auto_accept_masters" in m and "invalid type" in m for m in messages
    ), f"expected validation warning naming auto_accept_masters, got: {messages!r}"


def test_invalid_list_type_rejected(master_conf_path, caplog):
    """
    A scalar string where a list is required
    (``topology_summary_grains: os``) triggers a validation warning
    naming the key.
    """
    master_conf_path.write_text("topology_summary_grains: os\n")
    with caplog.at_level(logging.WARNING, logger="salt.config"):
        salt.config.master_config(str(master_conf_path))

    messages = [rec.getMessage() for rec in caplog.records]
    assert any(
        "topology_summary_grains" in m and "invalid type" in m for m in messages
    ), (
        "expected validation warning naming topology_summary_grains, "
        f"got: {messages!r}"
    )


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


def test_backward_compat_empty_master_config(master_conf_path):
    """
    A completely empty master config file still produces an opts dict
    with all topology opts at their defaults -- i.e. no in-tree code
    requires any of them to be set explicitly, and no implicit
    migration side effects fire for an empty config.
    """
    master_conf_path.write_text("")
    opts = salt.config.master_config(str(master_conf_path))

    for name, (_, default) in EXPECTED_TOPOLOGY_OPTS.items():
        assert opts[name] == default


def test_backward_compat_cluster_only_master_config(master_conf_path):
    """
    A legacy clustered-master config (defines ``cluster_id`` /
    ``cluster_peers`` but no topology_* keys) still loads cleanly and
    gets topology defaults.  Confirms topology opts are additive, not
    coupled to any existing cluster_* opt.
    """
    master_conf_path.write_text(
        """\
cluster_id: legacy
cluster_peers:
  - 10.0.0.2
  - 10.0.0.3
cluster_pki_dir: /etc/salt/pki/cluster
"""
    )
    opts = salt.config.master_config(str(master_conf_path))

    # Cluster opts came through
    assert opts["cluster_id"] == "legacy"
    assert opts["cluster_peers"] == ["10.0.0.2", "10.0.0.3"]

    # Topology opts at their defaults
    for name, (_, default) in EXPECTED_TOPOLOGY_OPTS.items():
        assert opts[name] == default, f"{name!r} not at default"


def test_backward_compat_missing_file(tmp_path):
    """
    A ``master_config`` call pointed at a path that does not exist
    returns an opts dict populated with every topology default.  This
    is the "fresh install, no master config yet" path.
    """
    opts = salt.config.master_config(str(tmp_path / "does-not-exist"))

    for name, (expected_type, default) in EXPECTED_TOPOLOGY_OPTS.items():
        assert name in opts
        assert isinstance(opts[name], expected_type)
        assert opts[name] == default
