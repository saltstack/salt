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


def _capture_jids_predicate(executed_calls, marker):
    """Return the parameterised SQL string from the first call whose text
    contains ``marker`` (e.g. ``"delete from jids"`` or ``"insert into"``)."""
    for call_ in executed_calls:
        if not call_.args:
            continue
        sql = call_.args[0]
        if isinstance(sql, str) and marker in sql:
            return sql
    raise AssertionError(
        f"no execute call contained {marker!r}; "
        f"saw: {[c.args for c in executed_calls]}"
    )


def test__purge_jobs_keeps_jids_with_any_recent_salt_returns_row():
    """Regression for the orphan-returns bug: ``_purge_jobs`` must delete
    a jids row only when every salt_returns row for that jid is older
    than the cutoff. The previous predicate fired as soon as one old
    return existed, which left recent returns from the same jid orphaned
    in salt_returns once the parent was deleted."""
    cursor = MagicMock()
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cursor

    with patch.object(pgjsonb, "_get_serv", serv):
        pgjsonb._purge_jobs("2026-01-01")

    sql = _capture_jids_predicate(cursor.execute.call_args_list, "delete from jids")
    # Antijoin: keep the row if any recent salt_returns row exists for it.
    assert "not exists" in sql.lower()
    assert "alter_time >= %s" in sql
    # Defence against regressing to the old predicate.
    assert "alter_time < %s" not in sql


def test__archive_jobs_keeps_jids_with_any_recent_salt_returns_row():
    """Mirror of the purge test for the archive path. The archive INSERT
    into ``jids_archive`` must use the same antijoin predicate so that it
    does not pick up parent rows whose recent returns were left behind in
    the source table."""
    cursor = MagicMock()
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cursor

    with patch.object(pgjsonb, "_get_serv", serv):
        pgjsonb._archive_jobs("2026-01-01")

    sql = _capture_jids_predicate(
        cursor.execute.call_args_list, "insert into jids_archive"
    )
    assert "not exists" in sql.lower()
    assert "alter_time >= %s" in sql
    assert "alter_time < %s" not in sql
