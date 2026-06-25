"""
Smoke-test the gitfs configurations shown in
``doc/topics/tutorials/gitfs.rst``.

For each example layout the docs publish we build a local bare repository and
verify that:

* The fileserver loads with the documented YAML structure (no schema
  errors, no exceptions during ``init`` / ``update`` / ``envs``).
* Both the ``pygit2`` and ``gitpython`` providers can serve the same
  config (each is skipped if its library is unavailable).
* The branches listed in the doc map to fileserver environments.

This guards against the docs drifting away from what the gitfs loader will
actually accept.
"""

import shutil
import subprocess

import pytest

import salt.fileserver.gitfs as gitfs
import salt.utils.gitfs as utils_gitfs
from salt.utils.gitfs import GITPYTHON_VERSION, PYGIT2_VERSION

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(
        shutil.which("git") is None, reason="system git binary required"
    ),
]


HAS_GITPYTHON = GITPYTHON_VERSION is not None
HAS_PYGIT2 = PYGIT2_VERSION is not None


def _run_git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
    )


def _seed_repo(repo_dir, branches=("master",), files=None):
    """
    Build a bare git repo + working tree at ``repo_dir`` with the given
    branches and a couple of top-level files per branch. Returns the bare
    repo path that gitfs should be pointed at.
    """
    files = files or ("top.sls", "init.sls")
    work = repo_dir / "work"
    bare = repo_dir / "bare.git"
    work.mkdir(parents=True)
    _run_git(work, "init", "-q", "-b", branches[0])
    _run_git(work, "config", "user.email", "salt-doc-test@example.invalid")
    _run_git(work, "config", "user.name", "Salt Doc Test")
    for branch in branches:
        if branch != branches[0]:
            _run_git(work, "checkout", "-q", "-b", branch)
        for name in files:
            target = work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# {branch}/{name}\n")
        _run_git(work, "add", *files)
        _run_git(work, "commit", "-q", "-m", f"seed {branch}")
    _run_git(work, "clone", "-q", "--bare", str(work), str(bare))
    return bare


@pytest.fixture
def base_opts(tmp_path):
    """Master opts skeleton matching what gitfs.init() needs."""
    return {
        "cachedir": str(tmp_path / "cache"),
        "sock_dir": str(tmp_path / "sock"),
        "fileserver_backend": ["gitfs"],
        "gitfs_remotes": [],
        "gitfs_root": "",
        "gitfs_base": "master",
        "gitfs_fallback": "",
        "gitfs_mountpoint": "",
        "gitfs_saltenv": [],
        "gitfs_saltenv_whitelist": [],
        "gitfs_saltenv_blacklist": [],
        "gitfs_user": "",
        "gitfs_password": "",
        "gitfs_insecure_auth": False,
        "gitfs_privkey": "",
        "gitfs_pubkey": "",
        "gitfs_passphrase": "",
        "gitfs_refspecs": [
            "+refs/heads/*:refs/remotes/origin/*",
            "+refs/tags/*:refs/tags/*",
        ],
        "gitfs_ssl_verify": True,
        "gitfs_disable_saltenv_mapping": False,
        "gitfs_ref_types": ["branch", "tag"],
        "gitfs_update_interval": 60,
        "gitfs_proxy": "",
        "__role": "master",
        "fileserver_events": False,
        "transport": "zeromq",
    }


def _build_gitfs(opts, remotes, provider):
    """Construct a fresh GitFS instance, isolating from any cached instances."""
    opts = dict(opts)
    opts["gitfs_provider"] = provider
    opts["gitfs_remotes"] = list(remotes)
    utils_gitfs.GitFS.instance_map.clear()
    return utils_gitfs.GitFS(
        opts,
        opts["gitfs_remotes"],
        per_remote_overrides=gitfs.PER_REMOTE_OVERRIDES,
        per_remote_only=gitfs.PER_REMOTE_ONLY,
    )


@pytest.fixture
def documented_simple_repo(tmp_path):
    """A single-branch (master) repo — matches the 'Simple Configuration'
    example."""
    return _seed_repo(tmp_path / "simple", branches=("master",))


@pytest.fixture
def documented_multi_env_repo(tmp_path):
    """A multi-branch repo — matches the 'Branches, Environments, and Top
    Files' example with base/qa/dev branches."""
    return _seed_repo(
        tmp_path / "multi_env",
        branches=("master", "qa", "dev"),
    )


def _provider_params():
    params = []
    if HAS_GITPYTHON:
        params.append(pytest.param("gitpython", id="gitpython"))
    if HAS_PYGIT2:
        params.append(pytest.param("pygit2", id="pygit2"))
    if not params:
        params.append(
            pytest.param(
                "missing",
                marks=pytest.mark.skip(reason="No gitfs provider available"),
                id="no-provider",
            )
        )
    return params


@pytest.mark.parametrize("provider", _provider_params())
def test_simple_remote_loads(provider, base_opts, documented_simple_repo):
    """The minimal 'fileserver_backend: [gitfs]' walkthrough config loads."""
    gfs = _build_gitfs(base_opts, [f"file://{documented_simple_repo}"], provider)
    gfs.update()
    envs = gfs.envs(ignore_cache=True)
    # Default base branch is 'master' — must appear as an env.
    assert "base" in envs


@pytest.mark.parametrize("provider", _provider_params())
def test_multi_env_remote_loads(provider, base_opts, documented_multi_env_repo):
    """qa/dev branches map to saltenvs as the walkthrough advertises."""
    gfs = _build_gitfs(base_opts, [f"file://{documented_multi_env_repo}"], provider)
    gfs.update()
    envs = set(gfs.envs(ignore_cache=True))
    # 'master' is implicitly remapped to 'base'.
    assert {"base", "qa", "dev"} <= envs


@pytest.mark.parametrize("provider", _provider_params())
def test_per_remote_root_loads(provider, base_opts, tmp_path):
    """The per-remote ``root`` example accepts a list-of-dict layout."""
    repo = _seed_repo(
        tmp_path / "rooted",
        branches=("master",),
        files=("subdir/init.sls", "subdir/top.sls", "README.md"),
    )
    gfs = _build_gitfs(
        base_opts,
        [
            {
                f"file://{repo}": [
                    {"root": "subdir"},
                    {"mountpoint": "salt://overlay"},
                ]
            }
        ],
        provider,
    )
    gfs.update()
    envs = gfs.envs(ignore_cache=True)
    assert "base" in envs


@pytest.mark.skipif(not HAS_PYGIT2, reason="auth params only honoured by pygit2")
def test_documented_auth_keys_accepted(base_opts, tmp_path):
    """The auth per-remote keys mentioned in the walkthrough are recognised
    by the loader. We do not drive a real auth session here — credentials are
    only meaningful over HTTPS/SSH, not file:// — but the loader must accept
    the documented YAML shape without raising. Auth params are only honoured
    by the pygit2 provider, so this test is pygit2-only."""
    repo = _seed_repo(tmp_path / "auth", branches=("master",))
    remotes = [
        {
            f"file://{repo}": [
                {"user": "salt-deploy"},
                {"password": "redacted"},
                {"insecure_auth": False},
            ]
        }
    ]
    gfs = _build_gitfs(base_opts, remotes, "pygit2")
    gfs.update()
