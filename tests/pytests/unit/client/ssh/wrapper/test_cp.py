"""
Test the SSHCpClient.

The following tests are adapted from
tests.pytests.unit.fileclient.test_fileclient_cache.

+ additional ones below
"""

import errno
import logging
import os
import shlex
import shutil
from pathlib import Path

import pytest

import salt.client.ssh.shell
import salt.exceptions
import salt.utils.files
from salt.client.ssh.wrapper import cp
from tests.support.mock import Mock, call, patch

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.skip_on_windows]

SUBDIR = "subdir"
TGT = "testtarget"


def _saltenvs():
    return ("base", "dev")


def _subdir_files():
    return ("foo.txt", "bar.txt", "baz.txt")


def _get_file_roots(fs_root):
    return {x: [os.path.join(fs_root, x)] for x in _saltenvs()}


@pytest.fixture
def fs_root(tmp_path):
    return os.path.join(tmp_path, "fileclient_fs_root")


@pytest.fixture
def cache_root(tmp_path):
    return os.path.join(tmp_path, "fileclient_cache_root")


@pytest.fixture
def remote_list(cache_root):
    cache_root = Path(cache_root)
    return {
        "files": {
            x
            for env in _saltenvs()
            for x in (
                Path("/tmp/targetdir/existingfile"),
                cache_root / f"files/{env}/filetodir",
                cache_root / f"extrn_files/{env}/filetodir",
                cache_root / f"files/{env}/foo.sls",
                cache_root / f"files/{env}/nested/path/foo.sls",
                cache_root / f"extrn_files/{env}/bar.sls",
                cache_root / f"files/{env}/rmfail/rmfailfile",
                cache_root / "localfiles/this/file/was/cached/locally",
            )
        },
        "dirs": {
            x
            for env in _saltenvs()
            for x in (
                (Path("/tmp/targetdir"),)
                + tuple((cache_root / f"extrn_files/{env}/dummy").parents)
                + tuple((cache_root / f"files/{env}/nested/path/dummy").parents)
                + tuple((cache_root / f"files/{env}/dirtofile/dummy").parents)
                + tuple((cache_root / f"extrn_files/{env}/dirtofile/dummy").parents)
                + tuple((cache_root / f"files/{env}/rmfail/dummy").parents)
                + tuple(
                    (
                        cache_root / f"localfiles/{env}/this/file/was/cached/locally"
                    ).parents
                )
            )
        },
        "send_fail": {
            x
            for env in _saltenvs()
            for x in (
                Path("/tmp/targetdir/failfile"),
                cache_root / f"files/{env}/{SUBDIR}/fail.sls",
            )
        },
        "rm_fail": {
            x
            for env in _saltenvs()
            for x in (
                cache_root / f"files/{env}/rmfail",
                cache_root / f"files/{env}/rmfail/rmfailfile",
            )
        },
    }


@pytest.fixture
def shell(request):
    remote_list = getattr(request, "param", None)
    removed = set()
    if remote_list is None:
        remote_list = request.getfixturevalue("remote_list")

    def exec_cmd(cmd):
        cmd = shlex.split(cmd)
        if cmd[0] == "rm":
            path = Path(cmd[2])
            if path in remote_list["rm_fail"]:
                return "", "you shall not pass", 1
            if cmd[1] == "-rf":
                path = Path(cmd[2])
                if path in removed:
                    return "", "deleted a path twice", 1
                removed.add(path)
            return "", "", 0
        if cmd[0] != "test":
            return "", "", 0
        if cmd[1] == "-d":
            return "", "", int(Path(cmd[2]) not in remote_list["dirs"])
        if cmd[1] == "-f":
            return "", "", int(Path(cmd[2]) not in remote_list["files"])
        if cmd[1] == "-e":
            return (
                "",
                "",
                int(
                    Path(cmd[2]) not in remote_list["files"]
                    and Path(cmd[2]) not in remote_list["dirs"]
                ),
            )
        return "", "", 0

    def send(src, dest, makedirs=False):
        dest = Path(dest)
        if dest in remote_list["send_fail"] or str(dest).endswith("fail"):
            return "", "sth went wrong", 1
        if any(x in remote_list["files"] and x not in removed for x in dest.parents):
            return "", "path contains files which were not removed: Not a directory", 1
        if dest.parent not in remote_list["dirs"] and not makedirs:
            return "", "tgt dir does not exist, no makedirs", 1
        if dest in remote_list["dirs"] and dest not in removed:
            # send should always receive the full path of the file
            return "", "just copied a file into a dir", 1
        return "", "", 0

    shl = Mock(spec=salt.client.ssh.shell.Shell)
    shl.exec_cmd.side_effect = exec_cmd
    shl.send.side_effect = send
    return shl


@pytest.fixture
def mocked_opts(tmp_path, fs_root, cache_root):
    return {
        "file_roots": _get_file_roots(fs_root),
        "fileserver_backend": ["roots"],
        "cachedir": cache_root,
        "file_client": "local",
    }


