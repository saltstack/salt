"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import pytest

import salt.modules.composer as composer
from salt.exceptions import (
    CommandExecutionError,
    CommandNotFoundError,
    SaltInvocationError,
)
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {composer: {}}


def test_install():
    """
    Test for Install composer dependencies for a directory.
    """

    # Test _valid_composer=False throws exception
    mock = MagicMock(return_value=False)
    with patch.object(composer, "_valid_composer", mock):
        pytest.raises(CommandNotFoundError, composer.install, "d")

    # Test no directory specified throws exception
    mock = MagicMock(return_value=True)
    with patch.object(composer, "_valid_composer", mock):
        pytest.raises(SaltInvocationError, composer.install, None)

    # Test `composer install` exit status != 0 throws exception
    mock = MagicMock(return_value=True)
    with patch.object(composer, "_valid_composer", mock):
        mock = MagicMock(return_value={"retcode": 1, "stderr": "A"})
        with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
            pytest.raises(CommandExecutionError, composer.install, "d")

    # Test success with quiet=True returns True
    mock = MagicMock(return_value=True)
    with patch.object(composer, "_valid_composer", mock):
        mock = MagicMock(return_value={"retcode": 0, "stderr": "A"})
        with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
            assert composer.install(
                "dir",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                True,
            )

    # Test success with quiet=False returns object
    mock = MagicMock(return_value=True)
    with patch.object(composer, "_valid_composer", mock):
        rval = {"retcode": 0, "stderr": "A", "stdout": "B"}
        mock = MagicMock(return_value=rval)
        with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
            assert composer.install("dir") == rval


def test_update():
    """
    Test for Update composer dependencies for a directory.
    """

    # Test _valid_composer=False throws exception
    mock = MagicMock(return_value=False)
    with patch.object(composer, "_valid_composer", mock):
        pytest.raises(CommandNotFoundError, composer.update, "d")

    # Test no directory specified throws exception
    mock = MagicMock(return_value=True)
    with patch.object(composer, "_valid_composer", mock):
        mock = MagicMock(return_value=True)
        with patch.object(composer, "did_composer_install", mock):
            pytest.raises(SaltInvocationError, composer.update, None)

    # Test update with error exit status throws exception
    mock = MagicMock(return_value=True)
    with patch.object(composer, "_valid_composer", mock):
        mock = MagicMock(return_value=True)
        with patch.object(composer, "did_composer_install", mock):
            mock = MagicMock(return_value={"retcode": 1, "stderr": "A"})
            with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                pytest.raises(CommandExecutionError, composer.update, "d")

    # Test update with existing vendor directory and quiet=True
    mock = MagicMock(return_value=True)
    with patch.object(composer, "_valid_composer", mock):
        mock = MagicMock(return_value=True)
        with patch.object(composer, "did_composer_install", mock):
            mock = MagicMock(return_value={"retcode": 0, "stderr": "A"})
            with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                assert composer.update(
                    "dir",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    True,
                )

    # Test update with no vendor directory and quiet=True
    mock = MagicMock(return_value=True)
    with patch.object(composer, "_valid_composer", mock):
        mock = MagicMock(return_value=False)
        with patch.object(composer, "did_composer_install", mock):
            mock = MagicMock(return_value={"retcode": 0, "stderr": "A"})
            with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                assert composer.update(
                    "dir",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    True,
                )

    # Test update with existing vendor directory
    mock = MagicMock(return_value=True)
    with patch.object(composer, "_valid_composer", mock):
        mock = MagicMock(return_value=True)
        with patch.object(composer, "did_composer_install", mock):
            rval = {"retcode": 0, "stderr": "A", "stdout": "B"}
            mock = MagicMock(return_value=rval)
            with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                assert composer.update("dir") == rval

    # Test update with no vendor directory
    mock = MagicMock(return_value=True)
    with patch.object(composer, "_valid_composer", mock):
        mock = MagicMock(return_value=False)
        with patch.object(composer, "did_composer_install", mock):
            rval = {"retcode": 0, "stderr": "A", "stdout": "B"}
            mock = MagicMock(return_value=rval)
            with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                assert composer.update("dir") == rval


def test_selfupdate():
    """
    Test for Composer selfupdate
    """
    mock = MagicMock(return_value=False)
    with patch.object(composer, "_valid_composer", mock):
        pytest.raises(CommandNotFoundError, composer.selfupdate)

    mock = MagicMock(return_value=True)
    with patch.object(composer, "_valid_composer", mock):
        mock = MagicMock(return_value={"retcode": 1, "stderr": "A"})
        with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
            pytest.raises(CommandExecutionError, composer.selfupdate)

    mock = MagicMock(return_value=True)
    with patch.object(composer, "_valid_composer", mock):
        mock = MagicMock(return_value={"retcode": 0, "stderr": "A"})
        with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
            assert composer.selfupdate(quiet=True)

    mock = MagicMock(return_value=True)
    with patch.object(composer, "_valid_composer", mock):
        rval = {"retcode": 0, "stderr": "A", "stdout": "B"}
        mock = MagicMock(return_value=rval)
        with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
            assert composer.selfupdate() == rval
