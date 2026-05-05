"""
Unit tests for the PGJsonb returner (pgjsonb).
"""

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


def test_get_fun_returns_one_full_ret_per_minion_with_postgres_compatible_sql():
    """``get_fun`` builds a per-minion last-execution dict.

    The previous SQL used MySQL-style backtick quoting (``MAX(`jid`)``),
    which raises a syntax error on PostgreSQL where the function lives.
    Verify both the produced mapping and that the issued SQL is free of
    backticks so the fix does not regress through future copy-paste from
    the mysql returner.
    """
    rows = [
        ("minion-1", "20260505000000000001", {"return": "ok-1", "fun": "test.ping"}),
        ("minion-2", "20260505000000000002", {"return": "ok-2", "fun": "test.ping"}),
    ]
    cur = MagicMock()
    cur.fetchall.return_value = rows
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cur

    with patch.object(pgjsonb, "_get_serv", serv):
        result = pgjsonb.get_fun("test.ping")

    assert result == {
        "minion-1": {"return": "ok-1", "fun": "test.ping"},
        "minion-2": {"return": "ok-2", "fun": "test.ping"},
    }
    issued_sql = cur.execute.call_args.args[0]
    assert (
        "`" not in issued_sql
    ), "MySQL-style backtick quoting in pgjsonb SQL — invalid on PostgreSQL"
