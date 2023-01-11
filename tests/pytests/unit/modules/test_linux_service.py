"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.linux_service
"""

import os

import pytest

import salt.modules.linux_service as service
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {service: {}}


def test_start():
    """
    Test to start the specified service
    """
    with patch.object(os.path, "join", return_value="A"):
        with patch.object(service, "run", MagicMock(return_value=True)):
            assert service.start("name")


def test_stop():
    """
    Test to stop the specified service
    """
    with patch.object(os.path, "join", return_value="A"):
        with patch.object(service, "run", MagicMock(return_value=True)):
            assert service.stop("name")


def test_restart():
    """
    Test to restart the specified service
    """
    with patch.object(os.path, "join", return_value="A"):
        with patch.object(service, "run", MagicMock(return_value=True)):
            assert service.restart("name")


def test_status():
    """
    Test to return the status for a service, returns the PID or an empty
    string if the service is running or not, pass a signature to use to
    find the service via ps
    """
    with patch.dict(service.__salt__, {"status.pid": MagicMock(return_value=True)}):
        assert service.status("name")


def test_reload_():
    """
    Test to restart the specified service
    """
    with patch.object(os.path, "join", return_value="A"):
        with patch.object(service, "run", MagicMock(return_value=True)):
            assert service.reload_("name")


def test_run():
    """
    Test to run the specified service
    """
    with patch.object(os.path, "join", return_value="A"):
        with patch.object(service, "run", MagicMock(return_value=True)):
            assert service.run("name", "action")


def test_available():
    """
    Test to returns ``True`` if the specified service is available,
    otherwise returns ``False``.
    """
    with patch.object(service, "get_all", return_value=["name", "A"]):
        assert service.available("name")


def test_missing():
    """
    Test to inverse of service.available.
    """
    with patch.object(service, "get_all", return_value=["name1", "A"]):
        assert service.missing("name")


def test_get_all():
    """
    Test to return a list of all available services
    """
    with patch.object(os.path, "isdir", side_effect=[False, True]):

        assert service.get_all() == []

        with patch.object(os, "listdir", return_value=["A", "B"]):
            assert service.get_all() == ["A", "B"]
