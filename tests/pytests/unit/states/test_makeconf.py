"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.makeconf as makeconf
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {makeconf: {}}


def test_present():
    """
    Test to verify that the variable is in the ``make.conf``
    and has the provided settings.
    """
    name = "makeopts"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock_t = MagicMock(return_value=True)
    with patch.dict(makeconf.__salt__, {"makeconf.get_var": mock_t}):
        comt = f"Variable {name} is already present in make.conf"
        ret.update({"comment": comt})
        assert makeconf.present(name) == ret


def test_absent():
    """
    Test to verify that the variable is not in the ``make.conf``.
    """
    name = "makeopts"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(return_value=None)
    with patch.dict(makeconf.__salt__, {"makeconf.get_var": mock}):
        comt = f"Variable {name} is already absent from make.conf"
        ret.update({"comment": comt})
        assert makeconf.absent(name) == ret