@pytest.fixture
def _setup(fs_root, cache_root):
    """
    No need to add a dummy foo.txt to muddy up the github repo, just make
    our own fileserver root on-the-fly.
    """

    def _new_dir(path):
        """
        Add a new dir at ``path`` using os.makedirs. If the directory
        already exists, remove it recursively and then try to create it
        again.
        """
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                # Just in case a previous test was interrupted, remove the
                # directory and try adding it again.
                shutil.rmtree(path)
                os.makedirs(path)
            else:
                raise

    # Crete the FS_ROOT
    for saltenv in _saltenvs():
        saltenv_root = os.path.join(fs_root, saltenv)
        # Make sure we have a fresh root dir for this saltenv
        _new_dir(saltenv_root)

        path = os.path.join(saltenv_root, "foo.txt")
        with salt.utils.files.fopen(path, "w") as fp_:
            fp_.write(f"This is a test file in the '{saltenv}' saltenv.\n")
        (Path(saltenv_root) / "dirtofile").touch()
        (Path(saltenv_root) / "filetodir").mkdir()
        (Path(saltenv_root) / "filetodir" / "foo.sh").touch()
        subdir_abspath = os.path.join(saltenv_root, SUBDIR)
        os.makedirs(subdir_abspath)
        for subdir_file in _subdir_files():
            path = os.path.join(subdir_abspath, subdir_file)
            with salt.utils.files.fopen(path, "w") as fp_:
                fp_.write(
                    "This is file '{}' in subdir '{} from saltenv '{}'".format(
                        subdir_file, SUBDIR, saltenv
                    )
                )
        (Path(subdir_abspath) / "fail.sls").touch()

    # Create the CACHE_ROOT
    _new_dir(cache_root)


@pytest.fixture
def client(minion_opts, mocked_opts, shell):
    patched_opts = minion_opts.copy()
    patched_opts.update(mocked_opts)
    return cp.SSHCpClient(patched_opts, shell, TGT)


@pytest.mark.usefixtures("_setup")
def test_cache_dir(client, cache_root):
    """
    Ensure entire directory is cached to correct location
    """
    for saltenv in _saltenvs():
        assert client.cache_dir(f"salt://{SUBDIR}", saltenv, cachedir=None)
        for subdir_file in _subdir_files():
            cache_loc = os.path.join(
                cache_root,
                "salt-ssh",
                TGT,
                "files",
                saltenv,
                SUBDIR,
                subdir_file,
            )
            # Double check that the content of the cached file
            # identifies it as being from the correct saltenv. The
            # setUp function creates the file with the name of the
            # saltenv mentioned in the file, so a simple 'in' check is
            # sufficient here. If opening the file raises an exception,
            # this is a problem, so we are not catching the exception
            # and letting it be raised so that the test fails.
            with salt.utils.files.fopen(cache_loc) as fp_:
                content = fp_.read()
            log.debug("cache_loc = %s", cache_loc)
            log.debug("content = %s", content)
            assert subdir_file in content
            assert SUBDIR in content
            assert saltenv in content
            minion_cache_loc = os.path.join(
                cache_root,
                "files",
                saltenv,
                SUBDIR,
                subdir_file,
            )
            client.shell.send.assert_any_call(cache_loc, minion_cache_loc, True)


@pytest.mark.usefixtures("_setup")
def test_cache_dir_with_alternate_cachedir_and_absolute_path(
    client, tmp_path, cache_root
):
    """
    Ensure entire directory is cached to the default location when an alternate
    cachedir is specified and that cachedir is an absolute path - but then
    sent to the correct cachedir on the minion.
    """
    alt_cachedir = os.path.join(tmp_path, "abs_cachedir")

    for saltenv in _saltenvs():
        assert client.cache_dir(f"salt://{SUBDIR}", saltenv, cachedir=alt_cachedir)
        for subdir_file in _subdir_files():
            cache_loc = os.path.join(
                cache_root,
                "salt-ssh",
                TGT,
                "absolute_root",
                alt_cachedir[1:],
                "files",
                saltenv,
                SUBDIR,
                subdir_file,
            )
            # Double check that the content of the cached file
            # identifies it as being from the correct saltenv. The
            # setUp function creates the file with the name of the
            # saltenv mentioned in the file, so a simple 'in' check is
            # sufficient here. If opening the file raises an exception,
            # this is a problem, so we are not catching the exception
            # and letting it be raised so that the test fails.
            with salt.utils.files.fopen(cache_loc) as fp_:
                content = fp_.read()
            log.debug("cache_loc = %s", cache_loc)
            log.debug("content = %s", content)
            assert subdir_file in content
            assert SUBDIR in content
            assert saltenv in content
            minion_cache_loc = os.path.join(
                alt_cachedir, "files", saltenv, SUBDIR, subdir_file
            )
            client.shell.send.assert_any_call(cache_loc, minion_cache_loc, True)


