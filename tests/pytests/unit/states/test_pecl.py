"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.pecl as pecl
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pecl: {}}


def test_installed():
    """
    Test to make sure that a pecl extension is installed.
    """
    name = "mongo"
    ver = "1.0.1"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    mock_lst = MagicMock(return_value={name: "stable"})
    mock_t = MagicMock(return_value=True)
    with patch.dict(pecl.__salt__, {"pecl.list": mock_lst, "pecl.install": mock_t}):
        comt = f"Pecl extension {name} is already installed."
        ret.update({"comment": comt, "result": True})
        assert pecl.installed(name) == ret

        with patch.dict(pecl.__opts__, {"test": True}):
            comt = "Pecl extension mongo-1.0.1 would have been installed"
            ret.update({"comment": comt, "result": None})
            assert pecl.installed(name, version=ver) == ret

        with patch.dict(pecl.__opts__, {"test": False}):
            comt = "Pecl extension mongo-1.0.1 was successfully installed"
            ret.update(
                {
                    "comment": comt,
                    "result": True,
                    "changes": {"mongo-1.0.1": "Installed"},
                }
            )
            assert pecl.installed(name, version=ver) == ret


def test_removed():
    """
    Test to make sure that a pecl extension is not installed.
    """
    name = "mongo"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    mock_lst = MagicMock(side_effect=[{}, {name: "stable"}, {name: "stable"}])
    mock_t = MagicMock(return_value=True)
    with patch.dict(pecl.__salt__, {"pecl.list": mock_lst, "pecl.uninstall": mock_t}):
        comt = f"Pecl extension {name} is not installed."
        ret.update({"comment": comt, "result": True})
        assert pecl.removed(name) == ret

        with patch.dict(pecl.__opts__, {"test": True}):
            comt = "Pecl extension mongo would have been removed"
            ret.update({"comment": comt, "result": None})
            assert pecl.removed(name) == ret

        with patch.dict(pecl.__opts__, {"test": False}):
            comt = "Pecl extension mongo was successfully removed."
            ret.update({"comment": comt, "result": True, "changes": {name: "Removed"}})
            assert pecl.removed(name) == ret
