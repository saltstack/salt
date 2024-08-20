"""
    :codeauthor: Eric Graham <eric.graham@vantagepnt.com>
"""

import logging

import pytest

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