@pytest.mark.usefixtures("_setup")
def test_cache_dir_with_alternate_cachedir_and_relative_path(client, cache_root):
    """
    Ensure entire directory is cached to correct location when an alternate
    cachedir is specified and that cachedir is a relative path
    """
    alt_cachedir = "foo"

    for saltenv in _saltenvs():
        assert client.cache_dir(f"salt://{SUBDIR}", saltenv, cachedir=alt_cachedir)
        for subdir_file in _subdir_files():
            cache_loc = os.path.join(
                cache_root,
                "salt-ssh",
                TGT,
                alt_cachedir,
                "files",
                saltenv,
                SUBDIR,
                subdir_file,
            )
            # Double check that the content of the cached file
            # identifies it as being from the correct saltenv. The
            # setUp function creates the file with the name of the
            # saltenv mentioned in the file, so a simple 'in' check is
            # sufficient here. If opening the file raises an exception,
            # this is a problem, so we are not catching the exception
            # and letting it be raised so that the test fails.
            with salt.utils.files.fopen(cache_loc) as fp_:
                content = fp_.read()
            log.debug("cache_loc = %s", cache_loc)
            log.debug("content = %s", content)
            assert subdir_file in content
            assert SUBDIR in content
            assert saltenv in content
            minion_cache_loc = os.path.join(
                cache_root,
                alt_cachedir,
                "files",
                saltenv,
                SUBDIR,
                subdir_file,
            )
            client.shell.send.assert_any_call(cache_loc, minion_cache_loc, True)


@pytest.mark.usefixtures("_setup")
def test_cache_file(client, cache_root):
    """
    Ensure file is cached to correct location
    """
    for saltenv in _saltenvs():
        assert client.cache_file("salt://foo.txt", saltenv, cachedir=None)
        cache_loc = os.path.join(
            cache_root, "salt-ssh", TGT, "files", saltenv, "foo.txt"
        )
        # Double check that the content of the cached file identifies
        # it as being from the correct saltenv. The setUp function
        # creates the file with the name of the saltenv mentioned in
        # the file, so a simple 'in' check is sufficient here. If
        # opening the file raises an exception, this is a problem, so
        # we are not catching the exception and letting it be raised so
        # that the test fails.
        with salt.utils.files.fopen(cache_loc) as fp_:
            content = fp_.read()
        log.debug("cache_loc = %s", cache_loc)
        log.debug("content = %s", content)
        assert saltenv in content
        minion_cache_loc = os.path.join(cache_root, "files", saltenv, "foo.txt")
        client.shell.send.assert_any_call(cache_loc, minion_cache_loc, True)


@pytest.mark.usefixtures("_setup")
def test_cache_file_with_alternate_cachedir_and_absolute_path(
    client, tmp_path, cache_root
):
    """
    Ensure file is cached to the default location when an alternate cachedir is
    specified and that cachedir is an absolute path, but then sent to
    the correct path on the minion
    """
    alt_cachedir = os.path.join(tmp_path, "abs_cachedir")
    for saltenv in _saltenvs():
        assert client.cache_file("salt://foo.txt", saltenv, cachedir=alt_cachedir)
        cache_loc = os.path.join(
            cache_root,
            "salt-ssh",
            TGT,
            "absolute_root",
            alt_cachedir[1:],
            "files",
            saltenv,
            "foo.txt",
        )
        # Double check that the content of the cached file identifies
        # it as being from the correct saltenv. The setUp function
        # creates the file with the name of the saltenv mentioned in
        # the file, so a simple 'in' check is sufficient here. If
        # opening the file raises an exception, this is a problem, so
        # we are not catching the exception and letting it be raised so
        # that the test fails.
        with salt.utils.files.fopen(cache_loc) as fp_:
            content = fp_.read()
        log.debug("cache_loc = %s", cache_loc)
        log.debug("content = %s", content)
        assert saltenv in content
        minion_cache_loc = os.path.join(alt_cachedir, "files", saltenv, "foo.txt")
        client.shell.send.assert_any_call(cache_loc, minion_cache_loc, True)


@pytest.mark.usefixtures("_setup")
def test_cache_file_with_alternate_cachedir_and_relative_path(client, cache_root):
    """
    Ensure file is cached to correct location when an alternate cachedir is
    specified and that cachedir is a relative path
    """
    alt_cachedir = "foo"

    for saltenv in _saltenvs():
        assert client.cache_file("salt://foo.txt", saltenv, cachedir=alt_cachedir)
        cache_loc = os.path.join(
            cache_root,
            "salt-ssh",
            TGT,
            alt_cachedir,
            "files",
            saltenv,
            "foo.txt",
        )
        # Double check that the content of the cached file identifies
        # it as being from the correct saltenv. The setUp function
        # creates the file with the name of the saltenv mentioned in
        # the file, so a simple 'in' check is sufficient here. If
        # opening the file raises an exception, this is a problem, so
        # we are not catching the exception and letting it be raised so
        # that the test fails.
        with salt.utils.files.fopen(cache_loc) as fp_:
            content = fp_.read()
        log.debug("cache_loc = %s", cache_loc)
        log.debug("content = %s", content)
        assert saltenv in content
        minion_cache_loc = os.path.join(
            cache_root,
            alt_cachedir,
            "files",
            saltenv,
            "foo.txt",
        )
        client.shell.send.assert_any_call(cache_loc, minion_cache_loc, True)


