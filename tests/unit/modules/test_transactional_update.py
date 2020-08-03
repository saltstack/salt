# -*- coding: utf-8 -*-

import pytest
import salt.modules.transactional_update as tu
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class TransactionalUpdateTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.transactional_update
    """

    def setup_loader_modules(self):
        return {tu: {"__salt__": {}, "__utils__": {}}}

    def test__global_params_no_self_update(self):
        """Test transactional_update._global_params without self_update

        """
        assert tu._global_params(self_update=False) == [
            "--non-interactive",
            "--drop-if-no-change",
            "--no-selfupdate",
        ]

    def test__global_params_self_update(self):
        """Test transactional_update._global_params with self_update

        """
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

    def test_commands_with_global_params(self):
        """Test commands that only accept global params"""
        for cmd in [
            "cleanup",
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
                        cmd.replace("_", "."),
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
