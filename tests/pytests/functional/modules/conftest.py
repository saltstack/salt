import pytest


@pytest.fixture(scope="module")
def modules(loaders):
    return loaders.modules


@pytest.fixture(scope="module")
def states(loaders):
    return loaders.states
