"""
Unit tests for salt.grains.metadata

Regression coverage for #62061: EC2 ``user-data`` must be returned verbatim
instead of falling through to the ``=`` line-splitter, which previously
corrupted any user-data payload containing ``=`` characters
(e.g. cloud-init ``#cloud-config`` blocks with ``key=value`` lines).
"""

import logging

import pytest

import salt.grains.metadata as metadata
import salt.utils.http as http
from tests.support.mock import create_autospec, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {metadata: {"__opts__": {"metadata_server_grains": "True"}}}


def _make_mock_http(responses):
    """
    Build a mock for salt.utils.http.query that returns canned responses
    keyed by URL. Unknown URLs return an empty body dict so the recursion
    terminates cleanly.
    """

    def mock_http(url="", headers=False, header_list=None, **_kwargs):
        if url in responses:
            return responses[url]
        # Default: empty body, plain text. Mirrors what the metadata
        # service does for absent leaves and lets recursion bottom out.
        return {"body": "", "headers": {"Content-Type": "text/plain"}}

    return mock_http


def test_user_data_with_equals_is_returned_verbatim():
    """
    Regression for #62061: user-data containing ``=`` must be returned
    as-is, not split by the ``=`` fallthrough branch.

    Before the fix, a ``latest/`` listing of ``user-data`` would fall
    through to ``elif "=" in line`` once recursed into ``latest/user-data/``,
    or worse, the user-data body itself (which contains ``=``) would be
    split if any caller iterated over body lines. The fix routes
    ``user-data`` to a dedicated ``http.query`` of the leaf and stores
    the body verbatim.
    """
    user_data_body = (
        "#cloud-config\n"
        "runcmd:\n"
        "  - echo FOO=bar > /tmp/foo\n"
        "  - export PATH=/usr/local/bin:$PATH\n"
    )
    responses = {
        "http://169.254.169.254/latest/": {
            "body": "meta-data/\nuser-data",
            "headers": {"Content-Type": "text/plain"},
        },
        "http://169.254.169.254/latest/meta-data/": {
            "body": "",
            "headers": {"Content-Type": "text/plain"},
        },
        "http://169.254.169.254/latest/user-data": {
            "body": user_data_body,
            "headers": {"Content-Type": "text/plain"},
        },
    }

    with patch(
        "salt.utils.http.query",
        create_autospec(
            http.query, autospec=True, side_effect=_make_mock_http(responses)
        ),
    ):
        result = metadata.metadata()

    assert "user-data" in result, result
    # Verbatim — no splitting on "=", no key/value mangling.
    assert result["user-data"] == user_data_body
    # And specifically, the ``=`` characters in the payload must survive.
    assert "FOO=bar" in result["user-data"]
    assert "PATH=/usr/local/bin:$PATH" in result["user-data"]


def test_user_data_missing_returns_none_without_crashing():
    """
    When the EC2 metadata service has no user-data configured for the
    instance, the user-data leaf either 404s or returns an empty body.
    ``http.query(...).get("body", None)`` evaluates to ``None`` (or an
    empty string for an empty body); the grain must store that without
    raising, matching the existing behavior for any failed leaf fetch.
    """
    responses = {
        "http://169.254.169.254/latest/": {
            "body": "meta-data/\nuser-data",
            "headers": {"Content-Type": "text/plain"},
        },
        "http://169.254.169.254/latest/meta-data/": {
            "body": "",
            "headers": {"Content-Type": "text/plain"},
        },
        # user-data leaf returns a payload with no "body" key, simulating
        # the missing/404 case. .get("body", None) -> None.
        "http://169.254.169.254/latest/user-data": {
            "headers": {"Content-Type": "text/plain"},
        },
    }

    with patch(
        "salt.utils.http.query",
        create_autospec(
            http.query, autospec=True, side_effect=_make_mock_http(responses)
        ),
    ):
        result = metadata.metadata()

    assert "user-data" in result
    assert result["user-data"] is None


def test_equals_lines_other_than_user_data_still_parse_via_splitter():
    """
    The ``=`` fallthrough remains in place for legitimate metadata lines
    that carry ``key=value`` listings (e.g. role-credential aliases).
    Tightening the user-data predicate to ``line == "user-data"`` must
    NOT break that path, nor accidentally short-circuit a sub-path line
    that happens to end in ``user-data``.
    """
    # Simulate the security-credentials/ tree, where each line is
    # "alias=role-name". On the buggy original PR (line.endswith("user-data")),
    # an alias ending in "user-data" would silently skip the "=" split.
    responses = {
        "http://169.254.169.254/latest/": {
            "body": "meta-data/",
            "headers": {"Content-Type": "text/plain"},
        },
        "http://169.254.169.254/latest/meta-data/": {
            "body": "iam/",
            "headers": {"Content-Type": "text/plain"},
        },
        "http://169.254.169.254/latest/meta-data/iam/": {
            "body": "security-credentials/",
            "headers": {"Content-Type": "text/plain"},
        },
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/": {
            # "alias=role" — the "=" branch must still fire for this.
            "body": "myrole-user-data=role-arn-suffix",
            "headers": {"Content-Type": "text/plain"},
        },
        # And the recursive call following the alias must succeed.
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/myrole-user-data": {
            "body": "",
            "headers": {"Content-Type": "text/plain"},
        },
    }

    with patch(
        "salt.utils.http.query",
        create_autospec(
            http.query, autospec=True, side_effect=_make_mock_http(responses)
        ),
    ):
        result = metadata.metadata()

    # The "=" splitter routes "alias=role" into ret[value] = _search(prefix=key),
    # so the resulting key must be the right-hand side ("role-arn-suffix"),
    # NOT the literal line. This proves the "=" branch is still reached for
    # lines that end in "user-data" but are not the bare ``user-data`` leaf.
    sc = result["meta-data"]["iam"]["security-credentials"]
    assert "role-arn-suffix" in sc, sc
    assert "myrole-user-data=role-arn-suffix" not in sc, sc
