import logging
import os
import re
import shutil
import textwrap

import pytest

import salt.config
import salt.loader
import salt.modules.cmdmod as cmdmod
import salt.modules.config as configmod
import salt.modules.file as filemod
import salt.utils.data
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from salt.utils.jinja import SaltCacheLoader
from tests.support.mock import MagicMock, Mock, patch

log = logging.getLogger(__name__)


class DummyStat:
    st_mode = 33188
    st_ino = 115331251
    st_dev = 44
    st_nlink = 1
    st_uid = 99200001
    st_gid = 99200001
    st_size = 41743
    st_atime = 1552661253
    st_mtime = 1552661253
    st_ctime = 1552661253


@pytest.fixture
def sed_content():
    sed_content = textwrap.dedent(
        """\
    test
    some
    content
    /var/lib/foo/app/test
    here
    """
    )

    return sed_content


@pytest.fixture
def configure_loader_modules():
    return {
        filemod: {
            "__salt__": {
                "config.manage_mode": configmod.manage_mode,
                "cmd.run": cmdmod.run,
                "cmd.run_all": cmdmod.run_all,
            },
            "__opts__": {
                "test": False,
                "file_roots": {"base": "tmp"},
                "pillar_roots": {"base": "tmp"},
                "cachedir": "tmp",
                "grains": {},
            },
            "__grains__": {"kernel": "Linux"},
            "__utils__": {"stringutils.get_diff": salt.utils.stringutils.get_diff},
        }
    }


# Make a unique subdir to avoid any tempfile conflicts
@pytest.fixture
def subdir(tmp_path):
    subdir = tmp_path / "test-file-module-subdir"
    subdir.mkdir()
    yield subdir
    shutil.rmtree(str(subdir))


def test_check_file_meta_binary_contents():
    """
    Ensure that using the check_file_meta function does not raise a
    UnicodeDecodeError when used with binary contents (issue #57184).
    """
    contents = b"\xf4\x91"
    filemod.check_file_meta(
        "test",
        "test",
        "salt://test",
        {},
        "root",
        "root",
        "755",
        None,
        "base",
        contents=contents,
    )


@pytest.mark.skip_on_windows(reason="lsattr is not available on Windows")
def test_check_file_meta_no_lsattr():
    """
    Ensure that we skip attribute comparison if lsattr(1) is not found
    """
    source = "salt:///README.md"
    name = "/home/git/proj/a/README.md"
    source_sum = {}
    stats_result = {
        "size": 22,
        "group": "wheel",
        "uid": 0,
        "type": "file",
        "mode": "0600",
        "gid": 0,
        "target": name,
        "user": "root",
        "mtime": 1508356390,
        "atime": 1508356390,
        "inode": 447,
        "ctime": 1508356390,
    }
    with patch("salt.modules.file.stats") as m_stats:
        m_stats.return_value = stats_result
        with patch("salt.utils.path.which") as m_which:
            m_which.return_value = None
            result = filemod.check_file_meta(
                name, name, source, source_sum, "root", "root", "755", None, "base"
            )
    assert result


@pytest.mark.skip_on_platforms(
    windows=True,
    aix=True,
    reason="lsattr is not available on Windows and AIX",
)
def test_cmp_attrs_extents_flag():
    """
    Test that the cmp_attr function handles the extents flag correctly.
    This test specifically tests for a bug described in #57189.
    """
    # If the e attribute is not present and shall not be set, it should be
    # neither in the added nor in the removed set.
    with patch("salt.modules.file.lsattr") as m_lsattr:
        m_lsattr.return_value = {"file": ""}
        changes = filemod._cmp_attrs("file", "")
        assert changes.added is None
        assert changes.removed is None
    # If the e attribute is present and shall also be set, it should be
    # neither in the added nor in the removed set.
    with patch("salt.modules.file.lsattr") as m_lsattr:
        m_lsattr.return_value = {"file": "e"}
        changes = filemod._cmp_attrs("file", "e")
        assert changes.added is None
        assert changes.removed is None
    # If the e attribute is present and shall not be set, it should be
    # neither in the added nor in the removed set. One would assume that it
    # should be in the removed set, but the e attribute can never be reset,
    # so it is correct that both sets are empty.
    with patch("salt.modules.file.lsattr") as m_lsattr:
        m_lsattr.return_value = {"file": "e"}
        changes = filemod._cmp_attrs("file", "")
        assert changes.added is None
        assert changes.removed is None
    # If the e attribute is not present and shall be set, it should be in
    # the added, but not in the removed set.
    with patch("salt.modules.file.lsattr") as m_lsattr:
        m_lsattr.return_value = {"file": ""}
        changes = filemod._cmp_attrs("file", "e")
        assert "e" == changes.added
        assert changes.removed is None


