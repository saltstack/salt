import copy
import logging
import os
import pathlib

import pytest

import salt.grains.core
import salt.modules.win_file as win_file
import salt.modules.win_lgpo as win_lgpo
import salt.utils.files
import salt.utils.versions
import salt.utils.win_dacl as win_dacl

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        win_lgpo: {
            "__opts__": minion_opts,
            "__salt__": {
                "file.file_exists": win_file.file_exists,
                "file.makedirs": win_file.makedirs_,
            },
        },
        win_file: {
            "__utils__": {
                "dacl.set_perms": win_dacl.set_perms,
            },
        },
    }


@pytest.fixture(scope="module")
def osversion():
    grains = salt.grains.core.os_data()
    yield grains.get("osversion", None)


@pytest.fixture
def clean_comp():
    reg_pol = pathlib.Path(
        os.getenv("SystemRoot"), "System32", "GroupPolicy", "Machine", "Registry.pol"
    )
    reg_pol.unlink(missing_ok=True)
    try:
        yield reg_pol
    finally:
        reg_pol.unlink(missing_ok=True)


@pytest.fixture
def checkbox_policy():
    policy_name = "Configure Corporate Windows Error Reporting"
    policy_settings = {
        "Connect using SSL": False,
        "Corporate server name": "fakeserver.com",
        "Only upload on free networks": False,
        "Server port": 1273,
    }
    win_lgpo.set_computer_policy(name=policy_name, setting=copy.copy(policy_settings))
    try:
        yield policy_name, policy_settings
    finally:
        win_lgpo.set_computer_policy(name=policy_name, setting="Not Configured")


def test_name(osversion):
    # Windows 10.0.17763 and lower use "Allow Telemetry"
    # Newer versions use "Allow Diagnostic Data"
    if salt.utils.versions.compare(ver1=osversion, oper=">", ver2="10.0.17763"):
        policy_name = "Allow Diagnostic Data"
    else:
        policy_name = "Allow Telemetry"
    result = win_lgpo.get_policy(
        policy_name=policy_name,
        policy_class="machine",
        return_value_only=True,
        return_full_policy_names=True,
        hierarchical_return=False,
    )
    expected = "Not Configured"
    assert result == expected


def test_id():
    result = win_lgpo.get_policy(
        policy_name="AllowTelemetry",
        policy_class="machine",
        return_value_only=True,
        return_full_policy_names=True,
        hierarchical_return=False,
    )
    expected = "Not Configured"
    assert result == expected


def test_name_full_return_full_names(osversion):
    # Windows 10.0.17763 and lower use "Allow Telemetry"
    # Newer versions use "Allow Diagnostic Data"
    if salt.utils.versions.compare(ver1=osversion, oper=">", ver2="10.0.17763"):
        policy_name = "Allow Diagnostic Data"
    else:
        policy_name = "Allow Telemetry"
    result = win_lgpo.get_policy(
        policy_name=policy_name,
        policy_class="machine",
        return_value_only=False,
        return_full_policy_names=True,
        hierarchical_return=False,
    )
    key = "Windows Components\\Data Collection and Preview Builds\\{}"
    expected = {key.format(policy_name): "Not Configured"}
    assert result == expected


def test_id_full_return_full_names(osversion):
    # Windows 10.0.17763 and lower use "Allow Telemetry"
    # Newer versions use "Allow Diagnostic Data"
    if salt.utils.versions.compare(ver1=osversion, oper=">", ver2="10.0.17763"):
        policy_name = "Allow Diagnostic Data"
    else:
        policy_name = "Allow Telemetry"
    result = win_lgpo.get_policy(
        policy_name="AllowTelemetry",
        policy_class="machine",
        return_value_only=False,
        return_full_policy_names=True,
        hierarchical_return=False,
    )
    key = "Windows Components\\Data Collection and Preview Builds\\{}"
    expected = {key.format(policy_name): "Not Configured"}
    assert result == expected


def test_name_full_return_ids(osversion):
    # Windows 10.0.17763 and lower use "Allow Telemetry"
    # Newer versions use "Allow Diagnostic Data"
    if salt.utils.versions.compare(ver1=osversion, oper=">", ver2="10.0.17763"):
        policy_name = "Allow Diagnostic Data"
    else:
        policy_name = "Allow Telemetry"
    result = win_lgpo.get_policy(
        policy_name=policy_name,
        policy_class="machine",
        return_value_only=False,
        return_full_policy_names=False,
        hierarchical_return=False,
    )
    expected = {"AllowTelemetry": "Not Configured"}
    assert result == expected


def test_id_full_return_ids():
    result = win_lgpo.get_policy(
        policy_name="AllowTelemetry",
        policy_class="machine",
        return_value_only=False,
        return_full_policy_names=False,
        hierarchical_return=False,
    )
    expected = {"AllowTelemetry": "Not Configured"}
    assert result == expected


def test_id_full_return_ids_hierarchical():
    result = win_lgpo.get_policy(
        policy_name="AllowTelemetry",
        policy_class="machine",
        return_value_only=False,
        return_full_policy_names=False,
        hierarchical_return=True,
    )
    expected = {
        "Computer Configuration": {
            "Administrative Templates": {
                "WindowsComponents": {
                    "DataCollectionAndPreviewBuilds": {
                        "AllowTelemetry": "Not Configured"
                    },
                },
            },
        },
    }
    assert result == expected


def test_name_return_full_names_hierarchical(osversion):
    # Windows 10.0.17763 and lower use "Allow Telemetry"
    # Newer versions use "Allow Diagnostic Data"
    if salt.utils.versions.compare(ver1=osversion, oper=">", ver2="10.0.17763"):
        policy_name = "Allow Diagnostic Data"
    else:
        policy_name = "Allow Telemetry"
    result = win_lgpo.get_policy(
        policy_name=policy_name,
        policy_class="machine",
        return_value_only=False,
        return_full_policy_names=True,
        hierarchical_return=True,
    )
    expected = {
        "Computer Configuration": {
            "Administrative Templates": {
                "Windows Components": {
                    "Data Collection and Preview Builds": {
                        policy_name: "Not Configured"
                    }
                }
            }
        }
    }
    assert result == expected


def test_checkboxes(checkbox_policy):
    """
    Test scenario where sometimes checkboxes aren't returned in the results
    """
    policy_name, expected = checkbox_policy
    result = win_lgpo.get_policy(policy_name=policy_name, policy_class="Machine")
    assert result == expected
