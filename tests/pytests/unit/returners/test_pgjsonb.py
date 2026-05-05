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


def _enter_get_serv(connect_mock):
    """Enter ``_get_serv`` once with a mocked ``psycopg2.connect`` and a
    minimal fake connection, so the body opens the connection and we can
    inspect the kwargs the caller passed to ``connect``."""
    fake_conn = MagicMock()
    fake_conn.server_version = 90500
    connect_mock.return_value = fake_conn
    with patch("psycopg2.connect", connect_mock):
        with pgjsonb._get_serv():
            pass


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test__get_serv_omits_connect_timeout_when_not_configured():
    """Existing deployments must keep their current connect behaviour:
    when no ``connect_timeout`` is configured, the kwarg is not passed to
    ``psycopg2.connect`` at all so libpq's default (no app-level timeout)
    still applies."""
    connect = MagicMock()
    with patch.object(pgjsonb, "_get_options", return_value={}):
        _enter_get_serv(connect)
    assert "connect_timeout" not in connect.call_args.kwargs


@pytest.mark.skipif(not pgjsonb.HAS_PG, reason="psycopg2 not installed")
def test__get_serv_passes_connect_timeout_when_configured():
    """When ``connect_timeout`` is configured, it is forwarded to
    ``psycopg2.connect`` verbatim."""
    connect = MagicMock()
    with patch.object(pgjsonb, "_get_options", return_value={"connect_timeout": 5}):
        _enter_get_serv(connect)
    assert connect.call_args.kwargs["connect_timeout"] == 5


def test__get_options_coerces_string_connect_timeout_to_int():
    """A string ``connect_timeout`` (as it can arrive from pillar or env)
    is coerced to int so ``psycopg2.connect`` does not get a string."""
    with patch.object(
        pgjsonb.salt.returners,
        "get_returner_options",
        return_value={"connect_timeout": "5", "port": "5432"},
    ):
        opts = pgjsonb._get_options()
    assert opts["connect_timeout"] == 5
    assert isinstance(opts["connect_timeout"], int)
