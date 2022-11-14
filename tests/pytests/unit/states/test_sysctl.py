"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.sysctl as sysctl
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {sysctl: {}}


def test_empty_config_file_and_value_not_found():
    """
    Test sysctl.present for an unknown sysctl, not present in config file
    """
    name = "some.unknown.oid"
    value = "1"
    comment = "Sysctl option {} would be changed to {}".format(name, value)

    ret = {"name": name, "result": None, "changes": {}, "comment": comment}

    with patch.dict(sysctl.__opts__, {"test": True}):
        mock_show = MagicMock(return_value={})
        with patch.dict(sysctl.__salt__, {"sysctl.show": mock_show}):
            mock_get = MagicMock(return_value="")
            with patch.dict(sysctl.__salt__, {"sysctl.get": mock_get}):
                assert sysctl.present(name, value) == ret


def test_inaccessible_config_file():
    """
    Test sysctl.present with a config file that cannot be opened
    """
    name = "some.unknown.oid"
    value = "1"
    config = "/etc/sysctl.conf"
    comment = (
        "Sysctl option {} might be changed, we failed to check "
        "config file at {}. The file is either unreadable, or "
        "missing.".format(name, config)
    )
    ret = {"name": name, "result": None, "changes": {}, "comment": comment}

    with patch.dict(sysctl.__opts__, {"test": True}):
        mock = MagicMock(return_value=None)
        with patch.dict(sysctl.__salt__, {"sysctl.show": mock}):
            assert sysctl.present(name, value) == ret


def test_to_be_changed_not_configured():
    """
    Test sysctl.present for a sysctl that isn't in the config file and must
    be changed.
    """
    name = "vfs.usermount"
    value = "1"
    comment = "Sysctl option {} set to be changed to {}".format(name, value)
    ret = {"name": name, "result": None, "changes": {}, "comment": comment}

    def mock_current(config_file=None):
        """
        Mock return value for __salt__.
        """
        if config_file is None:
            return {name: "0"}
        return {}

    with patch.dict(sysctl.__opts__, {"test": True}):
        with patch.dict(sysctl.__salt__, {"sysctl.show": mock_current}):
            mock_get = MagicMock(return_value="0")
            with patch.dict(sysctl.__salt__, {"sysctl.get": mock_get}):
                assert sysctl.present(name, value) == ret


def test_not_to_be_changed_not_configured():
    """
    Test sysctl.present for a sysctl that isn't in the config file but
    already has the correct value
    """
    name = "some.unknown.oid"
    value = "1"
    comment = (
        "Sysctl value is currently set on the running system but "
        "not in a config file. Sysctl option {} set to be "
        "changed to 1 in config file.".format(name)
    )

    ret = {"name": name, "result": None, "changes": {}, "comment": comment}

    def mock_current(config_file=None):
        if config_file is None:
            return {name: value}
        return {}

    with patch.dict(sysctl.__opts__, {"test": True}):
        with patch.dict(sysctl.__salt__, {"sysctl.show": mock_current}):
            mock_get = MagicMock(return_value=value)
            with patch.dict(sysctl.__salt__, {"sysctl.get": mock_get}):
                assert sysctl.present(name, value) == ret


def test_configured_but_unknown():
    """
    Test sysctl.present for a sysctl that is already configured but is
    not known by the system.  For example, a sysctl used by a kernel module
    that isn't loaded.
    """
    name = "vfs.usermount"
    value = "1"
    comment = (
        "Sysctl value {0} is present in configuration file but is not "
        "present in the running config. The value {0} is set to be "
        "changed to {1}".format(name, value)
    )
    ret = {"name": name, "result": None, "changes": {}, "comment": comment}

    def mock_config(config_file=None):
        if config_file is None:
            return {}
        return {name: value}

    with patch.dict(sysctl.__opts__, {"test": True}):
        with patch.dict(sysctl.__salt__, {"sysctl.show": mock_config}):
            mock_get = MagicMock(return_value="")
            with patch.dict(sysctl.__salt__, {"sysctl.get": mock_get}):
                assert sysctl.present(name, value) == ret


def test_no_change():
    """
    Test sysctl.present for an already-configured value
    """
    name = "vfs.usermount"
    value = "1"
    comment = "Sysctl value {} = {} is already set".format(name, value)
    ret = {"name": name, "result": True, "changes": {}, "comment": comment}

    def mock_config(config_file=None):
        if config_file is None:
            return {}
        return {name: value}

    with patch.dict(sysctl.__opts__, {"test": True}):
        with patch.dict(sysctl.__salt__, {"sysctl.show": mock_config}):
            mock_get = MagicMock(return_value=value)
            with patch.dict(sysctl.__salt__, {"sysctl.get": mock_get}):
                assert sysctl.present(name, value) == ret


def test_change():
    """
    Test sysctl.present for a value whose configuration must change
    """
    name = "vfs.usermount"
    old_value = "2"
    value = "1"
    comment = "Sysctl option {} would be changed to {}".format(name, value)
    ret = {"name": name, "result": None, "changes": {}, "comment": comment}

    def mock_config(config_file=None):
        if config_file is None:
            return {name: old_value}
        return {name: old_value}

    with patch.dict(sysctl.__opts__, {"test": True}):
        with patch.dict(sysctl.__salt__, {"sysctl.show": mock_config}):
            mock_get = MagicMock(return_value=old_value)
            with patch.dict(sysctl.__salt__, {"sysctl.get": mock_get}):
                assert sysctl.present(name, value) == ret


def test_failed_to_set():
    """
    Test sysctl.present when the sysctl command fails to change a value
    """
    name = "net.isr.maxthreads"
    value = "8"
    comment = "Failed to set {} to {}: ".format(name, value)
    ret = {"name": name, "result": False, "changes": {}, "comment": comment}

    with patch.dict(sysctl.__opts__, {"test": False}):
        mock = MagicMock(side_effect=CommandExecutionError)
        with patch.dict(sysctl.__salt__, {"sysctl.persist": mock}):
            assert sysctl.present(name, value) == ret


def test_already_set():
    """
    Test sysctl.present when the value is already set
    """
    name = "vfs.usermount"
    value = "1"
    comment = "Sysctl value {} = {} is already set".format(name, value)
    ret = {"name": name, "result": True, "changes": {}, "comment": comment}
    with patch.dict(sysctl.__opts__, {"test": False}):
        mock = MagicMock(return_value="Already set")
        with patch.dict(sysctl.__salt__, {"sysctl.persist": mock}):
            assert sysctl.present(name, value) == ret


def test_updated():
    """
    Test sysctl.present when the value is not already set
    """
    name = "vfs.usermount"
    value = "1"
    comment = "Updated sysctl value {} = {}".format(name, value)
    changes = {name: value}
    ret = {"name": name, "result": True, "changes": changes, "comment": comment}
    with patch.dict(sysctl.__opts__, {"test": False}):
        mock = MagicMock(return_value="Updated")
        with patch.dict(sysctl.__salt__, {"sysctl.persist": mock}):
            assert sysctl.present(name, value) == ret
