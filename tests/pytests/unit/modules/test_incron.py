"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.incron
"""


import pytest

import salt.modules.incron as incron
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def configure_loader_modules():
    return {incron: {}}


# 'write_incron_file' function tests: 1


def test_write_incron_file():
    """
    Test if it writes the contents of a file to a user's crontab
    """
    mock = MagicMock(return_value=0)
    with patch.dict(incron.__salt__, {"cmd.retcode": mock}), patch(
        "salt.modules.incron._get_incron_cmdstr",
        MagicMock(return_value="incrontab"),
    ):
        assert incron.write_incron_file("cybage", "/home/cybage/new_cron")


# 'write_cron_file_verbose' function tests: 1


def test_write_cron_file_verbose():
    """
    Test if it writes the contents of a file to a user's crontab and
    return error message on error
    """
    mock = MagicMock(return_value=True)
    with patch.dict(incron.__salt__, {"cmd.run_all": mock}), patch(
        "salt.modules.incron._get_incron_cmdstr",
        MagicMock(return_value="incrontab"),
    ):
        assert incron.write_incron_file_verbose("cybage", "/home/cybage/new_cron")


# 'raw_system_incron' function tests: 1


def test_raw_system_incron():
    """
    Test if it return the contents of the system wide incrontab
    """
    with patch("salt.modules.incron._read_file", MagicMock(return_value="salt")):
        assert incron.raw_system_incron() == "salt"


# 'raw_incron' function tests: 1


def test_raw_incron():
    """
    Test if it return the contents of the user's incrontab
    """
    mock = MagicMock(return_value="incrontab")
    expected_calls = [
        call("incrontab -l cybage", python_shell=False, rstrip=False, runas="cybage")
    ]

    with patch.dict(incron.__grains__, {"os_family": mock}):
        cmd_run_mock = MagicMock(return_value="salt")
        with patch.dict(incron.__salt__, {"cmd.run_stdout": cmd_run_mock}):
            assert incron.raw_incron("cybage") == "salt"
            cmd_run_mock.assert_has_calls(expected_calls)

            cmd = cmd_run_mock.call_args[0][0]
            assert "incrontab -l cybage" == cmd
            assert "-u" not in cmd


# 'list_tab' function tests: 1


def test_list_tab():
    """
    Test if it return the contents of the specified user's incrontab
    """
    mock = MagicMock(return_value="incrontab")
    with patch.dict(incron.__grains__, {"os_family": mock}):
        mock = MagicMock(return_value="salt")
        with patch.dict(incron.__salt__, {"cmd.run_stdout": mock}):
            assert incron.list_tab("cybage") == {"pre": ["salt"], "crons": []}


# 'set_job' function tests: 1


def test_set_job():
    """
    Test if it sets a cron job up for a specified user.
    """
    assert (
        incron.set_job("cybage", "/home/cybage", "TO_MODIFY", 'echo "$$ $@ $# $% $&"')
        == "Invalid mask type: TO_MODIFY"
    )

    val = {
        "pre": [],
        "crons": [{"path": "/home/cybage", "mask": "IN_MODIFY", "cmd": 'echo "SALT"'}],
    }
    with patch.object(incron, "list_tab", MagicMock(return_value=val)):
        assert (
            incron.set_job("cybage", "/home/cybage", "IN_MODIFY", 'echo "SALT"')
            == "present"
        )

    with patch.object(
        incron, "list_tab", MagicMock(return_value={"pre": ["salt"], "crons": []})
    ):
        mock = MagicMock(return_value="incrontab")
        with patch.dict(incron.__grains__, {"os_family": mock}):
            with patch.object(
                incron,
                "_write_incron_lines",
                MagicMock(return_value={"retcode": True, "stderr": "error"}),
            ):
                assert (
                    incron.set_job("cybage", "/home/cybage", "IN_MODIFY", 'echo "SALT"')
                    == "error"
                )

    with patch.object(
        incron, "list_tab", MagicMock(return_value={"pre": ["salt"], "crons": []})
    ):
        mock = MagicMock(return_value="incrontab")
        with patch.dict(incron.__grains__, {"os_family": mock}):
            with patch.object(
                incron,
                "_write_incron_lines",
                MagicMock(return_value={"retcode": False, "stderr": "error"}),
            ):
                assert (
                    incron.set_job("cybage", "/home/cybage", "IN_MODIFY", 'echo "SALT"')
                    == "new"
                )

    val = {
        "pre": [],
        "crons": [
            {
                "path": "/home/cybage",
                "mask": "IN_MODIFY,IN_DELETE",
                "cmd": 'echo "SALT"',
            }
        ],
    }
    with patch.object(incron, "list_tab", MagicMock(return_value=val)):
        mock = MagicMock(return_value="incrontab")
        with patch.dict(incron.__grains__, {"os_family": mock}):
            with patch.object(
                incron,
                "_write_incron_lines",
                MagicMock(return_value={"retcode": False, "stderr": "error"}),
            ):
                assert (
                    incron.set_job("cybage", "/home/cybage", "IN_DELETE", 'echo "SALT"')
                    == "updated"
                )


# 'rm_job' function tests: 1


def test_rm_job():
    """
    Test if it remove a cron job for a specified user. If any of the
    day/time params are specified, the job will only be removed if
    the specified params match.
    """
    assert (
        incron.rm_job("cybage", "/home/cybage", "TO_MODIFY", 'echo "$$ $@ $# $% $&"')
        == "Invalid mask type: TO_MODIFY"
    )

    with patch.object(
        incron, "list_tab", MagicMock(return_value={"pre": ["salt"], "crons": []})
    ):
        mock = MagicMock(return_value="incrontab")
        with patch.dict(incron.__grains__, {"os_family": mock}):
            with patch.object(
                incron,
                "_write_incron_lines",
                MagicMock(return_value={"retcode": True, "stderr": "error"}),
            ):
                assert (
                    incron.rm_job("cybage", "/home/cybage", "IN_MODIFY", 'echo "SALT"')
                    == "error"
                )

    with patch.object(
        incron, "list_tab", MagicMock(return_value={"pre": ["salt"], "crons": []})
    ):
        mock = MagicMock(return_value="incrontab")
        with patch.dict(incron.__grains__, {"os_family": mock}):
            with patch.object(
                incron,
                "_write_incron_lines",
                MagicMock(return_value={"retcode": False, "stderr": "error"}),
            ):
                assert (
                    incron.rm_job("cybage", "/home/cybage", "IN_MODIFY", 'echo "SALT"')
                    == "absent"
                )