@pytest.mark.usefixtures("_setup")
def test_cache_dest(client, cache_root):
    """
    Tests functionality for cache_dest
    """
    relpath = "foo.com/bar.txt"

    def _external(saltenv="base"):
        return salt.utils.path.join(
            cache_root, "salt-ssh", TGT, "extrn_files", saltenv, relpath
        )

    def _salt(saltenv="base"):
        return salt.utils.path.join(
            cache_root, "salt-ssh", TGT, "files", saltenv, relpath
        )

    def _check(ret, expected):
        assert ret == expected, f"{ret} != {expected}"

    _check(client.cache_dest(f"https://{relpath}"), _external())

    _check(client.cache_dest(f"https://{relpath}", "dev"), _external("dev"))

    _check(client.cache_dest(f"salt://{relpath}"), _salt())

    _check(client.cache_dest(f"salt://{relpath}", "dev"), _salt("dev"))

    _check(client.cache_dest(f"salt://{relpath}?saltenv=dev"), _salt("dev"))

    _check("/foo/bar", "/foo/bar")


# ------ END of adaptation of existing fileclient tests ------

# The following tests are for the client specifically, the wrapper
# function tests are implemented as integration ones.


def test_cache_local_file(client):
    """
    Caching local files would currently mean extracting files from the master
    to the minion, something that is likely very unexpected.
    Semantically, the other way around would be more expected, but receiving
    files from the minion is currently not implemented and might not be
    the best idea from a security perspective.
    """
    with pytest.raises(
        salt.exceptions.CommandExecutionError,
        match="Cannot cache local files via salt-ssh",
    ):
        client.cache_local_file("/foo/bar")


@pytest.mark.parametrize("master", (False, True))
@pytest.mark.parametrize("cachedir", (None, "", "relative/path", "/absolute/path"))
def test_get_cachedir(client, cachedir, master, cache_root):
    """
    Ensure that the cachedirs are correctly returned and that
    the master root cannot be overridden with an absolute path.
    """
    subdir = cachedir
    if cachedir is None:
        base = cache_root
    elif cachedir.startswith("/"):
        if master:
            base = cache_root
            subdir = "absolute_root" + cachedir
        else:
            base = cachedir
    else:
        base = cache_root
    if master:
        expected = str(Path(base) / "salt-ssh" / TGT / (subdir or "")).rstrip("/")
    else:
        expected = str(Path(base) / (subdir or "")).rstrip("/")
    if cachedir == "":
        # The usual fileclient does it this way as well
        expected += "/"
    assert client.get_cachedir(cachedir, master=master) == expected


@pytest.mark.usefixtures("_setup")
@pytest.mark.parametrize("saltenv", _saltenvs())
def test_cache_file_send_fail(client, saltenv, caplog, cache_root, fs_root):
    """
    Ensure that when a file transfer fails, an error is logged and
    the locally cached file is removed
    """
    with caplog.at_level(logging.ERROR):
        assert not client.cache_file(f"salt://{SUBDIR}/fail.sls", saltenv)
    assert "Failed sending file: sth went wrong" in caplog.text
    cache_loc = (
        Path(cache_root) / "salt-ssh" / TGT / "files" / saltenv / SUBDIR / "fail.sls"
    )
    assert not cache_loc.exists()


@pytest.mark.usefixtures("_setup")
def test_cache_file_dir_to_file(client, cache_root, remote_list, caplog):
    """
    Ensure that when a remote path is a directory, but should be a file,
    cache_file will remove the directory.
    """
    local_cache = Path(cache_root) / "salt-ssh" / TGT / "files" / "base" / "dirtofile"
    expected = Path(cache_root) / "files" / "base" / "dirtofile"
    res = client.cache_file("salt://dirtofile")
    assert res
    assert "just copied a file into a dir" not in caplog.text
    assert res == str(local_cache)
    assert local_cache.exists()
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == str(expected)
    client.shell.send.assert_called_once_with(str(local_cache), str(expected), True)


