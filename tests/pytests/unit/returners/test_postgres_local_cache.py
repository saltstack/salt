"""
Unit tests for the postgres_local_cache.
"""

import json

import pytest

import salt.returners.postgres_local_cache as postgres_local_cache
from tests.support.mock import MagicMock, patch

if postgres_local_cache.HAS_POSTGRES:
    import psycopg2
    import psycopg2.errors


@pytest.fixture
def configure_loader_modules(tmp_path):
    return {
        postgres_local_cache: {
            "__opts__": {
                "cachedir": str(tmp_path / "cache_dir"),
                "keep_jobs_seconds": 3600,
            }
        }
    }


def test_returner():
    """
    Tests that the returner function
    """
    load = {
        "tgt_type": "glob",
        "fun_args": [],
        "jid": "20200108221839189167",
        "return": True,
        "retcode": 0,
        "success": True,
        "tgt": "minion",
        "cmd": "_return",
        "_stamp": "2020-01-08T22:18:39.197774",
        "arg": [],
        "fun": "test.ping",
        "id": "minion",
    }

    expected = {"return": "True", "retcode": 0, "success": True}

    connect_mock = MagicMock()
    with patch.object(postgres_local_cache, "_get_conn", connect_mock):
        postgres_local_cache.returner(load)

        return_val = None
        for call in connect_mock.mock_calls:
            for arg in call.args:
                if isinstance(arg, tuple):
                    for val in arg:
                        if isinstance(val, str) and "return" in val:
                            return_val = json.loads(val)

        assert return_val is not None, None
        assert return_val == expected


@pytest.mark.skipif(
    not postgres_local_cache.HAS_POSTGRES, reason="psycopg2 not installed"
)
def test_save_load_swallows_duplicate_jid_unique_violation():
    """
    Regression test for #69214.

    In an active-active multi-master setup, both masters may call
    ``save_load`` for the same JID. The second INSERT into the ``jids``
    table hits the ``jids_pkey`` unique constraint and psycopg2 raises
    ``UniqueViolation``. That is an expected steady-state in multi-master
    deployments — it must be tolerated silently rather than raised up to
    the caller (where ``salt.utils.job.store_job`` only logs it as a
    CRITICAL stack trace).

    This exercises the legacy code path for PostgreSQL < 9.5 where the
    ON CONFLICT clause is not available and we rely on the exception
    handler to absorb the duplicate. PG >= 9.5 takes the ON CONFLICT
    path (covered by ``test_save_load_uses_upsert_sql_on_pg_95_or_newer``)
    and never raises.
    """
    conn = MagicMock()
    conn.server_version = 90400  # PG < 9.5: only path that reaches the catch.
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.execute.side_effect = psycopg2.errors.UniqueViolation(
        'duplicate key value violates unique constraint "jids_pkey"'
    )

    load = {
        "tgt_type": "glob",
        "cmd": "publish",
        "tgt": "*",
        "kwargs": {},
        "ret": "",
        "user": "root",
        "arg": [],
        "fun": "test.ping",
    }

    with patch.object(postgres_local_cache, "_get_conn", return_value=conn):
        # Must not raise — both masters writing the same jid is the
        # whole point of an active-active master cluster.
        postgres_local_cache.save_load("20260522093640648950", load)

    cur.execute.assert_called_once()


@pytest.mark.skipif(
    not postgres_local_cache.HAS_POSTGRES, reason="psycopg2 not installed"
)
def test_save_load_propagates_other_integrity_errors():
    """
    Only ``UniqueViolation`` on the jids primary key is the multi-master
    benign case. Other integrity errors (foreign-key, NOT NULL, CHECK)
    are real bugs and must propagate to the caller — silently swallowing
    them would hide schema-mismatch issues.
    """
    conn = MagicMock()
    conn.server_version = 90500
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.execute.side_effect = psycopg2.errors.ForeignKeyViolation("fk violation")

    load = {"fun": "test.ping"}

    with patch.object(postgres_local_cache, "_get_conn", return_value=conn):
        with pytest.raises(psycopg2.IntegrityError):
            postgres_local_cache.save_load("20260522093640648950", load)


@pytest.mark.skipif(
    not postgres_local_cache.HAS_POSTGRES, reason="psycopg2 not installed"
)
def test_save_load_uses_upsert_sql_on_pg_95_or_newer():
    """
    On PostgreSQL >= 9.5 the INSERT must use ``ON CONFLICT (jid) DO NOTHING``
    so duplicate-jid writes from a peer master are tolerated at the database
    layer rather than raising.
    """
    conn = MagicMock()
    conn.server_version = 90500
    cur = MagicMock()
    conn.cursor.return_value = cur

    load = {"fun": "test.ping"}

    with patch.object(postgres_local_cache, "_get_conn", return_value=conn):
        postgres_local_cache.save_load("20260522093640648950", load)

    sql = cur.execute.call_args.args[0]
    assert "ON CONFLICT" in sql


@pytest.mark.skipif(
    not postgres_local_cache.HAS_POSTGRES, reason="psycopg2 not installed"
)
def test_save_load_uses_plain_insert_on_pre_pg_95():
    """
    On PostgreSQL < 9.5 ``ON CONFLICT`` is not available; ``save_load`` must
    issue the plain INSERT and let the UniqueViolation exception handler
    absorb duplicate-jid writes.
    """
    conn = MagicMock()
    conn.server_version = 90400
    cur = MagicMock()
    conn.cursor.return_value = cur

    load = {"fun": "test.ping"}

    with patch.object(postgres_local_cache, "_get_conn", return_value=conn):
        postgres_local_cache.save_load("20260522093640648950", load)

    sql = cur.execute.call_args.args[0]
    assert "ON CONFLICT" not in sql


def test_returner_unicode_exception():
    """
    Tests that the returner function
    """
    return_val = "Trüe"

    load = {
        "tgt_type": "glob",
        "fun_args": [],
        "jid": "20200108221839189167",
        "return": return_val,
        "retcode": 0,
        "success": True,
        "tgt": "minion",
        "cmd": "_return",
        "_stamp": "2020-01-08T22:18:39.197774",
        "arg": [],
        "fun": "test.ping",
        "id": "minion",
    }

    expected = {"return": "Trüe", "retcode": 0, "success": True}

    connect_mock = MagicMock()
    with patch.object(postgres_local_cache, "_get_conn", connect_mock):
        postgres_local_cache.returner(load)

        return_val = None
        search_string = "return"
        for call in connect_mock.mock_calls:
            for arg in call.args:
                if isinstance(arg, tuple):
                    for val in arg:
                        if isinstance(val, str):
                            if search_string in val:
                                return_val = json.loads(val)

        assert return_val is not None, None
        assert return_val == expected
