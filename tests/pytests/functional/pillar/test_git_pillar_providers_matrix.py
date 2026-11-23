"""
Parametrize the git_pillar common path across all three providers.

Previously ``test_git_pillar.py`` and ``utils/gitfs/test_pillar.py`` covered
``gitpython`` + ``pygit2`` with one-shot tests built against a remote
github.com repository, and ``test_pillar_gitcli.py`` (added in #70852)
covered ``gitcli`` only. This module drives all three providers through a
compiled ``ext_pillar(...)`` return value on the SAME local bare repo, so
a provider that silently returns a different pillar dict (as gitcli did
before #70852) will show up as a diff instead of a missing test.
"""

import copy
import shutil
import subprocess

import pytest

import salt.utils.gitfs as utils_gitfs
from salt.pillar.git_pillar import ext_pillar
from tests.support.mock import patch

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(
        shutil.which("git") is None, reason="system git binary required"
    ),
]


@pytest.fixture(scope="module")
def git_pillar_remote(tmp_path_factory):
    """
    Local bare repo with two branches and a ``pillar/`` subtree. The branch
    names intentionally differ from the pillar_dir name so that the test
    catches a provider that silently resolves against the wrong branch.
    """
    root = tmp_path_factory.mktemp("git-pillar-matrix")
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
    pillar = work / "pillar"
    pillar.mkdir()
    (pillar / "top.sls").write_text("base:\n  '*':\n    - data\n", encoding="utf-8")
    (pillar / "data.sls").write_text("flavor: base\nnumber: 1\n", encoding="utf-8")
    _git("add", ".")
    _git("commit", "-q", "-m", "seed base pillar")

    _git("checkout", "-q", "-b", "qa")
    (pillar / "data.sls").write_text("flavor: qa\nnumber: 2\n", encoding="utf-8")
    _git("add", ".")
    _git("commit", "-q", "-m", "seed qa pillar")

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
            id="gitcli",
        ),
    ]


@pytest.fixture
def pillar_opts(salt_master, tmp_path, request):
    """Fresh opts dict with provider wired in and cachedir isolated per test."""
    provider = request.param
    opts = dict(salt_master.config)
    # Unwrap any immutable types so ext_pillar can mutate them.
    opts = copy.deepcopy(opts)
    opts["cachedir"] = str(tmp_path / "cache")
    opts["git_pillar_provider"] = provider
    opts["git_pillar_base"] = "master"
    opts["git_pillar_root"] = ""
    opts["git_pillar_includes"] = False
    opts["pillarenv"] = None
    opts["__role"] = "master"
    return opts


def _run_ext_pillar(opts, *repos):
    with patch("salt.pillar.git_pillar.__opts__", opts, create=True):
        with patch("salt.pillar.git_pillar.__grains__", {}, create=True):
            return ext_pillar("minion", None, *repos)


@pytest.mark.parametrize("pillar_opts", _provider_params(), indirect=True)
def test_ext_pillar_base_env_compiles(pillar_opts, git_pillar_remote):
    """All providers must compile the base-branch pillar to the same dict."""
    data = _run_ext_pillar(
        pillar_opts,
        {f"master {git_pillar_remote}": [{"root": "pillar"}, {"env": "base"}]},
    )
    assert data == {"flavor": "base", "number": 1}


@pytest.mark.parametrize("pillar_opts", _provider_params(), indirect=True)
def test_ext_pillar_non_base_branch_compiles(pillar_opts, git_pillar_remote):
    """A non-base branch targeted by its branch name must compile its own tree.

    Uses ``env: base`` so the pillar on the ``qa`` branch is still rendered
    with the default saltenv — we're only varying the git branch, not the
    saltenv, which is the common user case (promote a branch of pillar data
    while keeping salt roots consistent)."""
    data = _run_ext_pillar(
        pillar_opts,
        {f"qa {git_pillar_remote}": [{"root": "pillar"}, {"env": "base"}]},
    )
    assert data == {"flavor": "qa", "number": 2}


@pytest.mark.parametrize("pillar_opts", _provider_params(), indirect=True)
def test_ext_pillar_missing_env_returns_empty(pillar_opts, git_pillar_remote):
    """A branch that doesn't exist yields an empty pillar across all providers."""
    data = _run_ext_pillar(
        pillar_opts,
        {
            f"missing {git_pillar_remote}": [
                {"root": "pillar"},
                {"env": "base"},
            ]
        },
    )
    assert data == {}
