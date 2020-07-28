# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import pytest
import salt.modules.alternatives as alternatives
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def setup_loader(request):
    setup_loader_modules = {alternatives: {}}
    with pytest.helpers.loader_mock(request, setup_loader_modules) as loader_mock:
        yield loader_mock


def test_display():
    with patch.dict(alternatives.__grains__, {"os_family": "RedHat"}):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "salt"})
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.display("better-world")
            assert "salt" == solution
            mock.assert_called_once_with(
                ["alternatives", "--display", "better-world"],
                python_shell=False,
                ignore_retcode=True,
            )

    with patch.dict(alternatives.__grains__, {"os_family": "Suse"}):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "undoubtedly-salt"})
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.display("better-world")
            assert "undoubtedly-salt" == solution
            mock.assert_called_once_with(
                ["update-alternatives", "--display", "better-world"],
                python_shell=False,
                ignore_retcode=True,
            )

    with patch.dict(alternatives.__grains__, {"os_family": "RedHat"}):
        mock = MagicMock(
            return_value={"retcode": 1, "stdout": "salt-out", "stderr": "salt-err"}
        )
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.display("better-world")
            assert "salt-err" == solution
            mock.assert_called_once_with(
                ["alternatives", "--display", "better-world"],
                python_shell=False,
                ignore_retcode=True,
            )


def test_show_current():
    mock = MagicMock(return_value="/etc/alternatives/salt")
    with patch("salt.utils.path.readlink", mock):
        ret = alternatives.show_current("better-world")
        assert "/etc/alternatives/salt" == ret
        mock.assert_called_once_with("/etc/alternatives/better-world")

        with TstSuiteLoggingHandler() as handler:
            mock.side_effect = OSError("Hell was not found!!!")
            assert not alternatives.show_current("hell")
            mock.assert_called_with("/etc/alternatives/hell")
            assert "ERROR:alternative: hell does not exist" in handler.messages


def test_check_installed():
    mock = MagicMock(return_value="/etc/alternatives/salt")
    with patch("salt.utils.path.readlink", mock):
        assert alternatives.check_installed("better-world", "/etc/alternatives/salt")
        mock.return_value = False
        assert not alternatives.check_installed("help", "/etc/alternatives/salt")


def test_install():
    with patch.dict(alternatives.__grains__, {"os_family": "RedHat"}):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "salt"})
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.install(
                "better-world", "/usr/bin/better-world", "/usr/bin/salt", 100
            )
            assert "salt" == solution
            mock.assert_called_once_with(
                [
                    "alternatives",
                    "--install",
                    "/usr/bin/better-world",
                    "better-world",
                    "/usr/bin/salt",
                    "100",
                ],
                python_shell=False,
            )

    with patch.dict(alternatives.__grains__, {"os_family": "Debian"}):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "salt"})
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.install(
                "better-world", "/usr/bin/better-world", "/usr/bin/salt", 100
            )
            assert "salt" == solution
            mock.assert_called_once_with(
                [
                    "update-alternatives",
                    "--install",
                    "/usr/bin/better-world",
                    "better-world",
                    "/usr/bin/salt",
                    "100",
                ],
                python_shell=False,
            )

    with patch.dict(alternatives.__grains__, {"os_family": "RedHat"}):
        mock = MagicMock(
            return_value={"retcode": 1, "stdout": "salt-out", "stderr": "salt-err"}
        )
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            ret = alternatives.install(
                "better-world", "/usr/bin/better-world", "/usr/bin/salt", 100
            )
            assert "salt-err" == ret
            mock.assert_called_once_with(
                [
                    "alternatives",
                    "--install",
                    "/usr/bin/better-world",
                    "better-world",
                    "/usr/bin/salt",
                    "100",
                ],
                python_shell=False,
            )


def test_remove():
    with patch.dict(alternatives.__grains__, {"os_family": "RedHat"}):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "salt"})
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.remove("better-world", "/usr/bin/better-world",)
            assert "salt" == solution
            mock.assert_called_once_with(
                ["alternatives", "--remove", "better-world", "/usr/bin/better-world"],
                python_shell=False,
            )

    with patch.dict(alternatives.__grains__, {"os_family": "Debian"}):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "salt"})
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.remove("better-world", "/usr/bin/better-world",)
            assert "salt" == solution
            mock.assert_called_once_with(
                [
                    "update-alternatives",
                    "--remove",
                    "better-world",
                    "/usr/bin/better-world",
                ],
                python_shell=False,
            )

    with patch.dict(alternatives.__grains__, {"os_family": "RedHat"}):
        mock = MagicMock(
            return_value={"retcode": 1, "stdout": "salt-out", "stderr": "salt-err"}
        )
        with patch.dict(alternatives.__salt__, {"cmd.run_all": mock}):
            solution = alternatives.remove("better-world", "/usr/bin/better-world",)
            assert "salt-err" == solution
            mock.assert_called_once_with(
                ["alternatives", "--remove", "better-world", "/usr/bin/better-world"],
                python_shell=False,
            )
