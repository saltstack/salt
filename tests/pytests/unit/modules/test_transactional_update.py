import sys

import pytest
import salt.modules.state as statemod
import salt.modules.transactional_update as tu
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_on_windows(reason="Not supported on Windows"),
]


@pytest.fixture
def configure_loader_modules():
    return {
        tu: {"__salt__": {}, "__utils__": {}},
        statemod: {"__salt__": {}, "__context__": {}},
    }


def test__global_params_no_self_update():
    """Test transactional_update._global_params without self_update"""
    assert tu._global_params(self_update=False) == [
        "--non-interactive",
        "--drop-if-no-change",
        "--no-selfupdate",
    ]


def test__global_params_self_update():
    """Test transactional_update._global_params with self_update"""
    assert tu._global_params(self_update=True) == [
        "--non-interactive",
        "--drop-if-no-change",
    ]


def test__global_params_no_self_update_snapshot():
    """Test transactional_update._global_params without self_update and
    snapshot

    """
    assert tu._global_params(self_update=False, snapshot=10) == [
        "--non-interactive",
        "--drop-if-no-change",
        "--no-selfupdate",
        "--continue",
        10,
    ]


def test__global_params_no_self_update_continue():
    """Test transactional_update._global_params without self_update and
    snapshot conitue

    """
    assert tu._global_params(self_update=False, snapshot="continue") == [
        "--non-interactive",
        "--drop-if-no-change",
        "--no-selfupdate",
        "--continue",
    ]


def test__pkg_params_no_packages():
    """Test transactional_update._pkg_params without packages"""
    with pytest.raises(CommandExecutionError):
        tu._pkg_params(pkg=None, pkgs=None, args=None)


def test__pkg_params_pkg():
    """Test transactional_update._pkg_params with single package"""
    assert tu._pkg_params(pkg="pkg1", pkgs=None, args=None) == ["pkg1"]


def test__pkg_params_pkgs():
    """Test transactional_update._pkg_params with packages"""
    assert tu._pkg_params(pkg=None, pkgs="pkg1", args=None) == ["pkg1"]
    assert tu._pkg_params(pkg=None, pkgs="pkg1 pkg2 ", args=None) == [
        "pkg1",
        "pkg2",
    ]
    assert tu._pkg_params(pkg=None, pkgs=["pkg1", "pkg2"], args=None) == [
        "pkg1",
        "pkg2",
    ]


def test__pkg_params_pkg_pkgs():
    """Test transactional_update._pkg_params with packages"""
    assert tu._pkg_params(pkg="pkg1", pkgs="pkg2", args=None) == [
        "pkg1",
        "pkg2",
    ]


def test__pkg_params_args():
    """Test transactional_update._pkg_params with argumens"""
    assert tu._pkg_params(pkg="pkg1", pkgs=None, args="--arg1") == [
        "--arg1",
        "pkg1",
    ]
    assert tu._pkg_params(pkg="pkg1", pkgs=None, args="--arg1 --arg2") == [
        "--arg1",
        "--arg2",
        "pkg1",
    ]
    assert tu._pkg_params(pkg="pkg1", pkgs=None, args=["--arg1", "--arg2"]) == [
        "--arg1",
        "--arg2",
        "pkg1",
    ]


def test_transactional_transactional():
    """Test transactional_update.transactional"""
    matrix = (("/usr/sbin/transactional-update", True), ("", False))

    for path_which, result in matrix:
        utils_mock = {"path.which": MagicMock(return_value=path_which)}

        with patch.dict(tu.__utils__, utils_mock):
            assert tu.transactional() is result
            utils_mock["path.which"].assert_called_with("transactional-update")


def test_in_transaction():
    """Test transactional_update.in_transaction"""
    matrix = (
        ("/usr/sbin/transactional-update", True, True),
        ("/usr/sbin/transactional-update", False, False),
        ("", True, False),
        ("", False, False),
    )

    for path_which, in_chroot, result in matrix:
        utils_mock = {"path.which": MagicMock(return_value=path_which)}
        salt_mock = {"chroot.in_chroot": MagicMock(return_value=in_chroot)}

        with patch.dict(tu.__utils__, utils_mock):
            with patch.dict(tu.__salt__, salt_mock):
                assert tu.in_transaction() is result


