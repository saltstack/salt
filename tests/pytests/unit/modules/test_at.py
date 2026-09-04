"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    TestCase for the salt.modules.at module
"""

import pytest

import salt.modules.at as at
import salt.utils.path
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {at: {}}


@pytest.fixture
def atq_output():
    return {
        "jobs": [
            {
                "date": "2014-12-11",
                "job": 101,
                "queue": "A",
                "tag": "",
                "time": "19:48:47",
                "user": "B",
            }
        ]
    }


def test_atq_not_available():
    """
    Tests the at.atq not available for any type of os_family.
    """
    with patch("salt.modules.at._cmd", MagicMock(return_value=None)):
        with patch.dict(at.__grains__, {"os_family": "RedHat"}):
            assert at.atq() == "'at.atq' is not available."

        with patch.dict(at.__grains__, {"os_family": ""}):
            assert at.atq() == "'at.atq' is not available."


def test_atq_no_jobs_available():
    """
    Tests the no jobs available for any type of os_family.
    """
    with patch("salt.modules.at._cmd", MagicMock(return_value="")):
        with patch.dict(at.__grains__, {"os_family": "RedHat"}):
            assert at.atq() == {"jobs": []}

        with patch.dict(at.__grains__, {"os_family": ""}):
            assert at.atq() == {"jobs": []}


def test_atq_list():
    """
    Tests the list all queued and running jobs.
    """
    with patch("salt.modules.at._cmd") as salt_modules_at__cmd_mock:
        salt_modules_at__cmd_mock.return_value = (
            "101\tThu Dec 11             19:48:47 2014 A B"
        )
        with patch.dict(at.__grains__, {"os_family": "", "os": ""}):
            assert at.atq() == {
                "jobs": [
                    {
                        "date": "2014-12-11",
                        "job": 101,
                        "queue": "A",
                        "tag": "",
                        "time": "19:48:00",
                        "user": "B",
                    }
                ]
            }

        salt_modules_at__cmd_mock.return_value = (
            "101\t2014-12-11             19:48:47 A B"
        )
        with patch.dict(at.__grains__, {"os_family": "RedHat", "os": ""}):
            assert at.atq() == {
                "jobs": [
                    {
                        "date": "2014-12-11",
                        "job": 101,
                        "queue": "A",
                        "tag": "",
                        "time": "19:48:47",
                        "user": "B",
                    }
                ]
            }

        salt_modules_at__cmd_mock.return_value = (
            "SALT: Dec 11,             2014 19:48 A 101 B"
        )
        with patch.dict(at.__grains__, {"os_family": "", "os": "OpenBSD"}):
            assert at.atq() == {
                "jobs": [
                    {
                        "date": "2014-12-11",
                        "job": "101",
                        "queue": "B",
                        "tag": "",
                        "time": "19:48:00",
                        "user": "A",
                    }
                ]
            }


def test_atrm(atq_output):
    """
    Tests for remove jobs from the queue.
    """
    with patch("salt.modules.at.atq", MagicMock(return_value=atq_output)):
        with patch.object(salt.utils.path, "which", return_value=None):
            assert at.atrm() == "'at.atrm' is not available."

        with patch.object(salt.utils.path, "which", return_value=True):
            assert at.atrm() == {"jobs": {"removed": [], "tag": None}}

        with patch.object(at, "_cmd", return_value=True):
            with patch.object(salt.utils.path, "which", return_value=True):
                assert at.atrm("all") == {"jobs": {"removed": ["101"], "tag": None}}

        with patch.object(at, "_cmd", return_value=True):
            with patch.object(salt.utils.path, "which", return_value=True):
                assert at.atrm(101) == {"jobs": {"removed": ["101"], "tag": None}}

        with patch.object(at, "_cmd", return_value=None):
            assert at.atrm(101) == "'at.atrm' is not available."


def test_jobcheck(atq_output):
    """
    Tests for check the job from queue.
    """
    with patch("salt.modules.at.atq", MagicMock(return_value=atq_output)):
        assert at.jobcheck() == {"error": "You have given a condition"}

        assert at.jobcheck(runas="foo") == {
            "note": "No match jobs or time format error",
            "jobs": [],
        }

        assert at.jobcheck(
            runas="B", tag="", hour=19, minute=48, day=11, month=12, Year=2014
        ) == {
            "jobs": [
                {
                    "date": "2014-12-11",
                    "job": 101,
                    "queue": "A",
                    "tag": "",
                    "time": "19:48:47",
                    "user": "B",
                }
            ]
        }


def test_at(atq_output):
    """
    Tests for add a job to the queue.
    """
    with patch("salt.modules.at.atq", MagicMock(return_value=atq_output)):
        assert at.at() == {"jobs": []}

        with patch.object(salt.utils.path, "which", return_value=None):
            assert (
                at.at("12:05am", "/sbin/reboot", tag="reboot")
                == "'at.at' is not available."
            )

        with patch.object(salt.utils.path, "which", return_value=True):
            with patch.dict(at.__grains__, {"os_family": "RedHat"}):
                mock = MagicMock(return_value=None)
                with patch.dict(at.__salt__, {"cmd.run": mock}):
                    assert (
                        at.at("12:05am", "/sbin/reboot", tag="reboot")
                        == "'at.at' is not available."
                    )

                mock = MagicMock(return_value="Garbled time")
                with patch.dict(at.__salt__, {"cmd.run": mock}):
                    assert at.at("12:05am", "/sbin/reboot", tag="reboot") == {
                        "jobs": [],
                        "error": "invalid timespec",
                    }

                mock = MagicMock(return_value="warning: commands\nA B")
                with patch.dict(at.__salt__, {"cmd.run": mock}):
                    with patch.dict(at.__grains__, {"os": "OpenBSD"}):
                        assert at.at("12:05am", "/sbin/reboot", tag="reboot") == {
                            "jobs": [
                                {
                                    "date": "2014-12-11",
                                    "job": 101,
                                    "queue": "A",
                                    "tag": "",
                                    "time": "19:48:47",
                                    "user": "B",
                                }
                            ]
                        }

            with patch.dict(at.__grains__, {"os_family": ""}):
                mock = MagicMock(return_value=None)
                with patch.dict(at.__salt__, {"cmd.run": mock}):
                    assert (
                        at.at("12:05am", "/sbin/reboot", tag="reboot")
                        == "'at.at' is not available."
                    )


def test_atc():
    """
    Tests for atc
    """
    with patch.object(at, "_cmd", return_value=None):
        assert at.atc(101) == "'at.atc' is not available."

    with patch.object(at, "_cmd", return_value=""):
        assert at.atc(101) == {"error": "invalid job id '101'"}

    with patch.object(at, "_cmd", return_value="101\tThu Dec 11 19:48:47 2014 A B"):
        assert at.atc(101) == "101\tThu Dec 11 19:48:47 2014 A B"


def test_at_stdin_trailing_newline_58510(atq_output):
    """
    at.at() must terminate the stdin piped to ``at`` with a trailing newline
    for both the tagged (``tag=`` kwarg) and untagged branches.

    Distro-patched at (Fedora/RHEL, BZ 486844) appends its job delimiter
    immediately after the last stdin byte, so without a trailing newline the
    marker concatenates onto the final command and produces a job that never
    executes. Regression test for issue #58510.
    """
    with patch("salt.modules.at.atq", MagicMock(return_value=atq_output)):
        with patch.object(salt.utils.path, "which", return_value=True):
            with patch.dict(at.__grains__, {"os_family": "RedHat", "os": "Linux"}):
                # Tagged branch, production-exact:
                #   salt '*' at.at 12:05am '/sbin/reboot' tag=reboot
                tag_mock = MagicMock(return_value="job 101")
                with patch.dict(at.__salt__, {"cmd.run": tag_mock}):
                    at.at("12:05am", "/sbin/reboot", tag="reboot")
                assert tag_mock.call_args.kwargs["stdin"].endswith("\n")

                # Untagged branch:
                #   salt '*' at.at 12:05am '/sbin/reboot'
                notag_mock = MagicMock(return_value="job 101")
                with patch.dict(at.__salt__, {"cmd.run": notag_mock}):
                    at.at("12:05am", "/sbin/reboot")
                assert notag_mock.call_args.kwargs["stdin"].endswith("\n")


def test_at_stdin_payload_preserved_58510(atq_output):
    """
    Inverse guard for issue #58510: appending the trailing newline must not
    alter or duplicate the command payload. With trailing newlines stripped the
    stdin must equal exactly what at.at() built before the fix, and a single
    newline must not become a double newline. This passes with and without the
    fix, so it fails a fix that mangles the payload instead of only appending a
    newline.
    """
    with patch("salt.modules.at.atq", MagicMock(return_value=atq_output)):
        with patch.object(salt.utils.path, "which", return_value=True):
            with patch.dict(at.__grains__, {"os_family": "RedHat", "os": "Linux"}):
                tag_mock = MagicMock(return_value="job 101")
                with patch.dict(at.__salt__, {"cmd.run": tag_mock}):
                    at.at("12:05am", "/sbin/reboot", tag="reboot")
                tag_stdin = tag_mock.call_args.kwargs["stdin"]
                assert tag_stdin.rstrip("\n") == "### SALT: reboot\n/sbin/reboot"
                assert not tag_stdin.endswith("\n\n")

                notag_mock = MagicMock(return_value="job 101")
                with patch.dict(at.__salt__, {"cmd.run": notag_mock}):
                    at.at("12:05am", "/sbin/reboot")
                notag_stdin = notag_mock.call_args.kwargs["stdin"]
                assert notag_stdin.rstrip("\n") == "/sbin/reboot"
                assert not notag_stdin.endswith("\n\n")


def test_at_passes_cmd_and_runas_58510(atq_output):
    """
    Peripheral coverage of the command construction in at.at() around the
    touched stdin assembly: the timespec is passed as the second element of the
    command list, cmd.run is invoked with python_shell=False, and an explicit
    runas is forwarded.
    """
    with patch("salt.modules.at.atq", MagicMock(return_value=atq_output)):
        with patch.object(salt.utils.path, "which", return_value=True):
            with patch.dict(at.__grains__, {"os_family": "RedHat", "os": "Linux"}):
                mock = MagicMock(return_value="job 101")
                with patch.dict(at.__salt__, {"cmd.run": mock}):
                    at.at("12:05am", "/sbin/reboot", tag="reboot", runas="jim")
                cmd_arg = mock.call_args.args[0]
                assert cmd_arg[1] == "12:05am"
                assert mock.call_args.kwargs["python_shell"] is False
                assert mock.call_args.kwargs["runas"] == "jim"
