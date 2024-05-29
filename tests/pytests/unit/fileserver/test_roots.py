"""
    :codeauthor: Mike Place <mp@saltstack.com>
"""

import copy
import os
import pathlib
import shutil
import sys
import textwrap

import pytest

import salt.fileclient
import salt.fileserver.roots as roots
import salt.utils.files
import salt.utils.hashutils
import salt.utils.platform
import salt.utils.stringutils
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture(scope="module")
def unicode_filename():
    return "питон.txt"


@pytest.fixture(scope="module")
def unicode_dirname():
    return "соль"


@pytest.fixture
def testfile(tmp_path):
    fp = tmp_path / "testfile"
    fp.write_text("This is a testfile")
    return fp


@pytest.fixture
def tmp_state_tree(tmp_path, testfile, unicode_filename, unicode_dirname):
    dirname = tmp_path / "roots_tmp_state_tree"
    dirname.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(testfile), str(dirname / testfile.name))
    unicode_dir = dirname / unicode_dirname
    unicode_dir.mkdir(parents=True, exist_ok=True)
    (dirname / unicode_filename).write_text("this is a unicode file")
    (unicode_dir / unicode_filename).write_text(
        "this is a unicode file in a unicode env"
    )
    (unicode_dir / "notunicode").write_text(
        "this is NOT a unicode file in a unicode env"
    )

    return dirname


@pytest.fixture
def testfilepath(tmp_state_tree, testfile):
    return tmp_state_tree / testfile.name


@pytest.fixture
def configure_loader_modules(tmp_state_tree, master_opts):
    overrides = {"file_roots": {"base": [str(tmp_state_tree)]}}
    master_opts.update(overrides)
    return {roots: {"__opts__": master_opts}}


def test_file_list(unicode_filename):
    ret = roots.file_list({"saltenv": "base"})
    assert "testfile" in ret
    assert unicode_filename in ret


def test_find_file(tmp_state_tree):
    ret = roots.find_file("testfile")
    assert "testfile" == ret["rel"]

    full_path_to_file = str(tmp_state_tree / "testfile")
    assert full_path_to_file == ret["path"]


def test_serve_file(testfilepath):
    with patch.dict(roots.__opts__, {"file_buffer_size": 262144}):
        load = {
            "saltenv": "base",
            "path": str(testfilepath),
            "loc": 0,
        }
        fnd = {"path": str(testfilepath), "rel": "testfile"}
        ret = roots.serve_file(load, fnd)

        with salt.utils.files.fopen(str(testfilepath), "rb") as fp_:
            data = fp_.read()

        assert ret == {"data": data, "dest": "testfile"}


def test_envs(unicode_dirname):
    opts = {"file_roots": copy.copy(roots.__opts__["file_roots"])}
    opts["file_roots"][unicode_dirname] = opts["file_roots"]["base"]
    with patch.dict(roots.__opts__, opts):
        ret = roots.envs()
    assert "base" in ret
    assert unicode_dirname in ret


def test_file_hash(testfile):
    load = {
        "saltenv": "base",
        "path": str(testfile),
    }
    fnd = {"path": str(testfile), "rel": "testfile"}
    ret = roots.file_hash(load, fnd)

    # Hashes are different in Windows. May be how git translates line
    # endings
    with salt.utils.files.fopen(str(testfile), "rb") as fp_:
        hsum = salt.utils.hashutils.sha256_digest(fp_.read())

    assert ret == {"hsum": hsum, "hash_type": "sha256"}


def test_file_list_emptydirs(tmp_state_tree):
    empty_dir = tmp_state_tree / "empty_dir"
    empty_dir.mkdir(parents=True, exist_ok=True)
    ret = roots.file_list_emptydirs({"saltenv": "base"})
    assert "empty_dir" in ret