def test_commands_with_global_params():
    """Test commands that only accept global params"""
    for cmd in [
        "cleanup",
        "cleanup_snapshots",
        "cleanup_overlays",
        "grub_cfg",
        "bootloader",
        "initrd",
        "kdump",
        "reboot",
        "dup",
        "up",
        "patch",
        "migration",
    ]:
        salt_mock = {
            "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
        }
        with patch.dict(tu.__salt__, salt_mock):
            assert getattr(tu, cmd)() == "output"
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "transactional-update",
                    "--non-interactive",
                    "--drop-if-no-change",
                    "--no-selfupdate",
                    cmd.replace("_", ".")
                    if cmd.startswith("grub")
                    else cmd.replace("_", "-"),
                ]
            )


def test_run_error():
    """Test transactional_update.run with missing command"""
    with pytest.raises(CommandExecutionError):
        tu.run(None)


def test_run_string():
    """Test transactional_update.run with command as string"""
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(tu.__salt__, salt_mock):
        assert tu.run("cmd --flag p1 p2") == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            [
                "transactional-update",
                "--non-interactive",
                "--drop-if-no-change",
                "--no-selfupdate",
                "--quiet",
                "run",
                "cmd",
                "--flag",
                "p1",
                "p2",
            ]
        )


def test_run_array():
    """Test transactional_update.run with command as array"""
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(tu.__salt__, salt_mock):
        assert tu.run(["cmd", "--flag", "p1", "p2"]) == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            [
                "transactional-update",
                "--non-interactive",
                "--drop-if-no-change",
                "--no-selfupdate",
                "--quiet",
                "run",
                "cmd",
                "--flag",
                "p1",
                "p2",
            ]
        )


def test_pkg_commands():
    """Test transactional_update.pkg_* commands"""
    for cmd in ["pkg_install", "pkg_remove", "pkg_update"]:
        salt_mock = {
            "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
        }
        with patch.dict(tu.__salt__, salt_mock):
            assert getattr(tu, cmd)("pkg1", "pkg2 pkg3", "--arg") == "output"
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "transactional-update",
                    "--non-interactive",
                    "--drop-if-no-change",
                    "--no-selfupdate",
                    "pkg",
                    cmd.replace("pkg_", ""),
                    "--arg",
                    "pkg1",
                    "pkg2",
                    "pkg3",
                ]
            )


def test_rollback_error():
    """Test transactional_update.rollback with wrong snapshot"""
    with pytest.raises(CommandExecutionError):
        tu.rollback("error")


def test_rollback_default():
    """Test transactional_update.rollback with default snapshot"""
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(tu.__salt__, salt_mock):
        assert tu.rollback() == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            ["transactional-update", "rollback"]
        )


def test_rollback_snapshot_number():
    """Test transactional_update.rollback with numeric snapshot"""
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(tu.__salt__, salt_mock):
        assert tu.rollback(10) == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            ["transactional-update", "rollback", 10]
        )


def test_rollback_snapshot_str():
    """Test transactional_update.rollback with string snapshot"""
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(tu.__salt__, salt_mock):
        assert tu.rollback("10") == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            ["transactional-update", "rollback", "10"]
        )


def test_rollback_last():
    """Test transactional_update.rollback with last snapshot"""
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
    }
    with patch.dict(tu.__salt__, salt_mock):
        assert tu.rollback("last") == "output"
        salt_mock["cmd.run_all"].assert_called_with(
            ["transactional-update", "rollback", "last"]
        )


