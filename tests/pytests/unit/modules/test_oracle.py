"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>

    Test cases for salt.modules.oracle
"""

import os

import pytest

import salt.modules.oracle as oracle
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