@pytest.mark.skip_on_windows(reason="SED is not available on Windows")
def test_sed_limit_escaped(sed_content, subdir):
    with salt.utils.files.fopen(str(subdir / "tfile"), "w+") as tfile:
        tfile.write(sed_content)
        tfile.seek(0, 0)

        path = tfile.name
        before = "/var/lib/foo"
        after = ""
        limit = f"^{before}"

        filemod.sed(path, before, after, limit=limit)

        with salt.utils.files.fopen(path, "r") as newfile:
            assert sed_content.replace(before, "") == salt.utils.stringutils.to_unicode(
                newfile.read()
            )


def test_append_newline_at_eof(subdir):
    """
    Check that file.append works consistently on files with and without
    newlines at end of file.
    """
    # File ending with a newline
    with salt.utils.files.fopen(str(subdir / "tfile"), "wb") as tfile:
        tfile.write(salt.utils.stringutils.to_bytes("foo" + os.linesep))
        tfile.flush()
    filemod.append(tfile.name, "bar")
    expected = os.linesep.join(["foo", "bar", ""])
    with salt.utils.files.fopen(tfile.name) as tfile2:
        new_file = salt.utils.stringutils.to_unicode(tfile2.read())
    assert new_file == expected
    os.remove(tfile.name)

    # File not ending with a newline
    with salt.utils.files.fopen(str(subdir / "tfile"), "wb") as tfile:
        tfile.write(salt.utils.stringutils.to_bytes("foo"))
        tfile.flush()
    filemod.append(tfile.name, "bar")
    with salt.utils.files.fopen(tfile.name) as tfile2:
        assert salt.utils.stringutils.to_unicode(tfile2.read()) == expected

    # A newline should be added in empty files
    with salt.utils.files.fopen(str(subdir / "tfile"), "wb") as tfile:
        filemod.append(tfile.name, salt.utils.stringutils.to_str("bar"))
    with salt.utils.files.fopen(tfile.name) as tfile2:
        assert salt.utils.stringutils.to_unicode(tfile2.read()) == "bar" + os.linesep
    os.remove(tfile.name)