def test_pending_transaction():
    """Test transactional_update.pending_transaction"""
    matrix = (
        (False, ["1", "2+", "3-"], True),
        (False, ["1", "2-", "3+"], True),
        (False, ["1", "2", "3*"], False),
    )

    for in_transaction, snapshots, result in matrix:
        salt_mock = {
            "cmd.run_all": MagicMock(return_value={"stdout": snapshots, "retcode": 0})
        }

        tu_in_transaction = "salt.modules.transactional_update.in_transaction"
        with patch(tu_in_transaction) as in_transaction_mock:
            in_transaction_mock.return_value = in_transaction
            with patch.dict(tu.__salt__, salt_mock):
                assert tu.pending_transaction() is result
                salt_mock["cmd.run_all"].assert_called_with(
                    ["snapper", "--no-dbus", "list", "--columns", "number"]
                )


def test_pending_transaction_in_transaction():
    """Test transactional_update.pending_transaction when in transaction"""
    tu_in_transaction = "salt.modules.transactional_update.in_transaction"
    with patch(tu_in_transaction) as in_transaction_mock:
        in_transaction_mock.return_value = True
        with pytest.raises(CommandExecutionError):
            tu.pending_transaction()


def test_call_fails_input_validation():
    """Test transactional_update.call missing function name"""
    with pytest.raises(CommandExecutionError):
        tu.call("")


@patch("tempfile.mkdtemp", MagicMock(return_value="/var/cache/salt/minion/tmp01"))
def test_call_fails_untar():
    """Test transactional_update.call when tar fails"""
    utils_mock = {
        "thin.gen_thin": MagicMock(return_value="/salt-thin.tgz"),
        "files.rm_rf": MagicMock(),
    }
    opts_mock = {"cachedir": "/var/cache/salt/minion"}
    salt_mock = {
        "cmd.run": MagicMock(return_value="Error"),
        "config.option": MagicMock(),
    }
    with patch.dict(tu.__utils__, utils_mock), patch.dict(
        tu.__opts__, opts_mock
    ), patch.dict(tu.__salt__, salt_mock):
        assert tu.call("/chroot", "test.ping") == {
            "result": False,
            "comment": "Error",
        }

        utils_mock["thin.gen_thin"].assert_called_once()
        salt_mock["config.option"].assert_called()
        salt_mock["cmd.run"].assert_called_once()
        utils_mock["files.rm_rf"].assert_called_once()


@patch("tempfile.mkdtemp", MagicMock(return_value="/var/cache/salt/minion/tmp01"))
def test_call_fails_salt_thin():
    """Test transactional_update.chroot when fails salt_thin"""
    utils_mock = {
        "thin.gen_thin": MagicMock(return_value="/salt-thin.tgz"),
        "files.rm_rf": MagicMock(),
        "json.find_json": MagicMock(side_effect=ValueError()),
    }
    opts_mock = {"cachedir": "/var/cache/salt/minion"}
    salt_mock = {
        "cmd.run": MagicMock(return_value=""),
        "config.option": MagicMock(),
        "cmd.run_all": MagicMock(return_value={"retcode": 1, "stderr": "Error"}),
    }
    with patch.dict(tu.__utils__, utils_mock), patch.dict(
        tu.__opts__, opts_mock
    ), patch.dict(tu.__salt__, salt_mock):
        assert tu.call("test.ping") == {
            "result": False,
            "retcode": 1,
            "comment": "Error",
        }

        utils_mock["thin.gen_thin"].assert_called_once()
        salt_mock["config.option"].assert_called()
        salt_mock["cmd.run"].assert_called_once()
        salt_mock["cmd.run_all"].assert_called_with(
            [
                "transactional-update",
                "--non-interactive",
                "--drop-if-no-change",
                "--no-selfupdate",
                "--continue",
                "--quiet",
                "run",
                "python{}".format(sys.version_info[0]),
                "/var/cache/salt/minion/tmp01/salt-call",
                "--metadata",
                "--local",
                "--log-file",
                "/var/cache/salt/minion/tmp01/log",
                "--cachedir",
                "/var/cache/salt/minion/tmp01/cache",
                "--out",
                "json",
                "-l",
                "quiet",
                "--",
                "test.ping",
            ]
        )
        utils_mock["files.rm_rf"].assert_called_once()


