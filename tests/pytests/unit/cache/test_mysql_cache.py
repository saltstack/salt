"""
unit tests for the mysql_cache cache
"""


import logging

import pytest
import salt.cache.mysql_cache as mysql_cache
import salt.payload
import salt.utils.files
from salt.exceptions import SaltCacheError
from tests.support.mock import MagicMock, call, patch

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skipif(
        mysql_cache.MySQLdb is None, reason="No python mysql client installed."
    ),
]


@pytest.fixture
def configure_loader_modules():
    return {mysql_cache: {}}


@pytest.fixture
def master_config():
    opts = salt.config.DEFAULT_MASTER_OPTS.copy()
    opts["__role"] = "master"
    return opts


def test_run_query():
    """
    Tests that a SaltCacheError is raised when there is a problem writing to the
    cache file.
    """
    with patch("MySQLdb.connect", MagicMock()) as mock_connect:
        expected_calls = call.cursor().execute("SELECT 1;")
        mysql_cache.run_query(conn=mock_connect, query="SELECT 1;")
        mock_connect.assert_has_calls((expected_calls,), True)


def test_store(master_config):
    """
    Tests that the store function writes the data to the serializer for storage.
    """

    mock_connect_client = MagicMock()
    with patch.object(mysql_cache, "_init_client") as mock_init_client:
        with patch.dict(
            mysql_cache.__context__,
            {
                "mysql_table_name": "salt",
                "mysql_client": mock_connect_client,
            },
        ):
            with patch.object(mysql_cache, "run_query") as mock_run_query:
                mock_run_query.return_value = (MagicMock(), 1)

                expected_calls = [
                    call(
                        mock_connect_client,
                        b"REPLACE INTO salt (bank, etcd_key, data) values(%s,%s,%s)",
                        ("minions/minion", "key1", b"\xa4data"),
                    )
                ]

                try:
                    mysql_cache.store(bank="minions/minion", key="key1", data="data")
                except SaltCacheError:
                    pytest.fail("This test should not raise an exception")
                mock_run_query.assert_has_calls(expected_calls, True)

            with patch.object(mysql_cache, "run_query") as mock_run_query:
                mock_run_query.return_value = (MagicMock(), 2)

                expected_calls = [
                    call(
                        mock_connect_client,
                        b"REPLACE INTO salt (bank, etcd_key, data) values(%s,%s,%s)",
                        ("minions/minion", "key2", b"\xa4data"),
                    )
                ]

                try:
                    mysql_cache.store(bank="minions/minion", key="key2", data="data")
                except SaltCacheError:
                    pytest.fail("This test should not raise an exception")
                mock_run_query.assert_has_calls(expected_calls, True)

            with patch.object(mysql_cache, "run_query") as mock_run_query:
                mock_run_query.return_value = (MagicMock(), 0)
                with pytest.raises(SaltCacheError) as exc_info:
                    mysql_cache.store(bank="minions/minion", key="data", data="data")
                expected = "Error storing minions/minion data returned 0"
                assert expected in str(exc_info.value)


def test_fetch(master_config):
    """
    Tests that the fetch function reads the data from the serializer for storage.
    """

    with patch.object(mysql_cache, "_init_client") as mock_init_client:
        with patch("MySQLdb.connect") as mock_connect:
            mock_connection = mock_connect.return_value
            cursor = mock_connection.cursor.return_value
            cursor.fetchone.return_value = (b"\xa5hello",)

            with patch.dict(
                mysql_cache.__context__,
                {
                    "mysql_client": mock_connection,
                    "mysql_table_name": "salt",
                },
            ):
                ret = mysql_cache.fetch(bank="bank", key="key")
                assert ret == "hello"


def test_flush():
    """
    Tests the flush function in mysql_cache.
    """
    mock_connect_client = MagicMock()
    with patch.object(mysql_cache, "_init_client") as mock_init_client:
        with patch.dict(
            mysql_cache.__context__,
            {"mysql_client": mock_connect_client, "mysql_table_name": "salt"},
        ):
            with patch.object(mysql_cache, "run_query") as mock_run_query:

                expected_calls = [
                    call(mock_connect_client, "DELETE FROM salt WHERE bank='bank'"),
                ]
                mock_run_query.return_value = (MagicMock(), "")
                mysql_cache.flush(bank="bank")
                mock_run_query.assert_has_calls(expected_calls, True)

                expected_calls = [
                    call(
                        mock_connect_client,
                        "DELETE FROM salt WHERE bank='bank' AND etcd_key='key'",
                    )
                ]
                mysql_cache.flush(bank="bank", key="key")
                mock_run_query.assert_has_calls(expected_calls, True)


def test_init_client(master_config):
    """
    Tests that the _init_client places the correct information in __context__
    """
    with patch.dict(
        mysql_cache.__opts__,
        {"mysql.max_allowed_packet": 100000},
    ):
        with patch.object(mysql_cache, "_create_table") as mock_create_table:
            mysql_cache._init_client()

            assert "mysql_table_name" in mysql_cache.__context__
            assert mysql_cache.__context__["mysql_table_name"] == "salt"

            assert "mysql_kwargs" in mysql_cache.__context__
            assert mysql_cache.__context__["mysql_kwargs"]["autocommit"]
            assert mysql_cache.__context__["mysql_kwargs"]["host"] == "127.0.0.1"
            assert mysql_cache.__context__["mysql_kwargs"]["db"] == "salt_cache"
            assert mysql_cache.__context__["mysql_kwargs"]["port"] == 3306
            assert (
                mysql_cache.__context__["mysql_kwargs"]["max_allowed_packet"] == 100000
            )

    with patch.dict(
        mysql_cache.__opts__,
        {
            "mysql.max_allowed_packet": 100000,
            "mysql.db": "salt_mysql_db",
            "mysql.host": "mysql-host",
        },
    ):
        with patch.object(mysql_cache, "_create_table") as mock_create_table:
            mysql_cache._init_client()

            assert "mysql_table_name" in mysql_cache.__context__
            assert mysql_cache.__context__["mysql_table_name"] == "salt"

            assert "mysql_kwargs" in mysql_cache.__context__
            assert mysql_cache.__context__["mysql_kwargs"]["autocommit"]
            assert mysql_cache.__context__["mysql_kwargs"]["host"] == "mysql-host"
            assert mysql_cache.__context__["mysql_kwargs"]["db"] == "salt_mysql_db"
            assert mysql_cache.__context__["mysql_kwargs"]["port"] == 3306
            assert (
                mysql_cache.__context__["mysql_kwargs"]["max_allowed_packet"] == 100000
            )


def test_create_table(master_config):
    """
    Tests that the _create_table
    """

    mock_connect_client = MagicMock()
    with patch.dict(
        mysql_cache.__context__,
        {
            "mysql_table_name": "salt",
            "mysql_client": mock_connect_client,
            "mysql_kwargs": {"db": "salt_cache"},
        },
    ):
        with patch.object(mysql_cache, "run_query") as mock_run_query:
            mock_run_query.return_value = (MagicMock(), 1)

            sql_call = """CREATE TABLE IF NOT EXISTS salt (
      bank CHAR(255),
      etcd_key CHAR(255),
      data MEDIUMBLOB,
      PRIMARY KEY(bank, etcd_key)
    );"""
            expected_calls = [call(mock_connect_client, sql_call)]
            try:
                mysql_cache._create_table()
            except SaltCacheError:
                pytest.fail("This test should not raise an exception")
            mock_run_query.assert_has_calls(expected_calls, True)
