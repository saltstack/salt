import sys

import pytest
import salt.modules.transactional_update as tu
import salt.utils.platform
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf


@skipIf(salt.utils.platform.is_windows(), "Do not run these tests on Windows")
class TransactionalUpdateTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.transactional_update
    """

    def setup_loader_modules(self):
        return {tu: {"__salt__": {}, "__utils__": {}}}

    def test__global_params_no_self_update(self):
        """Test transactional_update._global_params without self_update"""
        assert tu._global_params(self_update=False) == [
            "--non-interactive",
            "--drop-if-no-change",
            "--no-selfupdate",
        ]

    def test__global_params_self_update(self):
        """Test transactional_update._global_params with self_update"""
        assert tu._global_params(self_update=True) == [
            "--non-interactive",
            "--drop-if-no-change",
        ]

    def test__global_params_no_self_update_snapshot(self):
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

    def test__global_params_no_self_update_continue(self):
        """Test transactional_update._global_params without self_update and
        snapshot conitue

        """
        assert tu._global_params(self_update=False, snapshot="continue") == [
            "--non-interactive",
            "--drop-if-no-change",
            "--no-selfupdate",
            "--continue",
        ]

    def test__pkg_params_no_packages(self):
        """Test transactional_update._pkg_params without packages"""
        with pytest.raises(CommandExecutionError):
            tu._pkg_params(pkg=None, pkgs=None, args=None)

    def test__pkg_params_pkg(self):
        """Test transactional_update._pkg_params with single package"""
        assert tu._pkg_params(pkg="pkg1", pkgs=None, args=None) == ["pkg1"]

    def test__pkg_params_pkgs(self):
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

    def test__pkg_params_pkg_pkgs(self):
        """Test transactional_update._pkg_params with packages"""
        assert tu._pkg_params(pkg="pkg1", pkgs="pkg2", args=None) == [
            "pkg1",
            "pkg2",
        ]

    def test__pkg_params_args(self):
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

    def test_transactional_transactional(self):
        """Test transactional_update.transactional"""
        matrix = (("/usr/sbin/transactional-update", True), ("", False))

        for path_which, result in matrix:
            utils_mock = {"path.which": MagicMock(return_value=path_which)}

            with patch.dict(tu.__utils__, utils_mock):
                assert tu.transactional() is result
                utils_mock["path.which"].assert_called_with("transactional-update")

    def test_in_transaction(self):
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

    def test_commands_with_global_params(self):
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
                "cmd.run_all": MagicMock(
                    return_value={"stdout": "output", "retcode": 0}
                )
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

    def test_run_error(self):
        """Test transactional_update.run with missing command"""
        with pytest.raises(CommandExecutionError):
            tu.run(None)

    def test_run_string(self):
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

    def test_run_array(self):
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

    def test_pkg_commands(self):
        """Test transactional_update.pkg_* commands"""
        for cmd in ["pkg_install", "pkg_remove", "pkg_update"]:
            salt_mock = {
                "cmd.run_all": MagicMock(
                    return_value={"stdout": "output", "retcode": 0}
                )
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

    def test_rollback_error(self):
        """Test transactional_update.rollback with wrong snapshot"""
        with pytest.raises(CommandExecutionError):
            tu.rollback("error")

    def test_rollback_default(self):
        """Test transactional_update.rollback with default snapshot"""
        salt_mock = {
            "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
        }
        with patch.dict(tu.__salt__, salt_mock):
            assert tu.rollback() == "output"
            salt_mock["cmd.run_all"].assert_called_with(
                ["transactional-update", "rollback"]
            )

    def test_rollback_snapshot_number(self):
        """Test transactional_update.rollback with numeric snapshot"""
        salt_mock = {
            "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
        }
        with patch.dict(tu.__salt__, salt_mock):
            assert tu.rollback(10) == "output"
            salt_mock["cmd.run_all"].assert_called_with(
                ["transactional-update", "rollback", 10]
            )

    def test_rollback_snapshot_str(self):
        """Test transactional_update.rollback with string snapshot"""
        salt_mock = {
            "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
        }
        with patch.dict(tu.__salt__, salt_mock):
            assert tu.rollback("10") == "output"
            salt_mock["cmd.run_all"].assert_called_with(
                ["transactional-update", "rollback", "10"]
            )

    def test_rollback_last(self):
        """Test transactional_update.rollback with last snapshot"""
        salt_mock = {
            "cmd.run_all": MagicMock(return_value={"stdout": "output", "retcode": 0})
        }
        with patch.dict(tu.__salt__, salt_mock):
            assert tu.rollback("last") == "output"
            salt_mock["cmd.run_all"].assert_called_with(
                ["transactional-update", "rollback", "last"]
            )

    def test_pending_transaction(self):
        """Test transactional_update.pending_transaction"""
        matrix = (
            (False, ["1", "2+", "3-"], True),
            (False, ["1", "2-", "3+"], True),
            (False, ["1", "2", "3*"], False),
        )

        for in_transaction, snapshots, result in matrix:
            salt_mock = {
                "cmd.run_all": MagicMock(
                    return_value={"stdout": snapshots, "retcode": 0}
                )
            }

            tu_in_transaction = "salt.modules.transactional_update.in_transaction"
            with patch(tu_in_transaction) as in_transaction_mock:
                in_transaction_mock.return_value = in_transaction
                with patch.dict(tu.__salt__, salt_mock):
                    assert tu.pending_transaction() is result
                    salt_mock["cmd.run_all"].assert_called_with(
                        ["snapper", "--no-dbus", "list", "--columns", "number"]
                    )

    def test_pending_transaction_in_transaction(self):
        """Test transactional_update.pending_transaction when in transaction"""
        tu_in_transaction = "salt.modules.transactional_update.in_transaction"
        with patch(tu_in_transaction) as in_transaction_mock:
            in_transaction_mock.return_value = True
            with pytest.raises(CommandExecutionError):
                tu.pending_transaction()

    def test_call_fails_input_validation(self):
        """Test transactional_update.call missing function name"""
        with pytest.raises(CommandExecutionError):
            tu.call("")

    @patch("tempfile.mkdtemp")
    def test_call_fails_untar(self, mkdtemp):
        """Test transactional_update.call when tar fails"""
        mkdtemp.return_value = "/var/cache/salt/minion/tmp01"
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

    @patch("tempfile.mkdtemp")
    def test_call_fails_salt_thin(self, mkdtemp):
        """Test transactional_update.chroot when fails salt_thin"""
        mkdtemp.return_value = "/var/cache/salt/minion/tmp01"
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

    @patch("tempfile.mkdtemp")
    def test_call_fails_function(self, mkdtemp):
        """Test transactional_update.chroot when fails the function"""
        mkdtemp.return_value = "/var/cache/salt/minion/tmp01"
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

    @patch("tempfile.mkdtemp")
    def test_call_success_no_reboot(self, mkdtemp):
        """Test transactional_update.chroot when succeed"""
        mkdtemp.return_value = "/var/cache/salt/minion/tmp01"
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

    @patch("salt.modules.transactional_update.reboot")
    @patch("salt.modules.transactional_update.pending_transaction")
    @patch("tempfile.mkdtemp")
    def test_call_success_reboot(self, mkdtemp, pending_transaction, reboot):
        """Test transactional_update.chroot when succeed and reboot"""
        mkdtemp.return_value = "/var/cache/salt/minion/tmp01"
        pending_transaction.return_value = True
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
            assert (
                tu.call("transactional_update.dup", activate_transaction=True)
                == "result"
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
            pending_transaction.assert_called_once()
            reboot.assert_called_once()

    @patch("tempfile.mkdtemp")
    def test_call_success_parameters(self, mkdtemp):
        """Test transactional_update.chroot when succeed with parameters"""
        mkdtemp.return_value = "/var/cache/salt/minion/tmp01"
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

    @patch("salt.modules.transactional_update._create_and_execute_salt_state")
    @patch("salt.modules.transactional_update.TransactionalUpdateHighstate")
    @patch("salt.fileclient.get_file_client")
    @patch("salt.utils.state.get_sls_opts")
    def test_sls(
        self,
        get_sls_opts,
        get_file_client,
        TransactionalUpdateHighstate,
        _create_and_execute_salt_state,
    ):
        """Test transactional_update.sls"""
        TransactionalUpdateHighstate.return_value = TransactionalUpdateHighstate
        TransactionalUpdateHighstate.render_highstate.return_value = (None, [])
        TransactionalUpdateHighstate.state.reconcile_extend.return_value = (None, [])
        TransactionalUpdateHighstate.state.requisite_in.return_value = (None, [])
        TransactionalUpdateHighstate.state.verify_high.return_value = []

        _create_and_execute_salt_state.return_value = "result"
        opts_mock = {
            "hash_type": "md5",
        }
        get_sls_opts.return_value = opts_mock
        with patch.dict(tu.__opts__, opts_mock):
            assert tu.sls("module") == "result"
            _create_and_execute_salt_state.assert_called_once()

    @patch("salt.modules.transactional_update._create_and_execute_salt_state")
    @patch("salt.modules.transactional_update.TransactionalUpdateHighstate")
    @patch("salt.fileclient.get_file_client")
    @patch("salt.utils.state.get_sls_opts")
    def test_highstate(
        self,
        get_sls_opts,
        get_file_client,
        TransactionalUpdateHighstate,
        _create_and_execute_salt_state,
    ):
        """Test transactional_update.highstage"""
        TransactionalUpdateHighstate.return_value = TransactionalUpdateHighstate

        _create_and_execute_salt_state.return_value = "result"
        opts_mock = {
            "hash_type": "md5",
        }
        get_sls_opts.return_value = opts_mock
        with patch.dict(tu.__opts__, opts_mock):
            assert tu.highstate() == "result"
            _create_and_execute_salt_state.assert_called_once()

    @patch("salt.modules.transactional_update._create_and_execute_salt_state")
    @patch("salt.client.ssh.state.SSHState")
    @patch("salt.utils.state.get_sls_opts")
    def test_single(self, get_sls_opts, SSHState, _create_and_execute_salt_state):
        """Test transactional_update.single"""
        SSHState.return_value = SSHState
        SSHState.verify_data.return_value = None

        _create_and_execute_salt_state.return_value = "result"
        opts_mock = {
            "hash_type": "md5",
        }
        get_sls_opts.return_value = opts_mock
        with patch.dict(tu.__opts__, opts_mock):
            assert tu.single("pkg.installed", name="emacs") == "result"
            _create_and_execute_salt_state.assert_called_once()
