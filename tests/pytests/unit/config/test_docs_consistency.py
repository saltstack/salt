"""
Documentation consistency tests for configuration options.

These tests cover the specific symptoms enumerated in the EPIC
saltstack/salt#58112 (PR2 audit). They are intentionally narrow: each test
asserts a single observable fact about a single file, so a regression is
easy to locate.
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def repo_root():
    # Walk up until we find a Makefile + conf/master sentinel.
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "conf" / "master").is_file() and (
            parent / "salt" / "config" / "__init__.py"
        ).is_file():
            return parent
    raise RuntimeError("could not locate Salt repo root from test file")


@pytest.fixture(scope="module")
def master_rst(repo_root):
    return (repo_root / "doc/ref/configuration/master.rst").read_text()


@pytest.fixture(scope="module")
def minion_rst(repo_root):
    return (repo_root / "doc/ref/configuration/minion.rst").read_text()


@pytest.fixture(scope="module")
def conf_master(repo_root):
    return (repo_root / "conf/master").read_text()


@pytest.fixture(scope="module")
def conf_minion(repo_root):
    return (repo_root / "conf/minion").read_text()


@pytest.fixture(scope="module")
def config_init(repo_root):
    return (repo_root / "salt/config/__init__.py").read_text()


@pytest.fixture(scope="module")
def logging_rst(repo_root):
    return (repo_root / "doc/ref/configuration/logging/index.rst").read_text()


@pytest.fixture(scope="module")
def salt_key_rst(repo_root):
    return (repo_root / "doc/ref/cli/salt-key.rst").read_text()


@pytest.fixture(scope="module")
def schedule_state(repo_root):
    return (repo_root / "salt/states/schedule.py").read_text()


@pytest.fixture(scope="module")
def timezone_state(repo_root):
    return (repo_root / "salt/states/timezone.py").read_text()


@pytest.fixture(scope="module")
def grains_core(repo_root):
    return (repo_root / "salt/grains/core.py").read_text()


# --- #59910: fips_mode -------------------------------------------------------


def test_fips_mode_documented_in_master_rst(master_rst):
    assert ".. conf_master:: fips_mode" in master_rst


def test_fips_mode_documented_in_minion_rst(minion_rst):
    assert ".. conf_minion:: fips_mode" in minion_rst


def test_fips_mode_in_example_master_conf(conf_master):
    assert "fips_mode" in conf_master


def test_fips_mode_in_example_minion_conf(conf_minion):
    assert "fips_mode" in conf_minion


# --- #58891: event_match_type ------------------------------------------------


def test_event_match_type_documented_in_master_rst(master_rst):
    assert ".. conf_master:: event_match_type" in master_rst
    # check we documented all five valid values
    for value in ("startswith", "endswith", "find", "regex", "fnmatch"):
        assert value in master_rst, value


def test_event_match_type_documented_in_minion_rst(minion_rst):
    assert ".. conf_minion:: event_match_type" in minion_rst
    for value in ("startswith", "endswith", "find", "regex", "fnmatch"):
        assert value in minion_rst, value


# --- #66587: state_top_saltenv ----------------------------------------------


def test_state_top_saltenv_master_doc_mentions_saltenv_precedence(master_rst):
    # find the state_top_saltenv block
    start = master_rst.index(".. conf_master:: state_top_saltenv")
    end = master_rst.index(".. conf_master::", start + 1)
    block = master_rst[start:end]
    # body must reference saltenv to clarify when this option actually applies
    assert "saltenv" in block.lower()
    assert "fallback" in block.lower()


def test_state_top_saltenv_minion_doc_mentions_saltenv_precedence(minion_rst):
    start = minion_rst.index(".. conf_minion:: state_top_saltenv")
    end = minion_rst.index(".. conf_minion::", start + 1)
    block = minion_rst[start:end]
    assert "saltenv" in block.lower()
    assert "fallback" in block.lower()


# --- #66533: multi-master DNS retry / acceptance_wait_time -------------------


def test_retry_dns_block_documents_failover_force_to_zero(minion_rst):
    start = minion_rst.index(".. conf_minion:: retry_dns\n")
    end = minion_rst.index(".. conf_minion::", start + 1)
    block = minion_rst[start:end]
    assert "failover" in block.lower()
    assert "acceptance_wait_time" in block


def test_acceptance_wait_time_block_documents_dns_retry_role(minion_rst):
    start = minion_rst.index(".. conf_minion:: acceptance_wait_time\n")
    end = minion_rst.index(".. conf_minion::", start + 1)
    block = minion_rst[start:end]
    assert "failover" in block.lower()
    assert "dns" in block.lower()


# --- #65866: grains.fqdns default -------------------------------------------


def test_fqdns_docstring_describes_platform_defaults(grains_core):
    # find the fqdns docstring
    idx = grains_core.index("def fqdns()")
    snippet = grains_core[idx : idx + 1500]
    assert "enable_fqdns_grains" in snippet
    # the docstring must mention the platforms with default-False behavior
    for token in ("Windows", "proxy", "AIX"):
        assert token in snippet, token
    # and the obsolete "actively disable it" framing must be gone
    assert "actively disable" not in snippet


# --- #58893: key_logfile ----------------------------------------------------


def test_key_logfile_xxx_comment_removed(config_init):
    # The original stale comment was:
    #     # XXX: Remove 'key_logfile' support in 2014.1.0
    # confirm the "XXX: Remove" form is gone (the prose explanation that
    # replaced it is fine and is not flagged here).
    assert "XXX: Remove 'key_logfile'" not in config_init


def test_key_logfile_documented_in_master_rst(master_rst):
    assert ".. conf_master:: key_logfile" in master_rst


def test_key_logfile_documented_in_minion_rst(minion_rst):
    assert ".. conf_minion:: key_logfile" in minion_rst


# --- #60732: cron + splay ---------------------------------------------------


def test_schedule_state_documents_cron_plus_splay(schedule_state):
    # there must be an example combining cron and splay
    assert "cron: '*/5 * * * *'" in schedule_state
    # and the doc must explicitly state cron and splay work together
    assert "cron`` and ``splay`` can be combined" in schedule_state


# --- #60630: timezone utc default -------------------------------------------


def test_timezone_state_docstring_default_is_consistent(timezone_state):
    # both the prose and the parameter doc must agree on default = True
    assert "defaults ``utc`` to ``True``" in timezone_state
    # the old conflicting "By default, the hardware clock is set to localtime"
    # phrasing should be gone
    assert "By default, the hardware clock is set to localtime" not in timezone_state


# --- #61963: master_type str default ----------------------------------------


def test_master_type_str_default_explained(minion_rst):
    start = minion_rst.index(".. conf_minion:: master_type")
    end = minion_rst.index(".. conf_minion::", start + 1)
    block = minion_rst[start:end]
    # the str-default case must describe what behavior is selected
    assert "hot" in block.lower()
    assert "multi-master" in block.lower()


# --- #60965: worker_threads tuning ------------------------------------------


def test_worker_threads_documents_syndic_consideration(master_rst):
    start = master_rst.index(".. conf_master:: worker_threads")
    end = master_rst.index(".. conf_master::", start + 1)
    block = master_rst[start:end]
    assert "syndic" in block.lower()


# --- #61293: http_*_timeout -------------------------------------------------


def test_http_connect_timeout_minion_distinguishes_from_request_timeout(minion_rst):
    start = minion_rst.index(".. conf_minion:: http_connect_timeout")
    end = minion_rst.index(".. conf_minion::", start + 1)
    block = minion_rst[start:end]
    assert "initial" in block.lower() or "handshake" in block.lower()
    assert "request_timeout" in block


def test_http_request_timeout_minion_describes_entire_request(minion_rst):
    start = minion_rst.index(".. conf_minion:: http_request_timeout")
    end = minion_rst.index(".. conf_minion::", start + 1)
    block = minion_rst[start:end]
    assert "entire" in block.lower()


def test_http_timeouts_master_points_at_minion_for_user_fetches(master_rst):
    for opt in ("http_connect_timeout", "http_request_timeout"):
        start = master_rst.index(f".. conf_master:: {opt}")
        end = master_rst.index(".. conf_master::", start + 1)
        block = master_rst[start:end]
        # master docs must redirect "user-facing fetches" guidance to minion
        assert ":conf_minion:" in block


# --- #57416: ssh_priv -------------------------------------------------------


def test_ssh_priv_documented_in_master_rst(master_rst):
    assert ".. conf_master:: ssh_priv\n" in master_rst


def test_ssh_priv_in_example_master_conf(conf_master):
    assert "ssh_priv:" in conf_master or "#ssh_priv:" in conf_master


# --- #69109: retry_dns inconsistency ----------------------------------------


def test_retry_dns_block_mentions_failover_critical_log(minion_rst):
    start = minion_rst.index(".. conf_minion:: retry_dns\n")
    end = minion_rst.index(".. conf_minion::", start + 1)
    block = minion_rst[start:end]
    # the actual code logs CRITICAL when retry_dns != 0 with failover master_type
    assert "CRITICAL" in block or "critical" in block.lower()


# --- #66270: request_channel_timeout default --------------------------------


def test_request_channel_timeout_default_matches_code(config_init, minion_rst):
    # confirm code default
    assert '"request_channel_timeout": 60' in config_init
    # confirm doc default matches
    start = minion_rst.index(".. conf_minion:: request_channel_timeout")
    end = minion_rst.index(".. conf_minion::", start + 1)
    block = minion_rst[start:end]
    assert "Default: ``60``" in block


# --- #66884: log_granular_levels --------------------------------------------


def test_log_granular_levels_uses_name_format(logging_rst):
    start = logging_rst.index(".. conf_log:: log_granular_levels")
    end = logging_rst.index(".. conf_log::", start + 1)
    block = logging_rst[start:end]
    # the doc must recommend %(name)s rather than %(module)s
    assert "%(name)s" in block
    # and must call out that %(module)s only prints the short name
    assert "short" in block.lower()


# --- #63109: salt-key --include-* -------------------------------------------


def test_salt_key_rst_documents_new_include_flags(salt_key_rst):
    for flag in ("--include-accepted", "--include-rejected", "--include-denied"):
        assert f".. option:: {flag}" in salt_key_rst, flag


def test_salt_key_rst_marks_include_all_deprecated(salt_key_rst):
    start = salt_key_rst.index(".. option:: --include-all")
    end = salt_key_rst.index(".. option::", start + 1)
    block = salt_key_rst[start:end]
    assert "deprecated" in block.lower()
