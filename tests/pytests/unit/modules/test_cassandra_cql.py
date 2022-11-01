"""
Test case for the cassandra_cql module
"""


import logging

import pytest

import salt.modules.cassandra_cql as cql
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {cql: {"__context__": {}}}


def test_cql_query(caplog):
    """
    Test salt.modules.cassandra_cql.cql_query function
    """

    mock_session = MagicMock()
    mock_client = MagicMock()
    mock = MagicMock(return_value=(mock_session, mock_client))
    query = "query"
    with patch.object(cql, "_connect", mock):
        query_result = cql.cql_query(query)

    assert query_result == []

    query = {"5.0.1": "query1", "5.0.0": "query2"}
    mock_version = MagicMock(return_value="5.0.1")
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock = MagicMock(return_value=(mock_session, mock_client))
    with patch.object(cql, "version", mock_version):
        with patch.object(cql, "_connect", mock):
            query_result = cql.cql_query(query)
    assert query_result == []


def test_cql_query_with_prepare(caplog):
    """
    Test salt.modules.cassandra_cql.cql_query_with_prepare function
    """

    mock_session = MagicMock()
    mock_client = MagicMock()
    mock = MagicMock(return_value=(mock_session, mock_client))
    query = "query"
    statement_args = {"arg1": "test"}

    mock_context = MagicMock(
        return_value={"cassandra_cql_prepared": {"statement_name": query}}
    )
    with patch.object(cql, "__context__", mock_context):
        with patch.object(cql, "_connect", mock):
            query_result = cql.cql_query_with_prepare(
                query, "statement_name", statement_args
            )
    assert query_result == []


def test_version(caplog):
    """
    Test salt.modules.cassandra_cql.version function
    """
    mock_cql_query = MagicMock(return_value=[{"release_version": "5.0.1"}])

    with patch.object(cql, "cql_query", mock_cql_query):
        version = cql.version()
    assert version == "5.0.1"

    mock_cql_query = MagicMock(side_effect=CommandExecutionError)
    with pytest.raises(CommandExecutionError) as err:
        with patch.object(cql, "cql_query", mock_cql_query):
            version = cql.version()
    assert "{}".format(err.value) == ""
    assert "Could not get Cassandra version." in caplog.text
    for record in caplog.records:
        assert record.levelname == "CRITICAL"


def test_info():
    """
    Test salt.modules.cassandra_cql.info function
    """
    expected = {"result": "info"}
    mock_cql_query = MagicMock(return_value=expected)
    with patch.object(cql, "cql_query", mock_cql_query):
        info = cql.info()

    assert info == expected


def test_list_keyspaces():
    """
    Test salt.modules.cassandra_cql.list_keyspaces function
    """
    expected = [{"keyspace_name": "name1"}, {"keyspace_name": "name2"}]
    mock_cql_query = MagicMock(return_value=expected)
    with patch.object(cql, "cql_query", mock_cql_query):
        keyspaces = cql.list_keyspaces()

    assert keyspaces == expected


def test_list_column_families():
    """
    Test salt.modules.cassandra_cql.list_column_families function
    """
    expected = [{"colum_name": "column1"}, {"column_name": "column2"}]
    mock_cql_query = MagicMock(return_value=expected)
    with patch.object(cql, "cql_query", mock_cql_query):
        columns = cql.list_column_families()

    assert columns == expected


def test_keyspace_exists():
    """
    Test salt.modules.cassandra_cql.keyspace_exists function
    """
    expected = "keyspace"
    mock_cql_query = MagicMock(return_value=expected)
    with patch.object(cql, "cql_query", mock_cql_query):
        exists = cql.keyspace_exists("keyspace")

    assert exists == bool(expected)

    expected = []
    mock_cql_query = MagicMock(return_value=expected)
    with patch.object(cql, "cql_query", mock_cql_query):
        exists = cql.keyspace_exists("keyspace")

    assert exists == bool(expected)


def test_create_keyspace():
    """
    Test salt.modules.cassandra_cql.create_keyspace function
    """
    expected = None
    mock_cql_query = MagicMock(return_value=expected)
    with patch.object(cql, "cql_query", mock_cql_query):
        result = cql.create_keyspace("keyspace")

    assert result == expected


def test_drop_keyspace():
    """
    Test salt.modules.cassandra_cql.drop_keyspace function
    """
    expected = True
    mock_cql_query = MagicMock(return_value=expected)
    with patch.object(cql, "cql_query", mock_cql_query):
        result = cql.drop_keyspace("keyspace")

    assert result == expected


def test_list_users():
    """
    Test salt.modules.cassandra_cql.list_users function
    """
    expected = [{"name": "user1", "super": True}, {"name": "user2", "super": False}]
    mock_cql_query = MagicMock(return_value=expected)
    with patch.object(cql, "cql_query", mock_cql_query):
        result = cql.list_users()

    assert result == expected


def test_create_user():
    """
    Test salt.modules.cassandra_cql.create_user function
    """
    expected = True
    mock_cql_query = MagicMock(return_value=expected)
    with patch.object(cql, "cql_query", mock_cql_query):
        result = cql.create_user("user", "password")

    assert result == expected


def test_list_permissions():
    """
    Test salt.modules.cassandra_cql.list_permissions function
    """
    expected = [
        {
            "permission": "ALTER",
            "resource": "<keyspace one>",
            "role": "user1",
            "username": "user1",
        }
    ]
    mock_cql_query = MagicMock(return_value=expected)
    with patch.object(cql, "cql_query", mock_cql_query):
        result = cql.list_permissions(username="user1", resource="one")

    assert result == expected


def test_grant_permission():
    """
    Test salt.modules.cassandra_cql.grant_permission function
    """
    expected = True
    mock_cql_query = MagicMock(return_value=expected)
    with patch.object(cql, "cql_query", mock_cql_query):
        result = cql.grant_permission(username="user1", resource="one")

    assert result == expected