@pytest.mark.usefixtures("_setup")
def test_cache_file_file_to_dir(client, cache_root, caplog):
    """
    Ensure that when a remote path is a file, but should be a directory,
    cache_file will remove the file.
    """
    local_cache = (
        Path(cache_root) / "salt-ssh" / TGT / "files" / "base" / "filetodir" / "foo.sh"
    )
    expected = Path(cache_root) / "files" / "base" / "filetodir" / "foo.sh"
    res = client.cache_file("salt://filetodir/foo.sh")
    assert res
    assert "path contains files which were not removed" not in caplog.text
    assert res == str(local_cache)
    assert local_cache.exists()
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == str(expected)
    client.shell.send.assert_called_with(str(local_cache), str(expected), True)


@pytest.mark.usefixtures("_setup")
def test_send_file_to_dir_rmfail(client, cache_root, caplog):
    """
    Ensure that when a remote path is a file, but should be a directory,
    cache_file will remove the file.
    """
    res = client._send_file(
        "/some/source/file",
        Path(cache_root) / "files/base/rmfail/rmfailfile/child",
        True,
        None,
    )
    assert res is False
    assert "path contains files which were not removed" in caplog.text
    assert "Failed deleting path" in caplog.text
    assert "you shall not pass" in caplog.text


def test_send_file_file_to_dir_outside_cachedir(client, caplog):
    """
    When sending a file to a path of which one parent is an existing file,
    ensure that the failure is passed through instead of trying to delete
    this file.
    """
    res = client._send_file(
        "/some/source/file", "/tmp/targetdir/existingfile/bar", True, None
    )
    assert res is False
    assert "path contains files which were not removed" in caplog.text
    assert (
        call("rm -rf /tmp/targetdir/existingfile")
        not in client.shell.exec_cmd.mock_calls
    )


def test_send_file_from_outside_cachedir_fail(client, caplog, tmp_path):
    """
    Ensure failed transfers do not result in a deleted source file if it is outside
    of the SSH master-minion cache
    """
    src = tmp_path / "this_should_not_be_deleted"
    src.touch()
    with caplog.at_level(logging.ERROR):
        res = client._send_file(
            "/some/source/file", "/tmp/targetdir/failfile", False, None
        )
    assert res is False
    assert src.exists()
    assert "sth went wrong" in caplog.text


@pytest.mark.usefixtures("_setup")
@pytest.mark.parametrize("saltenv", _saltenvs())
def test_get_file_to_cache_send_fail(client, saltenv, caplog, cache_root, fs_root):
    """
    Ensure that when a file transfer to the remote cache fails, an error is
    logged and the locally cached file is removed
    """
    with caplog.at_level(logging.ERROR):
        assert not client.get_file(f"salt://{SUBDIR}/fail.sls", "", saltenv=saltenv)
    assert "Failed sending file: sth went wrong" in caplog.text
    cache_loc = (
        Path(cache_root) / "salt-ssh" / TGT / "files" / saltenv / SUBDIR / "fail.sls"
    )
    assert not cache_loc.exists()


@pytest.mark.usefixtures("_setup")
@pytest.mark.parametrize("saltenv", _saltenvs())
def test_get_file_send_fail_dst(client, saltenv, caplog, cache_root, fs_root, tmp_path):
    """
    Ensure that when a file transfer to a remote path outside of the cachedir
    fails, an error is logged and the locally cached file is removed
    """
    tgt = tmp_path / "remote_target_fail"
    with caplog.at_level(logging.ERROR):
        assert not client.get_file(f"salt://{SUBDIR}/fail.sls", str(tgt), saltenv)
        assert not tgt.exists()
    assert "Failed sending file: sth went wrong" in caplog.text
    cache_loc = (
        Path(cache_root) / "salt-ssh" / TGT / "files" / saltenv / SUBDIR / "fail.sls"
    )
    assert not cache_loc.exists()


@pytest.mark.usefixtures("_setup")
@pytest.mark.parametrize("makedirs", (False, True))
def test_get_file_remote_isdir(client, cache_root, makedirs):
    """
    Ensure that if the remote path is a directory, the file will be
    copied into it, _send will be called with the full file path
    and that the correct path is present in the target map.
    """
    tgt = "/tmp/targetdir"
    expected = tgt + "/foo.txt"
    local_cache = Path(cache_root) / "salt-ssh" / TGT / "files" / "base" / "foo.txt"
    res = client.get_file("salt://foo.txt", tgt, makedirs=makedirs)
    assert res
    assert res == str(local_cache)
    assert local_cache.exists()
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == expected
    client.shell.send.assert_called_once_with(str(local_cache), expected, makedirs)


@pytest.mark.usefixtures("_setup")
@pytest.mark.parametrize("makedirs", (False, True))
def test_get_file_with_dest_slash(client, cache_root, makedirs):
    """
    Ensure that if the destination is specified with a trailing slash,
    it is assumed to be a directory and a check is not performed.
    """
    tgt = "/tmp/targetdir/"
    expected = tgt + "foo.txt"
    local_cache = Path(cache_root) / "salt-ssh" / TGT / "files" / "base" / "foo.txt"
    res = client.get_file("salt://foo.txt", tgt, makedirs=makedirs)
    assert res
    assert res == str(local_cache)
    assert local_cache.exists()
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == expected
    client.shell.send.assert_called_once_with(str(local_cache), expected, makedirs)
    # ensure we're not doing unnecessary remote executions
    assert call(f"test -d {tgt}") not in client.shell.exec_cmd.mock_calls