def test_file_list_with_slash(unicode_filename):
    opts = {"file_roots": copy.copy(roots.__opts__["file_roots"])}
    opts["file_roots"]["foo/bar"] = opts["file_roots"]["base"]
    load = {
        "saltenv": "foo/bar",
    }
    with patch.dict(roots.__opts__, opts):
        ret = roots.file_list(load)
    assert "testfile" in ret
    assert unicode_filename in ret


def test_dir_list(tmp_state_tree, unicode_dirname):
    empty_dir = tmp_state_tree / "empty_dir"
    empty_dir.mkdir(parents=True, exist_ok=True)
    ret = roots.dir_list({"saltenv": "base"})
    assert "empty_dir" in ret
    assert unicode_dirname in ret


def test_symlink_list(tmp_state_tree):
    source_sym = tmp_state_tree / "source_sym"
    source_sym.write_text("")
    dest_sym = tmp_state_tree / "dest_sym"
    dest_sym.symlink_to(str(source_sym))
    ret = roots.symlink_list({"saltenv": "base"})
    assert ret == {"dest_sym": str(source_sym)}


def test_dynamic_file_roots(tmp_path):
    dyn_root_dir = tmp_path / "dyn_root_dir"
    dyn_root_dir.mkdir(parents=True, exist_ok=True)
    top_sls = dyn_root_dir / "top.sls"
    with salt.utils.files.fopen(str(top_sls), "w") as fp_:
        fp_.write("{{saltenv}}:\n  '*':\n    - dynamo\n")
    dynamo_sls = dyn_root_dir / "dynamo.sls"
    with salt.utils.files.fopen(str(dynamo_sls), "w") as fp_:
        fp_.write("foo:\n  test.nop\n")
    opts = {"file_roots": copy.copy(roots.__opts__["file_roots"])}
    opts["file_roots"]["__env__"] = [str(dyn_root_dir)]
    with patch.dict(roots.__opts__, opts):
        ret1 = roots.find_file("dynamo.sls", "dyn")
        ret2 = roots.file_list({"saltenv": "dyn"})
    assert "dynamo.sls" == ret1["rel"]
    assert "top.sls" in ret2
    assert "dynamo.sls" in ret2


@pytest.mark.skip_on_windows(
    reason="Windows does not support this master function",
)
def test_update_no_change():
    # process all changes that have happen
    # changes will always take place the first time during testing
    ret = roots.update()
    assert ret["changed"] is True

    # check if no changes took place
    ret = roots.update()
    assert ret["changed"] is False
    assert ret["files"]["changed"] == []
    assert ret["files"]["removed"] == []
    assert ret["files"]["added"] == []


def test_update_mtime_map():
    """
    Test that files with colons in the filename are properly handled in the
    mtime_map, and that they are properly identified as having changed.
    """
    mtime_map_path = pathlib.Path(roots.__opts__["cachedir"], "roots", "mtime_map")
    mtime_map_mock = mock_open(
        read_data={
            str(mtime_map_path): textwrap.dedent(
                """\
                /srv/salt/kleine_Datei.txt:1594263154.0469685
                /srv/salt/große:Datei.txt:1594263160.9336357
                """
            ),
        }
    )
    new_mtime_map = {
        "/srv/salt/kleine_Datei.txt": 1594263154.0469685,
        "/srv/salt/große:Datei.txt": 1594263261.0616212,
    }

    with patch(
        "salt.fileserver.reap_fileserver_cache_dir", MagicMock(return_value=True)
    ), patch(
        "salt.fileserver.generate_mtime_map", MagicMock(return_value=new_mtime_map)
    ), patch.dict(
        roots.__opts__, {"fileserver_events": False}
    ), patch(
        "salt.utils.files.fopen", mtime_map_mock
    ):
        ret = roots.update()

    # Confirm the expected return from the function
    assert ret == {
        "changed": True,
        "files": {
            "changed": ["/srv/salt/große:Datei.txt"],
            "removed": [],
            "added": [],
        },
        "backend": "roots",
    }, ret

    # Confirm that the new values were written to the mtime_map. Sort both
    # lists of lines to account for variances in dictionary iteration order
    # between Python releases.
    lines_written = sorted(mtime_map_mock.write_calls())
    expected = sorted(
        salt.utils.stringutils.to_bytes(f"{key}:{val}\n")
        for key, val in new_mtime_map.items()
    )
    assert lines_written == expected, lines_written