@patch("tempfile.mkdtemp", MagicMock(return_value="/var/cache/salt/minion/tmp01"))
def test_call_fails_function():
    """Test transactional_update.chroot when fails the function"""
    utils_mock = {
        "thin.gen_thin": MagicMock(return_value="/salt-thin.tgz"),
        "files.rm_rf": MagicMock(),
        "json.find_json": MagicMock(side_effect=ValueError()),
    }
    opts_mock = {"cachedir": "/var/cache/salt/minion"}
    salt_mock = {
        "cmd.run": MagicMock(return_value=""),
        "config.option": MagicMock(),
        "cmd.run_all": MagicMock(
            return_value={"retcode": 0, "stdout": "Not found", "stderr": ""}
        ),
    }
    with patch.dict(tu.__utils__, utils_mock), patch.dict(
        tu.__opts__, opts_mock
    ), patch.dict(tu.__salt__, salt_mock):
        assert tu.call("test.ping") == {
            "result": False,
            "retcode": 1,
            "comment": "Not found",
        }

        utils_mock["thin.gen_thin"].assert_called_once()
        salt_mock["config.option"].assert_called()
        salt_mock["cmd.run"].assert_called_once()
        salt_mock["cmd.run_all"].assert_called_with(
            [
                "transactional-update",
                "--non-interactive",
                "--drop-if-no-change",
                "--no-selfupdate",
                "--continue",
                "--quiet",
                "run",
                "python{}".format(sys.version_info[0]),
                "/var/cache/salt/minion/tmp01/salt-call",
                "--metadata",
                "--local",
                "--log-file",
                "/var/cache/salt/minion/tmp01/log",
                "--cachedir",
                "/var/cache/salt/minion/tmp01/cache",
                "--out",
                "json",
                "-l",
                "quiet",
                "--",
                "test.ping",
            ]
        )
        utils_mock["files.rm_rf"].assert_called_once()


@patch("tempfile.mkdtemp", MagicMock(return_value="/var/cache/salt/minion/tmp01"))
def test_call_success_no_reboot():
    """Test transactional_update.chroot when succeed"""
    utils_mock = {
        "thin.gen_thin": MagicMock(return_value="/salt-thin.tgz"),
        "files.rm_rf": MagicMock(),
        "json.find_json": MagicMock(return_value={"return": "result"}),
    }
    opts_mock = {"cachedir": "/var/cache/salt/minion"}
    salt_mock = {
        "cmd.run": MagicMock(return_value=""),
        "config.option": MagicMock(),
        "cmd.run_all": MagicMock(return_value={"retcode": 0, "stdout": ""}),
    }
    with patch.dict(tu.__utils__, utils_mock), patch.dict(
        tu.__opts__, opts_mock
    ), patch.dict(tu.__salt__, salt_mock):
        assert tu.call("test.ping") == "result"

        utils_mock["thin.gen_thin"].assert_called_once()
        salt_mock["config.option"].assert_called()
        salt_mock["cmd.run"].assert_called_once()
        salt_mock["cmd.run_all"].assert_called_with(
            [
                "transactional-update",
                "--non-interactive",
                "--drop-if-no-change",
                "--no-selfupdate",
                "--continue",
                "--quiet",
                "run",
                "python{}".format(sys.version_info[0]),
                "/var/cache/salt/minion/tmp01/salt-call",
                "--metadata",
                "--local",
                "--log-file",
                "/var/cache/salt/minion/tmp01/log",
                "--cachedir",
                "/var/cache/salt/minion/tmp01/cache",
                "--out",
                "json",
                "-l",
                "quiet",
                "--",
                "test.ping",
            ]
        )
        utils_mock["files.rm_rf"].assert_called_once()


