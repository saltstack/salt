import logging
import os
import shutil

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
from tests.support.mock import MagicMock, call, patch

log = logging.getLogger(__name__)


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
        }
    }


@pytest.fixture
def tmp_sub_dir(tmp_path):
    directory = tmp_path / "file-basics-test-dir"
    directory.mkdir()

    yield directory

    shutil.rmtree(str(directory))


@pytest.fixture
def tfile(tmp_sub_dir):
    filename = str(tmp_sub_dir / "file-basics-test-file")

    with salt.utils.files.fopen(filename, "w+") as fp:
        fp.write("Hi hello! I am a file.")

    yield filename

    os.remove(filename)


@pytest.fixture
def myfile(tmp_sub_dir):
    filename = str(tmp_sub_dir / "myfile")

    with salt.utils.files.fopen(filename, "w+") as fp:
        fp.write(salt.utils.stringutils.to_str("Hello\n"))

    yield filename

    os.remove(filename)


@pytest.fixture
def a_link(tmp_sub_dir):
    path = tmp_sub_dir / "a_link"
    linkname = str(path)

    yield linkname

    if path.exists():
        os.remove(linkname)


@pytest.fixture
def a_hardlink(tmp_sub_dir):
    path = tmp_sub_dir / "a_hardlink"
    linkname = str(path)

    yield linkname

    if path.exists():
        os.remove(linkname)


@pytest.mark.skip_on_windows(reason="os.symlink is not available on Windows")
def test_symlink_already_in_desired_state(tfile, a_link):
    os.symlink(tfile, a_link)
    result = filemod.symlink(tfile, a_link)
    assert result


@pytest.mark.skip_on_windows(reason="os.link is not available on Windows")
def test_hardlink_sanity(tfile, a_hardlink):
    target = a_hardlink
    result = filemod.link(tfile, target)
    assert result


@pytest.mark.skip_on_windows(reason="os.link is not available on Windows")
def test_hardlink_numlinks(tfile, a_hardlink):
    target = a_hardlink
    result = filemod.link(tfile, target)
    name_i = os.stat(tfile).st_nlink
    assert name_i > 1


@pytest.mark.skip_on_windows(reason="os.link is not available on Windows")
def test_hardlink_working(tfile, a_hardlink):
    target = a_hardlink
    result = filemod.link(tfile, target)
    name_i = os.stat(tfile).st_ino
    target_i = os.stat(target).st_ino
    assert name_i == target_i


def test_source_list_for_list_returns_file_from_dict_via_http():
    with patch("salt.modules.file.os.remove") as remove:
        remove.return_value = None
        with patch.dict(
            filemod.__salt__,
            {
                "cp.list_master": MagicMock(return_value=[]),
                "cp.list_master_dirs": MagicMock(return_value=[]),
                "cp.cache_file": MagicMock(return_value="/tmp/http.conf"),
            },
        ):
            with patch("salt.utils.http.query") as http_query:
                http_query.return_value = {}
                ret = filemod.source_list(
                    [{"http://t.est.com/http/httpd.conf": "filehash"}], "", "base"
                )
                assert list(ret) == ["http://t.est.com/http/httpd.conf", "filehash"]


def test_source_list_use_requests():
    with patch("salt.modules.file.os.remove") as remove:
        remove.return_value = None
        with patch.dict(
            filemod.__salt__,
            {
                "cp.list_master": MagicMock(return_value=[]),
                "cp.list_master_dirs": MagicMock(return_value=[]),
                "cp.cache_file": MagicMock(return_value="/tmp/http.conf"),
            },
        ):
            expected_call = call(
                "http://t.est.com/http/file1",
                decode_body=False,
                method="HEAD",
            )
            with patch(
                "salt.utils.http.query", MagicMock(return_value={})
            ) as http_query:
                ret = filemod.source_list(
                    [{"http://t.est.com/http/file1": "filehash"}], "", "base"
                )
                assert list(ret) == ["http://t.est.com/http/file1", "filehash"]
                assert expected_call in http_query.mock_calls


def test_source_list_for_list_returns_existing_file():
    with patch.dict(
        filemod.__salt__,
        {
            "cp.list_master": MagicMock(return_value=["http/httpd.conf.fallback"]),
            "cp.list_master_dirs": MagicMock(return_value=[]),
        },
    ):
        ret = filemod.source_list(
            ["salt://http/httpd.conf", "salt://http/httpd.conf.fallback"],
            "filehash",
            "base",
        )
        assert list(ret) == ["salt://http/httpd.conf.fallback", "filehash"]


def test_source_list_for_list_returns_file_from_other_env():
    def list_master(env):
        dct = {"base": [], "dev": ["http/httpd.conf"]}
        return dct[env]

    with patch.dict(
        filemod.__salt__,
        {
            "cp.list_master": MagicMock(side_effect=list_master),
            "cp.list_master_dirs": MagicMock(return_value=[]),
        },
    ):
        ret = filemod.source_list(
            [
                "salt://http/httpd.conf?saltenv=dev",
                "salt://http/httpd.conf.fallback",
            ],
            "filehash",
            "base",
        )
        assert list(ret) == ["salt://http/httpd.conf?saltenv=dev", "filehash"]


def test_source_list_for_list_returns_file_from_dict():
    with patch.dict(
        filemod.__salt__,
        {
            "cp.list_master": MagicMock(return_value=["http/httpd.conf"]),
            "cp.list_master_dirs": MagicMock(return_value=[]),
        },
    ):
        ret = filemod.source_list([{"salt://http/httpd.conf": ""}], "filehash", "base")
        assert list(ret) == ["salt://http/httpd.conf", "filehash"]


def test_source_list_for_list_returns_existing_local_file_slash(myfile):
    with patch.dict(
        filemod.__salt__,
        {
            "cp.list_master": MagicMock(return_value=[]),
            "cp.list_master_dirs": MagicMock(return_value=[]),
        },
    ):
        ret = filemod.source_list([myfile + "-foo", myfile], "filehash", "base")
        assert list(ret) == [myfile, "filehash"]


def test_source_list_for_list_returns_existing_local_file_proto(myfile):
    with patch.dict(
        filemod.__salt__,
        {
            "cp.list_master": MagicMock(return_value=[]),
            "cp.list_master_dirs": MagicMock(return_value=[]),
        },
    ):
        ret = filemod.source_list(
            ["file://" + myfile + "-foo", "file://" + myfile],
            "filehash",
            "base",
        )
        assert list(ret) == ["file://" + myfile, "filehash"]


def test_source_list_for_list_returns_local_file_slash_from_dict(myfile):
    with patch.dict(
        filemod.__salt__,
        {
            "cp.list_master": MagicMock(return_value=[]),
            "cp.list_master_dirs": MagicMock(return_value=[]),
        },
    ):
        ret = filemod.source_list([{myfile: ""}], "filehash", "base")
        assert list(ret) == [myfile, "filehash"]


def test_source_list_for_list_returns_local_file_proto_from_dict(myfile):
    with patch.dict(
        filemod.__salt__,
        {
            "cp.list_master": MagicMock(return_value=[]),
            "cp.list_master_dirs": MagicMock(return_value=[]),
        },
    ):
        ret = filemod.source_list([{"file://" + myfile: ""}], "filehash", "base")
        assert list(ret) == ["file://" + myfile, "filehash"]
