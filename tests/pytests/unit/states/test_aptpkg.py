"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.aptpkg as aptpkg
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {aptpkg: {}}


def test_held():
    """
    Test to set package in 'hold' state, meaning it will not be upgraded.
    """
    name = "tmux"

    ret = {
        "name": name,
        "result": False,
        "changes": {},
        "comment": f"Package {name} does not have a state",
    }

    mock = MagicMock(return_value=False)
    with patch.dict(aptpkg.__salt__, {"pkg.get_selections": mock}):
        assert aptpkg.held(name) == ret