@patch("tempfile.mkdtemp", MagicMock(return_value="/var/cache/salt/minion/tmp01"))
def test_call_success_reboot():
    """Test transactional_update.chroot when succeed and reboot"""
    pending_transaction_mock = MagicMock(return_value=True)
    reboot_mock = MagicMock()
    utils_mock = {
        "thin.gen_thin": MagicMock(return_value="/salt-thin.tgz"),
        "files.rm_rf": MagicMock(),
        "json.find_json": MagicMock(return_value={"return": "result"}),
    }
    opts_mock = {"cachedir": "/var/cache/salt/minion"}
    salt_mock = {
        "cmd.run": MagicMock(return_value=""),
        "config.option": MagicMock(),
        "cmd.run_all": MagicMock(return_value={"retcode": 0, "stdout": ""}),
    }
    with patch.dict(tu.__utils__, utils_mock), patch.dict(
        tu.__opts__, opts_mock
    ), patch.dict(tu.__salt__, salt_mock), patch(
        "salt.modules.transactional_update.pending_transaction",
        pending_transaction_mock,
    ), patch(
        "salt.modules.transactional_update.reboot", reboot_mock
    ):
        assert (
            tu.call("transactional_update.dup", activate_transaction=True) == "result"
        )

        utils_mock["thin.gen_thin"].assert_called_once()
        salt_mock["config.option"].assert_called()
        salt_mock["cmd.run"].assert_called_once()
        salt_mock["cmd.run_all"].assert_called_with(
            [
                "transactional-update",
                "--non-interactive",
                "--drop-if-no-change",
                "--no-selfupdate",
                "--continue",
                "--quiet",
                "run",
                "python{}".format(sys.version_info[0]),
                "/var/cache/salt/minion/tmp01/salt-call",
                "--metadata",
                "--local",
                "--log-file",
                "/var/cache/salt/minion/tmp01/log",
                "--cachedir",
                "/var/cache/salt/minion/tmp01/cache",
                "--out",
                "json",
                "-l",
                "quiet",
                "--",
                "transactional_update.dup",
            ]
        )
        utils_mock["files.rm_rf"].assert_called_once()
        pending_transaction_mock.assert_called_once()
        reboot_mock.assert_called_once()


@patch("tempfile.mkdtemp", MagicMock(return_value="/var/cache/salt/minion/tmp01"))
def test_call_success_parameters():
    """Test transactional_update.chroot when succeed with parameters"""
    utils_mock = {
        "thin.gen_thin": MagicMock(return_value="/salt-thin.tgz"),
        "files.rm_rf": MagicMock(),
        "json.find_json": MagicMock(return_value={"return": "result"}),
    }
    opts_mock = {"cachedir": "/var/cache/salt/minion"}
    salt_mock = {
        "cmd.run": MagicMock(return_value=""),
        "config.option": MagicMock(),
        "cmd.run_all": MagicMock(return_value={"retcode": 0, "stdout": ""}),
    }
    with patch.dict(tu.__utils__, utils_mock), patch.dict(
        tu.__opts__, opts_mock
    ), patch.dict(tu.__salt__, salt_mock):
        assert tu.call("module.function", key="value") == "result"

        utils_mock["thin.gen_thin"].assert_called_once()
        salt_mock["config.option"].assert_called()
        salt_mock["cmd.run"].assert_called_once()
        salt_mock["cmd.run_all"].assert_called_with(
            [
                "transactional-update",
                "--non-interactive",
                "--drop-if-no-change",
                "--no-selfupdate",
                "--continue",
                "--quiet",
                "run",
                "python{}".format(sys.version_info[0]),
                "/var/cache/salt/minion/tmp01/salt-call",
                "--metadata",
                "--local",
                "--log-file",
                "/var/cache/salt/minion/tmp01/log",
                "--cachedir",
                "/var/cache/salt/minion/tmp01/cache",
                "--out",
                "json",
                "-l",
                "quiet",
                "--",
                "module.function",
                "key=value",
            ]
        )
        utils_mock["files.rm_rf"].assert_called_once()


