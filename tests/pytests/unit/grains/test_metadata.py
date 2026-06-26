"""
    Unit test for salt.grains.metadata


    :codeauthor: :email" `Gareth J. Greenaway <ggreenaway@vmware.com>

Regression coverage for #62061: EC2 ``user-data`` must be returned verbatim
instead of falling through to the ``=`` line-splitter, which previously
corrupted any user-data payload containing ``=`` characters
(e.g. cloud-init ``#cloud-config`` blocks with ``key=value`` lines).

Regression coverage for #65184: when ``salt.utils.http.query`` returns an
error response (4xx/5xx with a body, e.g. AWS IMDS returning HTTP 400 for a
bogus path produced by the legacy ``=``-splitter), the tornado backend
populates ``body`` and ``status`` but does NOT set ``headers``.
``salt.grains.metadata._search()`` previously indexed ``linedata["headers"]``
unconditionally and crashed with ``KeyError: 'headers'``, causing the entire
metadata grain to fail to load with::

    [CRITICAL] Failed to load grains defined in grain file metadata.metadata
    ...
    KeyError: 'headers'
"""

import logging

import pytest

import salt.grains.metadata as metadata
import salt.utils.http as http
from tests.support.mock import MagicMock, create_autospec, patch

log = logging.getLogger(__name__)


class MockSocketClass:
    def __init__(self, *args, **kwargs):
        pass

    def settimeout(self, *args, **kwargs):
        pass

    def connect_ex(self, *args, **kwargs):
        return 0


@pytest.fixture
def configure_loader_modules():
    return {metadata: {"__opts__": {"metadata_server_grains": "True"}}}


def test_metadata_search():
    def mock_http(
        url="",
        method="GET",
        headers=False,
        header_list=None,
        header_dict=None,
        status=False,
    ):
        metadata_vals = {
            "http://169.254.169.254/latest/api/token": {
                "body": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX==",
                "status": 200,
                "headers": {},
            },
            "http://169.254.169.254/latest/": {
                "body": "meta-data",
                "headers": {},
            },
            "http://169.254.169.254/latest/meta-data/": {
                "body": "ami-id\nami-launch-index\nami-manifest-path\nhostname",
                "headers": {},
            },
            "http://169.254.169.254/latest/meta-data/ami-id": {
                "body": "ami-xxxxxxxxxxxxxxxxx",
                "headers": {},
            },
            "http://169.254.169.254/latest/meta-data/ami-launch-index": {
                "body": "0",
                "headers": {},
            },
            "http://169.254.169.254/latest/meta-data/ami-manifest-path": {
                "body": "(unknown)",
                "headers": {},
            },
            "http://169.254.169.254/latest/meta-data/hostname": {
                "body": "ip-xx-x-xx-xx.us-west-2.compute.internal",
                "headers": {},
            },
        }

        return metadata_vals[url]

    with patch(
        "salt.utils.http.query",
        create_autospec(http.query, autospec=True, side_effect=mock_http),
    ):
        ret = metadata.metadata()
        assert ret == {
            "meta-data": {
                "ami-id": "ami-xxxxxxxxxxxxxxxxx",
                "ami-launch-index": "0",
                "ami-manifest-path": "(unknown)",
                "hostname": "ip-xx-x-xx-xx.us-west-2.compute.internal",
            }
        }

    with patch.dict(
        metadata.__context__,
        {
            "metadata_aws_token": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=="
        },
    ):
        with patch(
            "salt.utils.http.query",
            create_autospec(http.query, autospec=True, side_effect=mock_http),
        ):
            ret = metadata.metadata()
            assert ret == {
                "meta-data": {
                    "ami-id": "ami-xxxxxxxxxxxxxxxxx",
                    "ami-launch-index": "0",
                    "ami-manifest-path": "(unknown)",
                    "hostname": "ip-xx-x-xx-xx.us-west-2.compute.internal",
                }
            }


def test_metadata_refresh_token():
    with patch(
        "salt.utils.http.query",
        create_autospec(
            http.query,
            autospec=True,
            return_value={
                "body": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX==",
            },
        ),
    ):
        metadata._refresh_token()
        assert "metadata_aws_token" in metadata.__context__
        assert (
            metadata.__context__["metadata_aws_token"]
            == "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=="
        )


