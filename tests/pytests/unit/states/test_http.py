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

    with patch.dict(http.__opts__, {"test": False}):
        mock = MagicMock(return_value={"body": "http body", "status": 200})
        expected = {
            "name": "http://example.com/",
            "result": True,
            "comment": "Status 200 was found.",
            "changes": {},
            "data": {"body": "http body", "status": 200},
        }

        with patch.dict(http.__salt__, {"http.query": mock}):
            assert (
                http.query(name="http://example.com/", status=200, decode=False)
                == expected
            )

    with patch.dict(http.__opts__, {"test": False}):
        mock = MagicMock(return_value={"body": "http body", "status": 200})
        expected = {
            "name": "http://example.com/",
            "result": True,
            "comment": "Status 200 was found.",
            "changes": {},
            "data": {"body": "http body", "status": 200},
        }

        with patch.dict(http.__salt__, {"http.wait_for_successful_query": mock}):
            assert (
                http.query(name="http://example.com/", status=200, wait_for=300)
                == expected
            )

    with patch.dict(http.__opts__, {"test": True}):
        mock = MagicMock(return_value={"body": "http body", "status": 200})
        expected = {
            "name": "http://example.com/",
            "result": None,
            "comment": "Status 200 was found. (TEST MODE, TEST URL WAS: http://status.example.com)",
            "changes": {},
            "data": {"body": "http body", "status": 200},
        }

        with patch.dict(http.__salt__, {"http.query": mock}):
            assert (
                http.query(
                    name="http://example.com/",
                    status=200,
                    test_url="http://status.example.com",
                )
                == expected
            )


def test_query_pcre_statustype():
    """
    Test to perform an HTTP query with a regex used to match the status code and statefully return the result
    """
    testurl = "salturl"

    with patch.dict(http.__opts__, {"test": False}):
        http_result = {"text": "This page returned a 201 status code", "status": "201"}
        mock = MagicMock(return_value=http_result)

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

    with patch.dict(http.__opts__, {"test": False}):
        http_result = {"text": "This page returned a 201 status code", "status": "201"}
        mock = MagicMock(return_value=http_result)

        state_return = {
            "changes": {},
            "comment": ('Status pattern "200|201" was found.'),
            "data": {"status": "201", "text": "This page returned a 201 status code"},
            "name": testurl,
            "result": True,
        }

        with patch.dict(http.__salt__, {"http.query": mock}):
            assert (
                http.query(
                    testurl,
                    status="200|201",
                    status_type="pcre",
                )
                == state_return
            )

        http_result = {"text": "This page returned a 403 status code", "status": "403"}
        mock = MagicMock(return_value=http_result)

        state_return = {
            "name": "salturl",
            "result": False,
            "comment": 'Match text "This page returned" was found. Status pattern "200|201" was not found.',
            "changes": {},
            "data": {"text": "This page returned a 403 status code", "status": "403"},
        }

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


def test_query_pcre_matchtype():
    """
    Test to perform an HTTP query with a regex used to match the returned text and statefully return the result
    """
    testurl = "salturl"

    with patch.dict(http.__opts__, {"test": False}):
        http_result = {"text": "This page returned a 201 status code", "status": "201"}
        mock = MagicMock(return_value=http_result)

        state_return = {
            "changes": {},
            "comment": ('Match pattern "This page returned" was found.'),
            "data": {"status": "201", "text": "This page returned a 201 status code"},
            "name": testurl,
            "result": True,
        }

        with patch.dict(http.__salt__, {"http.query": mock}):
            assert (
                http.query(
                    testurl,
                    match="This page returned",
                    match_type="pcre",
                )
                == state_return
            )

        http_result = {
            "text": "This page did not return a 201 status code",
            "status": "403",
        }
        mock = MagicMock(return_value=http_result)

        state_return = {
            "changes": {},
            "comment": ('Match pattern "This page returned" was not found.'),
            "data": {
                "status": "403",
                "text": "This page did not return a 201 status code",
            },
            "name": testurl,
            "result": False,
        }

        with patch.dict(http.__salt__, {"http.query": mock}):
            assert (
                http.query(
                    testurl,
                    match="This page returned",
                    match_type="pcre",
                )
                == state_return
            )


