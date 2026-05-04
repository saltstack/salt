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


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test_save_load_swallows_duplicate_jid_unique_violation():
    """A duplicate-jid unique violation on PG < 9.5 is the legacy case
    from #22171 (PG >= 9.5 uses ON CONFLICT and never reaches here);
    it must be tolerated silently."""
    cur = MagicMock()
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
    cur.execute.side_effect = psycopg2.errors.ForeignKeyViolation("fk violation")
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cur

    with patch.object(pgjsonb, "_get_serv", serv):
        with pytest.raises(psycopg2.IntegrityError):
            pgjsonb.save_load("20260504000000000001", {"fun": "test.ping"})
