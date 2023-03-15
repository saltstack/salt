"""
    :codeauthor: Erik Johnson <erik@saltstack.com>
"""


import copy
import logging
import os
import subprocess

import pytest

import salt.modules.git as git_mod  # Don't potentially shadow GitPython
from salt.utils.versions import Version
from tests.support.mock import MagicMock, Mock, patch

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def worktree_root():
    return "/tmp/salt-tests-tmpdir/main"


@pytest.fixture(scope="module")
def worktree_info(worktree_root):
    worktree_info = {
        worktree_root: {
            "HEAD": "119f025073875a938f2456f5ffd7d04e79e5a427",
            "branch": "refs/heads/master",
            "stale": False,
        },
        "/tmp/salt-tests-tmpdir/worktree1": {
            "HEAD": "d8d19cf75d7cc3bdc598dc2d472881d26b51a6bf",
            "branch": "refs/heads/worktree1",
            "stale": False,
        },
        "/tmp/salt-tests-tmpdir/worktree2": {
            "HEAD": "56332ca504aa8b37bb62b54272d52b1d6d832629",
            "branch": "refs/heads/worktree2",
            "stale": True,
        },
        "/tmp/salt-tests-tmpdir/worktree3": {
            "HEAD": "e148ea2d521313579f661373fbb93a48a5a6d40d",
            "branch": "detached",
            "tags": ["v1.1"],
            "stale": False,
        },
        "/tmp/salt-tests-tmpdir/worktree4": {
            "HEAD": "6bbac64d3ad5582b3147088a708952df185db020",
            "branch": "detached",
            "stale": True,
        },
    }

    return worktree_info


def _git_version():
    git_version = subprocess.Popen(
        ["git", "--version"],
        shell=False,
        close_fds=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).communicate()[0]
    if not git_version:
        log.error("Git not installed")
        return False
    log.debug("Detected git version %s", git_version)
    return Version(git_version.split()[-1])


@pytest.fixture
def configure_loader_modules():
    return {git_mod: {"__utils__": {"ssh.key_is_encrypted": Mock(return_value=False)}}}


def test_list_worktrees(worktree_info, worktree_root):
    """
    This tests git.list_worktrees
    """

    def _build_worktree_output(path):
        """
        Build 'git worktree list' output for a given path
        """
        return "worktree {}\nHEAD {}\n{}\n".format(
            path,
            worktree_info[path]["HEAD"],
            "branch {}".format(worktree_info[path]["branch"])
            if worktree_info[path]["branch"] != "detached"
            else "detached",
        )

    # Build dict for _cmd_run_side_effect below. Start with the output from
    # 'git worktree list'.
    _cmd_run_values = {
        "git worktree list --porcelain": "\n".join(
            [_build_worktree_output(x) for x in worktree_info]
        ),
        "git --version": "git version 2.7.0",
    }
    # Add 'git tag --points-at' output for detached HEAD worktrees with
    # tags pointing at HEAD.
    for path in worktree_info:
        if worktree_info[path]["branch"] != "detached":
            continue
        key = "git tag --points-at " + worktree_info[path]["HEAD"]
        _cmd_run_values[key] = "\n".join(worktree_info[path].get("tags", []))

    def _cmd_run_side_effect(key, **kwargs):
        # Not using dict.get() here because we want to know if
        # _cmd_run_values doesn't account for all uses of cmd.run_all.
        return {
            "stdout": _cmd_run_values[" ".join(key)],
            "stderr": "",
            "retcode": 0,
            "pid": 12345,
        }

    def _isdir_side_effect(key):
        # os.path.isdir() would return True on a non-stale worktree
        return not worktree_info[key].get("stale", False)

    # Build return dict for comparison
    worktree_ret = copy.deepcopy(worktree_info)
    for key in worktree_ret:
        ptr = worktree_ret.get(key)
        ptr["detached"] = ptr["branch"] == "detached"
        ptr["branch"] = (
            None if ptr["detached"] else ptr["branch"].replace("refs/heads/", "", 1)
        )

    cmd_run_mock = MagicMock(side_effect=_cmd_run_side_effect)
    isdir_mock = MagicMock(side_effect=_isdir_side_effect)
    with patch.dict(git_mod.__salt__, {"cmd.run_all": cmd_run_mock}):
        with patch.object(os.path, "isdir", isdir_mock):
            # Test all=True. Include all return data.
            assert (
                git_mod.list_worktrees(worktree_root, all=True, stale=False)
                == worktree_ret
            )
            # Test all=False and stale=False. Exclude stale worktrees from
            # return data.
            assert git_mod.list_worktrees(worktree_root, all=False, stale=False) == {
                x: worktree_ret[x]
                for x in worktree_info
                if not worktree_info[x].get("stale", False)
            }
            # Test stale=True. Exclude non-stale worktrees from return
            # data.
            assert git_mod.list_worktrees(worktree_root, all=False, stale=True) == {
                x: worktree_ret[x]
                for x in worktree_info
                if worktree_info[x].get("stale", False)
            }


def test__git_run_tmp_wrapper():
    """
    When an identity file is specified, make sure we don't attempt to
    remove a temp wrapper that wasn't created. Windows doesn't use temp
    wrappers, and *NIX won't unless no username was specified and the path
    is not executable.
    """
    file_remove_mock = Mock()
    mock_true = Mock(return_value=True)
    mock_false = Mock(return_value=False)
    cmd_mock = MagicMock(return_value={"retcode": 0, "stdout": "", "stderr": ""})
    with patch.dict(
        git_mod.__salt__,
        {
            "file.file_exists": mock_true,
            "file.remove": file_remove_mock,
            "cmd.run_all": cmd_mock,
            "ssh.key_is_encrypted": mock_false,
        },
    ):

        # Non-windows
        with patch("salt.utils.platform.is_windows", mock_false), patch.object(
            git_mod, "_path_is_executable_others", mock_true
        ):

            # Command doesn't really matter here since we're mocking
            git_mod._git_run(
                ["git", "rev-parse", "HEAD"],
                cwd="/some/path",
                user=None,
                identity="/root/.ssh/id_rsa",
            )

            file_remove_mock.assert_not_called()

        file_remove_mock.reset_mock()
        with patch("salt.utils.platform.is_windows", mock_true), patch.object(
            git_mod, "_find_ssh_exe", MagicMock(return_value=r"C:\Git\ssh.exe")
        ):
            # Command doesn't really matter here since we're mocking
            git_mod._git_run(
                ["git", "rev-parse", "HEAD"],
                cwd=r"C:\some\path",
                user=None,
                identity=r"C:\ssh\id_rsa",
            )

            file_remove_mock.assert_not_called()