def test_query_stringstatustype():
    """
    Test to perform an HTTP query with a string status code and statefully return the result
    """
    testurl = "salturl"

    with patch.dict(http.__opts__, {"test": False}):
        http_result = {"text": "This page returned a 201 status code", "status": "201"}
        mock = MagicMock(return_value=http_result)

        with patch.dict(http.__salt__, {"http.query": mock}):
            state_return = {
                "changes": {},
                "comment": 'Match text "This page returned" was found. Status 201 was found.',
                "data": {
                    "status": "201",
                    "text": "This page returned a 201 status code",
                },
                "name": testurl,
                "result": True,
            }

            assert (
                http.query(
                    testurl,
                    match="This page returned",
                    status="201",
                    status_type="string",
                )
                == state_return
            )

        http_result = {"text": "This page returned a 403 status code", "status": "403"}
        mock = MagicMock(return_value=http_result)

        with patch.dict(http.__salt__, {"http.query": mock}):
            state_return = {
                "name": "salturl",
                "result": False,
                "comment": 'Match text "This page returned" was found. Status 201 was not found.',
                "changes": {},
                "data": {
                    "text": "This page returned a 403 status code",
                    "status": "403",
                },
            }

            assert (
                http.query(
                    testurl,
                    match="This page returned",
                    status="201",
                    status_type="string",
                )
                == state_return
            )


def test_query_invalidstatustype():
    """
    Test to perform an HTTP query with a string status code and statefully return the result
    """
    testurl = "salturl"

    with patch.dict(http.__opts__, {"test": False}):
        http_result = {"text": "This page returned a 201 status code", "status": "201"}
        mock = MagicMock(return_value=http_result)

        with patch.dict(http.__salt__, {"http.query": mock}):
            state_return = {
                "name": "salturl",
                "result": None,
                "comment": "",
                "changes": {},
                "data": {
                    "text": "This page returned a 201 status code",
                    "status": "201",
                },
            }

            assert (
                http.query(
                    testurl,
                    status="201",
                    status_type="invalid",
                )
                == state_return
            )


def test_query_liststatustype():
    """
    Test to perform an HTTP query with a list of status codes and statefully return the result
    """
    testurl = "salturl"

    with patch.dict(http.__opts__, {"test": False}):
        http_result = {"text": "This page returned a 201 status code", "status": "201"}
        state_return = {
            "changes": {},
            "comment": 'Match text "This page returned" was found. Status 201 was found.',
            "data": {"status": "201", "text": "This page returned a 201 status code"},
            "name": testurl,
            "result": True,
        }

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

    with patch.dict(http.__opts__, {"test": False}):
        http_result = {"text": "This page returned a 201 status code", "status": "201"}
        state_return = {
            "changes": {},
            "comment": "Status 201 was found.",
            "data": {"status": "201", "text": "This page returned a 201 status code"},
            "name": testurl,
            "result": True,
        }

        mock = MagicMock(return_value=http_result)
        with patch.dict(http.__salt__, {"http.query": mock}):
            assert (
                http.query(
                    testurl,
                    status=["200", "201"],
                    status_type="list",
                )
                == state_return
            )

        http_result = {"text": "This page returned a 403 status code", "status": "403"}
        state_return = {
            "name": "salturl",
            "result": False,
            "comment": "Match text \"This page returned a 200\" was not found. Statuses ['200', '201'] were not found.",
            "changes": {},
            "data": {"text": "This page returned a 403 status code", "status": "403"},
        }

        mock = MagicMock(return_value=http_result)
        with patch.dict(http.__salt__, {"http.query": mock}):
            assert (
                http.query(
                    testurl,
                    match="This page returned a 200",
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

    query_mock = MagicMock(return_value={"result": False})

    with patch.object(http, "query", query_mock):
        with patch(
            "time.time", MagicMock(side_effect=[1697564521.9640958, 1697564822.9640958])
        ):
            assert http.wait_for_successful_query("url", status=200) == {
                "result": False
            }

    query_mock = MagicMock(side_effect=Exception())

    with patch.object(http, "query", query_mock):
        with patch(
            "time.time", MagicMock(side_effect=[1697564521.9640958, 1697564822.9640958])
        ):
            with pytest.raises(Exception):
                http.wait_for_successful_query("url", status=200)
