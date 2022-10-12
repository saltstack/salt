"""
    :codeauthor: asomers <asomers@gmail.com>
"""

import pytest

import salt.modules.freebsd_sysctl as freebsd_sysctl
import salt.modules.systemd_service as systemd
from salt.exceptions import CommandExecutionError
from tests.support.helpers import dedent
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {freebsd_sysctl: {}, systemd: {}}


def test_get():
    """
    Tests the return of get function
    """
    mock_cmd = MagicMock(return_value="1")
    with patch.dict(freebsd_sysctl.__salt__, {"cmd.run": mock_cmd}):
        assert freebsd_sysctl.get("vfs.usermount") == "1"


def test_assign_failed():
    """
    Tests if the assignment was successful or not
    """
    cmd = {
        "pid": 1337,
        "retcode": 1,
        "stderr": "sysctl: unknown oid 'asef.esrhaseras.easr'",
        "stdout": "",
    }
    mock_cmd = MagicMock(return_value=cmd)
    with patch.dict(freebsd_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
        pytest.raises(
            CommandExecutionError,
            freebsd_sysctl.assign,
            "asef.esrhaseras.easr",
            "backward",
        )


def test_assign_success():
    """
    Tests the return of successful assign function
    """
    cmd = {
        "pid": 1337,
        "retcode": 0,
        "stderr": "",
        "stdout": "vfs.usermount: 0 -> 1",
    }
    ret = {"vfs.usermount": "1"}
    mock_cmd = MagicMock(return_value=cmd)
    with patch.dict(freebsd_sysctl.__salt__, {"cmd.run_all": mock_cmd}):
        assert freebsd_sysctl.assign("vfs.usermount", 1) == ret


def test_persist_no_conf_failure():
    """
    Tests adding of config file failure
    """
    asn_cmd = {
        "pid": 1337,
        "retcode": 1,
        "stderr": "sysctl: vfs.usermount=1: Operation not permitted",
        "stdout": "vfs.usermount: 1",
    }
    mock_asn_cmd = MagicMock(return_value=asn_cmd)
    cmd = "sysctl vfs.usermount=1"
    mock_cmd = MagicMock(return_value=cmd)
    with patch.dict(
        freebsd_sysctl.__salt__,
        {"cmd.run_stdout": mock_cmd, "cmd.run_all": mock_asn_cmd},
    ):
        with patch("salt.utils.files.fopen", mock_open()) as m_open:
            pytest.raises(
                CommandExecutionError,
                freebsd_sysctl.persist,
                "net.ipv4.ip_forward",
                1,
                config=None,
            )


def test_persist_nochange():
    """
    Tests success when no changes need to be made
    """
    mock_get_cmd = MagicMock(return_value="1")
    content = "vfs.usermount=1\n"
    with patch("salt.utils.files.fopen", mock_open(read_data=content)):
        with patch.dict(
            freebsd_sysctl.__salt__,
            {"cmd.run": mock_get_cmd},
        ):
            assert freebsd_sysctl.persist("vfs.usermount", 1) == "Already set"


def test_persist_in_memory():
    """
    Tests success when the on-disk value is correct but the in-memory value
    needs updating.
    """
    mock_get_cmd = MagicMock(return_value="0")
    set_cmd = {
        "pid": 1337,
        "retcode": 0,
        "stderr": "",
        "stdout": "vfs.usermount: 0 -> 1",
    }
    mock_set_cmd = MagicMock(return_value=set_cmd)
    content = "vfs.usermount=1\n"
    with patch("salt.utils.files.fopen", mock_open(read_data=content)):
        with patch.dict(
            freebsd_sysctl.__salt__,
            {"cmd.run": mock_get_cmd},
        ):
            with patch.dict(
                freebsd_sysctl.__salt__,
                {"cmd.run_all": mock_set_cmd},
            ):
                assert freebsd_sysctl.persist("vfs.usermount", 1) == "Updated"


def test_persist_updated():
    """
    Tests sysctl.conf success
    """
    cmd = {
        "pid": 1337,
        "retcode": 0,
        "stderr": "",
        "stdout": "vfs.usermount: 1 -> 1",
    }
    mock_cmd = MagicMock(return_value=cmd)

    with patch("salt.utils.files.fopen", mock_open()):
        with patch.dict(
            freebsd_sysctl.__salt__,
            {"cmd.run_all": mock_cmd},
        ):
            assert freebsd_sysctl.persist("vfs.usermount", 1) == "Updated"


def test_persist_updated_tunable():
    """
    Tests loader.conf success
    """

    with patch("salt.utils.files.fopen", mock_open()):
        assert (
            freebsd_sysctl.persist("vfs.usermount", 1, "/boot/loader.conf") == "Updated"
        )


def test_show():
    """
    Tests the show function
    """
    # Mock just a small portion of the full "sysctl -ae" output, but be
    # sure to include a multi-line value.
    mock_cmd = MagicMock(
        return_value=dedent(
            """\
        kern.ostype=FreeBSD
        kern.osrelease=13.0-CURRENT
        kern.osrevision=199506
        kern.version=FreeBSD 13.0-CURRENT #246 r365916M: Thu Sep 24 09:17:12 MDT 2020
            user@host.domain:/usr/obj/usr/src/head
        /amd64.amd64/sys/GENERIC

        kern.maxvnodes=213989
        """,
            "\n",
        )
    )
    with patch.dict(freebsd_sysctl.__salt__, {"cmd.run": mock_cmd}):
        ret = freebsd_sysctl.show()
        assert "FreeBSD" == ret["kern.ostype"]
        assert (
            dedent(
                """\
            FreeBSD 13.0-CURRENT #246 r365916M: Thu Sep 24 09:17:12 MDT 2020
                user@host.domain:/usr/obj/usr/src/head
            /amd64.amd64/sys/GENERIC
            """,
                "\n",
            )
            == ret["kern.version"]
        )