def test_extract_hash(subdir):
    """
    Check various hash file formats.
    """
    # With file name
    with salt.utils.files.fopen(str(subdir / "tfile"), "w+b") as tfile:
        tfile.write(
            salt.utils.stringutils.to_bytes(
                "rc.conf ef6e82e4006dee563d98ada2a2a80a27\n"
                "ead48423703509d37c4a90e6a0d53e143b6fc268  example.tar.gz\n"
                "fe05bcdcdc4928012781a5f1a2a77cbb5398e106 ./subdir/example.tar.gz\n"
                "ad782ecdac770fc6eb9a62e44f90873fb97fb26b *foo.tar.bz2\n"
            )
        )
        tfile.flush()

    result = filemod.extract_hash(tfile.name, "", "/rc.conf")
    assert result == {"hsum": "ef6e82e4006dee563d98ada2a2a80a27", "hash_type": "md5"}

    result = filemod.extract_hash(tfile.name, "", "/example.tar.gz")
    assert result == {
        "hsum": "ead48423703509d37c4a90e6a0d53e143b6fc268",
        "hash_type": "sha1",
    }

    # All the checksums in this test file are sha1 sums. We run this
    # loop three times. The first pass tests auto-detection of hash
    # type by length of the hash. The second tests matching a specific
    # type. The third tests a failed attempt to match a specific type,
    # since sha256 was requested but sha1 is what is in the file.
    for hash_type in ("", "sha1", "sha256"):
        # Test the source_hash_name argument. Even though there are
        # matches in the source_hash file for both the file_name and
        # source params, they should be ignored in favor of the
        # source_hash_name.
        file_name = "/example.tar.gz"
        source = "https://mydomain.tld/foo.tar.bz2?key1=val1&key2=val2"
        source_hash_name = "./subdir/example.tar.gz"
        result = filemod.extract_hash(
            tfile.name, hash_type, file_name, source, source_hash_name
        )
        expected = (
            {
                "hsum": "fe05bcdcdc4928012781a5f1a2a77cbb5398e106",
                "hash_type": "sha1",
            }
            if hash_type != "sha256"
            else None
        )
        assert result == expected

        # Test both a file_name and source but no source_hash_name.
        # Even though there are matches for both file_name and
        # source_hash_name, file_name should be preferred.
        file_name = "/example.tar.gz"
        source = "https://mydomain.tld/foo.tar.bz2?key1=val1&key2=val2"
        source_hash_name = None
        result = filemod.extract_hash(
            tfile.name, hash_type, file_name, source, source_hash_name
        )
        expected = (
            {
                "hsum": "ead48423703509d37c4a90e6a0d53e143b6fc268",
                "hash_type": "sha1",
            }
            if hash_type != "sha256"
            else None
        )
        assert result == expected

        # Test both a file_name and source but no source_hash_name.
        # Since there is no match for the file_name, the source is
        # matched.
        file_name = "/somefile.tar.gz"
        source = "https://mydomain.tld/foo.tar.bz2?key1=val1&key2=val2"
        source_hash_name = None
        result = filemod.extract_hash(
            tfile.name, hash_type, file_name, source, source_hash_name
        )
        expected = (
            {
                "hsum": "ad782ecdac770fc6eb9a62e44f90873fb97fb26b",
                "hash_type": "sha1",
            }
            if hash_type != "sha256"
            else None
        )
        assert result == expected
    os.remove(tfile.name)

    # Hash only, no file name (Maven repo checksum format)
    # Since there is no name match, the first checksum in the file will
    # always be returned, never the second.
    with salt.utils.files.fopen(str(subdir / "tfile"), "w+b") as tfile:
        tfile.write(
            salt.utils.stringutils.to_bytes(
                "ead48423703509d37c4a90e6a0d53e143b6fc268\n"
                "ad782ecdac770fc6eb9a62e44f90873fb97fb26b\n"
            )
        )
        tfile.flush()

    for hash_type in ("", "sha1", "sha256"):
        result = filemod.extract_hash(tfile.name, hash_type, "/testfile")
        expected = (
            {
                "hsum": "ead48423703509d37c4a90e6a0d53e143b6fc268",
                "hash_type": "sha1",
            }
            if hash_type != "sha256"
            else None
        )
        assert result == expected
    os.remove(tfile.name)


def test_user_to_uid_int():
    """
    Tests if user is passed as an integer
    """
    user = 5034
    ret = filemod.user_to_uid(user)
    assert ret == user


def test_group_to_gid_int():
    """
    Tests if group is passed as an integer
    """
    group = 5034
    ret = filemod.group_to_gid(group)
    assert ret == group


def test__get_flags():
    """
    Test to ensure _get_flags returns a regex flag
    """
    flags = 10
    ret = filemod._get_flags(flags)
    assert ret == re.IGNORECASE | re.MULTILINE

    flags = "MULTILINE"
    ret = filemod._get_flags(flags)
    assert ret == re.MULTILINE

    flags = ["IGNORECASE", "MULTILINE"]
    ret = filemod._get_flags(flags)
    assert ret == re.IGNORECASE | re.MULTILINE

    flags = re.IGNORECASE | re.MULTILINE
    ret = filemod._get_flags(flags)
    assert ret == re.IGNORECASE | re.MULTILINE


