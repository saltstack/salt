import pytest

import salt.loader.context
import salt.modules.state as statemod
import salt.modules.transactional_update as tu
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_on_windows(reason="Not supported on Windows"),
]


@pytest.fixture
def configure_loader_modules():
    loader_context = salt.loader.context.LoaderContext()
    return {
        tu: {
            "__salt__": {},
            "__utils__": {"files.rm_rf": MagicMock()},
            "__pillar__": salt.loader.context.NamedLoaderContext(
                "__pillar__", loader_context, {}
            ),
            "__opts__": {"extension_modules": "", "cachedir": "/tmp/"},
        },
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
                    (
                        cmd.replace("_", ".")
                        if cmd.startswith("grub")
                        else cmd.replace("_", "-")
                    ),
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


def test_call_fails_function():
    """Test transactional_update.chroot when fails the function"""
    utils_mock = {
        "json.find_json": MagicMock(side_effect=ValueError()),
    }
    salt_mock = {
        "cmd.run_all": MagicMock(
            return_value={"retcode": 0, "stdout": "Not found", "stderr": ""}
        ),
    }
    with patch.dict(tu.__utils__, utils_mock), patch.dict(tu.__salt__, salt_mock):
        assert tu.call("test.ping") == {
            "result": False,
            "retcode": 1,
            "comment": "Not found",
        }

        salt_mock["cmd.run_all"].assert_called_with(
            [
                "transactional-update",
                "--non-interactive",
                "--drop-if-no-change",
                "--no-selfupdate",
                "--continue",
                "--quiet",
                "run",
                "salt-call",
                "--out",
                "json",
                "-l",
                "quiet",
                "--no-return-event",
                "--",
                "test.ping",
            ]
        )


def test_call_success_no_reboot():
    """Test transactional_update.chroot when succeed"""
    utils_mock = {
        "json.find_json": MagicMock(return_value={"return": "result"}),
    }
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"retcode": 0, "stdout": ""}),
    }
    with patch.dict(tu.__utils__, utils_mock), patch.dict(tu.__salt__, salt_mock):
        assert tu.call("test.ping") == "result"

        salt_mock["cmd.run_all"].assert_called_with(
            [
                "transactional-update",
                "--non-interactive",
                "--drop-if-no-change",
                "--no-selfupdate",
                "--continue",
                "--quiet",
                "run",
                "salt-call",
                "--out",
                "json",
                "-l",
                "quiet",
                "--no-return-event",
                "--",
                "test.ping",
            ]
        )


def test_call_success_reboot():
    """Test transactional_update.chroot when succeed and reboot"""
    pending_transaction_mock = MagicMock(return_value=True)
    reboot_mock = MagicMock()
    utils_mock = {
        "json.find_json": MagicMock(return_value={"return": "result"}),
    }
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"retcode": 0, "stdout": ""}),
    }
    with patch.dict(tu.__utils__, utils_mock), patch.dict(
        tu.__salt__, salt_mock
    ), patch.dict(tu.__salt__, salt_mock), patch(
        "salt.modules.transactional_update.pending_transaction",
        pending_transaction_mock,
    ), patch(
        "salt.modules.transactional_update.reboot", reboot_mock
    ):
        assert (
            tu.call("transactional_update.dup", activate_transaction=True) == "result"
        )

        salt_mock["cmd.run_all"].assert_called_with(
            [
                "transactional-update",
                "--non-interactive",
                "--drop-if-no-change",
                "--no-selfupdate",
                "--continue",
                "--quiet",
                "run",
                "salt-call",
                "--out",
                "json",
                "-l",
                "quiet",
                "--no-return-event",
                "--",
                "transactional_update.dup",
            ]
        )
        pending_transaction_mock.assert_called_once()
        reboot_mock.assert_called_once()