def test_sls():
    """Test transactional_update.sls"""
    transactional_update_highstate_mock = MagicMock()
    transactional_update_highstate_mock.return_value = (
        transactional_update_highstate_mock
    )
    transactional_update_highstate_mock.render_highstate.return_value = (None, [])
    transactional_update_highstate_mock.state.reconcile_extend.return_value = (None, [])
    transactional_update_highstate_mock.state.requisite_in.return_value = (None, [])
    transactional_update_highstate_mock.state.verify_high.return_value = []

    _create_and_execute_salt_state_mock = MagicMock(return_value="result")
    opts_mock = {
        "hash_type": "md5",
    }
    salt_mock = {
        "saltutil.is_running": MagicMock(return_value=[]),
    }
    get_sls_opts_mock = MagicMock(return_value=opts_mock)
    with patch.dict(tu.__opts__, opts_mock), patch.dict(
        statemod.__salt__, salt_mock
    ), patch("salt.utils.state.get_sls_opts", get_sls_opts_mock), patch(
        "salt.fileclient.get_file_client", MagicMock()
    ), patch(
        "salt.modules.transactional_update.TransactionalUpdateHighstate",
        transactional_update_highstate_mock,
    ), patch(
        "salt.modules.transactional_update._create_and_execute_salt_state",
        _create_and_execute_salt_state_mock,
    ):
        assert tu.sls("module") == "result"
        _create_and_execute_salt_state_mock.assert_called_once()


def test_sls_queue_true():
    """Test transactional_update.sls"""
    transactional_update_highstate_mock = MagicMock()
    transactional_update_highstate_mock.return_value = (
        transactional_update_highstate_mock
    )
    transactional_update_highstate_mock.render_highstate.return_value = (None, [])
    transactional_update_highstate_mock.state.reconcile_extend.return_value = (None, [])
    transactional_update_highstate_mock.state.requisite_in.return_value = (None, [])
    transactional_update_highstate_mock.state.verify_high.return_value = []

    _create_and_execute_salt_state_mock = MagicMock(return_value="result")
    opts_mock = {
        "hash_type": "md5",
    }
    salt_mock = {
        "saltutil.is_running": MagicMock(
            side_effect=[
                [
                    {
                        "fun": "state.running",
                        "pid": "4126",
                        "jid": "20150325123407204096",
                    }
                ],
                [],
            ]
        ),
    }
    get_sls_opts_mock = MagicMock(return_value=opts_mock)
    with patch.dict(tu.__opts__, opts_mock), patch.dict(
        statemod.__salt__, salt_mock
    ), patch("salt.utils.state.get_sls_opts", get_sls_opts_mock), patch(
        "salt.fileclient.get_file_client", MagicMock()
    ), patch(
        "salt.modules.transactional_update.TransactionalUpdateHighstate",
        transactional_update_highstate_mock,
    ), patch(
        "salt.modules.transactional_update._create_and_execute_salt_state",
        _create_and_execute_salt_state_mock,
    ):
        assert tu.sls("module", queue=True) == "result"
        _create_and_execute_salt_state_mock.assert_called_once()


def test_sls_queue_false_failing():
    """Test transactional_update.sls"""
    transactional_update_highstate_mock = MagicMock()
    transactional_update_highstate_mock.return_value = (
        transactional_update_highstate_mock
    )
    transactional_update_highstate_mock.render_highstate.return_value = (None, [])
    transactional_update_highstate_mock.state.reconcile_extend.return_value = (None, [])
    transactional_update_highstate_mock.state.requisite_in.return_value = (None, [])
    transactional_update_highstate_mock.state.verify_high.return_value = []

    _create_and_execute_salt_state_mock = MagicMock(return_value="result")
    opts_mock = {
        "hash_type": "md5",
    }
    salt_mock = {
        "saltutil.is_running": MagicMock(
            side_effect=[
                [
                    {
                        "fun": "state.running",
                        "pid": "4126",
                        "jid": "20150325123407204096",
                    }
                ],
                [],
            ]
        ),
    }
    get_sls_opts_mock = MagicMock(return_value=opts_mock)
    with patch.dict(tu.__opts__, opts_mock), patch.dict(
        statemod.__salt__, salt_mock
    ), patch("salt.utils.state.get_sls_opts", get_sls_opts_mock), patch(
        "salt.fileclient.get_file_client", MagicMock()
    ), patch(
        "salt.modules.transactional_update.TransactionalUpdateHighstate",
        transactional_update_highstate_mock,
    ), patch(
        "salt.modules.transactional_update._create_and_execute_salt_state",
        _create_and_execute_salt_state_mock,
    ):
        assert tu.sls("module", queue=False) == [
            'The function "state.running" is running as PID 4126 and was started at 2015, Mar 25 12:34:07.204096 with jid 20150325123407204096'
        ]
        _create_and_execute_salt_state_mock.assert_not_called()


