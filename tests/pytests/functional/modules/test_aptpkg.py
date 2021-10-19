import pathlib
import shutil

import pytest
import salt.exceptions
import salt.modules.aptpkg as aptpkg
import salt.modules.cmdmod as cmd
import salt.modules.file as file
import salt.utils.files
import salt.utils.stringutils
from tests.support.mock import Mock, patch

pytestmark = [
    pytest.mark.skip_if_binaries_missing("apt-cache", "grep"),
]


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        aptpkg: {
            "__salt__": {
                "cmd.run_all": cmd.run_all,
                "cmd.run": cmd.run,
                "file.replace": file.replace,
                "file.append": file.append,
                "file.grep": file.grep,
            },
            "__opts__": minion_opts,
        },
        file: {
            "__salt__": {"cmd.run_all": cmd.run_all},
            "__utils__": {
                "files.is_text": salt.utils.files.is_text,
                "stringutils.get_diff": salt.utils.stringutils.get_diff,
            },
            "__opts__": minion_opts,
        },
    }


@pytest.fixture()
def revert_repo_file(tmp_path):
    try:
        repo_file = pathlib.Path("/etc") / "apt" / "sources.list"
        backup = tmp_path / "repo_backup"
        # make copy of repo file
        shutil.copy(str(repo_file), str(backup))
        yield
    finally:
        # revert repo file
        shutil.copy(str(backup), str(repo_file))
        aptpkg.refresh_db()


def get_current_repo(multiple_comps=False):
    """
    Get a repo currently in sources.list

    multiple_comps:
        Search for a repo that contains multiple comps.
        For example: main, restricted
    """
    with salt.utils.files.fopen("/etc/apt/sources.list") as fp:
        for line in fp:
            if line.startswith("#"):
                continue
            if "ubuntu.com" in line or "debian.org" in line:
                test_repo = line.strip()
                comps = test_repo.split()[3:]
                if multiple_comps:
                    if len(comps) > 1:
                        break
                else:
                    break
    return test_repo, comps


def test_list_repos():
    """
    Test aptpkg.list_repos
    """
    ret = aptpkg.list_repos()
    repos = [x for x in ret if "http" in x]
    for repo in repos:
        check_repo = ret[repo][0]
        for key in [
            "comps",
            "dist",
            "uri",
            "line",
            "architectures",
            "file",
            "type",
        ]:
            assert key in check_repo
        assert pathlib.Path(check_repo["file"]).is_file()
        assert check_repo["dist"] in check_repo["line"]
        if isinstance(check_repo["comps"], list):
            assert " ".join(check_repo["comps"]) in check_repo["line"]
        else:
            assert check_repo["comps"] in check_repo["line"]


def test_get_repos():
    """
    Test aptpkg.get_repos
    """
    test_repo, comps = get_current_repo()
    if not test_repo:
        pytest.skip("Did not detect an apt repo")
    exp_ret = test_repo.split()
    ret = aptpkg.get_repo(repo=test_repo)
    assert ret["type"] == exp_ret[0]
    assert ret["uri"] == exp_ret[1]
    assert ret["dist"] == exp_ret[2]
    assert ret["comps"] == exp_ret[3:]
    assert ret["file"] == "/etc/apt/sources.list"


def test_get_repos_multiple_comps():
    """
    Test aptpkg.get_repos when multiple comps
    exist in repo.
    """
    test_repo, comps = get_current_repo(multiple_comps=True)
    if not test_repo:
        pytest.skip("Did not detect an ubuntu repo")
    exp_ret = test_repo.split()
    ret = aptpkg.get_repo(repo=test_repo)
    assert ret["type"] == exp_ret[0]
    assert ret["uri"] == exp_ret[1]
    assert ret["dist"] == exp_ret[2]
    assert ret["comps"] == exp_ret[3:]


def test_get_repos_doesnot_exist():
    """
    Test aptpkg.get_repos when passing a repo
    that does not exist
    """
    for test_repo in [
        "doesnotexist",
        "deb http://archive.ubuntu.com/ubuntu/ focal-backports compdoesnotexist",
    ]:
        ret = aptpkg.get_repo(repo=test_repo)
        assert not ret


@pytest.mark.skip_if_binaries_missing("apt-add-repository")
@pytest.mark.destructive_test
def test_del_repo(revert_repo_file):
    """
    Test aptpkg.del_repo when passing repo
    that exists. And checking correct error
    is returned when it no longer exists.
    """
    test_repo, comps = get_current_repo()
    ret = aptpkg.del_repo(repo=test_repo)
    assert "Repo '{}' has been removed".format(test_repo)
    with pytest.raises(salt.exceptions.CommandExecutionError) as exc:
        ret = aptpkg.del_repo(repo=test_repo)
    assert "Repo {} doesn't exist".format(test_repo) in exc.value.message


def test_expand_repo_def():
    """
    Test aptpkg.expand_repo_def when the repo exists.
    """
    test_repo, comps = get_current_repo()
    ret = aptpkg.expand_repo_def(repo=test_repo)
    for key in [
        "comps",
        "dist",
        "uri",
        "line",
        "architectures",
        "file",
        "type",
    ]:
        assert key in ret
        assert pathlib.Path(ret["file"]).is_file()
        assert ret["dist"] in ret["line"]
        if isinstance(ret["comps"], list):
            for comp in ret["comps"]:
                assert comp in ret["line"]
        else:
            assert ret["comps"] in ret["line"]


@pytest.mark.destructive_test
def test_mod_repo(revert_repo_file):
    """
    Test aptpkg.mod_repo when the repo exists.
    """
    test_repo, comps = get_current_repo()
    msg = "This is a test"
    with patch.dict(aptpkg.__salt__, {"config.option": Mock()}):
        ret = aptpkg.mod_repo(repo=test_repo, comments=msg)
    assert sorted(ret[list(ret.keys())[0]]["comps"]) == sorted(comps)
    ret = file.grep("/etc/apt/sources.list", msg)
    assert "#{}".format(msg) in ret["stdout"]


@pytest.mark.destructive_test
def test_mod_repo_no_file(tmp_path, revert_repo_file):
    """
    Test aptpkg.mod_repo when the file does not exist.
    It should create the file.
    """
    test_repo, comps = get_current_repo()
    test_file = str(tmp_path / "test_repo")
    with patch.dict(aptpkg.__salt__, {"config.option": Mock()}):
        ret = aptpkg.mod_repo(repo=test_repo, file=test_file)
    with salt.utils.files.fopen(test_file, "r") as fp:
        ret = fp.read()
    assert test_repo.split()[1] in ret.strip()
    for comp in comps:
        assert comp in ret
