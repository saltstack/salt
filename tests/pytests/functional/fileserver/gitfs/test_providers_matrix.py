"""
Parametrize gitfs's common path across all three documented providers.

Prior to this test only ``test_documented_providers.py`` loaded gitfs under
``gitpython`` and ``pygit2`` on a local bare repo. The ``gitcli`` provider
was covered by ``test_gitcli.py`` alone, which does not cross-check that
``file_list`` / ``envs`` / ``serve_file`` return equivalent results across
providers. PR #70852 showed that gitcli can diverge silently; this module
treats the three providers as a matrix so a future divergence shows up as
a diff.
"""

import pathlib
import shutil
import subprocess
import weakref

import pytest

import salt.utils.gitfs as utils_gitfs

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(
        shutil.which("git") is None, reason="system git binary required"
    ),
]


@pytest.fixture(scope="module")
def local_remote(tmp_path_factory):
    """Build a local bare repo with base + a non-base branch, and files in each."""
    root = tmp_path_factory.mktemp("gitfs-matrix")
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
    (work / "top.sls").write_text("base: top\n", encoding="utf-8")
    (work / "common.sls").write_text("base: common\n", encoding="utf-8")
    (work / "subdir").mkdir()
    (work / "subdir" / "nested.sls").write_text("base: nested\n", encoding="utf-8")
    _git("add", ".")
    _git("commit", "-q", "-m", "seed base")

    _git("checkout", "-q", "-b", "dev")
    (work / "common.sls").write_text("dev: common\n", encoding="utf-8")
    (work / "dev-only.sls").write_text("dev: only\n", encoding="utf-8")
    _git("add", ".")
    _git("commit", "-q", "-m", "seed dev")

    _git("clone", "-q", "--bare", str(work), str(bare))
    return bare.as_uri()


def _provider_params():
    """Build a parametrize list, letting pytest skip at collection time
    if a given library is unavailable rather than hiding whole runs."""
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
        pytest.param("gitcli", id="gitcli"),
    ]


@pytest.fixture
def gitfs(master_opts, tmp_path, local_remote, request, monkeypatch):
    """A fresh GitFS instance bound to ``local_remote`` for the given provider."""
    provider = request.param
    opts = master_opts.copy()
    opts.update(
        cachedir=str(tmp_path / "cache"),
        sock_dir=str(tmp_path / "sock"),
        fileserver_backend=["gitfs"],
        gitfs_provider=provider,
        gitfs_remotes=[local_remote],
        gitfs_base="master",
        gitfs_root="",
        gitfs_mountpoint="",
        gitfs_saltenv=[],
        gitfs_saltenv_whitelist=[],
        gitfs_saltenv_blacklist=[],
        gitfs_ref_types=["branch", "tag"],
        gitfs_disable_saltenv_mapping=False,
        gitfs_depth=1,
    )
    # GitFS caches instances on the opts id; wipe so each parametrize run is
    # isolated and we're not reusing a previously-built provider.
    monkeypatch.setattr(utils_gitfs.GitFS, "instance_map", weakref.WeakKeyDictionary())
    instance = utils_gitfs.GitFS(opts, opts["gitfs_remotes"])
    instance.update()
    return instance


@pytest.mark.parametrize("gitfs", _provider_params(), indirect=True)
def test_envs_lists_configured_branches(gitfs):
    """All three providers must enumerate the same saltenvs for the same tree."""
    envs = set(gitfs.envs(ignore_cache=True))
    # 'master' is implicitly remapped to 'base' by gitfs_base.
    assert "base" in envs
    assert "dev" in envs


@pytest.mark.parametrize("gitfs", _provider_params(), indirect=True)
def test_file_list_base_env(gitfs):
    files = set(gitfs.file_list({"saltenv": "base"}))
    assert {"top.sls", "common.sls", "subdir/nested.sls"} <= files
    # dev-only.sls is only on the dev branch.
    assert "dev-only.sls" not in files


@pytest.mark.parametrize("gitfs", _provider_params(), indirect=True)
def test_file_list_non_base_env(gitfs):
    files = set(gitfs.file_list({"saltenv": "dev"}))
    assert {"top.sls", "common.sls", "dev-only.sls", "subdir/nested.sls"} <= files


@pytest.mark.parametrize("gitfs", _provider_params(), indirect=True)
def test_find_file_and_serve_base(gitfs):
    """find_file + serve_file is the path salt-master takes to hand bytes
    back to a minion. All three providers must return identical bytes for
    the same path in the same env."""
    found = gitfs.find_file("common.sls", "base")
    assert found["rel"] == "common.sls"
    assert found["path"], "find_file returned no on-disk path"
    assert pathlib.Path(found["path"]).read_text(encoding="utf-8") == "base: common\n"

    served = gitfs.serve_file(
        {"path": "salt://common.sls", "saltenv": "base", "loc": 0}, found
    )
    assert served["dest"] == "common.sls"
    assert served["data"] == "base: common\n"


@pytest.mark.parametrize("gitfs", _provider_params(), indirect=True)
def test_find_file_non_base(gitfs):
    """Confirm the content actually tracks the branch, not just the path."""
    found = gitfs.find_file("common.sls", "dev")
    assert found["path"], "find_file returned no on-disk path"
    assert pathlib.Path(found["path"]).read_text(encoding="utf-8") == "dev: common\n"
