"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import pytest
import salt.states.http as http
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {http: {}}


def test_query():
    """
    Test to perform an HTTP query and statefully return the result
    """
    ret = [
        {
            "changes": {},
            "comment": (
                " Either match text (match) or a status code (status) is required."
            ),
            "data": {},
            "name": "salt",
            "result": False,
        },
        {
            "changes": {},
            "comment": " (TEST MODE)",
            "data": True,
            "name": "salt",
            "result": None,
        },
    ]
    assert http.query("salt") == ret[0]

    with patch.dict(http.__opts__, {"test": True}):
        mock = MagicMock(return_value=True)
        with patch.dict(http.__salt__, {"http.query": mock}):
            assert http.query("salt", "Dude", "stack") == ret[1]


def test_query_pcre_statustype():
    """
    Test to perform an HTTP query with a regex used to match the status code and statefully return the result
    """
    testurl = "salturl"
    http_result = {"text": "This page returned a 201 status code", "status": "201"}
    state_return = {
        "changes": {},
        "comment": (
            'Match text "This page returned" was found. Status pattern "200|201" was'
            " found."
        ),
        "data": {"status": "201", "text": "This page returned a 201 status code"},
        "name": testurl,
        "result": True,
    }

    with patch.dict(http.__opts__, {"test": False}):
        mock = MagicMock(return_value=http_result)
        with patch.dict(http.__salt__, {"http.query": mock}):
            assert (
                http.query(
                    testurl,
                    match="This page returned",
                    status="200|201",
                    status_type="pcre",
                )
                == state_return
            )


def test_query_stringstatustype():
    """
    Test to perform an HTTP query with a string status code and statefully return the result
    """
    testurl = "salturl"
    http_result = {"text": "This page returned a 201 status code", "status": "201"}
    state_return = {
        "changes": {},
        "comment": 'Match text "This page returned" was found. Status 201 was found.',
        "data": {"status": "201", "text": "This page returned a 201 status code"},
        "name": testurl,
        "result": True,
    }

    with patch.dict(http.__opts__, {"test": False}):
        mock = MagicMock(return_value=http_result)
        with patch.dict(http.__salt__, {"http.query": mock}):
            assert (
                http.query(
                    testurl,
                    match="This page returned",
                    status="201",
                    status_type="string",
                )
                == state_return
            )


def test_query_liststatustype():
    """
    Test to perform an HTTP query with a list of status codes and statefully return the result
    """
    testurl = "salturl"
    http_result = {"text": "This page returned a 201 status code", "status": "201"}
    state_return = {
        "changes": {},
        "comment": 'Match text "This page returned" was found. Status 201 was found.',
        "data": {"status": "201", "text": "This page returned a 201 status code"},
        "name": testurl,
        "result": True,
    }

    with patch.dict(http.__opts__, {"test": False}):
        mock = MagicMock(return_value=http_result)
        with patch.dict(http.__salt__, {"http.query": mock}):
            assert (
                http.query(
                    testurl,
                    match="This page returned",
                    status=["200", "201"],
                    status_type="list",
                )
                == state_return
            )


def test_wait_for_with_interval():
    """
    Test for wait_for_successful_query waits for request_interval
    """

    query_mock = MagicMock(side_effect=[{"error": "error"}, {"result": True}])

    with patch.object(http, "query", query_mock):
        with patch("time.sleep", MagicMock()) as sleep_mock:
            assert http.wait_for_successful_query(
                "url", request_interval=1, status=200
            ) == {"result": True}
            sleep_mock.assert_called_once_with(1)


def test_wait_for_without_interval():
    """
    Test for wait_for_successful_query waits for request_interval
    """

    query_mock = MagicMock(side_effect=[{"error": "error"}, {"result": True}])

    with patch.object(http, "query", query_mock):
        with patch("time.sleep", MagicMock()) as sleep_mock:
            assert http.wait_for_successful_query("url", status=200) == {"result": True}
            sleep_mock.assert_not_called()
