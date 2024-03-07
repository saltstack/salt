import getpass
import logging
import os

import pytest

import salt.modules.file as filemod
import salt.utils.files
import salt.utils.platform
from tests.support.mock import Mock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {
        filemod: {
            "__context__": {},
            "__opts__": {"test": False},
        }
    }


@pytest.fixture
def tfile(tmp_path):
    filename = str(tmp_path / "file-check-test-file")

    with salt.utils.files.fopen(filename, "w") as fp:
        fp.write("Hi hello! I am a file.")
    os.chmod(filename, 0o644)

    yield filename

    os.remove(filename)


@pytest.fixture
def a_link(tmp_path, tfile):
    linkname = str(tmp_path / "a_link")
    os.symlink(tfile, linkname)

    yield linkname

    os.remove(linkname)


def get_link_perms():
    if salt.utils.platform.is_linux():
        return "0777"
    return "0755"


@pytest.mark.skip_on_windows(reason="os.symlink is not available on Windows")
def test_check_file_meta_follow_symlinks(a_link, tfile):
    user = getpass.getuser()
    lperms = get_link_perms()

    # follow_symlinks=False (default)
    ret = filemod.check_file_meta(
        a_link, tfile, None, None, user, None, lperms, None, None
    )
    assert ret == {}

    ret = filemod.check_file_meta(
        a_link, tfile, None, None, user, None, "0644", None, None
    )
    assert ret == {"mode": "0644"}

    # follow_symlinks=True
    ret = filemod.check_file_meta(
        a_link, tfile, None, None, user, None, "0644", None, None, follow_symlinks=True
    )
    assert ret == {}


@pytest.mark.skip_on_windows(reason="os.symlink is not available on Windows")
def test_check_managed_follow_symlinks(a_link, tfile):
    user = getpass.getuser()
    lperms = get_link_perms()

    # Function check_managed() ignores mode changes for files in the temp directory.
    # Trick it to not recognize a_link as such.
    a_link = "/" + a_link

    # follow_symlinks=False (default)
    ret, comments = filemod.check_managed(
        a_link, tfile, None, None, user, None, lperms, None, None, None, None, None
    )
    assert ret is True
    assert comments == f"The file {a_link} is in the correct state"

    ret, comments = filemod.check_managed(
        a_link, tfile, None, None, user, None, "0644", None, None, None, None, None
    )
    assert ret is None
    assert comments == "The following values are set to be changed:\nmode: 0644\n"

    # follow_symlinks=True
    ret, comments = filemod.check_managed(
        a_link,
        tfile,
        None,
        None,
        user,
        None,
        "0644",
        None,
        None,
        None,
        None,
        None,
        follow_symlinks=True,
    )
    assert ret is True
    assert comments == f"The file {a_link} is in the correct state"


@pytest.mark.skip_on_windows(reason="os.symlink is not available on Windows")
def test_check_managed_changes_follow_symlinks(a_link, tfile):
    user = getpass.getuser()
    lperms = get_link_perms()

    # follow_symlinks=False (default)
    ret = filemod.check_managed_changes(
        a_link, tfile, None, None, user, None, lperms, None, None, None, None, None
    )
    assert ret == {}

    ret = filemod.check_managed_changes(
        a_link, tfile, None, None, user, None, "0644", None, None, None, None, None
    )
    assert ret == {"mode": "0644"}

    # follow_symlinks=True
    ret = filemod.check_managed_changes(
        a_link,
        tfile,
        None,
        None,
        user,
        None,
        "0644",
        None,
        None,
        None,
        None,
        None,
        follow_symlinks=True,
    )
    assert ret == {}


@pytest.mark.skip_on_windows(reason="os.symlink is not available on Windows")
@pytest.mark.parametrize(
    "input,expected",
    [
        # user/group changes needed by name
        (
            {"user": "cuser", "group": "cgroup"},
            {"user": "cuser", "group": "cgroup"},
        ),
        # no changes needed by name
        (
            {"user": "luser", "group": "lgroup"},
            {},
        ),
        # user/group changes needed by id
        (
            {"user": 1001, "group": 2001},
            {"user": 1001, "group": 2001},
        ),
        # no user/group changes needed by id
        (
            {"user": 3001, "group": 4001},
            {},
        ),
    ],
)
def test_check_perms_user_group_name_and_id(input, expected):
    filename = "/path/to/fnord"
    with patch("os.path.exists", Mock(return_value=True)):
        # Consistent initial file stats
        stat_out = {
            "user": "luser",
            "group": "lgroup",
            "uid": 3001,
            "gid": 4001,
            "mode": "123",
        }

        patch_stats = patch(
            "salt.modules.file.stats",
            Mock(return_value=stat_out),
        )

        # "chown" the file to the permissions we want in test["input"]
        # pylint: disable=W0640
        def fake_chown(cmd, *args, **kwargs):
            for k, v in input.items():
                stat_out.update({k: v})

        patch_chown = patch(
            "salt.modules.file.chown",
            Mock(side_effect=fake_chown),
        )

        with patch_stats, patch_chown:
            ret, pre_post = filemod.check_perms(
                name=filename,
                ret={},
                user=input["user"],
                group=input["group"],
                mode="123",
                follow_symlinks=False,
            )
            assert ret["changes"] == expected
