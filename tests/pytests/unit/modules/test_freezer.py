import pytest

import salt.modules.freezer as freezer
from salt.exceptions import CommandExecutionError


@pytest.fixture()
def configure_loader_modules():
    return {freezer: {"__opts__": {"cachedir": ""}}}


def test_compare_no_args():
    """
    Test freezer.compare with no arguments
    """
    with pytest.raises(TypeError):
        freezer.compare()  # pylint: disable=no-value-for-parameter


def test_compare_not_enough_args():
    """
    Test freezer.compare without enough arguments
    """
    with pytest.raises(TypeError):
        freezer.compare(None)  # pylint: disable=no-value-for-parameter


def test_compare_too_many_args():
    """
    Test freezer.compare with too many arguments
    """
    with pytest.raises(TypeError):
        freezer.compare(None, None, None)  # pylint: disable=too-many-function-args


def test_compare_no_names():
    """
    Test freezer.compare with no real freeze names as arguments
    """
    with pytest.raises(CommandExecutionError):
        freezer.compare(old=None, new=None)
