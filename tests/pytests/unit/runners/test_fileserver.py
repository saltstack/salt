"""
unit tests for the fileserver runner
"""


import pytest

import salt.loader
import salt.runners.fileserver as fileserver
import salt.utils.files
from tests.support.mock import MagicMock, patch


class DummyFS:
    """
    Dummy object to provide the attributes needed to run unit tests
    """

    def __init__(self, backends):
        self.backends = backends

    def keys(self):
        return ["{}.envs".format(x) for x in self.backends]


@pytest.fixture
def cachedir(tmp_path):
    return tmp_path / "cache"


@pytest.fixture
def configure_loader_modules():
    return {fileserver: {"__opts__": {"extension_modules": ""}}}


def _make_file_lists_cache(cachedir, backends):
    """
    Create some dummy files to represent file list caches, as well as other
    files that aren't file list caches, so that we can confirm that *only*
    the cache files are touched. Create a dir for each configured backend,
    as well as for the roots backend (which is *not* configured as a
    backend in this test), so that we can ensure that its cache is left
    alone.
    """
    for back in backends:
        back_cachedir = cachedir / "file_lists" / back
        back_cachedir.mkdir(parents=True, exist_ok=True)
        for filename in ("base.p", "dev.p", "foo.txt"):
            (back_cachedir / filename).touch()


def test_clear_file_list_cache_vcs(cachedir):
    """
    Test that VCS backends are cleared irrespective of whether they are
    configured as gitfs/git, hgfs/hg, svnfs/svn.
    """
    # Mixture of VCS backends specified with and without "fs" at the end,
    # to confirm that the correct dirs are cleared.
    backends = ["gitfs", "hg", "svnfs"]
    opts = {
        "fileserver_backend": backends,
        "cachedir": str(cachedir),
    }
    mock_fs = DummyFS(backends)

    _make_file_lists_cache(cachedir, backends + ["roots"])

    with patch.dict(fileserver.__opts__, opts), patch.object(
        salt.loader, "fileserver", MagicMock(return_value=mock_fs)
    ):
        cleared = fileserver.clear_file_list_cache()

    # Make sure the return data matches what you'd expect
    expected = {
        "gitfs": ["base", "dev"],
        "hg": ["base", "dev"],
        "svnfs": ["base", "dev"],
    }
    assert cleared == expected, cleared

    # Trust, but verify! Check that the correct files are actually gone
    assert not (cachedir / "file_lists" / "gitfs" / "base.p").exists()
    assert not (cachedir / "file_lists" / "gitfs" / "dev.p").exists()
    assert not (cachedir / "file_lists" / "hg" / "base.p").exists()
    assert not (cachedir / "file_lists" / "gitfs" / "dev.p").exists()
    assert not (cachedir / "file_lists" / "hg" / "base.p").exists()
    assert not (cachedir / "file_lists" / "svnfs" / "dev.p").exists()

    # These files *should* exist and shouldn't have been cleaned
    assert (cachedir / "file_lists" / "gitfs" / "foo.txt").exists()
    assert (cachedir / "file_lists" / "hg" / "foo.txt").exists()
    assert (cachedir / "file_lists" / "svnfs" / "foo.txt").exists()
    assert (cachedir / "file_lists" / "roots" / "base.p").exists()
    assert (cachedir / "file_lists" / "roots" / "dev.p").exists()
    assert (cachedir / "file_lists" / "roots" / "foo.txt").exists()


def test_clear_file_list_cache_vcs_limited(cachedir):
    """
    Test the arguments to limit what is cleared
    """
    # Mixture of VCS backends specified with and without "fs" at the end,
    # to confirm that the correct dirs are cleared.
    backends = ["gitfs", "hg", "svnfs"]
    opts = {
        "fileserver_backend": backends,
        "cachedir": str(cachedir),
    }
    mock_fs = DummyFS(backends)

    _make_file_lists_cache(cachedir, backends + ["roots"])

    with patch.dict(fileserver.__opts__, opts), patch.object(
        salt.loader, "fileserver", MagicMock(return_value=mock_fs)
    ):
        cleared = fileserver.clear_file_list_cache(saltenv="base", backend="gitfs")

    expected = {"gitfs": ["base"]}
    assert cleared == expected, cleared

    # Trust, but verify! Check that the correct files are actually gone
    assert not (cachedir / "file_lists" / "gitfs" / "base.p").exists()

    # These files *should* exist and shouldn't have been cleaned
    assert (cachedir / "file_lists" / "gitfs" / "dev.p").exists()
    assert (cachedir / "file_lists" / "gitfs" / "foo.txt").exists()
    assert (cachedir / "file_lists" / "hg" / "base.p").exists()
    assert (cachedir / "file_lists" / "hg" / "dev.p").exists()
    assert (cachedir / "file_lists" / "hg" / "foo.txt").exists()
    assert (cachedir / "file_lists" / "svnfs" / "base.p").exists()
    assert (cachedir / "file_lists" / "svnfs" / "dev.p").exists()
    assert (cachedir / "file_lists" / "svnfs" / "foo.txt").exists()
    assert (cachedir / "file_lists" / "roots" / "base.p").exists()
    assert (cachedir / "file_lists" / "roots" / "dev.p").exists()
    assert (cachedir / "file_lists" / "roots" / "foo.txt").exists()