def test_highstate():
    """Test transactional_update.highstage"""
    transactional_update_highstate_mock = MagicMock()
    transactional_update_highstate_mock.return_value = (
        transactional_update_highstate_mock
    )

    _create_and_execute_salt_state_mock = MagicMock(return_value="result")
    opts_mock = {
        "hash_type": "md5",
    }
    salt_mock = {
        "saltutil.is_running": MagicMock(return_value=[]),
    }
    get_sls_opts_mock = MagicMock(return_value=opts_mock)
    with patch.dict(tu.__opts__, opts_mock), patch.dict(
        statemod.__salt__, salt_mock
    ), patch("salt.utils.state.get_sls_opts", get_sls_opts_mock), patch(
        "salt.fileclient.get_file_client", MagicMock()
    ), patch(
        "salt.modules.transactional_update.TransactionalUpdateHighstate",
        transactional_update_highstate_mock,
    ), patch(
        "salt.modules.transactional_update._create_and_execute_salt_state",
        _create_and_execute_salt_state_mock,
    ):
        assert tu.highstate() == "result"
        _create_and_execute_salt_state_mock.assert_called_once()


def test_highstate_queue_true():
    """Test transactional_update.highstage"""
    transactional_update_highstate_mock = MagicMock()
    transactional_update_highstate_mock.return_value = (
        transactional_update_highstate_mock
    )

    _create_and_execute_salt_state_mock = MagicMock(return_value="result")
    opts_mock = {
        "hash_type": "md5",
    }
    salt_mock = {
        "saltutil.is_running": MagicMock(
            side_effect=[
                [
                    {
                        "fun": "state.running",
                        "pid": "4126",
                        "jid": "20150325123407204096",
                    }
                ],
                [],
            ]
        ),
    }
    get_sls_opts_mock = MagicMock(return_value=opts_mock)
    with patch.dict(tu.__opts__, opts_mock), patch.dict(
        statemod.__salt__, salt_mock
    ), patch("salt.utils.state.get_sls_opts", get_sls_opts_mock), patch(
        "salt.fileclient.get_file_client", MagicMock()
    ), patch(
        "salt.modules.transactional_update.TransactionalUpdateHighstate",
        transactional_update_highstate_mock,
    ), patch(
        "salt.modules.transactional_update._create_and_execute_salt_state",
        _create_and_execute_salt_state_mock,
    ):
        assert tu.highstate(queue=True) == "result"
        _create_and_execute_salt_state_mock.assert_called_once()


def test_highstate_queue_false_failing():
    """Test transactional_update.highstage"""
    transactional_update_highstate_mock = MagicMock()
    transactional_update_highstate_mock.return_value = (
        transactional_update_highstate_mock
    )

    _create_and_execute_salt_state_mock = MagicMock(return_value="result")
    opts_mock = {
        "hash_type": "md5",
    }
    salt_mock = {
        "saltutil.is_running": MagicMock(
            side_effect=[
                [
                    {
                        "fun": "state.running",
                        "pid": "4126",
                        "jid": "20150325123407204096",
                    }
                ],
                [],
            ]
        ),
    }
    get_sls_opts_mock = MagicMock(return_value=opts_mock)
    with patch.dict(tu.__opts__, opts_mock), patch.dict(
        statemod.__salt__, salt_mock
    ), patch("salt.utils.state.get_sls_opts", get_sls_opts_mock), patch(
        "salt.fileclient.get_file_client", MagicMock()
    ), patch(
        "salt.modules.transactional_update.TransactionalUpdateHighstate",
        transactional_update_highstate_mock,
    ), patch(
        "salt.modules.transactional_update._create_and_execute_salt_state",
        _create_and_execute_salt_state_mock,
    ):
        assert tu.highstate(queue=False) == [
            'The function "state.running" is running as PID 4126 and was started at 2015, Mar 25 12:34:07.204096 with jid 20150325123407204096'
        ]
        _create_and_execute_salt_state_mock.assert_not_called()


