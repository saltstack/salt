import getpass
import logging
import os

import pytest

import salt.modules.file as filemod
import salt.utils.files
import salt.utils.platform

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {filemod: {"__context__": {}}}


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
    assert comments == "The file {} is in the correct state".format(a_link)

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
    assert comments == "The file {} is in the correct state".format(a_link)


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
