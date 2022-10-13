"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""


import pytest

import salt.modules.monit as monit
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {monit: {}}


def test_start():
    """
    Test for start
    """
    with patch.dict(monit.__salt__, {"cmd.retcode": MagicMock(return_value=False)}):
        assert monit.start("name")


def test_stop():
    """
    Test for Stops service via monit
    """
    with patch.dict(monit.__salt__, {"cmd.retcode": MagicMock(return_value=False)}):
        assert monit.stop("name")


def test_restart():
    """
    Test for Restart service via monit
    """
    with patch.dict(monit.__salt__, {"cmd.retcode": MagicMock(return_value=False)}):
        assert monit.restart("name")


def test_unmonitor():
    """
    Test for Unmonitor service via monit
    """
    with patch.dict(monit.__salt__, {"cmd.retcode": MagicMock(return_value=False)}):
        assert monit.unmonitor("name")


def test_monitor():
    """
    Test for monitor service via monit
    """
    with patch.dict(monit.__salt__, {"cmd.retcode": MagicMock(return_value=False)}):
        assert monit.monitor("name")


def test_summary():
    """
    Test for Display a summary from monit
    """
    mock = MagicMock(side_effect=["daemon is not running", "A\nB\nC\nD\nE"])
    with patch.dict(monit.__salt__, {"cmd.run": mock}):
        assert monit.summary() == {"monit": "daemon is not running", "result": False}

        assert monit.summary() == {}


def test_status():
    """
    Test for Display a process status from monit
    """
    with patch.dict(monit.__salt__, {"cmd.run": MagicMock(return_value="Process")}):
        assert monit.status("service") == "No such service"


def test_reload():
    """
    Test for Reload configuration
    """
    mock = MagicMock(return_value=0)
    with patch.dict(monit.__salt__, {"cmd.retcode": mock}):
        assert monit.reload_()


def test_version():
    """
    Test for Display version from monit -V
    """
    mock = MagicMock(return_value="This is Monit version 5.14\nA\nB")
    with patch.dict(monit.__salt__, {"cmd.run": mock}):
        assert monit.version() == "5.14"


def test_id():
    """
    Test for Display unique id
    """
    mock = MagicMock(return_value="Monit ID: d3b1aba48527dd599db0e86f5ad97120")
    with patch.dict(monit.__salt__, {"cmd.run": mock}):
        assert monit.id_() == "d3b1aba48527dd599db0e86f5ad97120"


def test_reset_id():
    """
    Test for Regenerate a unique id
    """
    expected = {"stdout": "Monit id d3b1aba48527dd599db0e86f5ad97120 and ..."}
    mock = MagicMock(return_value=expected)
    with patch.dict(monit.__salt__, {"cmd.run_all": mock}):
        assert monit.id_(reset=True) == "d3b1aba48527dd599db0e86f5ad97120"


def test_configtest():
    """
    Test for Check configuration syntax
    """
    excepted = {"stdout": "Control file syntax OK", "retcode": 0, "stderr": ""}
    mock = MagicMock(return_value=excepted)
    with patch.dict(monit.__salt__, {"cmd.run_all": mock}):
        assert monit.configtest()["result"]
        assert monit.configtest()["comment"] == "Syntax OK"


def test_validate():
    """
    Test for Check all services are monitored
    """
    mock = MagicMock(return_value=0)
    with patch.dict(monit.__salt__, {"cmd.retcode": mock}):
        assert monit.validate()
