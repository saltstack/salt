"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.process as process
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {process: {}}


def test_absent():
    """
    Test to ensures that the named command is not running.
    """
    name = "apache2"

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    mock = MagicMock(return_value="")
    with patch.dict(process.__salt__, {"ps.pgrep": mock, "ps.pkill": mock}):
        with patch.dict(process.__opts__, {"test": True}):
            comt = "No matching processes running"
            ret.update({"comment": comt})
            assert process.absent(name) == ret

        with patch.dict(process.__opts__, {"test": False}):
            ret.update({"result": True})
            assert process.absent(name) == ret
