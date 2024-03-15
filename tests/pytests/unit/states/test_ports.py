"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import os

import pytest

import salt.states.ports as ports
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, patch


class MockModule:
    __module__ = "A"


class MockContext:
    __context__ = {"ports.install_error": "salt"}


class MockSys:
    def __init__(self):
        self.modules = {"A": MockContext()}


@pytest.fixture
def configure_loader_modules():
    return {ports: {"sys": MockSys()}}


def test_installed():
    """
    Test to verify that the desired port is installed,
    and that it was compiled with the desired options.
    """
    name = "security/nmap"
    options = [{"IPV6": "on"}]

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=SaltInvocationError)
    with patch.dict(ports.__salt__, {"ports.showconfig": mock}):
        comt = (
            "Unable to get configuration for {}. Port name may "
            "be invalid, or ports tree may need to be updated. "
            "Error message: ".format(name)
        )
        ret.update({"comment": comt, "result": False})
        assert ports.installed(name) == ret

    mock = MagicMock(return_value={})
    mock_lst = MagicMock(return_value={"origin": {"origin": name}})
    with patch.dict(
        ports.__salt__, {"ports.showconfig": mock, "pkg.list_pkgs": mock_lst}
    ):
        comt = "security/nmap is already installed"
        ret.update({"comment": comt, "result": True})
        assert ports.installed(name) == ret

        comt = (
            "security/nmap does not have any build options, yet options were specified"
        )
        ret.update({"comment": comt, "result": False})
        assert ports.installed(name, options) == ret

        mock_dict = MagicMock(return_value={"origin": {"origin": "salt"}})
        with patch.dict(ports.__salt__, {"pkg.list_pkgs": mock_dict}):
            with patch.dict(ports.__opts__, {"test": True}):
                comt = f"{name} will be installed"
                ret.update({"comment": comt, "result": None})
                assert ports.installed(name) == ret

    mock = MagicMock(return_value={"salt": {"salt": "salt"}})
    mock_dict = MagicMock(return_value={"origin": {"origin": "salt"}})
    mock_f = MagicMock(return_value=False)
    mock_t = MagicMock(return_value=True)
    with patch.dict(
        ports.__salt__,
        {
            "ports.showconfig": mock,
            "pkg.list_pkgs": mock_dict,
            "ports.config": mock_f,
            "ports.rmconfig": mock_t,
        },
    ):
        with patch.dict(ports.__opts__, {"test": True}):
            comt = "The following options are not available for security/nmap: IPV6"
            ret.update({"comment": comt, "result": False})
            assert ports.installed(name, options) == ret

            comt = "security/nmap will be installed with the default build options"
            ret.update({"comment": comt, "result": None})
            assert ports.installed(name) == ret

        with patch.dict(ports.__opts__, {"test": False}):
            comt = "Unable to set options for security/nmap"
            ret.update({"comment": comt, "result": False})
            assert ports.installed(name, [{"salt": "salt"}]) == ret

            with patch.object(os.path, "isfile", mock_t):
                with patch.object(os.path, "isdir", mock_t):
                    comt = "Unable to clear options for security/nmap"
                    ret.update({"comment": comt, "result": False})
                    assert ports.installed(name) == ret

            with patch.dict(
                ports.__salt__,
                {
                    "ports.config": mock_t,
                    "ports.install": mock_t,
                    "test.ping": MockModule(),
                },
            ):
                comt = "Failed to install security/nmap. Error message:\nsalt"
                ret.update({"comment": comt, "result": False, "changes": True})
                assert ports.installed(name, [{"salt": "salt"}]) == ret
