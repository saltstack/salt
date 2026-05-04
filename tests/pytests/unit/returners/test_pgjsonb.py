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


def test_prep_jid_returns_passed_jid_unchanged():
    """``prep_jid(passed_jid=X)`` returns X verbatim."""
    assert pgjsonb.prep_jid(passed_jid="20260504000000000001") == "20260504000000000001"


def test_prep_jid_generates_a_valid_jid_when_none_passed():
    """With no ``passed_jid``, ``prep_jid`` returns Salt's default
    20-character all-digit jid."""
    out = pgjsonb.prep_jid()
    assert isinstance(out, str)
    assert out.isdigit()
    assert len(out) == 20


def test_get_jids_returns_one_formatted_entry_per_row():
    """``get_jids`` reads ``(jid, load)`` rows from the ``jids`` table
    and returns ``{jid: format_jid_instance(jid, load)}``."""
    rows = [
        (
            "20260504000000000001",
            {"fun": "test.ping", "tgt": "*", "user": "root", "arg": []},
        ),
        (
            "20260504000000000002",
            {
                "fun": "state.apply",
                "tgt": "minion-1",
                "user": "salt",
                "arg": ["highstate"],
            },
        ),
    ]
    cur = MagicMock()
    cur.fetchall.return_value = rows
    serv = MagicMock()
    serv.return_value.__enter__.return_value = cur

    with patch.object(pgjsonb, "_get_serv", serv):
        result = pgjsonb.get_jids()

    assert set(result) == {"20260504000000000001", "20260504000000000002"}
    assert result["20260504000000000001"]["Function"] == "test.ping"
    assert result["20260504000000000001"]["Target"] == "*"
    assert result["20260504000000000001"]["User"] == "root"
    assert result["20260504000000000002"]["Function"] == "state.apply"
    assert result["20260504000000000002"]["Target"] == "minion-1"
    assert result["20260504000000000002"]["Arguments"] == ["highstate"]
    assert result["20260504000000000002"]["User"] == "salt"