def test_metadata_virtual():
    with patch("socket.socket", MagicMock(return_value=MockSocketClass())):
        with patch(
            "salt.utils.http.query",
            create_autospec(
                http.query,
                autospec=True,
                return_value={"error": "[Errno -2] Name or service not known"},
            ),
        ):
            assert metadata.__virtual__() is False

        with patch(
            "salt.utils.http.query",
            create_autospec(
                http.query,
                autospec=True,
                return_value={
                    "body": "dynamic\nmeta-data\nuser-data",
                    "status": 200,
                },
            ),
        ):
            assert metadata.__virtual__() is True

        with patch(
            "salt.utils.http.query",
            create_autospec(
                http.query,
                autospec=True,
                side_effect=[
                    {
                        "body": "",
                        "status": 401,
                    },
                    {
                        "body": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX==",
                    },
                    {
                        "body": "dynamic\nmeta-data\nuser-data",
                        "status": 200,
                    },
                ],
            ),
        ):
            assert metadata.__virtual__() is True


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


def test_search_handles_error_response_without_headers_65184():
    """
    Regression for #65184: a recursive ``http.query`` call that returns an
    error-shaped response (``body`` present, ``headers`` absent — the shape
    produced by the tornado backend on HTTPError since 3006.3) must not
    crash ``_search()`` with ``KeyError: 'headers'``.

    The reporter's traceback shows the crash happens on the recursive call
    triggered by a top-level metadata listing entry (the ``prefix == "latest/"``
    branch), where the recursive ``_search`` then calls ``http.query`` for
    ``latest/dynamic/`` (or similar) and gets back an error response without a
    ``headers`` key. Before the fix the indexing ``linedata["headers"]`` raised.
    After the fix the missing-headers case is treated like "no Content-Type
    information" and parsing proceeds.
    """
    responses = {
        "http://169.254.169.254/latest/": {
            "body": "dynamic",
            "headers": {"Content-Type": "text/plain"},
        },
        # Recursive call: error-shape response. Body + status + error, NO
        # headers key. This is exactly what salt.utils.http.query returns on
        # tornado HTTPError since commit 43b7fb52842 (3006.3).
        "http://169.254.169.254/latest/dynamic/": {
            "body": "<html><body><h1>400 Bad request</h1></body></html>\n",
            "status": 400,
            "error": "HTTP 400: Bad request",
        },
    }

    with patch(
        "salt.utils.http.query",
        create_autospec(
            http.query, autospec=True, side_effect=_make_mock_http(responses)
        ),
    ):
        # Must not raise KeyError. Whatever it returns for the bad leaf is
        # secondary; the contract is "do not crash the whole grain load".
        result = metadata.metadata()

    assert isinstance(result, dict)
    assert "dynamic" in result


def test_search_handles_missing_headers_on_initial_query_65184():
    """
    Companion to the above: the very first call inside ``_search()`` can also
    produce a no-headers response (e.g. the metadata service returns 4xx for
    the top-level listing). The function must still return a dict instead of
    raising.
    """
    responses = {
        "http://169.254.169.254/latest/": {
            "body": "some-error-body",
            "status": 400,
            "error": "HTTP 400: Bad request",
        },
    }

    with patch(
        "salt.utils.http.query",
        create_autospec(
            http.query, autospec=True, side_effect=_make_mock_http(responses)
        ),
    ):
        result = metadata.metadata()

    # Either an empty dict or a parsed body is acceptable; the contract is
    # "no KeyError".
    assert isinstance(result, (dict, str))


def test_search_octet_stream_still_returns_body_verbatim():
    """
    Sanity guard: the existing ``application/octet-stream`` short-circuit
    (return body verbatim) must keep working. The fix for #65184 must not
    regress that path.
    """
    responses = {
        "http://169.254.169.254/latest/": {
            "body": "raw-octet-stream-payload",
            "headers": {"Content-Type": "application/octet-stream"},
        },
    }

    with patch(
        "salt.utils.http.query",
        create_autospec(
            http.query, autospec=True, side_effect=_make_mock_http(responses)
        ),
    ):
        result = metadata.metadata()

    # Body returned verbatim, not wrapped in a dict.
    assert result == "raw-octet-stream-payload"
