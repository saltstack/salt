import pytest

import salt.modules.pf as pf
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pf: {}}


def test_enable_when_disabled():
    """
    Tests enabling pf when it's not enabled yet.
    """
    ret = {}
    ret["stderr"] = "pf enabled"
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert pf.enable()["changes"]


def test_enable_when_enabled():
    """
    Tests enabling pf when it already enabled.
    """
    ret = {}
    ret["stderr"] = "pfctl: pf already enabled"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert not pf.enable()["changes"]


def test_disable_when_enabled():
    """
    Tests disabling pf when it's enabled.
    """
    ret = {}
    ret["stderr"] = "pf disabled"
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert pf.disable()["changes"]


def test_disable_when_disabled():
    """
    Tests disabling pf when it already disabled.
    """
    ret = {}
    ret["stderr"] = "pfctl: pf not enabled"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert not pf.disable()["changes"]


def test_loglevel_freebsd():
    """
    Tests setting a loglevel.
    """
    ret = {}
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        pf.__grains__, {"os": "FreeBSD"}
    ):
        res = pf.loglevel("urgent")
        mock_cmd.assert_called_once_with(
            "pfctl -x urgent", output_loglevel="trace", python_shell=False
        )
        assert res["changes"]


def test_loglevel_openbsd():
    """
    Tests setting a loglevel.
    """
    ret = {}
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        pf.__grains__, {"os": "OpenBSD"}
    ):
        res = pf.loglevel("crit")
        mock_cmd.assert_called_once_with(
            "pfctl -x crit", output_loglevel="trace", python_shell=False
        )
        assert res["changes"]


def test_load():
    """
    Tests loading ruleset.
    """
    ret = {}
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        res = pf.load()
        mock_cmd.assert_called_once_with(
            ["pfctl", "-f", "/etc/pf.conf"],
            output_loglevel="trace",
            python_shell=False,
        )
        assert res["changes"]


def test_load_noop():
    """
    Tests evaluating but not actually loading ruleset.
    """
    ret = {}
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        res = pf.load(noop=True)
        mock_cmd.assert_called_once_with(
            ["pfctl", "-f", "/etc/pf.conf", "-n"],
            output_loglevel="trace",
            python_shell=False,
        )
        assert not res["changes"]


def test_flush():
    """
    Tests a regular flush command.
    """
    ret = {}
    ret["stderr"] = "pf: statistics cleared"
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        res = pf.flush("info")
        mock_cmd.assert_called_once_with(
            "pfctl -v -F info", output_loglevel="trace", python_shell=False
        )
        assert res["changes"]


def test_flush_capital():
    """
    Tests a flush command starting with a capital letter.
    """
    ret = {}
    ret["stderr"] = "2 tables cleared"
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        res = pf.flush("tables")
        mock_cmd.assert_called_once_with(
            "pfctl -v -F Tables", output_loglevel="trace", python_shell=False
        )
        assert res["changes"]


def test_flush_without_changes():
    """
    Tests a flush command that has no changes.
    """
    ret = {}
    ret["stderr"] = "0 tables cleared"
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert not pf.flush("tables")["changes"]


def test_table():
    """
    Tests a regular table command.
    """
    ret = {}
    ret["stderr"] = "42 addresses deleted"
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert pf.table("flush", table="bad_hosts")["changes"]


def test_table_expire():
    """
    Tests the table expire command.
    """
    ret = {}
    ret["stderr"] = "1/1 addresses expired."
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert pf.table("expire", table="bad_hosts", number=300)["changes"]


def test_table_add_addresses():
    """
    Tests adding addresses to a table.
    """
    ret = {}
    ret["stderr"] = "2/2 addressess added."
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert pf.table("add", table="bad_hosts", addresses=["1.2.3.4", "5.6.7.8"])[
            "changes"
        ]


def test_table_delete_addresses():
    """
    Tests deleting addresses in a table.
    """
    ret = {}
    ret["stderr"] = "2/2 addressess deleted."
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert pf.table("delete", table="bad_hosts", addresses=["1.2.3.4", "5.6.7.8"])[
            "changes"
        ]


def test_table_test_address():
    """
    Tests testing addresses in a table.
    """
    ret = {}
    ret["stderr"] = "1/2 addressess match."
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert pf.table("test", table="bad_hosts", addresses=["1.2.3.4"])["matches"]


def test_table_no_changes():
    """
    Tests a table command that has no changes.
    """
    ret = {}
    ret["stderr"] = "0/1 addresses expired."
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert not pf.table("expire", table="bad_hosts", number=300)["changes"]


def test_table_show():
    """
    Tests showing table contents.
    """
    ret = {}
    ret["stdout"] = "1.2.3.4\n5.6.7.8"
    ret["retcode"] = 0
    expected = ["1.2.3.4", "5.6.7.8"]
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert pf.table("show", table="bad_hosts")["comment"] == expected


def test_table_zero():
    """
    Tests clearing all the statistics of a table.
    """
    ret = {}
    ret["stderr"] = "42 addresses has been cleared"
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert pf.table("zero", table="bad_hosts")["changes"]


def test_show_rules():
    """
    Tests show rules command.
    """
    ret = {}
    ret["stdout"] = "block return\npass"
    ret["retcode"] = 0
    expected = ["block return", "pass"]
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert pf.show("rules")["comment"] == expected


def test_show_states():
    """
    Tests show states command.
    """
    ret = {}
    ret["stdout"] = "all udp 192.168.1.1:3478\n"
    ret["retcode"] = 0
    expected = ["all udp 192.168.1.1:3478", ""]
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        assert pf.show("states")["comment"] == expected


def test_show_tables():
    """
    Tests show tables command.
    """
    ret = {}
    ret["stdout"] = "bad_hosts"
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(pf.__salt__, {"cmd.run_all": mock_cmd}):
        res = pf.show("tables")
        mock_cmd.assert_called_once_with(
            "pfctl -s Tables", output_loglevel="trace", python_shell=False
        )
        assert not res["changes"]
