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
    with patch.object(pgjsonb, "_get_serv"):
        with patch.object(psycopg2.extras, "Json") as json_mock:
            pgjsonb.save_load(load["jid"], load)
            json_mock.assert_called_with(decoded_load)


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


def test_get_fun_orders_by_alter_time_desc_not_max_jid():
    """``get_fun`` must determine "latest execution per minion" from
    ``alter_time`` rather than from a lexicographic ordering of jids.

    The previous SQL used ``MAX(jid)``, which works only when jids are
    timestamp-formatted strings of equal length (Salt's default
    ``YYYYMMDDHHMMSSffffff`` and the ``nano`` variant). Deployments that
    override ``master_job_cache.gen_jid`` (custom prep_jid emitting UUIDs,
    snowflake ids, or any non-sortable scheme), or that hold rows written
    under different jid formats from a past config change, get a
    silently wrong answer with ``MAX(jid)`` -- the lexicographic max is
    not the time-latest.

    Pin the algorithm: order by ``alter_time DESC`` (which Postgres
    populates via ``DEFAULT NOW()``), and guard against regression to
    the ``MAX(jid)`` form.
    """
    cur = MagicMock()
    cur.fetchall.return_value = []
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cur

    with patch.object(pgjsonb, "_get_serv", serv):
        pgjsonb.get_fun("test.ping")

    sql = cur.execute.call_args.args[0].lower()
    assert "alter_time" in sql
    assert "order by" in sql
    assert "desc" in sql
    assert "max(jid)" not in sql
