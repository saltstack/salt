import logging
import textwrap

import pytest

import salt.modules.cmdmod as cmdmod
import salt.modules.file as filemod
from salt.exceptions import SaltInvocationError
from tests.support.mock import Mock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def _common_patches():
    with patch("salt.utils.platform.is_aix", Mock(return_value=False)), patch(
        "os.path.exists", Mock(return_value=True)
    ), patch("salt.utils.path.which", Mock(return_value="fnord")):
        yield


@pytest.fixture
def configure_loader_modules(_common_patches):
    return {
        filemod: {"__salt__": {"cmd.run": cmdmod.run}},
    }


def test_if_lsattr_is_missing_it_should_return_None():
    patch_which = patch(
        "salt.utils.path.which",
        Mock(return_value=None),
    )
    with patch_which:
        actual = filemod.lsattr("foo")
        assert actual is None, actual


def test_on_aix_lsattr_should_be_None():
    patch_aix = patch(
        "salt.utils.platform.is_aix",
        Mock(return_value=True),
    )
    with patch_aix:
        # SaltInvocationError will be raised if filemod.lsattr
        # doesn't early exit
        actual = filemod.lsattr("foo")
        assert actual is None


def test_SaltInvocationError_should_be_raised_when_file_is_missing():
    patch_exists = patch(
        "os.path.exists",
        Mock(return_value=False),
    )
    with patch_exists, pytest.raises(SaltInvocationError):
        filemod.lsattr("foo")


def test_if_chattr_version_is_less_than_required_flags_should_ignore_extended():
    fname = "/path/to/fnord"
    with_extended = (
        textwrap.dedent(
            """
        aAcCdDeijPsStTu---- {}
        """
        )
        .strip()
        .format(fname)
    )
    expected = set("acdijstuADST")
    patch_has_ext = patch(
        "salt.modules.file._chattr_has_extended_attrs",
        Mock(return_value=False),
    )
    patch_run = patch.dict(
        filemod.__salt__,
        {"cmd.run": Mock(return_value=with_extended)},
    )
    with patch_has_ext, patch_run:
        actual = set(filemod.lsattr(fname)[fname])
        msg = "Actual: {!r} Expected: {!r}".format(
            actual, expected
        )  # pylint: disable=E1322
        assert actual == expected, msg


def test_if_chattr_version_is_high_enough_then_extended_flags_should_be_returned():
    fname = "/path/to/fnord"
    with_extended = (
        textwrap.dedent(
            """
        aAcCdDeijPsStTu---- {}
        """
        )
        .strip()
        .format(fname)
    )
    expected = set("aAcCdDeijPsStTu")
    patch_has_ext = patch(
        "salt.modules.file._chattr_has_extended_attrs",
        Mock(return_value=True),
    )
    patch_run = patch.dict(
        filemod.__salt__,
        {"cmd.run": Mock(return_value=with_extended)},
    )
    with patch_has_ext, patch_run:
        actual = set(filemod.lsattr(fname)[fname])
        msg = "Actual: {!r} Expected: {!r}".format(
            actual, expected
        )  # pylint: disable=E1322
        assert actual == expected, msg


def test_if_supports_extended_but_there_are_no_flags_then_none_should_be_returned():
    fname = "/path/to/fnord"
    with_extended = (
        textwrap.dedent(
            """
        ------------------- {}
        """
        )
        .strip()
        .format(fname)
    )
    expected = set("")
    patch_has_ext = patch(
        "salt.modules.file._chattr_has_extended_attrs",
        Mock(return_value=True),
    )
    patch_run = patch.dict(
        filemod.__salt__,
        {"cmd.run": Mock(return_value=with_extended)},
    )
    with patch_has_ext, patch_run:
        actual = set(filemod.lsattr(fname)[fname])
        msg = "Actual: {!r} Expected: {!r}".format(
            actual, expected
        )  # pylint: disable=E1322
        assert actual == expected, msg
