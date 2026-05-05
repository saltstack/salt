"""
Unit tests for the PGJsonb returner (pgjsonb).
"""

import logging

import pytest

import salt.returners.pgjsonb as pgjsonb
from tests.support.mock import MagicMock, call, patch

if pgjsonb.HAS_PG:
    import psycopg2
    import psycopg2.extras


@pytest.fixture
def configure_loader_modules():
    return {pgjsonb: {"__opts__": {"keep_jobs_seconds": 3600, "archive_jobs": 0}}}


def test_clean_old_jobs_purge():
    """
    Tests that the function returns None when no jid_root is found.
    """
    connect_mock = MagicMock()
    with patch.object(pgjsonb, "_get_serv", connect_mock):
        with patch.dict(pgjsonb.__salt__, {"config.option": MagicMock()}):
            assert pgjsonb.clean_old_jobs() is None


def test_clean_old_jobs_archive():
    """
    Tests that the function returns None when no jid_root is found.
    """
    connect_mock = MagicMock()
    with patch.object(pgjsonb, "_get_serv", connect_mock):
        with patch.dict(pgjsonb.__salt__, {"config.option": MagicMock()}):
            with patch.dict(pgjsonb.__opts__, {"archive_jobs": 1}):
                assert pgjsonb.clean_old_jobs() is None


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test_returner_with_bytes():
    ret = {
        "success": True,
        "return": b"bytes",
        "retcode": 0,
        "jid": "20221101172203459989",
        "fun": "file.read",
        "fun_args": ["/fake/path", {"binary": True}],
        "id": "minion-1",
    }
    decoded_ret = {
        "success": True,
        "return": "bytes",
        "retcode": 0,
        "jid": "20221101172203459989",
        "fun": "file.read",
        "fun_args": ["/fake/path", {"binary": True}],
        "id": "minion-1",
    }
    calls = [call("bytes"), call(decoded_ret)]
    with patch.object(pgjsonb, "_get_serv"):
        with patch.object(psycopg2.extras, "Json") as json_mock:
            pgjsonb.returner(ret)
            json_mock.assert_has_calls(calls)


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test_save_load_with_bytes():
    load = {
        "return": b"bytes",
        "jid": "20221101172203459989",
    }
    decoded_load = {
        "return": "bytes",
        "jid": "20221101172203459989",
    }
    with patch.object(pgjsonb, "_get_serv"):
        with patch.object(psycopg2.extras, "Json") as json_mock:
            pgjsonb.save_load(load["jid"], load)
            json_mock.assert_called_with(decoded_load)


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test__purge_jobs_logs_via_salt_logger_and_reraises_on_db_error(caplog):
    """When the DELETE inside ``_purge_jobs`` fails, the error must reach
    Salt's logger (not stderr), the transaction is rolled back, and the
    original ``DatabaseError`` is re-raised."""
    cursor = MagicMock()
    cursor.execute.side_effect = [psycopg2.DatabaseError("boom"), None]
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cursor

    with patch.object(pgjsonb, "_get_serv", serv):
        with caplog.at_level(logging.ERROR, logger="salt.returners.pgjsonb"):
            with pytest.raises(psycopg2.DatabaseError):
                pgjsonb._purge_jobs("2026-01-01")

    cursor.execute.assert_any_call("ROLLBACK")
    assert any("failed to purge jids" in r.message for r in caplog.records)


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test__archive_jobs_logs_via_salt_logger_and_reraises_on_db_error(caplog):
    """When the CREATE TABLE inside ``_archive_jobs`` fails, the error
    reaches Salt's logger, the transaction is rolled back, and the
    original ``DatabaseError`` is re-raised."""
    cursor = MagicMock()
    cursor.execute.side_effect = [psycopg2.DatabaseError("boom"), None]
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cursor

    with patch.object(pgjsonb, "_get_serv", serv):
        with caplog.at_level(logging.ERROR, logger="salt.returners.pgjsonb"):
            with pytest.raises(psycopg2.DatabaseError):
                pgjsonb._archive_jobs("2026-01-01")

    cursor.execute.assert_any_call("ROLLBACK")
    assert any("failed to create archive table" in r.message for r in caplog.records)


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test__get_serv_logs_via_salt_logger_and_reraises_on_yield_error(caplog):
    """When the caller of ``_get_serv()`` raises a DatabaseError inside
    the ``with`` block, ``_get_serv`` must log via Salt's logger,
    issue ROLLBACK on the connection, and re-raise."""
    fake_conn = MagicMock()
    fake_conn.server_version = 90500
    fake_cursor = MagicMock()
    fake_conn.cursor.return_value = fake_cursor

    with patch.object(pgjsonb, "_get_options", return_value={}):
        with patch("psycopg2.connect", return_value=fake_conn):
            with caplog.at_level(logging.ERROR, logger="salt.returners.pgjsonb"):
                with pytest.raises(psycopg2.DatabaseError):
                    with pgjsonb._get_serv():
                        raise psycopg2.DatabaseError("boom")

    fake_cursor.execute.assert_any_call("ROLLBACK")
    assert any("_get_serv" in r.message for r in caplog.records)
