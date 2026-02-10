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


def test_pre_releases_upgrade_with_prerelease_available():
    """
    Test that pip.installed with upgrade=True and pre_releases=True
    will upgrade to pre-release versions when available.
    This test verifies the fix for issue #68525.
    """
    pkg_name = "test-package"
    installed_version = "1.0.0"
    available_prerelease = "1.0.1rc1"

    mock_pip_list = MagicMock(
        side_effect=[
            {pkg_name: installed_version},  # Pre-cache pip list
            {pkg_name: installed_version},  # Check if installed
        ]
    )
    mock_pip_version = MagicMock(return_value="21.0.0")
    mock_pip_list_all_versions = MagicMock(
        return_value=["1.0.0", "1.0.1rc1", "1.0.1"]
    )
    mock_pip_install = MagicMock(return_value={"retcode": 0, "stdout": ""})

    with patch.dict(
        pip_state.__salt__,
        {
            "pip.list": mock_pip_list,
            "pip.version": mock_pip_version,
            "pip.list_all_versions": mock_pip_list_all_versions,
            "pip.install": mock_pip_install,
            "pip.normalize": pip_module.normalize,
        },
    ):
        result = pip_state.installed(
            name=pkg_name,
            upgrade=True,
            pre_releases=True,
        )

        # Verify that list_all_versions was called with pre_releases=True
        # This ensures pre-releases are included in available versions
        call_kwargs = mock_pip_list_all_versions.call_args.kwargs
        assert call_kwargs.get("pre_releases") is True
        assert call_kwargs.get("include_alpha") is True
        assert call_kwargs.get("include_beta") is True
        assert call_kwargs.get("include_rc") is True

        # Verify that pip.install was called to upgrade the package
        assert mock_pip_install.called
        assert mock_pip_install.call_args.kwargs["upgrade"] is True
        assert mock_pip_install.call_args.kwargs["pre_releases"] is True


def test_pre_releases_upgrade_without_prerelease_flag():
    """
    Test that pip.installed with upgrade=True but pre_releases=False
    does not include pre-releases in version checking.
    """
    pkg_name = "test-package"
    installed_version = "1.0.0"

    mock_pip_list = MagicMock(
        side_effect=[
            {pkg_name: installed_version},  # Pre-cache pip list
            {pkg_name: installed_version},  # Check if installed
        ]
    )
    mock_pip_version = MagicMock(return_value="21.0.0")
    mock_pip_list_all_versions = MagicMock(
        return_value=["1.0.0", "1.0.1rc1", "1.0.1"]
    )
    mock_pip_install = MagicMock(return_value={"retcode": 0, "stdout": ""})

    with patch.dict(
        pip_state.__salt__,
        {
            "pip.list": mock_pip_list,
            "pip.version": mock_pip_version,
            "pip.list_all_versions": mock_pip_list_all_versions,
            "pip.install": mock_pip_install,
            "pip.normalize": pip_module.normalize,
        },
    ):
        result = pip_state.installed(
            name=pkg_name,
            upgrade=True,
            pre_releases=False,
        )

        # Verify that list_all_versions was called with pre_releases=False
        call_kwargs = mock_pip_list_all_versions.call_args.kwargs
        assert call_kwargs.get("pre_releases") is False