def test_patch():
    with patch("os.path.isdir", return_value=False) as mock_isdir, patch(
        "salt.utils.path.which", return_value="/bin/patch"
    ) as mock_which:
        cmd_mock = MagicMock(return_value="test_retval")
        with patch.dict(filemod.__salt__, {"cmd.run_all": cmd_mock}):
            ret = filemod.patch("/path/to/file", "/path/to/patch")
        cmd = [
            "/bin/patch",
            "--forward",
            "--reject-file=-",
            "-i",
            "/path/to/patch",
            "/path/to/file",
        ]
        cmd_mock.assert_called_once_with(cmd, python_shell=False)
        assert "test_retval" == ret


def test_patch_dry_run():
    with patch("os.path.isdir", return_value=False) as mock_isdir, patch(
        "salt.utils.path.which", return_value="/bin/patch"
    ) as mock_which:
        cmd_mock = MagicMock(return_value="test_retval")
        with patch.dict(filemod.__salt__, {"cmd.run_all": cmd_mock}):
            ret = filemod.patch("/path/to/file", "/path/to/patch", dry_run=True)
        cmd = [
            "/bin/patch",
            "--dry-run",
            "--forward",
            "--reject-file=-",
            "-i",
            "/path/to/patch",
            "/path/to/file",
        ]
        cmd_mock.assert_called_once_with(cmd, python_shell=False)
        assert "test_retval" == ret


def test_patch_dir():
    with patch("os.path.isdir", return_value=True) as mock_isdir, patch(
        "salt.utils.path.which", return_value="/bin/patch"
    ) as mock_which:
        cmd_mock = MagicMock(return_value="test_retval")
        with patch.dict(filemod.__salt__, {"cmd.run_all": cmd_mock}):
            ret = filemod.patch("/path/to/dir", "/path/to/patch")
        cmd = [
            "/bin/patch",
            "--forward",
            "--reject-file=-",
            "-i",
            "/path/to/patch",
            "-d",
            "/path/to/dir",
            "--strip=0",
        ]
        cmd_mock.assert_called_once_with(cmd, python_shell=False)
        assert "test_retval" == ret


def test_apply_template_on_contents():
    """
    Tests that the templating engine works on string contents
    """
    contents = "This is a {{ template }}."
    defaults = {"template": "templated file"}
    with patch.object(SaltCacheLoader, "file_client", Mock()):
        ret = filemod.apply_template_on_contents(
            contents,
            template="jinja",
            context={"opts": filemod.__opts__},
            defaults=defaults,
            saltenv="base",
        )
    assert ret == "This is a templated file."