def test_single():
    """Test transactional_update.single"""
    ssh_state_mock = MagicMock()
    ssh_state_mock.return_value = ssh_state_mock
    ssh_state_mock.verify_data.return_value = None

    _create_and_execute_salt_state_mock = MagicMock(return_value="result")
    opts_mock = {
        "hash_type": "md5",
    }
    salt_mock = {
        "saltutil.is_running": MagicMock(return_value=[]),
    }
    get_sls_opts_mock = MagicMock(return_value=opts_mock)
    with patch.dict(tu.__opts__, opts_mock), patch.dict(
        statemod.__salt__, salt_mock
    ), patch("salt.utils.state.get_sls_opts", get_sls_opts_mock), patch(
        "salt.fileclient.get_file_client", MagicMock()
    ), patch(
        "salt.client.ssh.state.SSHState", ssh_state_mock
    ), patch(
        "salt.modules.transactional_update._create_and_execute_salt_state",
        _create_and_execute_salt_state_mock,
    ):
        assert tu.single("pkg.installed", name="emacs") == "result"
        _create_and_execute_salt_state_mock.assert_called_once()


def test_single_queue_false_failing():
    """Test transactional_update.single"""
    ssh_state_mock = MagicMock()
    ssh_state_mock.return_value = ssh_state_mock
    ssh_state_mock.verify_data.return_value = None

    _create_and_execute_salt_state_mock = MagicMock(return_value="result")
    opts_mock = {
        "hash_type": "md5",
    }
    salt_mock = {
        "saltutil.is_running": MagicMock(
            side_effect=[
                [
                    {
                        "fun": "state.running",
                        "pid": "4126",
                        "jid": "20150325123407204096",
                    }
                ],
                [],
            ]
        ),
    }
    get_sls_opts_mock = MagicMock(return_value=opts_mock)
    with patch.dict(tu.__opts__, opts_mock), patch.dict(
        statemod.__salt__, salt_mock
    ), patch("salt.utils.state.get_sls_opts", get_sls_opts_mock), patch(
        "salt.fileclient.get_file_client", MagicMock()
    ), patch(
        "salt.client.ssh.state.SSHState", ssh_state_mock
    ), patch(
        "salt.modules.transactional_update._create_and_execute_salt_state",
        _create_and_execute_salt_state_mock,
    ):
        assert tu.single("pkg.installed", name="emacs", queue=False) == [
            'The function "state.running" is running as PID 4126 and was started at 2015, Mar 25 12:34:07.204096 with jid 20150325123407204096'
        ]
        _create_and_execute_salt_state_mock.assert_not_called()


def test_single_queue_true():
    """Test transactional_update.single"""
    ssh_state_mock = MagicMock()
    ssh_state_mock.return_value = ssh_state_mock
    ssh_state_mock.verify_data.return_value = None

    _create_and_execute_salt_state_mock = MagicMock(return_value="result")
    opts_mock = {
        "hash_type": "md5",
    }
    salt_mock = {
        "saltutil.is_running": MagicMock(
            side_effect=[
                [
                    {
                        "fun": "state.running",
                        "pid": "4126",
                        "jid": "20150325123407204096",
                    }
                ],
                [],
            ]
        ),
    }
    get_sls_opts_mock = MagicMock(return_value=opts_mock)
    with patch.dict(tu.__opts__, opts_mock), patch.dict(
        statemod.__salt__, salt_mock
    ), patch("salt.utils.state.get_sls_opts", get_sls_opts_mock), patch(
        "salt.fileclient.get_file_client", MagicMock()
    ), patch(
        "salt.client.ssh.state.SSHState", ssh_state_mock
    ), patch(
        "salt.modules.transactional_update._create_and_execute_salt_state",
        _create_and_execute_salt_state_mock,
    ):
        assert tu.single("pkg.installed", name="emacs", queue=True) == "result"
        _create_and_execute_salt_state_mock.assert_called_once()
