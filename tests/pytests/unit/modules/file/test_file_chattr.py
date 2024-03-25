import logging
import textwrap

import pytest

import salt.modules.cmdmod as cmdmod
import salt.modules.file as filemod
from tests.support.mock import MagicMock, Mock, patch

log = logging.getLogger(__name__)

pytestmark = pytest.mark.skip_on_windows(
    reason="Chattr shouldn't be available on Windows"
)


@pytest.fixture
def _common_patches():
    with patch("salt.utils.platform.is_aix", Mock(return_value=False)), patch(
        "os.path.exists", Mock(return_value=True)
    ), patch("salt.utils.path.which", Mock(return_value="some/tune2fs")):
        yield


@pytest.fixture
def configure_loader_modules(_common_patches):
    return {
        filemod: {
            "__salt__": {"cmd.run": cmdmod.run},
            "__opts__": {"test": False},
        },
    }


def test_chattr_version_returns_None_if_no_tune2fs_exists():
    with patch("salt.utils.path.which", Mock(return_value="")):
        actual = filemod._chattr_version()
        assert actual is None


def test_on_aix_chattr_version_should_be_None_even_if_tune2fs_exists():
    patch_which = patch(
        "salt.utils.path.which",
        Mock(return_value="fnord"),
    )
    patch_aix = patch(
        "salt.utils.platform.is_aix",
        Mock(return_value=True),
    )
    mock_run = MagicMock(return_value="fnord")
    patch_run = patch.dict(filemod.__salt__, {"cmd.run": mock_run})
    with patch_which, patch_aix, patch_run:
        actual = filemod._chattr_version()
        assert actual is None
        mock_run.assert_not_called()


def test_chattr_version_should_return_version_from_tune2fs():
    expected = "1.43.4"
    sample_output = textwrap.dedent(
        """
        tune2fs 1.43.4 (31-Jan-2017)
        Usage: tune2fs [-c max_mounts_count] [-e errors_behavior] [-f] [-g group]
        [-i interval[d|m|w]] [-j] [-J journal_options] [-l]
        [-m reserved_blocks_percent] [-o [^]mount_options[,...]]
        [-p mmp_update_interval] [-r reserved_blocks_count] [-u user]
        [-C mount_count] [-L volume_label] [-M last_mounted_dir]
        [-O [^]feature[,...]] [-Q quota_options]
        [-E extended-option[,...]] [-T last_check_time] [-U UUID]
        [-I new_inode_size] [-z undo_file] device
        """
    )
    patch_which = patch(
        "salt.utils.path.which",
        Mock(return_value="fnord"),
    )
    patch_run = patch.dict(
        filemod.__salt__,
        {"cmd.run": MagicMock(return_value=sample_output)},
    )
    with patch_which, patch_run:
        actual = filemod._chattr_version()
        assert actual == expected


def test_if_tune2fs_has_no_version_version_should_be_None():
    patch_which = patch(
        "salt.utils.path.which",
        Mock(return_value="fnord"),
    )
    patch_run = patch.dict(
        filemod.__salt__,
        {"cmd.run": MagicMock(return_value="fnord")},
    )
    with patch_which, patch_run:
        actual = filemod._chattr_version()
        assert actual is None


def test_chattr_has_extended_attrs_should_return_False_if_chattr_version_is_None():
    patch_chattr = patch(
        "salt.modules.file._chattr_version",
        Mock(return_value=None),
    )
    with patch_chattr:
        actual = filemod._chattr_has_extended_attrs()
        assert not actual, actual


def test_chattr_has_extended_attrs_should_return_False_if_version_is_too_low():
    below_expected = "0.1.1"
    patch_chattr = patch(
        "salt.modules.file._chattr_version",
        Mock(return_value=below_expected),
    )
    with patch_chattr:
        actual = filemod._chattr_has_extended_attrs()
        assert not actual, actual


def test_chattr_has_extended_attrs_should_return_False_if_version_is_equal_threshold():
    threshold = "1.41.12"
    patch_chattr = patch(
        "salt.modules.file._chattr_version",
        Mock(return_value=threshold),
    )
    with patch_chattr:
        actual = filemod._chattr_has_extended_attrs()
        assert not actual, actual


def test_chattr_has_extended_attrs_should_return_True_if_version_is_above_threshold():
    higher_than = "1.41.13"
    patch_chattr = patch(
        "salt.modules.file._chattr_version",
        Mock(return_value=higher_than),
    )
    with patch_chattr:
        actual = filemod._chattr_has_extended_attrs()
        assert actual, actual


def test_check_perms_should_report_no_attr_changes_if_there_are_none():
    filename = "/path/to/fnord"
    attrs = "aAcCdDeijPsStTu"

    higher_than = "1.41.13"
    patch_chattr = patch(
        "salt.modules.file._chattr_version",
        Mock(return_value=higher_than),
    )
    patch_exists = patch(
        "os.path.exists",
        Mock(return_value=True),
    )
    patch_stats = patch(
        "salt.modules.file.stats",
        Mock(return_value={"user": "foo", "group": "bar", "mode": "123"}),
    )
    patch_run = patch.dict(
        filemod.__salt__,
        {"cmd.run": MagicMock(return_value="--------- " + filename)},
    )
    with patch_chattr, patch_exists, patch_stats, patch_run:
        actual_ret, actual_perms = filemod.check_perms(
            name=filename,
            ret=None,
            user="foo",
            group="bar",
            mode="123",
            attrs=attrs,
            follow_symlinks=False,
        )
        assert actual_ret.get("changes", {}).get("attrs") is None, actual_ret


def test_check_perms_should_report_attrs_new_and_old_if_they_changed():
    filename = "/path/to/fnord"
    attrs = "aAcCdDeijPsStTu"
    existing_attrs = "aeiu"
    expected = {
        "attrs": {"old": existing_attrs, "new": attrs},
    }

    higher_than = "1.41.13"
    patch_chattr = patch(
        "salt.modules.file._chattr_version",
        Mock(return_value=higher_than),
    )
    patch_stats = patch(
        "salt.modules.file.stats",
        Mock(return_value={"user": "foo", "group": "bar", "mode": "123"}),
    )
    patch_cmp = patch(
        "salt.modules.file._cmp_attrs",
        MagicMock(
            side_effect=[
                filemod.AttrChanges(
                    added="aAcCdDeijPsStTu",
                    removed="",
                ),
                filemod.AttrChanges(
                    None,
                    None,
                ),
            ]
        ),
    )
    patch_chattr = patch(
        "salt.modules.file.chattr",
        MagicMock(),
    )

    def fake_cmd(cmd, *args, **kwargs):
        if cmd == ["lsattr", "/path/to/fnord"]:
            return textwrap.dedent(
                """
                {}---- {}
                """.format(
                    existing_attrs, filename
                )
            ).strip()
        else:
            assert False, f"not sure how to handle {cmd}"

    patch_run = patch.dict(
        filemod.__salt__,
        {"cmd.run": MagicMock(side_effect=fake_cmd)},
    )
    patch_ver = patch(
        "salt.modules.file._chattr_has_extended_attrs",
        MagicMock(return_value=True),
    )
    with patch_chattr, patch_stats, patch_cmp, patch_run, patch_ver:
        actual_ret, actual_perms = filemod.check_perms(
            name=filename,
            ret=None,
            user="foo",
            group="bar",
            mode="123",
            attrs=attrs,
            follow_symlinks=False,
        )
        assert actual_ret["changes"] == expected