@pytest.mark.usefixtures("_setup")
def test_get_file_with_different_name(client, cache_root):
    """
    Ensure that if the target path is not a directory, the final
    path component will be the name of the file.
    """
    tgt = "/tmp/targetdir/hithere"
    local_cache = Path(cache_root) / "salt-ssh" / TGT / "files" / "base" / "foo.txt"
    res = client.get_file("salt://foo.txt", tgt)
    assert res
    assert res == str(local_cache)
    assert local_cache.exists()
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == tgt
    client.shell.send.assert_called_once_with(str(local_cache), tgt, False)


@pytest.mark.usefixtures("_setup")
def test_get_url_salt_none_without_no_cache(client, cache_root):
    """
    note: salt:// URIs do not respect no_cache
    """
    tgt = Path(cache_root) / "files" / "base" / "foo.txt"
    local_cache = Path(cache_root) / "salt-ssh" / TGT / "files" / "base" / "foo.txt"
    res = client.get_url("salt://foo.txt", None)
    assert res
    assert local_cache.exists()
    assert res == local_cache.read_bytes()
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == str(tgt)
    client.shell.send.assert_called_once_with(str(local_cache), str(tgt), True)


@pytest.fixture
def _http_patch():
    def query(*args, **kwargs):
        kwargs["header_callback"]("HTTP/1.1 200 OK")
        kwargs["streaming_callback"](b"hi there")
        return {"handle": Mock(), "status": 200}

    with patch("salt.utils.http.query", side_effect=query):
        yield


@pytest.mark.usefixtures("_setup", "_http_patch")
@pytest.mark.parametrize("dest", ("", None))
def test_get_url_non_salt_dest_empty_without_no_cache(client, cache_root, dest):
    """
    Even when dest is None, but no_cache is False, the file should be sent
    to the minion cache.
    """
    tgt = (
        Path(cache_root) / "extrn_files" / "base" / "repo.saltproject.io" / "index.html"
    )
    local_cache = (
        Path(cache_root)
        / "salt-ssh"
        / TGT
        / "extrn_files"
        / "base"
        / "repo.saltproject.io"
        / "index.html"
    )
    res = client.get_url("https://repo.saltproject.io/index.html", dest)
    assert res
    assert local_cache.exists()
    assert local_cache.read_text() == "hi there"
    assert res == str(local_cache)
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == str(tgt)
    client.shell.send.assert_called_once_with(str(local_cache), str(tgt), True)


@pytest.mark.usefixtures("_setup", "_http_patch")
def test_get_url_non_salt_dest_slash(client, cache_root, tmp_path):
    expected = str(tmp_path) + "/foo.html"
    local_cache = (
        Path(cache_root)
        / "salt-ssh"
        / TGT
        / "extrn_files"
        / "base"
        / "repo.saltproject.io"
        / "foo.html"
    )
    res = client.get_url("https://repo.saltproject.io/foo.html", str(tmp_path) + "/")
    assert res
    assert local_cache.exists()
    assert local_cache.read_text() == "hi there"
    assert res == str(local_cache)
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == expected
    client.shell.send.assert_called_once_with(str(local_cache), expected, False)
    assert call(f"test -d {tmp_path}") not in client.shell.exec_cmd.mock_calls


@pytest.mark.usefixtures("_setup", "_http_patch")
def test_get_url_non_salt_dest_isdir(client, cache_root):
    dest = "/tmp/targetdir"
    expected = dest + "/foo.html"
    local_cache = (
        Path(cache_root)
        / "salt-ssh"
        / TGT
        / "extrn_files"
        / "base"
        / "repo.saltproject.io"
        / "foo.html"
    )
    res = client.get_url("https://repo.saltproject.io/foo.html", dest)
    assert res
    assert local_cache.exists()
    assert local_cache.read_text() == "hi there"
    assert res == str(local_cache)
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == expected
    client.shell.send.assert_called_once_with(str(local_cache), expected, False)
    client.shell.exec_cmd.assert_called_with(f"test -d {dest}")


@pytest.mark.usefixtures("_setup", "_http_patch")
def test_get_url_non_salt_dest_name_override(client, cache_root):
    dest = "/tmp/targetdir/bar.html"
    local_cache = (
        Path(cache_root)
        / "salt-ssh"
        / TGT
        / "extrn_files"
        / "base"
        / "repo.saltproject.io"
        / "foo.html"
    )
    res = client.get_url("https://repo.saltproject.io/foo.html", dest)
    assert res
    assert local_cache.exists()
    assert local_cache.read_text() == "hi there"
    assert res == str(local_cache)
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == dest
    client.shell.send.assert_called_once_with(str(local_cache), dest, False)
    client.shell.exec_cmd.assert_called_with(f"test -d {dest}")


