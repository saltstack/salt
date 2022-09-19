import pytest

import salt.modules.saltcheck as saltcheck
from tests.support.mock import MagicMock


@pytest.fixture()
def configure_loader_modules():
    return {saltcheck: {"__salt__": {"state.show_top": MagicMock()}}}


@pytest.mark.parametrize("saltenv", ["base", "dev", "howdy"])
def test__get_top_states_call_args(saltenv):
    saltcheck._get_top_states(saltenv=saltenv)
    saltcheck.__salt__["state.show_top"].assert_called_with(saltenv=saltenv)
