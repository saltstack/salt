import os

import pytest


@pytest.fixture(scope="package", autouse=True)
def _onedir_env():
    """
    Functional tests cannot currently test the
    onedir artifact. This will need to be removed
    when we do add onedir support for functional tests.
    This is specifically needed for testing the new
    package grain when calling from the grains module.
    """
    if os.environ.get("ONEDIR_TESTRUN", "0") == "1":
        try:
            os.environ["ONEDIR_TESTRUN"] = "0"
            yield
        finally:
            os.environ["ONEDIR_TESTRUN"] = "1"
    else:
        yield


@pytest.fixture(scope="module")
def modules(loaders):
    return loaders.modules


@pytest.fixture(scope="module")
def states(loaders):
    return loaders.states
