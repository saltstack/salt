import pytest


@pytest.fixture(scope="module")
def states(loaders):
    return loaders.states
