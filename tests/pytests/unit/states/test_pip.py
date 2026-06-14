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


@pytest.mark.parametrize(
    "pkg,expected_clean,expected_spec",
    [
        (
            "git+https://example.com/foo.git#egg=Foo>=0.5.1",
            "git+https://example.com/foo.git#egg=Foo",
            ">=0.5.1",
        ),
        (
            "git+https://example.com/foo.git#egg=Foo==1.2.3",
            "git+https://example.com/foo.git#egg=Foo",
            "==1.2.3",
        ),
        (
            "git+https://example.com/foo.git#egg=Foo[extra]>=1.0,<2.0",
            "git+https://example.com/foo.git#egg=Foo[extra]",
            ">=1.0,<2.0",
        ),
        (
            "git+https://example.com/foo.git#egg=Foo>=1.0&subdirectory=src",
            "git+https://example.com/foo.git#egg=Foo&subdirectory=src",
            ">=1.0",
        ),
        (
            "git+https://example.com/foo.git#egg=Foo",
            "git+https://example.com/foo.git#egg=Foo",
            None,
        ),
        ("pep8>=1.3.1", "pep8>=1.3.1", None),
        ("plain_pkg", "plain_pkg", None),
    ],
)
def test_split_egg_version_spec(pkg, expected_clean, expected_spec):
    """
    The helper introduced for pip 26 compatibility must strip inline
    version specifiers from ``#egg=`` fragments without disturbing
    plain requirements or already-legal URL references.
    """
    cleaned, extracted = pip_state._split_egg_version_spec(pkg)
    assert cleaned == expected_clean
    assert extracted == expected_spec


def test_check_pkg_version_format_egg_with_specifier():
    """
    pip 26 rejects ``#egg=name<spec>`` URLs outright. ``_check_pkg_version_format``
    must still return a successful parse with the extracted specifier captured
    in ``version_spec``.
    """
    pkg = "git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting>=0.5.1"
    with patch.dict(
        pip_state.__salt__,
        {"pip.normalize": pip_module.normalize},
    ):
        result = pip_state._check_pkg_version_format(pkg)
    assert result["result"] is True
    assert result["prefix"] == "salttesting"
    version_spec = result["version_spec"] or []
    assert (">=", "0.5.1") in version_spec
