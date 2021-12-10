import pytest
import salt.roster.ansible as ansible
from tests.support.mock import patch


@pytest.mark.parametrize(
    "which_value",
    [False, None],
)
def test_virtual_returns_False_if_ansible_inventory_doesnt_exist(which_value):
    with patch("salt.utils.path.which", autospec=True, return_value=which_value):
        assert ansible.__virtual__() == (False, "Install `ansible` to use inventory")