def test_update_mtime_map_unicode_error(tmp_path):
    """
    Test that a malformed mtime_map (which causes an UnicodeDecodeError
    exception) is handled properly.
    """
    new_mtime_map = {
        "/srv/salt/große:Datei.txt": 1594263261.0616212,
    }
    tmpdirname = tmp_path / "unicode_error"
    mtime_map_path = tmpdirname / "roots" / "mtime_map"
    mtime_map_path.parent.mkdir(parents=True, exist_ok=True)
    with salt.utils.files.fopen(str(mtime_map_path), "wb") as fp:
        fp.write(b"\x9c")

    with patch(
        "salt.fileserver.reap_fileserver_cache_dir",
        MagicMock(return_value=True),
    ), patch(
        "salt.fileserver.generate_mtime_map",
        MagicMock(return_value=new_mtime_map),
    ), patch.dict(
        roots.__opts__,
        {"fileserver_events": False, "cachedir": str(tmpdirname)},
    ):
        ret = roots.update()

    assert ret == {
        "changed": True,
        "files": {
            "changed": [],
            "removed": [],
            "added": ["/srv/salt/große:Datei.txt"],
        },
        "backend": "roots",
    }


def test_find_file_not_in_root(tmp_state_tree):
    """
    Fileroots should never 'find' a file that is outside of it's root.
    """
    badfile = pathlib.Path(tmp_state_tree).parent / "bar"
    badfile.write_text("Bad file")
    badpath = "../bar"
    ret = roots.find_file(badpath)
    assert ret == {"path": "", "rel": ""}
    badpath = f"{tmp_state_tree / '..' / 'bar'}"
    ret = roots.find_file(badpath)
    assert ret == {"path": "", "rel": ""}


def test_serve_file_not_in_root(tmp_state_tree):
    """
    Fileroots should never 'serve' a file that is outside of it's root.
    """
    badfile = pathlib.Path(tmp_state_tree).parent / "bar"
    badfile.write_text("Bad file")
    badpath = "../bar"
    load = {"path": "salt://|..\\bar", "saltenv": "base", "loc": 0}
    fnd = {
        "path": f"{tmp_state_tree / '..' / 'bar'}",
        "rel": f"{pathlib.Path('..') / 'bar'}",
    }
    ret = roots.serve_file(load, fnd)
    if "win" in sys.platform:
        assert ret == {"data": "", "dest": "..\\bar"}
    else:
        assert ret == {"data": "", "dest": "../bar"}


def test_find_file_symlink_destination_not_in_root(tmp_state_tree):
    dirname = pathlib.Path(tmp_state_tree).parent / "foo"
    dirname.mkdir(parents=True, exist_ok=True)
    testfile = dirname / "testfile"
    testfile.write_text("testfile")
    symlink = tmp_state_tree / "bar"
    symlink.symlink_to(str(dirname))
    ret = roots.find_file("bar/testfile")
    assert ret["path"] == str(symlink / "testfile")
    assert ret["rel"] == f"bar{os.sep}testfile"


def test_serve_file_symlink_destination_not_in_root(tmp_state_tree):
    dirname = pathlib.Path(tmp_state_tree).parent / "foo"
    dirname.mkdir(parents=True, exist_ok=True)
    testfile = dirname / "testfile"
    testfile.write_text("testfile")
    symlink = tmp_state_tree / "bar"
    symlink.symlink_to(str(dirname))
    load = {"path": "bar/testfile", "saltenv": "base", "loc": 0}
    fnd = {"path": str(symlink / "testfile"), "rel": "bar/testfile"}
    ret = roots.serve_file(load, fnd)
    assert ret == {"data": b"testfile", "dest": "bar/testfile"}