@pytest.mark.usefixtures("_setup", "_http_patch")
def test_get_url_non_salt_dest_default_name(client, cache_root, tmp_path):
    expected = str(tmp_path / "index.html")
    # Yup, the regular fileclient will save this with the domain name only.
    # If you then try to cache any other file from that domain, it will
    # actually raise an exception because it attempts to create a dir with the same name
    local_cache = (
        Path(cache_root)
        / "salt-ssh"
        / TGT
        / "extrn_files"
        / "base"
        / "repo.saltproject.io"
    )
    res = client.get_url("https://repo.saltproject.io", str(tmp_path) + "/")
    assert res
    assert local_cache.exists()
    assert local_cache.read_text() == "hi there"
    assert res == str(local_cache)
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == expected
    client.shell.send.assert_called_once_with(str(local_cache), expected, False)


def test_get_url_non_salt_fetch_fail(client):
    with patch("salt.fileclient.Client.get_url", return_value=False):
        res = client.get_url("https://fooba.rs", "")
        assert res is False


@pytest.mark.usefixtures("_setup")
@pytest.mark.parametrize("dest", ("", None))
def test_get_template_cache(client, dest, cache_root):
    tgt = Path(cache_root) / "extrn_files" / "base" / "foo.txt"
    local_cache = (
        Path(cache_root) / "salt-ssh" / TGT / "extrn_files" / "base" / "foo.txt"
    )
    res = client.get_template("salt://foo.txt", dest, opts=client.opts)
    assert res
    assert local_cache.exists()
    assert res == str(local_cache)
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == str(tgt)
    client.shell.send.assert_called_with(str(local_cache), str(tgt), True)


@pytest.mark.usefixtures("_setup")
def test_get_template_name_override(client, cache_root):
    dest = "/tmp/targetdir/bar"
    local_cache = (
        Path(cache_root) / "salt-ssh" / TGT / "extrn_files" / "base" / "foo.txt"
    )
    res = client.get_template("salt://foo.txt", dest, opts=client.opts)
    assert res
    assert local_cache.exists()
    assert res == str(local_cache)
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == dest
    client.shell.send.assert_called_with(str(local_cache), dest, False)


@pytest.mark.usefixtures("_setup", "_http_patch")
def test_get_template_dest_slash(client, cache_root, tmp_path):
    expected = str(tmp_path) + "/foo.txt"
    local_cache = (
        Path(cache_root) / "salt-ssh" / TGT / "extrn_files" / "base" / "foo.txt"
    )
    res = client.get_template("salt://foo.txt", str(tmp_path) + "/", opts=client.opts)
    assert res
    assert local_cache.exists()
    assert (
        local_cache.read_text().strip() == "This is a test file in the 'base' saltenv."
    )
    assert res == str(local_cache)
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == expected
    client.shell.send.assert_called_with(str(local_cache), expected, False)
    assert call(f"test -d {tmp_path}") not in client.shell.exec_cmd.mock_calls


@pytest.mark.usefixtures("_setup", "_http_patch")
def test_get_template_dest_isdir(client, cache_root):
    dest = "/tmp/targetdir"
    expected = dest + "/foo.txt"
    local_cache = (
        Path(cache_root) / "salt-ssh" / TGT / "extrn_files" / "base" / "foo.txt"
    )
    res = client.get_template("salt://foo.txt", dest, opts=client.opts)
    assert res
    assert local_cache.exists()
    assert (
        local_cache.read_text().strip() == "This is a test file in the 'base' saltenv."
    )
    assert res == str(local_cache)
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == expected
    client.shell.send.assert_called_with(str(local_cache), expected, False)
    client.shell.exec_cmd.assert_called_with(f"test -d {dest}")


@pytest.mark.usefixtures("_setup", "_http_patch")
def test_get_template_dest_name_override(client, cache_root):
    dest = "/tmp/targetdir/bar.html"
    local_cache = (
        Path(cache_root)
        / "salt-ssh"
        / TGT
        / "extrn_files"
        / "base"
        / "repo.saltproject.io"
        / "foo.html"
    )
    res = client.get_url("https://repo.saltproject.io/foo.html", dest)
    assert res
    assert local_cache.exists()
    assert local_cache.read_text() == "hi there"
    assert res == str(local_cache)
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == dest
    client.shell.send.assert_called_once_with(str(local_cache), dest, False)
    client.shell.exec_cmd.assert_called_with(f"test -d {dest}")