def test_get_diff():

    text1 = textwrap.dedent(
        """\
        foo
        bar
        baz
        спам
        """
    )
    text2 = textwrap.dedent(
        """\
        foo
        bar
        baz
        яйца
        """
    )
    diff_result = textwrap.dedent(
        """\
        --- text1
        +++ text2
        @@ -1,4 +1,4 @@
         foo
         bar
         baz
        -спам
        +яйца
        """
    )

    # The below two variables are 8 bytes of data pulled from /dev/urandom
    binary1 = b"\xd4\xb2\xa6W\xc6\x8e\xf5\x0f"
    binary2 = b",\x13\x04\xa5\xb0\x12\xdf%"

    # pylint: disable=no-self-argument
    class MockFopen:
        """
        Provides a fake filehandle object that has just enough to run
        readlines() as file.get_diff does. Any significant changes to
        file.get_diff may require this class to be modified.
        """

        def __init__(
            mockself, path, *args, **kwargs
        ):  # pylint: disable=unused-argument
            mockself.path = path

        def readlines(mockself):  # pylint: disable=unused-argument
            if mockself.path == "text1":
                return text1.encode("utf8").splitlines(True)
            if mockself.path == "text2":
                return text2.encode("utf8").splitlines(True)
            if mockself.path == "binary1":
                return binary1.splitlines(True)
            if mockself.path == "binary2":
                return binary2.splitlines(True)

        def __enter__(mockself):
            return mockself

        def __exit__(mockself, *args):  # pylint: disable=unused-argument
            pass

    # pylint: enable=no-self-argument

    fopen = MagicMock(side_effect=lambda x, *args, **kwargs: MockFopen(x))
    cache_file = MagicMock(side_effect=lambda x, *args, **kwargs: x.split("/")[-1])

    # Mocks for __utils__['files.is_text']
    mock_text_text = MagicMock(side_effect=[True, True])
    mock_bin_bin = MagicMock(side_effect=[False, False])
    mock_text_bin = MagicMock(side_effect=[True, False])
    mock_bin_text = MagicMock(side_effect=[False, True])

    with patch.dict(filemod.__salt__, {"cp.cache_file": cache_file}), patch.object(
        salt.utils.files, "fopen", fopen
    ):

        # Test diffing two text files
        with patch.dict(filemod.__utils__, {"files.is_text": mock_text_text}):

            # Identical files
            ret = filemod.get_diff("text1", "text1")
            assert ret == ""

            # Non-identical files
            ret = filemod.get_diff("text1", "text2")
            assert ret == diff_result

            # Repeat the above test with remote file paths. The expectation
            # is that the cp.cache_file mock will ensure that we are not
            # trying to do an fopen on the salt:// URL, but rather the
            # "cached" file path we've mocked.
            with patch.object(filemod, "_binary_replace", MagicMock(return_value="")):
                ret = filemod.get_diff("salt://text1", "salt://text1")
                assert ret == ""
                ret = filemod.get_diff("salt://text1", "salt://text2")
                assert ret == diff_result

        # Test diffing two binary files
        with patch.dict(filemod.__utils__, {"files.is_text": mock_bin_bin}):

            # Identical files
            ret = filemod.get_diff("binary1", "binary1")
            assert ret == ""

            # Non-identical files
            ret = filemod.get_diff("binary1", "binary2")
            assert ret == "Replace binary file"

        # Test diffing a text file with a binary file
        with patch.dict(filemod.__utils__, {"files.is_text": mock_text_bin}):

            ret = filemod.get_diff("text1", "binary1")
            assert ret == "Replace text file with binary file"

        # Test diffing a binary file with a text file
        with patch.dict(filemod.__utils__, {"files.is_text": mock_bin_text}):

            ret = filemod.get_diff("binary1", "text1")
            assert ret == "Replace binary file with text file"


def test_stats():
    with patch("os.path.expanduser", MagicMock(side_effect=lambda path: path)), patch(
        "os.path.exists", MagicMock(return_value=True)
    ), patch("os.stat", MagicMock(return_value=DummyStat())):
        ret = filemod.stats("dummy", None, True)
        assert ret["mode"] == "0644"
        assert ret["type"] == "file"


def test_file_move_disallow_copy_and_unlink():
    mock_shutil_move = MagicMock()
    mock_os_rename = MagicMock()
    with patch("os.path.expanduser", MagicMock(side_effect=lambda path: path)), patch(
        "os.path.isabs", MagicMock(return_value=True)
    ), patch("shutil.move", mock_shutil_move), patch("os.rename", mock_os_rename):
        ret = filemod.move("source", "dest", disallow_copy_and_unlink=False)
        mock_shutil_move.assert_called_once()
        mock_os_rename.assert_not_called()
        assert ret["result"] is True

        mock_shutil_move.reset_mock()

        ret = filemod.move("source", "dest", disallow_copy_and_unlink=True)
        mock_os_rename.assert_called_once()
        mock_shutil_move.assert_not_called()
        assert ret is True
