"""
integration tests for mac_service
"""

import plistlib

import pytest

import salt.utils.files

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("launchctl", "plutil"),
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="function", autouse=True)
def service_name(salt_call_cli, service_name):

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
    salt_call_cli.run("service.enable", service_name)
    salt_call_cli.run("service.start", service_name)

    try:
        yield service_name
    finally:
        salt_call_cli.run("service.stop", service_name)
        salt.utils.files.safe_rm(service_path)


def test_show(salt_call_cli, service_name):
    """
    Test service.show
    """
    # Existing Service
    service_info = salt_call_cli.run("service.show", service_name)
    assert isinstance(service_info.data, dict)
    assert service_info.data["plist"]["Label"] == service_name

    # Missing Service
    ret = salt_call_cli.run("service.show", "spongebob")
    assert "Service not found" in ret.stderr


def test_launchctl(salt_call_cli, service_name):
    """
    Test service.launchctl
    """
    # Expected Functionality
    ret = salt_call_cli.run("service.launchctl", "error", "bootstrap", 64)
    assert ret.data

    ret = salt_call_cli.run(
        "service.launchctl", "error", "bootstrap", 64, return_stdout=True
    )
    assert ret.data == "64: unknown error code"

    # Raise an error
    ret = salt_call_cli.run("service.launchctl", "error", "bootstrap")
    assert "Failed to error service" in ret.stderr


def test_list(salt_call_cli, service_name):
    """
    Test service.list
    """
    # Expected Functionality
    ret = salt_call_cli.run("service.list")
    assert "PID" in ret.data
    ret = salt_call_cli.run("service.list", service_name)
    assert "{" in ret.data

    # Service not found
    ret = salt_call_cli.run("service.list", "spongebob")
    assert "Service not found" in ret.stderr


def test_enable(salt_call_cli, service_name):
    """
    Test service.enable
    """
    ret = salt_call_cli.run("service.enable", service_name)
    assert ret.data

    ret = salt_call_cli.run("service.enable", "spongebob")
    assert "Service not found" in ret.stderr


def test_disable(salt_call_cli, service_name):
    """
    Test service.disable
    """
    ret = salt_call_cli.run("service.disable", service_name)
    assert ret.data

    ret = salt_call_cli.run("service.disable", "spongebob")
    assert "Service not found" in ret.stderr


def test_start(salt_call_cli, service_name):
    """
    Test service.start
    Test service.stop
    Test service.status
    """
    salt_call_cli.run("service.stop", service_name)
    ret = salt_call_cli.run("service.start", service_name)
    assert ret.data

    ret = salt_call_cli.run("service.start", "spongebob")
    assert "Service not found" in ret.stderr


def test_stop(salt_call_cli, service_name):
    """
    Test service.stop
    """
    ret = salt_call_cli.run("service.stop", service_name)
    assert ret.data

    ret = salt_call_cli.run("service.stop", "spongebob")
    assert "Service not found" in ret.stderr


def test_status(salt_call_cli, service_name):
    """
    Test service.status
    """
    # A running service
    salt_call_cli.run("service.start", service_name)
    ret = salt_call_cli.run("service.status", service_name)
    assert ret.data

    # A stopped service
    salt_call_cli.run("service.stop", service_name)
    ret = salt_call_cli.run("service.status", service_name)
    assert not ret.data

    # Service not found
    ret = salt_call_cli.run("service.status", "spongebob")
    assert not ret.data


def test_available(salt_call_cli, service_name):
    """
    Test service.available
    """
    ret = salt_call_cli.run("service.available", service_name)
    assert ret.data

    ret = salt_call_cli.run("service.available", "spongebob")
    assert not ret.data


def test_missing(salt_call_cli, service_name):
    """
    Test service.missing
    """
    ret = salt_call_cli.run("service.missing", service_name)
    assert not ret.data

    ret = salt_call_cli.run("service.missing", "spongebob")
    assert ret.data


def test_enabled(salt_call_cli, service_name):
    """
    Test service.enabled
    """
    salt_call_cli.run("service.disabled", service_name)
    ret = salt_call_cli.run("service.enabled", service_name)
    assert ret.data

    ret = salt_call_cli.run("service.enabled", "spongebob")
    assert "Service not found: spongebob" in ret.stderr


def test_disabled(salt_call_cli, service_name):
    """
    Test service.disabled
    """
    salt_call_cli.run("service.enabled", service_name)
    salt_call_cli.run("service.start", service_name)

    ret = salt_call_cli.run("service.disabled", service_name)
    assert not ret.data

    ret = salt_call_cli.run("service.disable", service_name)
    assert ret.data

    ret = salt_call_cli.run("service.disabled", service_name)
    assert ret.data

    ret = salt_call_cli.run("service.enable", service_name)
    assert ret.data

    ret = salt_call_cli.run("service.disable", "spongebob")
    assert "Service not found: spongebob" in ret.stderr


def test_get_all(salt_call_cli, service_name):
    """
    Test service.get_all
    """
    services = salt_call_cli.run("service.get_all")
    assert isinstance(services.data, list)
    assert service_name in services.data


def test_get_enabled(salt_call_cli, service_name):
    """
    Test service.get_enabled
    """
    services = salt_call_cli.run("service.get_enabled")
    assert isinstance(services.data, list)
    assert service_name in services.data


def test_service_laoded(salt_call_cli, service_name):
    """
    Test service.get_enabled
    """
    ret = salt_call_cli.run("service.loaded", service_name)
    assert ret.data
