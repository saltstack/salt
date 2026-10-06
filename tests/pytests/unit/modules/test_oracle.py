"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>

    Test cases for salt.modules.oracle
"""

import os

import pytest

import salt.modules.oracle as oracle
import salt.utils.data
import salt.utils.secret
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {oracle: {"cx_Oracle": object()}}


def test_run_query():
    """
    Test for Run SQL query and return result
    """
    with patch.object(oracle, "_connect", MagicMock()) as mock_connect:
        mock_connect.cursor.execute.fetchall.return_value = True
        with patch.object(oracle, "show_dbs", MagicMock()):
            assert oracle.run_query("db", "query")


def test_show_dbs():
    """
    Test for Show databases configuration from pillar. Filter by `*args`
    """
    with patch.dict(oracle.__salt__, {"pillar.get": MagicMock(return_value="a")}):
        assert oracle.show_dbs("A", "B") == {"A": "a", "B": "a"}

        assert oracle.show_dbs() == "a"


def test_version():
    """
    Test for Server Version (select banner  from v$version)
    """
    with patch.dict(oracle.__salt__, {"pillar.get": MagicMock(return_value="a")}):
        with patch.object(oracle, "run_query", return_value="A"):
            assert oracle.version() == {}


def test_client_version():
    """
    Test for Oracle Client Version
    """
    with patch.object(oracle, "cx_Oracle", MagicMock(side_effect=MagicMock())):
        assert oracle.client_version() == ""


def test_show_pillar():
    """
    Test for Show Pillar segment oracle.*
    """
    with patch.dict(oracle.__salt__, {"pillar.get": MagicMock(return_value="a")}):
        assert oracle.show_pillar("item") == "a"


def _masking_pillar_get(pillar):
    """
    Build a fake pillar.get that behaves like the real 3008 one: values are
    run through salt.utils.secret.serial() (strings redacted) unless
    unmask=True, in which case they are expose()d to plain values.
    """
    hidden = salt.utils.secret.hide(pillar)

    def fake_pillar_get(key, default=None, *args, unmask=None, **kwargs):
        value = salt.utils.data.traverse_dict_and_list(hidden, key, default)
        if unmask:
            return salt.utils.secret.expose(value)
        return salt.utils.secret.serial(value)

    return fake_pillar_get


def test_show_dbs_returns_unmasked_uri():
    """
    show_dbs(db) must return the real connection uri, not the redact
    placeholder, because run_query() feeds it to _connect().
    """
    real_uri = "scott/tiger@oradb1:1521/orcl"
    fake_get = _masking_pillar_get({"oracle": {"dbs": {"my_db": {"uri": real_uri}}}})
    with patch.dict(oracle.__salt__, {"pillar.get": fake_get}):
        assert oracle.show_dbs("my_db") == {"my_db": {"uri": real_uri}}


def test_run_query_connects_with_unmasked_uri():
    """
    run_query() must pass the real (unmasked) uri to _connect().
    """
    real_uri = "scott/tiger@oradb1:1521/orcl"
    fake_get = _masking_pillar_get({"oracle": {"dbs": {"my_db": {"uri": real_uri}}}})
    with patch.dict(oracle.__salt__, {"pillar.get": fake_get}):
        with patch.object(oracle, "_connect", MagicMock()) as mock_connect:
            oracle.run_query("my_db", "select 1 from dual")
    mock_connect.assert_called_once_with(real_uri)
    assert salt.utils.secret.REDACT_PLACEHOLDER not in mock_connect.call_args.args[0]


def test_show_env():
    """
    Test for Show Environment used by Oracle Client
    """
    with patch.object(
        os,
        "environ",
        return_value={
            "PATH": "PATH",
            "ORACLE_HOME": "ORACLE_HOME",
            "TNS_ADMIN": "TNS_ADMIN",
            "NLS_LANG": "NLS_LANG",
        },
    ):
        assert oracle.show_env() == {}
