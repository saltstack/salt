import pytest
import salt.utils.gitfs
from salt.runners import winrepo
from tests.support.mock import patch

pytestmark = [pytest.mark.windows_whitelisted]


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        winrepo: {
            "__opts__": minion_opts,
        }
    }


@pytest.fixture
def winrepo_remotes(minion_opts):
    winrepo_remotes = minion_opts.get("winrepo_remotes", [])
    winrepo_remotes_ng = minion_opts.get("winrepo_remotes_ng", [])
    winrepo_remotes.extend(winrepo_remotes_ng)
    return winrepo_remotes


def test_update_git_repos(winrepo_remotes):
    """
    Ensure update git repos works as intended.
    """
    res = winrepo.update_git_repos()

    assert res

    for remote in winrepo_remotes:
        assert remote in res
        assert res[remote]


def test_legacy_update_git_repos(winrepo_remotes):
    """
    Ensure update git repos works as intended with legacy (non-gitfs) code.
    """
    with patch.object(salt.utils.gitfs, "GITPYTHON_VERSION", False):
        with patch.object(salt.utils.gitfs, "PYGIT2_VERSION", False):
            res = winrepo.update_git_repos()

            assert res

            for remote in winrepo_remotes:
                assert remote in res
                assert res[remote]
