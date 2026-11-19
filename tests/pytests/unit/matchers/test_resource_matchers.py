"""
Tests for the T@ (resource_match) and M@ (managing_minion_match) matchers.
"""

import pytest

import salt.matchers.managing_minion_match as managing_minion_match
import salt.matchers.resource_match as resource_match
from tests.support.mock import patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RESOURCES = {
    "dummy": ["dummy-01", "dummy-02", "dummy-03"],
    "ssh": ["node1", "localhost"],
}


def _fake_resource_loader(resources):
    """
    Build a dict shaped like ``salt.loader.resource(opts)``: every type
    in ``resources`` exposes a ``<type>.discover`` entry that yields the
    bare IDs for that type (generator semantics -- the matcher never
    materializes the full list).
    """
    funcs = {}
    for rtype, rids in resources.items():
        # Default argument captures the current list per iteration so each
        # closure gets its own values.
        def _discover(opts, _rids=rids):
            yield from _rids

        funcs[f"{rtype}.discover"] = _discover
    return funcs


@pytest.fixture
def opts_with_resources(minion_opts):
    """Opts configured with ``resource_types`` matching RESOURCES keys."""
    minion_opts["id"] = "minion"
    minion_opts["resource_types"] = list(RESOURCES)
    return minion_opts


@pytest.fixture
def opts_no_resources(minion_opts):
    """Opts with no resource_types -- matcher must return False."""
    minion_opts["id"] = "minion"
    minion_opts.pop("resource_types", None)
    return minion_opts


@pytest.fixture(autouse=True)
def patched_loader():
    """
    Patch ``salt.loader.resource`` so the matcher's lazy loader call
    sees the RESOURCES-backed fake.  Autouse so every test in this
    module gets it.
    """
    funcs = _fake_resource_loader(RESOURCES)
    with patch("salt.loader.resource", return_value=funcs):
        yield


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
    """T@dummy:dummy-99 does not match -- dummy-99 is not managed."""
    assert resource_match.match("dummy:dummy-99", opts=opts_with_resources) is False


def test_resource_match_full_srn_miss_wrong_type(opts_with_resources):
    """T@vcf_host:dummy-01 does not match -- type is wrong."""
    assert resource_match.match("vcf_host:dummy-01", opts=opts_with_resources) is False


def test_resource_match_ssh_type(opts_with_resources):
    """T@ssh matches a minion that manages SSH resources."""
    assert resource_match.match("ssh", opts=opts_with_resources) is True


def test_resource_match_ssh_full_srn(opts_with_resources):
    """T@ssh:node1 matches the specific SSH resource."""
    assert resource_match.match("ssh:node1", opts=opts_with_resources) is True


def test_resource_match_no_resources(opts_no_resources):
    """T@dummy returns False when opts has no resource_types configured."""
    assert resource_match.match("dummy", opts=opts_no_resources) is False


def test_resource_match_empty_resources(minion_opts):
    """T@dummy returns False when opts['resource_types'] is an empty list."""
    minion_opts["resource_types"] = []
    assert resource_match.match("dummy", opts=minion_opts) is False


def test_resource_match_srn_short_circuits_on_first_hit(opts_with_resources):
    """
    SRN matching must short-circuit on the first hit so a 200K-resource
    discover generator doesn't materialize the full inventory.  Patch
    the discover function to raise on any iteration past the first
    match, and assert the match still succeeds.
    """
    seen = {"count": 0}

    def _discover(_opts):
        for rid in ["dummy-01", "dummy-02", "dummy-03"]:
            seen["count"] += 1
            yield rid
            if rid == "dummy-01":
                # If we get here on iteration 2+, short-circuit failed.
                pass

    with patch("salt.loader.resource", return_value={"dummy.discover": _discover}):
        assert resource_match.match("dummy:dummy-01", opts=opts_with_resources) is True
    # First-match short-circuit should stop after yielding dummy-01.
    assert seen["count"] == 1


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
