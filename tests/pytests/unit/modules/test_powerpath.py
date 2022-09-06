"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.powerpath as powerpath
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {powerpath: {}}


def test_has_powerpath():
    """
    Test for powerpath
    """
    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = True
        assert powerpath.has_powerpath()

        mock_exists.return_value = False
        assert not powerpath.has_powerpath()


def test_list_licenses():
    """
    Test to returns a list of applied powerpath license keys
    """
    with patch.dict(powerpath.__salt__, {"cmd.run": MagicMock(return_value="A\nB")}):
        assert powerpath.list_licenses() == []


def test_add_license():
    """
    Test to add a license
    """
    with patch.object(powerpath, "has_powerpath", return_value=False):
        assert powerpath.add_license("key") == {
            "output": "PowerPath is not installed",
            "result": False,
            "retcode": -1,
        }

    mock = MagicMock(return_value={"retcode": 1, "stderr": "stderr"})
    with patch.object(powerpath, "has_powerpath", return_value=True):
        with patch.dict(powerpath.__salt__, {"cmd.run_all": mock}):
            assert powerpath.add_license("key") == {
                "output": "stderr",
                "result": False,
                "retcode": 1,
            }


def test_remove_license():
    """
    Test to remove a license
    """
    with patch.object(powerpath, "has_powerpath", return_value=False):
        assert powerpath.remove_license("key") == {
            "output": "PowerPath is not installed",
            "result": False,
            "retcode": -1,
        }

    mock = MagicMock(return_value={"retcode": 1, "stderr": "stderr"})
    with patch.object(powerpath, "has_powerpath", return_value=True):
        with patch.dict(powerpath.__salt__, {"cmd.run_all": mock}):
            assert powerpath.remove_license("key") == {
                "output": "stderr",
                "result": False,
                "retcode": 1,
            }