def test_call_success_parameters():
    """Test transactional_update.chroot when succeed with parameters"""
    utils_mock = {
        "json.find_json": MagicMock(return_value={"return": "result"}),
    }
    salt_mock = {
        "cmd.run_all": MagicMock(return_value={"retcode": 0, "stdout": ""}),
    }
    with patch.dict(tu.__utils__, utils_mock), patch.dict(tu.__salt__, salt_mock):
        assert tu.call("module.function", key="value") == "result"

        salt_mock["cmd.run_all"].assert_called_with(
            [
                "transactional-update",
                "--non-interactive",
                "--drop-if-no-change",
                "--no-selfupdate",
                "--continue",
                "--quiet",
                "run",
                "salt-call",
                "--out",
                "json",
                "-l",
                "quiet",
                "--no-return-event",
                "--",
                "module.function",
                "key=value",
            ]
        )


def test_sls():
    """Test transactional_update.sls"""
    salt_mock = {
        "saltutil.is_running": MagicMock(return_value=[]),
    }
    with patch.dict(statemod.__salt__, salt_mock), patch(
        "salt.modules.transactional_update.call", MagicMock(return_value="result")
    ):
        assert tu.sls("module") == "result"


def test_sls_queue_true():
    """Test transactional_update.sls"""
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
    with patch.dict(statemod.__salt__, salt_mock), patch(
        "salt.modules.transactional_update.call", MagicMock(return_value="result")
    ):
        assert tu.sls("module", queue=True) == "result"


def test_sls_queue_false_failing():
    """Test transactional_update.sls"""
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
    with patch.dict(statemod.__salt__, salt_mock), patch(
        "salt.modules.transactional_update.call", MagicMock(return_value="result")
    ):
        assert tu.sls("module", queue=False) == [
            'The function "state.running" is running as PID 4126 and was started at 2015, Mar 25 12:34:07.204096 with jid 20150325123407204096'
        ]


def test_highstate():
    """Test transactional_update.highstage"""
    salt_mock = {
        "saltutil.is_running": MagicMock(return_value=[]),
    }
    with patch.dict(statemod.__salt__, salt_mock), patch(
        "salt.modules.transactional_update.call", MagicMock(return_value="result")
    ):
        assert tu.highstate() == "result"


def test_highstate_queue_true():
    """Test transactional_update.highstage"""
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
    with patch.dict(statemod.__salt__, salt_mock), patch(
        "salt.modules.transactional_update.call", MagicMock(return_value="result")
    ):
        assert tu.highstate(queue=True) == "result"


def test_highstate_queue_false_failing():
    """Test transactional_update.highstage"""
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
    with patch.dict(statemod.__salt__, salt_mock), patch(
        "salt.modules.transactional_update.call", MagicMock(return_value="result")
    ):
        assert tu.highstate(queue=False) == [
            'The function "state.running" is running as PID 4126 and was started at 2015, Mar 25 12:34:07.204096 with jid 20150325123407204096'
        ]


def test_single():
    """Test transactional_update.single"""
    salt_mock = {
        "saltutil.is_running": MagicMock(return_value=[]),
    }
    with patch.dict(statemod.__salt__, salt_mock), patch(
        "salt.modules.transactional_update.call", MagicMock(return_value="result")
    ):
        assert tu.single("pkg.installed", name="emacs") == "result"


def test_single_queue_false_failing():
    """Test transactional_update.single"""
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
    with patch.dict(statemod.__salt__, salt_mock), patch(
        "salt.modules.transactional_update.call", MagicMock(return_value="result")
    ):
        assert tu.single("pkg.installed", name="emacs", queue=False) == [
            'The function "state.running" is running as PID 4126 and was started at 2015, Mar 25 12:34:07.204096 with jid 20150325123407204096'
        ]


def test_single_queue_true():
    """Test transactional_update.single"""
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
    with patch.dict(statemod.__salt__, salt_mock), patch(
        "salt.modules.transactional_update.call", MagicMock(return_value="result")
    ):
        assert tu.single("pkg.installed", name="emacs", queue=True) == "result"
