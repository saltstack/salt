import os

import pytest

from salt.runners import winrepo
from tests.support.mock import patch

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def configure_loader_modules(minion_opts, tmp_path):
    winrepo_dir = tmp_path / "winrepo"
    winrepo_dir.mkdir()
    winrepo_dir_ng = tmp_path / "winrepo_ng"
    winrepo_dir_ng.mkdir()
    minion_opts["winrepo_dir"] = str(winrepo_dir)
    minion_opts["winrepo_dir_ng"] = str(winrepo_dir_ng)
    return {winrepo: {"__opts__": minion_opts}}


@pytest.fixture
def winrepo_remotes(minion_opts):
    remotes = set()
    remotes.update(minion_opts.get("winrepo_remotes", []))
    remotes.update(minion_opts.get("winrepo_remotes_ng", []))
    return remotes


def test_update_git_repos(winrepo_remotes):
    """
    Ensure update git repos works as intended.
    """
    res = winrepo.update_git_repos()
    assert res

    for remote in winrepo_remotes:
        assert remote in res
        assert res[remote]

        # Make sure there are package definitions in the root
        assert res[remote].endswith("_")
        pkg_def = os.path.join(res[remote], "7zip.sls")
        assert os.path.exists(pkg_def)


def test_legacy_update_git_repos(winrepo_remotes, minion_opts):
    """
    Ensure update git repos works as intended with legacy (non-gitfs) code.
    """
    with patch.object(winrepo, "_legacy_git", return_value=True):
        res = winrepo.update_git_repos()

        assert res

        for remote in winrepo_remotes:
            assert remote in res
            assert res[remote]

            # Make sure there are package definitions in the root
            # We have to look up the actual repo dir here because the legacy
            # update only returns True or False, not a path
            if "-ng" in remote:
                path = minion_opts["winrepo_dir_ng"]
                pkg_def = os.path.join(path, "salt-winrepo-ng", "_", "7zip.sls")
            else:
                path = minion_opts["winrepo_dir"]
                pkg_def = os.path.join(path, "salt-winrepo", "_", "7zip.sls")

            assert os.path.exists(pkg_def)
