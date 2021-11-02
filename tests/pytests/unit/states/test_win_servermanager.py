import pytest
import salt.states.win_servermanager as win_servermanager
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {win_servermanager: {}}


def test_installed():
    """
    Test to install the windows feature
    """
    mock_list = MagicMock(
        side_effect=[
            {"spongebob": "squarepants"},
            {"squidward": "patrick"},
            {"spongebob": "squarepants"},
            {"spongebob": "squarepants", "squidward": "patrick"},
        ]
    )
    mock_install = MagicMock(
        return_value={
            "Success": True,
            "Restarted": False,
            "RestartNeeded": False,
            "ExitCode": 1234,
            "Features": {
                "squidward": {
                    "DisplayName": "Squidward",
                    "Message": "",
                    "RestartNeeded": True,
                    "SkipReason": 0,
                    "Success": True,
                }
            },
        }
    )
    with patch.dict(
        win_servermanager.__salt__,
        {
            "win_servermanager.list_installed": mock_list,
            "win_servermanager.install": mock_install,
        },
    ):
        ret = {
            "name": "spongebob",
            "changes": {},
            "result": True,
            "comment": "The following features are already installed:\n- spongebob",
        }
        assert win_servermanager.installed("spongebob") == ret

        with patch.dict(win_servermanager.__opts__, {"test": True}):
            ret = {
                "name": "spongebob",
                "result": None,
                "comment": "",
                "changes": {"spongebob": "Will be installed recurse=False"},
            }
            assert win_servermanager.installed("spongebob") == ret

        with patch.dict(win_servermanager.__opts__, {"test": False}):
            ret = {
                "name": "squidward",
                "result": True,
                "comment": "Installed the following:\n- squidward",
                "changes": {"squidward": {"new": "patrick", "old": ""}},
            }
            assert win_servermanager.installed("squidward") == ret


def test_removed():
    """
    Test to remove the windows feature
    """
    mock_list = MagicMock(
        side_effect=[
            {"spongebob": "squarepants"},
            {"squidward": "patrick"},
            {"spongebob": "squarepants", "squidward": "patrick"},
            {"spongebob": "squarepants"},
        ]
    )
    mock_remove = MagicMock(
        return_value={
            "Success": True,
            "RestartNeeded": False,
            "Restarted": False,
            "ExitCode": 1234,
            "Features": {
                "squidward": {
                    "DisplayName": "Squidward",
                    "Message": "",
                    "RestartNeeded": True,
                    "SkipReason": 0,
                    "Success": True,
                }
            },
        }
    )
    with patch.dict(
        win_servermanager.__salt__,
        {
            "win_servermanager.list_installed": mock_list,
            "win_servermanager.remove": mock_remove,
        },
    ):
        ret = {
            "name": "squidward",
            "changes": {},
            "result": True,
            "comment": "The following features are not installed:\n- squidward",
        }
        assert win_servermanager.removed("squidward") == ret

        with patch.dict(win_servermanager.__opts__, {"test": True}):
            ret = {
                "name": "squidward",
                "result": None,
                "comment": "",
                "changes": {"squidward": "Will be removed"},
            }
            assert win_servermanager.removed("squidward") == ret

        with patch.dict(win_servermanager.__opts__, {"test": False}):
            ret = {
                "name": "squidward",
                "result": True,
                "comment": "Removed the following:\n- squidward",
                "changes": {"squidward": {"new": "", "old": "patrick"}},
            }
            assert win_servermanager.removed("squidward") == ret
