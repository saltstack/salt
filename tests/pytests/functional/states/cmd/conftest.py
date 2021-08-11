import pytest


@pytest.fixture
def cmd(states):
    return states.cmd
