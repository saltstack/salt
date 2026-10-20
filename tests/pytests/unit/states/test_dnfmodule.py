import pytest

import salt.states.dnfmodule as dnfmodule
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_unless_on_linux,
]


@pytest.fixture
def configure_loader_modules():
    return {dnfmodule: {"__opts__": {"test": False}}}


def test_enabled_already_enabled():
    salt_mock = {"dnfmodule.is_enabled": MagicMock(return_value=True)}
    with patch.dict(dnfmodule.__salt__, salt_mock):
        ret = dnfmodule.enabled("nodejs:18")
    assert ret["result"] is True
    assert ret["changes"] == {}
    assert "already enabled" in ret["comment"]


def test_enabled_test_mode():
    salt_mock = {
        "dnfmodule.is_enabled": MagicMock(return_value=False),
        "dnfmodule.enabled_stream": MagicMock(return_value=None),
    }
    with patch.dict(dnfmodule.__salt__, salt_mock), patch.dict(
        dnfmodule.__opts__, {"test": True}
    ):
        ret = dnfmodule.enabled("nodejs:18")
    assert ret["result"] is None
    assert ret["changes"] == {"enabled": "nodejs:18"}


def test_enabled_conflict_without_switch_fails():
    salt_mock = {
        "dnfmodule.is_enabled": MagicMock(return_value=False),
        "dnfmodule.enabled_stream": MagicMock(return_value="3.0"),
    }
    with patch.dict(dnfmodule.__salt__, salt_mock):
        ret = dnfmodule.enabled("swig:4.0")
    assert ret["result"] is False
    assert ret["changes"] == {}
    assert "already has stream '3.0' enabled" in ret["comment"]


def test_enabled_switch_test_mode():
    salt_mock = {
        "dnfmodule.is_enabled": MagicMock(return_value=False),
        "dnfmodule.enabled_stream": MagicMock(return_value="3.0"),
    }
    with patch.dict(dnfmodule.__salt__, salt_mock), patch.dict(
        dnfmodule.__opts__, {"test": True}
    ):
        ret = dnfmodule.enabled("swig:4.0", switch=True)
    assert ret["result"] is None
    assert ret["changes"] == {"swig": {"old": "3.0", "new": "4.0"}}


def test_enabled_switch_delegates_to_enable():
    enable = MagicMock(return_value=True)
    salt_mock = {
        "dnfmodule.is_enabled": MagicMock(return_value=False),
        "dnfmodule.enabled_stream": MagicMock(return_value="3.0"),
        "dnfmodule.enable": enable,
    }
    with patch.dict(dnfmodule.__salt__, salt_mock):
        ret = dnfmodule.enabled("swig:4.0", switch=True)
    enable.assert_called_once_with("swig:4.0", switch=True)
    assert ret["result"] is True
    assert ret["changes"] == {"swig": {"old": "3.0", "new": "4.0"}}


def test_enabled_applies_change_no_conflict():
    enable = MagicMock(return_value=True)
    salt_mock = {
        "dnfmodule.is_enabled": MagicMock(return_value=False),
        "dnfmodule.enabled_stream": MagicMock(return_value=None),
        "dnfmodule.enable": enable,
    }
    with patch.dict(dnfmodule.__salt__, salt_mock):
        ret = dnfmodule.enabled("nodejs:18")
    enable.assert_called_once_with("nodejs:18")
    assert ret["changes"] == {"enabled": "nodejs:18"}


def test_disabled_applies_change():
    disable = MagicMock(return_value=True)
    salt_mock = {
        "dnfmodule.is_disabled": MagicMock(return_value=False),
        "dnfmodule.disable": disable,
    }
    with patch.dict(dnfmodule.__salt__, salt_mock):
        ret = dnfmodule.disabled("nodejs")
    disable.assert_called_once_with("nodejs")
    assert ret["changes"] == {"disabled": "nodejs"}


def test_installed_already_installed():
    salt_mock = {"dnfmodule.is_installed": MagicMock(return_value=True)}
    with patch.dict(dnfmodule.__salt__, salt_mock):
        ret = dnfmodule.installed("nodejs:18/common")
    assert ret["changes"] == {}
    assert "already installed" in ret["comment"]


def test_installed_applies_change():
    install = MagicMock(return_value=True)
    salt_mock = {
        "dnfmodule.is_installed": MagicMock(return_value=False),
        "dnfmodule.install": install,
    }
    with patch.dict(dnfmodule.__salt__, salt_mock):
        ret = dnfmodule.installed("nodejs:18/common")
    install.assert_called_once_with("nodejs:18/common")
    assert ret["changes"] == {"installed": "nodejs:18/common"}


def test_removed_when_not_installed():
    salt_mock = {"dnfmodule.is_installed": MagicMock(return_value=False)}
    with patch.dict(dnfmodule.__salt__, salt_mock):
        ret = dnfmodule.removed("nodejs:18/common")
    assert ret["changes"] == {}
    assert ret["result"] is True


def test_removed_applies_change():
    remove = MagicMock(return_value=True)
    salt_mock = {
        "dnfmodule.is_installed": MagicMock(return_value=True),
        "dnfmodule.remove": remove,
    }
    with patch.dict(dnfmodule.__salt__, salt_mock):
        ret = dnfmodule.removed("nodejs:18/common")
    remove.assert_called_once_with("nodejs:18/common")
    assert ret["changes"] == {"removed": "nodejs:18/common"}
