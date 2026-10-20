"""
    :codeauthor: Eric Graham <eric.graham@vantagepnt.com>
"""

import logging

import pytest

import salt.modules.pip as pip_module
import salt.states.pip_state as pip_state
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pip_state: {"__env__": "base", "__opts__": {"test": False}}}


def test_issue_64169(caplog):
    pkg_to_install = "nonexistent_package"
    exception_message = "Invalid JSON (test_issue_64169)"

    mock_pip_list = MagicMock(
        side_effect=[
            CommandExecutionError(
                exception_message
            ),  # pre-cache the pip list (preinstall)
            {},  # Checking if the pkg is already installed
            {pkg_to_install: "100.10.1"},  # Confirming successful installation
        ]
    )
    mock_pip_version = MagicMock(return_value="100.10.1")
    mock_pip_install = MagicMock(return_value={"retcode": 0, "stdout": ""})

    with patch.dict(
        pip_state.__salt__,
        {
            "pip.list": mock_pip_list,
            "pip.version": mock_pip_version,
            "pip.install": mock_pip_install,
            "pip.normalize": pip_module.normalize,
        },
    ):
        with caplog.at_level(logging.WARNING):
            # Call pip.installed with a specifically 'broken' pip.list.
            # pip.installed should continue, but log the exception from pip.list.
            # pip.installed should NOT raise an exception itself.
            # noinspection PyBroadException
            try:
                pip_state.installed(
                    name=pkg_to_install,
                    use_wheel=False,  # Set False to simplify testing
                    no_use_wheel=False,  # '
                    no_binary=False,  # '
                    log=None,  # Regression will cause this function call to throw an AttributeError
                )
            except AttributeError as exc:
                # Observed behavior in #64169
                pytest.fail(
                    "Regression on #64169: pip_state.installed seems to be throwing an unexpected AttributeException: "
                    f"{exc}"
                )

            # Take 64169 further and actually confirm that the exception from pip.list got logged.
            assert (
                "Pre-caching of PIP packages during states.pip.installed failed by exception "
                f"from pip.list: {exception_message}" in caplog.messages
            )

        # Confirm that the state continued to install the package as expected.
        # Only check the 'pkgs' parameter of pip.install
        assert mock_pip_install.call_args.kwargs["pkgs"] == pkg_to_install


def test_already_satisfied_not_reported_as_change():
    """
    When pip outputs 'Requirement already satisfied' (modern pip >= 10) for a
    package that ended up in target_pkgs, the state must NOT report it as a
    change. Previously only the old 'Requirement already up-to-date' message
    was checked, causing the state to always report the package as installed.
    """
    pkg_name = "my-package"
    pkg_version = "1.0.0"

    mock_pip_list = MagicMock(
        side_effect=[
            {},  # pre-cache: empty → package goes to target_pkgs
            {},  # _check_if_installed fallback: package not found
            {pkg_name: pkg_version},  # post-install verification
        ]
    )
    mock_pip_version = MagicMock(return_value="24.0.0")
    mock_pip_install = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": f"Requirement already satisfied: {pkg_name} in /path/to/site-packages",
        }
    )

    with patch.dict(
        pip_state.__salt__,
        {
            "pip.list": mock_pip_list,
            "pip.version": mock_pip_version,
            "pip.install": mock_pip_install,
            "pip.normalize": pip_module.normalize,
        },
    ):
        ret = pip_state.installed(name=pkg_name)

    assert ret["result"] is True
    # The package was already satisfied — no changes should be reported
    assert (
        ret["changes"] == {}
    ), "Package reported as 'Requirement already satisfied' must not appear in changes"


def test_already_satisfied_with_version_spec_not_reported_as_change():
    """
    When pip outputs 'Requirement already satisfied: pkg==x.y.z ...' (with a
    version specifier in the message), the version suffix must be stripped when
    checking against already_installed_packages so the package is still
    correctly excluded from changes.
    """
    pkg_name = "my-package"
    pkg_version = "1.0.0"

    mock_pip_list = MagicMock(
        side_effect=[
            {},  # pre-cache: empty
            {},  # _check_if_installed fallback
            {pkg_name: pkg_version},  # post-install verification
        ]
    )
    mock_pip_version = MagicMock(return_value="24.0.0")
    mock_pip_install = MagicMock(
        return_value={
            "retcode": 0,
            # pip includes the version spec in the satisfied message
            "stdout": f"Requirement already satisfied: {pkg_name}=={pkg_version} in /path",
        }
    )

    with patch.dict(
        pip_state.__salt__,
        {
            "pip.list": mock_pip_list,
            "pip.version": mock_pip_version,
            "pip.install": mock_pip_install,
            "pip.normalize": pip_module.normalize,
        },
    ):
        ret = pip_state.installed(name=pkg_name)

    assert ret["result"] is True
    assert (
        ret["changes"] == {}
    ), "Package with version spec in satisfied message must not appear in changes"
