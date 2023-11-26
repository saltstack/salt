import shutil
import tempfile
from pathlib import Path

import psutil  # pylint: disable=3rd-party-module-not-gated
import pytest
from pytestshellutils.utils.processes import terminate_process

import salt.fileserver.hgfs as hgfs
from tests.support.mock import patch

try:
    import hglib

    HAS_HG = True
except ImportError:
    HAS_HG = False


@pytest.fixture(scope="module")
def configure_loader_modules(master_opts):
    master_opts["fileserver_backend"] = ["hgfs"]
    yield {hgfs: {"__opts__": master_opts}}


@pytest.fixture
def hgfs_setup_and_teardown():
    """
    build up and tear down hg repos to test with.
    """
    initial_child_processes = psutil.Process().children()
    source_dir = Path(__file__).resolve().parent.joinpath("files")
    tempdir = tempfile.TemporaryDirectory()
    tempsubdir = tempdir.name / Path("subdir/")
    tempsubdir.mkdir()
    tempdirPath = Path(tempdir.name)
    for file in source_dir.iterdir():
        to_file = tempdirPath / file.name
        to_file2 = tempsubdir / file.name
        shutil.copy(file.as_posix(), to_file.as_posix())
        shutil.copy(file.as_posix(), to_file2.as_posix())

    client = hglib.init(bytes(tempdirPath.as_posix(), encoding="utf8"))
    client.close()
    with hglib.open(bytes(tempdirPath.as_posix(), encoding="utf8")) as repo:
        repo.add(bytes(tempdirPath.as_posix(), encoding="utf8"))
        repo.commit(b"init commit", user="test")
        repo.tag(b"test", user="test")
        repo.branch(b"test")
        repo.commit(b"create test branch", user="test")
        repo.bookmark(b"bookmark_test")
    try:
        yield tempdirPath.as_uri()
    finally:
        tempdir.cleanup()
        for child in psutil.Process().children():
            if child not in initial_child_processes:
                terminate_process(process=child, kill_children=True)


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_fix_58852(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        repo = hgfs.init()
        assert isinstance(repo, list)
        if isinstance(repo, list):
            for value in repo:
                assert isinstance(value, dict)
                for key, value in value.items():
                    if key != "repo":
                        assert isinstance(value, str)


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_all_branches(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        repos = hgfs.init()
        hgfs.update()
        for repo in repos:
            repo["repo"].open()
            branches = hgfs._all_branches(repo["repo"])
            assert isinstance(branches, list)
            if isinstance(branches, list):
                for value in branches:
                    assert isinstance(value, tuple)
                    assert len(value) == 3
                    assert value[0] in ["default", "test"]
                    assert isinstance(value[1], int)
                    assert isinstance(value[2], str)


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_get_branch(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        repo = hgfs.init()
        hgfs.update()
        repo[0]["repo"].open()
        branch = hgfs._get_branch(repo[0]["repo"], "test")
        assert isinstance(branch, tuple)
        assert len(branch) == 3
        assert branch[0] in "test"
        assert branch[1] == 2
        assert isinstance(branch[2], str)

        # Fail test
        branch = hgfs._get_branch(repo[0]["repo"], "fake")
        assert branch is False


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_all_bookmarks(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        repos = hgfs.init()
        hgfs.update()
        for repo in repos:
            repo["repo"].open()
            bookmarks = hgfs._all_bookmarks(repo["repo"])
            assert isinstance(bookmarks, list)
            if isinstance(bookmarks, list):
                for value in bookmarks:
                    assert isinstance(value, tuple)
                    assert len(value) == 3
                    assert value[0] in ["bookmark_test"]
                    assert value[1] == 2
                    assert isinstance(value[2], str)


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_get_bookmark(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        repo = hgfs.init()
        hgfs.update()
        repo[0]["repo"].open()
        bookmark = hgfs._get_bookmark(repo[0]["repo"], "bookmark_test")
        assert isinstance(bookmark, tuple)
        assert len(bookmark) == 3
        assert bookmark[0] in "bookmark_test"
        assert bookmark[1] == 2
        assert isinstance(bookmark[2], str)

        # Fail test
        bookmark = hgfs._get_bookmark(repo[0]["repo"], "fake")
        assert bookmark is False


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_all_tags(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        repos = hgfs.init()
        hgfs.update()
        for repo in repos:
            repo["repo"].open()
            tags = hgfs._all_tags(repo["repo"])
            assert isinstance(tags, list)
            if isinstance(tags, list):
                for value in tags:
                    assert isinstance(value, tuple)
                    assert len(value) == 4
                    assert value[0] in ["test"]
                    assert value[0] not in ["tip"]
                    assert value[1] == 0
                    assert isinstance(value[2], str)
                    assert value[3] is False


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_get_tag(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        repo = hgfs.init()
        hgfs.update()
        repo[0]["repo"].open()
        tag = hgfs._get_tag(repo[0]["repo"], "test")
        assert isinstance(tag, tuple)
        assert len(tag) == 4
        assert tag[0] in "test"
        assert tag[1] == 0
        assert isinstance(tag[2], str)

        # Fail test
        tag = hgfs._get_tag(repo[0]["repo"], "fake")
        assert tag is False

        # real tag that should fail
        tag = hgfs._get_tag(repo[0]["repo"], "tip")
        assert tag is False


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_get_ref(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        repo = hgfs.init()[0]
        hgfs.update()
        repo["repo"].open()
        ref = hgfs._get_ref(repo, "base")
        assert isinstance(ref, tuple)
        assert len(ref) == 3
        assert ref[0] == "default"
        assert ref[1] == 1
        assert isinstance(ref[2], str)

    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [
                {str(hgfs_setup_and_teardown): [{"base": "bookmark_test"}]}
            ],
            "hgfs_branch_method": "bookmarks",
        },
    ):
        repo = hgfs.init()[0]
        hgfs.update()
        repo["repo"].open()
        ref = hgfs._get_ref(repo, "base")
        assert isinstance(ref, tuple)
        assert len(ref) == 3
        assert ref[0] in "bookmark_test"
        assert ref[1] == 2
        assert isinstance(ref[2], str)

    # Fail test
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        repo = hgfs.init()[0]
        hgfs.update()
        repo["repo"].open()
        ref = hgfs._get_ref(repo, "fake")
        assert ref is False


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_get_manifest(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        repo = hgfs.init()[0]
        hgfs.update()
        repo["repo"].open()
        ref = hgfs._get_ref(repo, "base")
        manifest = hgfs._get_manifest(repo["repo"], ref=ref)
        assert isinstance(manifest, list)
        for value in manifest:
            assert len(value) == 5
            assert isinstance(value[0], str)
            assert value[1] == "644"
            assert value[2] is False
            assert value[3] is False
            assert value[4] in [
                "test.sls",
                "test2.sls",
                ".hgtags",
                "subdir/test.sls",
                "subdir/test2.sls",
            ]


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_envs(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
            "hgfs_branch_method": "branches",
        },
    ):
        hgfs.init()
        hgfs.update()
        envs = hgfs.envs(ignore_cache=True)
        assert isinstance(envs, list)
        assert envs == ["base", "test"]
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [
                {str(hgfs_setup_and_teardown): [{"base": "bookmark_test"}]}
            ],
            "hgfs_branch_method": "bookmarks",
        },
    ):
        hgfs.init()
        hgfs.update()
        envs = hgfs.envs(ignore_cache=True)
        assert isinstance(envs, list)

        # apperently test is coming from the tags which will always be included in the envs unless blacklisted.
        # Do we really want that behavior?
        assert envs == ["base", "test"]


@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_env_is_exposed_blacklist():
    with patch.dict(
        hgfs.__opts__,
        {"hgfs_saltenv_whitelist": "", "hgfs_saltenv_blacklist": "test"},
    ):
        hgfs.init()
        hgfs.update()
        assert hgfs._env_is_exposed("base") is True
        assert hgfs._env_is_exposed("test") is False
        assert hgfs._env_is_exposed("unset") is True


@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_env_is_exposed_whitelist():
    with patch.dict(
        hgfs.__opts__,
        {"hgfs_saltenv_whitelist": "base", "hgfs_saltenv_blacklist": ""},
    ):
        hgfs.init()
        hgfs.update()
        assert hgfs._env_is_exposed("base") is True
        assert hgfs._env_is_exposed("test") is False
        assert hgfs._env_is_exposed("unset") is False


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_find_file(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        hgfs.init()
        hgfs.update()
        file = hgfs.find_file(path="test.sls", tgt_env="base")
        assert file["path"] == hgfs.__opts__["cachedir"] + "/hgfs/refs/base/test.sls"
        assert file["rel"] == "test.sls"
        assert isinstance(file["stat"], list)
        for i in file["stat"]:
            assert isinstance(i, int)


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_serve_file(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        hgfs.init()
        hgfs.update()
        file = hgfs.find_file(path="test.sls", tgt_env="base")
        load = {"saltenv": "base", "loc": 0, "path": "test.sls"}
        data = hgfs.serve_file(load, file)
        assert data == {
            "data": "always-passes:\n  test.succeed_without_changes:\n    - name: foo\n",
            "dest": "test.sls",
        }


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_file_hash(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        hgfs.init()
        hgfs.update()
        file = hgfs.find_file(path="test.sls", tgt_env="base")
        load = {"saltenv": "base", "loc": 0, "path": "test.sls"}
        data = hgfs.file_hash(load, file)
        assert data == {
            "hash_type": "sha256",
            "hsum": "a6a48d90dce9c9b580efb2ed308af100a8328913dcf9441705125866551c7d8d",
        }


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_file_list(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        hgfs.init()
        hgfs.update()
        load = {"saltenv": "base", "loc": 0, "path": "test.sls"}
        data = hgfs.file_list(load)
        assert data == [
            ".hgtags",
            "subdir/test.sls",
            "subdir/test2.sls",
            "test.sls",
            "test2.sls",
        ]


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="testing break in windows")
def test_dir_list(hgfs_setup_and_teardown):
    with patch.dict(
        hgfs.__opts__,
        {
            "hgfs_remotes": [{str(hgfs_setup_and_teardown): [{"base": "default"}]}],
        },
    ):
        hgfs.init()
        hgfs.update()
        load = {"saltenv": "base", "loc": 0, "path": "test.sls"}
        data = hgfs.dir_list(load)
        assert data == ["subdir"]
