"""
Parametrize winrepo's common path across all three providers.

Prior to this test only ``test_winrepo.py`` covered winrepo under
``gitpython`` + ``pygit2`` on the remote github.com repo. The gitcli
coverage introduced by PR #70852 is checkout-presence only; it does not
compare the on-disk listing to the other providers for the same source
tree. This module checks all three producers land the same set of
package-definition files for the same bare repo so a future provider
divergence (as gitcli had before #70852) shows up as a diff.
"""

import pathlib
import shutil
import subprocess

import pytest

import salt.utils.gitfs as utils_gitfs
from salt.utils.gitfs import WinRepo
from salt.utils.immutabletypes import ImmutableDict, ImmutableList

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(
        shutil.which("git") is None, reason="system git binary required"
    ),
]


@pytest.fixture(scope="module")
def winrepo_remote(tmp_path_factory):
    """Local bare repo that mimics the layout of salt-winrepo-ng."""
    root = tmp_path_factory.mktemp("winrepo-matrix")
    work = root / "work"
    bare = root / "bare.git"
    work.mkdir()

    def _git(*args):
        subprocess.run(
            ["git", "-C", str(work), *args],
            check=True,
            capture_output=True,
        )

    _git("init", "-q", "-b", "master")
    _git("config", "user.email", "salt-test@example.invalid")
    _git("config", "user.name", "Salt Test")
    _git("config", "commit.gpgsign", "false")
    # Three package definitions and a nested one so we see directory
    # traversal, not just a top-level listing.
    (work / "firefox.sls").write_text("firefox:\n  '*':\n    installer: ff\n")
    (work / "7zip.sls").write_text("7zip:\n  '*':\n    installer: 7z\n")
    subdir = work / "office"
    subdir.mkdir()
    (subdir / "libreoffice.sls").write_text("libreoffice:\n  '*':\n    installer: lo\n")
    _git("add", ".")
    _git("commit", "-q", "-m", "seed winrepo")

    _git("clone", "-q", "--bare", str(work), str(bare))
    return bare.as_uri()


def _provider_params():
    return [
        pytest.param(
            "gitpython",
            marks=pytest.mark.skipif(
                utils_gitfs.GITPYTHON_VERSION is None, reason="gitpython not installed"
            ),
            id="gitpython",
        ),
        pytest.param(
            "pygit2",
            marks=pytest.mark.skipif(
                utils_gitfs.PYGIT2_VERSION is None, reason="pygit2 not installed"
            ),
            id="pygit2",
        ),
        pytest.param(
            "gitcli",
            marks=pytest.mark.xfail(
                strict=False,
                reason=(
                    "GitCLI does not write worktree files to disk for "
                    "winrepo on 3008.x; fix lands with #70852. When that "
                    "lands these params will XPASS; remove this marker."
                ),
            ),
            id="gitcli",
        ),
    ]


@pytest.fixture
def winrepo_opts(salt_factories, tmp_path, request):
    provider = request.param
    factory = salt_factories.salt_master_daemon(
        f"winrepo-matrix-master-{provider}",
        defaults={"cachedir": str(tmp_path / "cache")},
    )
    opts = dict(factory.config)
    # Unwrap the immutable types so WinRepo can mutate them.
    for key, item in list(opts.items()):
        if isinstance(item, ImmutableDict):
            opts[key] = dict(item)
        elif isinstance(item, ImmutableList):
            opts[key] = list(item)
    opts["cachedir"] = str(tmp_path / "cache")
    opts["winrepo_provider"] = provider
    opts["winrepo_branch"] = "master"
    return opts


def _list_sls(repo_dir):
    """Return sorted relative paths of *.sls under ``repo_dir``."""
    root = pathlib.Path(repo_dir)
    return sorted(str(p.relative_to(root)) for p in root.rglob("*.sls") if p.is_file())


def _only_winrepo_dir(repo):
    """Return the single checkout dir from a WinRepo instance."""
    dirs = list(repo.winrepo_dirs.values())
    assert len(dirs) == 1, f"expected 1 winrepo dir, got {dirs!r}"
    return dirs[0]


@pytest.mark.parametrize("winrepo_opts", _provider_params(), indirect=True)
def test_winrepo_checkout_lists_all_packages(winrepo_opts, winrepo_remote):
    """All three providers must produce the same checkout output."""
    repo = WinRepo(winrepo_opts, [winrepo_remote])
    repo.fetch_remotes()
    repo.checkout()
    listed = _list_sls(_only_winrepo_dir(repo))
    assert listed == ["7zip.sls", "firefox.sls", "office/libreoffice.sls"]


@pytest.mark.parametrize("winrepo_opts", _provider_params(), indirect=True)
def test_winrepo_file_contents_match(winrepo_opts, winrepo_remote):
    """Byte-for-byte the files in the checkout dir must match the source."""
    repo = WinRepo(winrepo_opts, [winrepo_remote])
    repo.fetch_remotes()
    repo.checkout()
    winrepo_dir = _only_winrepo_dir(repo)
    firefox = pathlib.Path(winrepo_dir) / "firefox.sls"
    assert firefox.read_text(encoding="utf-8") == (
        "firefox:\n  '*':\n    installer: ff\n"
    )
    libreoffice = pathlib.Path(winrepo_dir) / "office" / "libreoffice.sls"
    assert libreoffice.read_text(encoding="utf-8") == (
        "libreoffice:\n  '*':\n    installer: lo\n"
    )


@pytest.mark.parametrize("winrepo_opts", _provider_params(), indirect=True)
def test_winrepo_checkout_is_idempotent(winrepo_opts, winrepo_remote):
    """Re-running checkout must not break the on-disk tree."""
    repo = WinRepo(winrepo_opts, [winrepo_remote])
    repo.fetch_remotes()
    repo.checkout()
    first = _list_sls(next(iter(repo.winrepo_dirs.values())))

    repo2 = WinRepo(winrepo_opts, [winrepo_remote])
    repo2.fetch_remotes()
    repo2.checkout()
    second = _list_sls(next(iter(repo2.winrepo_dirs.values())))

    assert first == second == ["7zip.sls", "firefox.sls", "office/libreoffice.sls"]
