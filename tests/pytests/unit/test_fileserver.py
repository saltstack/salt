import datetime
import os
import time

import salt.fileserver
import salt.utils.files


def test_diff_with_diffent_keys():
    """
    Test that different maps are indeed reported different
    """
    map1 = {"file1": 1234}
    map2 = {"file2": 1234}
    assert salt.fileserver.diff_mtime_map(map1, map2) is True


def test_diff_with_diffent_values():
    """
    Test that different maps are indeed reported different
    """
    map1 = {"file1": 12345}
    map2 = {"file1": 1234}
    assert salt.fileserver.diff_mtime_map(map1, map2) is True


def test_whitelist():
    opts = {
        "fileserver_backend": ["roots", "git", "s3fs", "hgfs", "svn"],
        "extension_modules": "",
    }
    fs = salt.fileserver.Fileserver(opts)
    assert sorted(fs.servers.whitelist) == sorted(
        ["git", "gitfs", "hg", "hgfs", "svn", "svnfs", "roots", "s3fs"]
    ), fs.servers.whitelist


def test_future_file_list_cache_file_ignored(tmp_path):
    opts = {
        "fileserver_backend": ["roots"],
        "cachedir": tmp_path,
        "extension_modules": "",
    }

    back_cachedir = os.path.join(tmp_path, "file_lists/roots")
    os.makedirs(os.path.join(back_cachedir))

    # Touch a couple files
    for filename in ("base.p", "foo.txt"):
        with salt.utils.files.fopen(os.path.join(back_cachedir, filename), "wb") as _f:
            if filename == "base.p":
                _f.write(b"\x80")

    # Set modification time to file list cache file to 1 year in the future
    now = datetime.datetime.utcnow()
    future = now + datetime.timedelta(days=365)
    mod_time = time.mktime(future.timetuple())
    os.utime(os.path.join(back_cachedir, "base.p"), (mod_time, mod_time))

    list_cache = os.path.join(back_cachedir, "base.p")
    w_lock = os.path.join(back_cachedir, ".base.w")
    ret = salt.fileserver.check_file_list_cache(opts, "files", list_cache, w_lock)
    assert (
        ret[1] is True
    ), "Cache file list cache file is not refreshed when future modification time"


def test_file_server_url_escape(tmp_path):
    (tmp_path / "srv").mkdir()
    (tmp_path / "srv" / "salt").mkdir()
    (tmp_path / "foo").mkdir()
    (tmp_path / "foo" / "bar").write_text("Bad file")
    fileroot = str(tmp_path / "srv" / "salt")
    badfile = str(tmp_path / "foo" / "bar")
    opts = {
        "fileserver_backend": ["roots"],
        "extension_modules": "",
        "optimization_order": [
            0,
        ],
        "file_roots": {
            "base": [fileroot],
        },
        "file_ignore_regex": "",
        "file_ignore_glob": "",
    }
    fs = salt.fileserver.Fileserver(opts)
    ret = fs.find_file(
        "salt://|..\\..\\..\\foo/bar",
        "base",
    )
    assert ret == {"path": "", "rel": ""}


def test_file_server_serve_url_escape(tmp_path):
    (tmp_path / "srv").mkdir()
    (tmp_path / "srv" / "salt").mkdir()
    (tmp_path / "foo").mkdir()
    (tmp_path / "foo" / "bar").write_text("Bad file")
    fileroot = str(tmp_path / "srv" / "salt")
    badfile = str(tmp_path / "foo" / "bar")
    opts = {
        "fileserver_backend": ["roots"],
        "extension_modules": "",
        "optimization_order": [
            0,
        ],
        "file_roots": {
            "base": [fileroot],
        },
        "file_ignore_regex": "",
        "file_ignore_glob": "",
        "file_buffer_size": 2048,
    }
    fs = salt.fileserver.Fileserver(opts)
    ret = fs.serve_file(
        {
            "path": "salt://|..\\..\\..\\foo/bar",
            "saltenv": "base",
            "loc": 0,
        }
    )
    assert ret == {"data": "", "dest": ""}
