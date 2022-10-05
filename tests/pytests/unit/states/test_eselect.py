"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
import pytest

import salt.states.eselect as eselect
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {eselect: {}}


def test_set_():
    """
    Test to verify that the given module is set to the given target
    """
    name = "myeselect"
    target = "hardened/linux/amd64"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(return_value=target)
    with patch.dict(eselect.__salt__, {"eselect.get_current_target": mock}):
        comt = "Target '{}' is already set on '{}' module.".format(target, name)
        ret.update({"comment": comt})
        assert eselect.set_(name, target) == ret
