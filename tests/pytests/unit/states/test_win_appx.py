import pytest

import salt.states.win_appx as win_appx
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    return {win_appx: {}}


def test_absent_missing():
    expected = {
        "comment": "No apps found matching query: *candy*",
        "changes": {},
        "name": "remove_candy",
        "result": True,
    }
    mock_list = MagicMock(return_value=["package1", "package2"])
    with patch.dict(win_appx.__salt__, {"appx.list": mock_list}):
        result = win_appx.absent("remove_candy", "*candy*")
        assert result == expected


def test_absent_test_true():
    expected = {
        "comment": "The following apps will be removed:\n- king.com.CandyCrush",
        "changes": {},
        "name": "remove_candy",
        "result": None,
    }
    mock_list = MagicMock(return_value=["package1", "king.com.CandyCrush"])
    with patch.dict(win_appx.__salt__, {"appx.list": mock_list}):
        with patch.dict(win_appx.__opts__, {"test": True}):
            result = win_appx.absent("remove_candy", "*candy*")
            assert result == expected


def test_absent_missing_after_test():
    expected = {
        "comment": "No apps found matching query: *candy*",
        "changes": {},
        "name": "remove_candy",
        "result": False,
    }
    mock_list = MagicMock(return_value=["package1", "king.com.CandyCrush"])
    with patch.dict(
        win_appx.__salt__,
        {
            "appx.list": mock_list,
            "appx.remove": MagicMock(return_value=None),
        },
    ):
        with patch.dict(win_appx.__opts__, {"test": False}):
            result = win_appx.absent("remove_candy", "*candy*")
            assert result == expected


def test_absent():
    expected = {
        "comment": "Removed apps matching query: *candy*",
        "changes": {"old": ["king.com.CandyCrush"]},
        "name": "remove_candy",
        "result": True,
    }
    mock_list = MagicMock(
        side_effect=(
            ["package1", "king.com.CandyCrush"],
            ["package1"],
        ),
    )
    with patch.dict(
        win_appx.__salt__,
        {
            "appx.list": mock_list,
            "appx.remove": MagicMock(return_value=True),
        },
    ):
        with patch.dict(win_appx.__opts__, {"test": False}):
            result = win_appx.absent("remove_candy", "*candy*")
            assert result == expected
