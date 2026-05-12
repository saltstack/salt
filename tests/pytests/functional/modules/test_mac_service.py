"""
integration tests for mac_service
"""

import plistlib

import pytest

import salt.utils.files
from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("launchctl", "plutil"),
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="module")
def service(modules):
    return modules.service


@pytest.fixture(scope="function", autouse=True)
def service_name(service):

    service_name = "com.salt.integration.test"
    service_path = "/Library/LaunchDaemons/com.salt.integration.test.plist"

    service_data = {
        "KeepAlive": True,
        "Label": service_name,
        "ProgramArguments": ["/bin/sleep", "1000"],
        "RunAtLoad": True,
    }
    with salt.utils.files.fopen(service_path, "wb") as fp:
        plistlib.dump(service_data, fp)
    service.enable(service_name)
    service.start(service_name)

    try:
        yield service_name
    finally:
        # Try to stop the service if it's running
        try:
            service.stop(service_name)
        except CommandExecutionError:
            pass
        salt.utils.files.safe_rm(service_path)


def test_show(service, service_name):
    """
    Test service.show
    """
    # Existing Service
    service_info = service.show(service_name)
    assert isinstance(service_info, dict)
    assert service_info["plist"]["Label"] == service_name

    # Missing Service
    with pytest.raises(CommandExecutionError) as exc:
        ret = service.show("spongebob")
        assert "Service not found" in str(exc.value)


def test_launchctl(service, service_name):
    """
    Test service.launchctl
    """
    # Expected Functionality
    ret = service.launchctl("error", "bootstrap", 64)
    assert ret

    ret = service.launchctl("error", "bootstrap", 64, return_stdout=True)
    assert ret == "64: unknown error code"

    # Raise an error
    with pytest.raises(CommandExecutionError) as exc:
        ret = service.launchctl("error", "bootstrap")
        assert "Failed to error service" in str(exc.value)


def test_list(service, service_name):
    """
    Test service.list
    """
    # Expected Functionality
    ret = service.list()
    assert "PID" in ret
    ret = service.list(service_name)
    assert "{" in ret

    # Service not found
    with pytest.raises(CommandExecutionError) as exc:
        ret = service.list("spongebob")
        assert "Service not found" in str(exc.value)


def test_enable(service, service_name):
    """
    Test service.enable
    """
    ret = service.enable(service_name)
    assert ret

    with pytest.raises(CommandExecutionError) as exc:
        ret = service.enable("spongebob")
        assert "Service not found" in str(exc.value)


def test_disable(service, service_name):
    """
    Test service.disable
    """
    ret = service.disable(service_name)
    assert ret

    with pytest.raises(CommandExecutionError) as exc:
        ret = service.disable("spongebob")
        assert "Service not found" in str(exc.value)


def test_start(service, service_name):
    """
    Test service.start
    Test service.stop
    Test service.status
    """
    service.stop(service_name)
    ret = service.start(service_name)
    assert ret

    with pytest.raises(CommandExecutionError) as exc:
        ret = service.start("spongebob")
        assert "Service not found" in str(exc.value)


def test_stop(service, service_name):
    """
    Test service.stop
    """
    ret = service.stop(service_name)
    assert ret

    with pytest.raises(CommandExecutionError) as exc:
        ret = service.stop("spongebob")
        assert "Service not found" in str(exc.value)

    service.start(service_name)


def test_status(service, service_name):
    """
    Test service.status
    """
    # A running service
    ret = service.status(service_name)
    assert ret

    # A stopped service
    service.stop(service_name)
    ret = service.status(service_name)
    assert not ret

    # Service not found
    ret = service.status("spongebob")
    assert not ret

    service.start(service_name)


def test_available(service, service_name):
    """
    Test service.available
    """
    ret = service.available(service_name)
    assert ret

    ret = service.available("spongebob")
    assert not ret


def test_missing(service, service_name):
    """
    Test service.missing
    """
    ret = service.missing(service_name)
    assert not ret

    ret = service.missing("spongebob")
    assert ret


def test_enabled(service, service_name):
    """
    Test service.enabled
    """
    service.disabled(service_name)
    ret = service.enabled(service_name)
    assert ret

    with pytest.raises(CommandExecutionError) as exc:
        ret = service.enabled("spongebob")
        assert "Service not found: spongebob" in str(exc.value)


def test_disabled(service, service_name):
    """
    Test service.disabled
    """
    ret = service.disabled(service_name)
    assert not ret

    ret = service.disable(service_name)
    assert ret

    ret = service.disabled(service_name)
    assert ret

    ret = service.enable(service_name)
    assert ret

    with pytest.raises(CommandExecutionError) as exc:
        ret = service.disable("spongebob")
        assert "Service not found: spongebob" in str(exc.value)


def test_get_all(service, service_name):
    """
    Test service.get_all
    """
    services = service.get_all()
    assert isinstance(services, list)
    assert service_name in services


def test_get_enabled(service, service_name):
    """
    Test service.get_enabled
    """
    services = service.get_enabled()
    assert isinstance(services, list)
    assert service_name in services


def test_service_laoded(service, service_name):
    """
    Test service.get_enabled
    """
    ret = service.loaded(service_name)
    assert ret
