"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.openstack_config as openstack_config
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {openstack_config: {"__opts__": {"test": False}}}


def test_present():
    """
    Test to ensure a value is set in an OpenStack configuration file.
    """
    name = "salt"
    filename = "/tmp/salt"
    section = "A"
    value = "SALT"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock_lst = MagicMock(side_effect=[value, CommandExecutionError, "A"])
    mock_t = MagicMock(return_value=True)
    with patch.dict(
        openstack_config.__salt__,
        {"openstack_config.get": mock_lst, "openstack_config.set": mock_t},
    ):
        comt = "The value is already set to the correct value"
        ret.update({"comment": comt, "result": True})
        assert openstack_config.present(name, filename, section, value) == ret

        pytest.raises(
            CommandExecutionError,
            openstack_config.present,
            name,
            filename,
            section,
            value,
        )

        comt = "The value has been updated"
        ret.update({"comment": comt, "changes": {"Value": "Updated"}})
        assert openstack_config.present(name, filename, section, value) == ret


def test_absent():
    """
    Test to ensure a value is not set in an OpenStack configuration file.
    """
    name = "salt"
    filename = "/tmp/salt"
    section = "A"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock_lst = MagicMock(
        side_effect=[
            CommandExecutionError("parameter not found:"),
            CommandExecutionError,
            "A",
        ]
    )
    mock_t = MagicMock(return_value=True)
    with patch.dict(
        openstack_config.__salt__,
        {"openstack_config.get": mock_lst, "openstack_config.delete": mock_t},
    ):
        comt = "The value is already absent"
        ret.update({"comment": comt, "result": True})
        assert openstack_config.absent(name, filename, section) == ret

        pytest.raises(
            CommandExecutionError, openstack_config.absent, name, filename, section
        )

        comt = "The value has been deleted"
        ret.update({"comment": comt, "changes": {"Value": "Deleted"}})
        assert openstack_config.absent(name, filename, section) == ret
