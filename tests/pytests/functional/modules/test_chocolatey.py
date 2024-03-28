import pytest

from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def chocolatey(modules):
    return modules.chocolatey


@pytest.fixture()
def clean(chocolatey):
    chocolatey.unbootstrap()
    try:
        chocolatey_version = chocolatey.chocolatey_version(refresh=True)
    except CommandExecutionError:
        chocolatey_version = None
    assert chocolatey_version is None
    try:
        yield
    finally:
        chocolatey.unbootstrap()


def test_bootstrap(chocolatey, clean):
    chocolatey.bootstrap()
    try:
        chocolatey_version = chocolatey.chocolatey_version(refresh=True)
    except CommandExecutionError:
        chocolatey_version = None
    assert chocolatey_version is not None


def test_bootstrap_version(chocolatey, clean):
    chocolatey.bootstrap(version="1.4.0")
    try:
        chocolatey_version = chocolatey.chocolatey_version(refresh=True)
    except CommandExecutionError:
        chocolatey_version = None
    assert chocolatey_version == "1.4.0"
