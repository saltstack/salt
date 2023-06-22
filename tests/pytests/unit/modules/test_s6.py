"""
    :codeauthor: Marek Skrobacki <skrobul@skrobul.com>

    Test cases for salt.modules.s6
"""


import os

import pytest

import salt.modules.s6 as s6
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {s6: {"SERVICE_DIR": "/etc/service"}}


# 'start' function tests: 1


def test_start():
    """
    Test if it starts service via s6-svc.
    """
    mock_ret = MagicMock(return_value=False)
    with patch.dict(s6.__salt__, {"cmd.retcode": mock_ret}):
        assert s6.start("ssh")


# 'stop' function tests: 1


def test_stop():
    """
    Test if it stops service via s6.
    """
    mock_ret = MagicMock(return_value=False)
    with patch.dict(s6.__salt__, {"cmd.retcode": mock_ret}):
        assert s6.stop("ssh")


# 'term' function tests: 1


def test_term():
    """
    Test if it send a TERM to service via s6.
    """
    mock_ret = MagicMock(return_value=False)
    with patch.dict(s6.__salt__, {"cmd.retcode": mock_ret}):
        assert s6.term("ssh")


# 'reload_' function tests: 1


def test_reload():
    """
    Test if it send a HUP to service via s6.
    """
    mock_ret = MagicMock(return_value=False)
    with patch.dict(s6.__salt__, {"cmd.retcode": mock_ret}):
        assert s6.reload_("ssh")


# 'restart' function tests: 1


def test_restart():
    """
    Test if it restart service via s6. This will stop/start service.
    """
    mock_ret = MagicMock(return_value=False)
    with patch.dict(s6.__salt__, {"cmd.retcode": mock_ret}):
        assert s6.restart("ssh")


# 'full_restart' function tests: 1


def test_full_restart():
    """
    Test if it calls s6.restart() function.
    """
    mock_ret = MagicMock(return_value=False)
    with patch.dict(s6.__salt__, {"cmd.retcode": mock_ret}):
        assert s6.full_restart("ssh") is None


# 'status' function tests: 1


def test_status():
    """
    Test if it return the status for a service via s6,
    return pid if running.
    """
    mock_run = MagicMock(return_value="salt")
    with patch.dict(s6.__salt__, {"cmd.run_stdout": mock_run}):
        assert s6.status("ssh") == ""


# 'available' function tests: 1


def test_available():
    """
    Test if it returns ``True`` if the specified service is available,
    otherwise returns ``False``.
    """
    with patch.object(os, "listdir", MagicMock(return_value=["/etc/service"])):
        assert s6.available("/etc/service")


# 'missing' function tests: 1


def test_missing():
    """
    Test if it returns ``True`` if the specified service is not available,
    otherwise returns ``False``.
    """
    with patch.object(os, "listdir", MagicMock(return_value=["/etc/service"])):
        assert s6.missing("foo")


# 'get_all' function tests: 1


def test_get_all():
    """
    Test if it return a list of all available services.
    """
    with patch.object(os, "listdir", MagicMock(return_value=["/etc/service"])):
        assert s6.get_all() == ["/etc/service"]
