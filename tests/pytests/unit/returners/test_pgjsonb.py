"""
Unit tests for the PGJsonb returner (pgjsonb).
"""

import logging

import pytest

import salt.exceptions
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
    serv = MagicMock()
    serv.return_value.__enter__.return_value.connection.server_version = 90500
    with patch.object(pgjsonb, "_get_serv", serv):
        with patch.object(psycopg2.extras, "Json") as json_mock:
            pgjsonb.save_load(load["jid"], load)
            json_mock.assert_called_with(decoded_load)


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test_save_load_swallows_duplicate_jid_unique_violation():
    """A duplicate-jid unique violation on PG < 9.5 is the legacy case
    from #22171 (PG >= 9.5 uses ON CONFLICT and never reaches here);
    it must be tolerated silently."""
    cur = MagicMock()
    cur.connection.server_version = 90400  # PG < 9.5: only path that reaches the catch.
    cur.execute.side_effect = psycopg2.errors.UniqueViolation("duplicate jid")
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cur

    with patch.object(pgjsonb, "_get_serv", serv):
        # Should not raise.
        pgjsonb.save_load("20260504000000000001", {"fun": "test.ping"})

    cur.execute.assert_called_once()


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test_save_load_propagates_other_integrity_errors():
    """Non-unique-violation IntegrityErrors (foreign-key, NOT NULL, CHECK)
    are real bugs and must surface instead of being silently swallowed."""
    cur = MagicMock()
    cur.connection.server_version = 90500
    cur.execute.side_effect = psycopg2.errors.ForeignKeyViolation("fk violation")
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cur

    with patch.object(pgjsonb, "_get_serv", serv):
        with pytest.raises(psycopg2.IntegrityError):
            pgjsonb.save_load("20260504000000000001", {"fun": "test.ping"})


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test_save_load_uses_upsert_sql_on_pg_95_or_newer():
    """On PostgreSQL >= 9.5 ``save_load`` must issue the ON CONFLICT form
    so a re-publish of the same jid updates the row instead of raising
    a unique violation."""
    cur = MagicMock()
    cur.connection.server_version = 90500
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cur

    with patch.object(pgjsonb, "_get_serv", serv):
        pgjsonb.save_load("20260504000000000001", {"fun": "test.ping"})

    sql = cur.execute.call_args.args[0]
    assert "ON CONFLICT" in sql


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test_save_load_uses_plain_insert_on_pre_pg_95():
    """On PostgreSQL < 9.5 ``save_load`` falls back to a plain INSERT
    (ON CONFLICT is unavailable). The UniqueViolation handler covers the
    duplicate-jid case from #22171."""
    cur = MagicMock()
    cur.connection.server_version = 90400
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cur

    with patch.object(pgjsonb, "_get_serv", serv):
        pgjsonb.save_load("20260504000000000001", {"fun": "test.ping"})

    sql = cur.execute.call_args.args[0]
    assert "ON CONFLICT" not in sql


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


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test_returner_logs_on_connection_failure_without_raising(caplog):
    """When the database is unreachable, ``returner`` must not propagate
    the SaltMasterError. The drop is logged at CRITICAL with jid and id
    so operators can correlate it to the lost return."""
    serv = MagicMock(side_effect=salt.exceptions.SaltMasterError("pg down"))
    with patch.object(pgjsonb, "_get_serv", serv):
        with caplog.at_level(logging.CRITICAL, logger="salt.returners.pgjsonb"):
            pgjsonb.returner(
                {
                    "fun": "test.ping",
                    "jid": "20260505000000000001",
                    "id": "minion-1",
                    "return": True,
                }
            )

    assert any(
        "PostgreSQL unavailable" in r.message
        and "20260505000000000001" in r.message
        and "minion-1" in r.message
        for r in caplog.records
    )


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test_returner_logs_on_database_error_without_raising(caplog):
    """A DatabaseError during the INSERT into ``salt_returns`` must not
    propagate; ``returner`` logs and drops the return so that one bad row
    cannot escape into syndic-aggregate paths that lack an outer catch."""
    cur = MagicMock()
    cur.execute.side_effect = psycopg2.DatabaseError("bad row")
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cur

    with patch.object(pgjsonb, "_get_serv", serv):
        with caplog.at_level(logging.ERROR, logger="salt.returners.pgjsonb"):
            pgjsonb.returner(
                {
                    "fun": "test.ping",
                    "jid": "20260505000000000002",
                    "id": "minion-2",
                    "return": True,
                }
            )

    assert any(
        "failed to store return" in r.message
        and "20260505000000000002" in r.message
        and "minion-2" in r.message
        for r in caplog.records
    )


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test_event_return_inserts_each_event_into_salt_events():
    """``event_return`` writes one row to ``salt_events`` per queued event,
    carrying the event tag and the master id. Also pins that ``_get_serv``
    is opened with ``commit=True`` only -- passing the events list as the
    positional ``ret`` argument was a copy-paste leftover from
    ``returner(ret)``."""
    events = [
        {"tag": "salt/job/1/new", "data": {"jid": "1", "fun": "test.ping"}},
        {"tag": "salt/auth", "data": {"id": "minion-1", "act": "accept"}},
    ]
    cur = MagicMock()
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cur

    with patch.object(pgjsonb, "_get_serv", serv):
        with patch.dict(pgjsonb.__opts__, {"id": "master-A"}):
            with patch("salt.returners.pgjsonb.time.time", return_value=1700000000.0):
                pgjsonb.event_return(events)

    serv.assert_called_once_with(commit=True)

    assert cur.execute.call_count == len(events)
    for executed_call, event in zip(cur.execute.call_args_list, events):
        sql, params = executed_call.args
        assert "INSERT INTO salt_events" in sql
        tag, _data_json, master_id, ts = params
        assert tag == event["tag"]
        assert master_id == "master-A"
        assert ts == 1700000000.0


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test_event_return_logs_on_database_error_without_raising(caplog):
    """A DatabaseError mid-batch must not propagate out of ``event_return``;
    the queue length is logged so operators see how many events were lost."""
    events = [{"tag": f"tag-{i}", "data": {}} for i in range(3)]
    cur = MagicMock()
    cur.execute.side_effect = psycopg2.DatabaseError("bad event")
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cur

    with patch.object(pgjsonb, "_get_serv", serv):
        with patch.dict(pgjsonb.__opts__, {"id": "master-A"}):
            with caplog.at_level(logging.ERROR, logger="salt.returners.pgjsonb"):
                pgjsonb.event_return(events)

    assert any(
        "failed to store" in r.message and "3 event" in r.message
        for r in caplog.records
    )
