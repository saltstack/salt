import pytest

from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
    pytest.mark.skipif(
        True,
        reason="CI/CD making too many requests to chocolatey and we're getting blocked",
    ),
]


@pytest.fixture(scope="module")
def chocolatey(modules):
    return modules.chocolatey


@pytest.fixture()
def clean(chocolatey):
    result = chocolatey.unbootstrap()

    # Try to get the new version, should throw an error
    try:
        chocolatey_version = chocolatey.chocolatey_version(refresh=True)
    except CommandExecutionError:
        chocolatey_version = None

    # Assert the chocolatey is not installed
    assert chocolatey_version is None
    try:
        # We're yielding "result" here so we can see any problems with
        # unbootstrap if the test fails
        yield result
    finally:
        try:
            # If chocolatey is not installed, this will throw an error
            chocolatey.chocolatey_version(refresh=True)
            # If we get this far, chocolatey is installed... let's uninstall
            chocolatey.unbootstrap()
        except CommandExecutionError:
            pass


def test_bootstrap(chocolatey, clean):
    # We're defining "result" here to see the output of the bootstrap function
    # if the test fails
    result = chocolatey.bootstrap()
    # Let's run it outside the try/except to see what the error is
    chocolatey_version = chocolatey.chocolatey_version(refresh=True)
    # try:
    #     chocolatey_version = chocolatey.chocolatey_version(refresh=True)
    # except CommandExecutionError:
    #     chocolatey_version = None
    assert chocolatey_version is not None


def test_bootstrap_version(chocolatey, clean):
    chocolatey.bootstrap(version="1.4.0")
    chocolatey_version = chocolatey.chocolatey_version(refresh=True)
    # try:
    #     chocolatey_version = chocolatey.chocolatey_version(refresh=True)
    # except CommandExecutionError:
    #     chocolatey_version = None
    assert chocolatey_version == "1.4.0"