@pytest.mark.usefixtures("_setup")
def test_get_template_dir_to_file(client, cache_root, remote_list, caplog):
    """
    Ensure that when a remote path is a directory, but should be a file,
    get_template will remove the directory.
    """
    local_cache = (
        Path(cache_root) / "salt-ssh" / TGT / "extrn_files" / "base" / "dirtofile"
    )
    expected = Path(cache_root) / "extrn_files" / "base" / "dirtofile"
    res = client.get_template("salt://dirtofile", "", opts=client.opts)
    assert res
    assert "just copied a file into a dir" not in caplog.text
    assert res == str(local_cache)
    assert local_cache.exists()
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == str(expected)
    client.shell.send.assert_called_with(str(local_cache), str(expected), True)


@pytest.mark.usefixtures("_setup")
def test_get_template_file_to_dir(client, cache_root, caplog):
    """
    Ensure that when a remote path is a file, but should be a directory,
    get_template will remove the file.
    """
    local_cache = (
        Path(cache_root)
        / "salt-ssh"
        / TGT
        / "extrn_files"
        / "base"
        / "filetodir"
        / "foo.sh"
    )
    expected = Path(cache_root) / "extrn_files" / "base" / "filetodir" / "foo.sh"
    res = client.get_template("salt://filetodir/foo.sh", "", opts=client.opts)
    assert res
    assert "path contains files which were not removed" not in caplog.text
    assert res == str(local_cache)
    assert local_cache.exists()
    assert str(local_cache) in client.target_map
    assert client.target_map[str(local_cache)] == str(expected)
    client.shell.send.assert_called_with(str(local_cache), str(expected), True)


@pytest.mark.parametrize(
    "arg,raises",
    [
        (
            ("foo/bar", "/foo/bar"),
            pytest.raises(ValueError, match=".*must be absolute.*as src"),
        ),
        (
            ("/foo/bar", "foo/bar"),
            pytest.raises(ValueError, match=".*must be absolute.*as dest"),
        ),
    ],
)
def test_send_file_sanity_checks(client, raises, arg):
    with raises:
        client._send_file(*arg, True, None)


@pytest.mark.parametrize(
    "path,raises",
    [
        (
            "",
            pytest.raises(
                ValueError, match="Not deleting unspecified, relative or root path"
            ),
        ),
        (
            "foo/bar",
            pytest.raises(
                ValueError, match="Not deleting unspecified, relative or root path"
            ),
        ),
        (
            "/",
            pytest.raises(
                ValueError, match="Not deleting unspecified, relative or root path"
            ),
        ),
        (
            "/some/path/not/in/cache/dir",
            pytest.raises(
                ValueError,
                match="Not recursively deleting a path outside of the cachedir.*",
            ),
        ),
    ],
)
def test_rmpath_sanity_checks(client, raises, path):
    with raises:
        client._rmpath(path)
    client.shell.exec_cmd.assert_not_called()


def test_rmpath_can_delete_minion_cache_dir(client, cache_root):
    client._rmpath(cache_root)
    client.shell.exec_cmd.assert_called_once_with(f"rm -rf {cache_root}")


def test_rmpath_does_not_delete_minion_cache_dir_parent(client, cache_root):
    with pytest.raises(
        ValueError, match="Not recursively deleting a path outside of the cachedir.*"
    ):
        client._rmpath(Path(cache_root).parent)
    client.shell.exec_cmd.assert_not_called()


@pytest.mark.parametrize(
    "path,expected", [("files/base/dirtofile", True), ("files/base/rmfail", False)]
)
def test_rmpath_retcode(client, cache_root, path, expected, caplog):
    with caplog.at_level(logging.ERROR):
        res = client._rmpath(Path(cache_root) / path)
    assert res is expected
    if not expected:
        assert "Failed deleting path" in caplog.text
        assert "you shall not pass" in caplog.text


def test_is_cached_localfiles(client, cache_root):
    """
    A check for having cached a local file on the minion should only check
    if the file exists on the target since we're not syncing to the master
    """
    tgt = "/this/file/was/cached/locally"
    res = client.is_cached(tgt)
    assert res == str(Path(cache_root) / "localfiles" / tgt[1:])


@pytest.mark.parametrize("saltenv", _saltenvs())
@pytest.mark.usefixtures("_setup")
def test_cache_master(client, cache_root, saltenv):
    """
    Files are copied one by one currently, so this is done as a unit test
    to save execution time and resources.
    """
    with patch.object(cp, "_client", return_value=client):
        res = cp.cache_master(saltenv)
    assert isinstance(res, list)
    assert res
    minion_parent = Path(cache_root) / "files" / saltenv
    master_parent = Path(cache_root) / "salt-ssh" / TGT / "files" / saltenv
    for path in res:
        assert path
        path = Path(path)
        assert minion_parent in path.parents
        master_path = master_parent / path.relative_to(minion_parent)
        assert master_path.exists()
        if path.name == "foo.txt":
            assert saltenv in master_path.read_text()
        client.shell.send.assert_any_call(str(master_path), str(path), True)
