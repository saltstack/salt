"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.introspect
"""


import pytest

import salt.modules.introspect as introspect
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {introspect: {}}


# 'running_service_owners' function tests: 1


def test_running_service_owners():
    """
    Test if it determine which packages own the currently running services.
    """
    err1 = (
        "The module for the package manager on this system does not"
        " support looking up which package(s) owns which file(s)"
    )
    err2 = (
        "The file module on this system does not "
        "support looking up open files on the system"
    )
    ret = {
        "Error": {
            "Unsupported File Module": "{}".format(err2),
            "Unsupported Package Manager": "{}".format(err1),
        }
    }
    assert introspect.running_service_owners() == ret

    mock = MagicMock(return_value={})
    with patch.dict(
        introspect.__salt__,
        {"pkg.owner": mock, "file.open_files": mock, "service.execs": mock},
    ):
        assert introspect.running_service_owners() == {}


# 'enabled_service_owners' function tests: 1


def test_enabled_service_owners():
    """
    Test if it return which packages own each of the services
    that are currently enabled.
    """
    err1 = (
        "The module for the package manager on this system does not"
        " support looking up which package(s) owns which file(s)"
    )
    err2 = (
        "The module for the service manager on this system does not"
        " support showing descriptive service data"
    )
    ret = {
        "Error": {
            "Unsupported Service Manager": "{}".format(err2),
            "Unsupported Package Manager": "{}".format(err1),
        }
    }
    assert introspect.enabled_service_owners() == ret

    mock = MagicMock(return_value={})
    with patch.dict(
        introspect.__salt__,
        {"pkg.owner": mock, "service.show": mock, "service.get_enabled": mock},
    ):
        assert introspect.enabled_service_owners() == {}


# 'service_highstate' function tests: 1


def test_service_highstate():
    """
    Test if it return running and enabled services in a highstate structure.
    """
    with patch(
        "salt.modules.introspect.running_service_owners", MagicMock(return_value={})
    ), patch(
        "salt.modules.introspect.enabled_service_owners", MagicMock(return_value={})
    ):
        assert introspect.service_highstate() == {}
