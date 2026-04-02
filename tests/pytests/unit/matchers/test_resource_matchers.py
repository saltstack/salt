"""
Tests for the T@ (resource_match) and M@ (managing_minion_match) matchers.
"""

import pytest

import salt.matchers.managing_minion_match as managing_minion_match
import salt.matchers.resource_match as resource_match

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RESOURCES = {
    "dummy": ["dummy-01", "dummy-02", "dummy-03"],
    "ssh": ["node1", "localhost"],
}


@pytest.fixture
def opts_with_resources(minion_opts):
    minion_opts["id"] = "minion"
    minion_opts["resources"] = RESOURCES
    return minion_opts


@pytest.fixture
def opts_no_resources(minion_opts):
    minion_opts["id"] = "minion"
    minion_opts.pop("resources", None)
    return minion_opts


# ---------------------------------------------------------------------------
# resource_match (T@) tests
# ---------------------------------------------------------------------------


def test_resource_match_bare_type_hits(opts_with_resources):
    """T@dummy matches a minion that manages at least one dummy resource."""
    assert resource_match.match("dummy", opts=opts_with_resources) is True


def test_resource_match_bare_type_miss(opts_with_resources):
    """T@vcf_host does not match when the minion has no vcf_host resources."""
    assert resource_match.match("vcf_host", opts=opts_with_resources) is False


def test_resource_match_full_srn_hits(opts_with_resources):
    """T@dummy:dummy-01 matches when dummy-01 is in the dummy resource list."""
    assert resource_match.match("dummy:dummy-01", opts=opts_with_resources) is True


def test_resource_match_full_srn_miss_wrong_id(opts_with_resources):
    """T@dummy:dummy-99 does not match — dummy-99 is not managed."""
    assert resource_match.match("dummy:dummy-99", opts=opts_with_resources) is False


def test_resource_match_full_srn_miss_wrong_type(opts_with_resources):
    """T@vcf_host:dummy-01 does not match — type is wrong."""
    assert resource_match.match("vcf_host:dummy-01", opts=opts_with_resources) is False


def test_resource_match_ssh_type(opts_with_resources):
    """T@ssh matches a minion that manages SSH resources."""
    assert resource_match.match("ssh", opts=opts_with_resources) is True


def test_resource_match_ssh_full_srn(opts_with_resources):
    """T@ssh:node1 matches the specific SSH resource."""
    assert resource_match.match("ssh:node1", opts=opts_with_resources) is True


def test_resource_match_no_resources(opts_no_resources):
    """T@dummy returns False when opts has no resources configured."""
    assert resource_match.match("dummy", opts=opts_no_resources) is False


def test_resource_match_empty_resources(minion_opts):
    """T@dummy returns False when opts["resources"] is an empty dict."""
    minion_opts["resources"] = {}
    assert resource_match.match("dummy", opts=minion_opts) is False


# ---------------------------------------------------------------------------
# managing_minion_match (M@) tests
# ---------------------------------------------------------------------------


def test_managing_minion_match_own_id(opts_with_resources):
    """M@minion matches a minion with id='minion'."""
    assert managing_minion_match.match("minion", opts=opts_with_resources) is True


def test_managing_minion_match_different_id(opts_with_resources):
    """M@other-minion does not match a minion with id='minion'."""
    assert (
        managing_minion_match.match("other-minion", opts=opts_with_resources) is False
    )


def test_managing_minion_match_empty_string(opts_with_resources):
    """M@ with empty string does not match."""
    assert managing_minion_match.match("", opts=opts_with_resources) is False


def test_managing_minion_match_minion_id_kwarg(minion_opts):
    """The minion_id kwarg overrides opts['id'] for the comparison."""
    minion_opts["id"] = "minion"
    assert (
        managing_minion_match.match(
            "override-id", opts=minion_opts, minion_id="override-id"
        )
        is True
    )
    assert (
        managing_minion_match.match("minion", opts=minion_opts, minion_id="override-id")
        is False
    )
