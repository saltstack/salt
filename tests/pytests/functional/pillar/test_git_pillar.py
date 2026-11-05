from collections import OrderedDict

import pytest

from salt.pillar.git_pillar import ext_pillar
from salt.utils.immutabletypes import ImmutableDict, ImmutableList
from tests.support.mock import patch

pytestmark = [
    pytest.mark.slow_test,
]


try:
    import git  # pylint: disable=unused-import

    HAS_GITPYTHON = True
except ImportError:
    HAS_GITPYTHON = False


try:
    import pygit2  # pylint: disable=unused-import

    HAS_PYGIT2 = True
except ImportError:
    HAS_PYGIT2 = False


skipif_no_gitpython = pytest.mark.skipif(not HAS_GITPYTHON, reason="Missing gitpython")
skipif_no_pygit2 = pytest.mark.skipif(not HAS_PYGIT2, reason="Missing pygit2")


@pytest.fixture
def git_pillar_opts(salt_master, tmp_path):
    opts = dict(salt_master.config)
    opts["cachedir"] = str(tmp_path)
    for key, item in opts.items():
        if isinstance(item, ImmutableDict):
            opts[key] = dict(item)
        elif isinstance(item, ImmutableList):
            opts[key] = list(item)
    return opts


@pytest.fixture
def gitpython_pillar_opts(git_pillar_opts):
    git_pillar_opts["verified_git_pillar_provider"] = "gitpython"
    return git_pillar_opts


@pytest.fixture
def pygit2_pillar_opts(git_pillar_opts):
    git_pillar_opts["verified_git_pillar_provider"] = "pygit2"
    return git_pillar_opts


def _get_ext_pillar(minion, pillar_opts, grains, *repos):
    with patch("salt.pillar.git_pillar.__opts__", pillar_opts, create=True):
        with patch("salt.pillar.git_pillar.__grains__", grains, create=True):
            return ext_pillar(minion, None, *repos)


def _test_simple(pillar_opts, grains):
    data = _get_ext_pillar(
        "minion",
        pillar_opts,
        grains,
        "https://github.com/saltstack/salt-test-pillar-gitfs.git",
    )
    assert data == {"key": "value"}


@skipif_no_gitpython
def test_gitpython_simple(gitpython_pillar_opts, grains):
    _test_simple(gitpython_pillar_opts, grains)


@skipif_no_pygit2
def test_pygit2_simple(pygit2_pillar_opts, grains):
    _test_simple(pygit2_pillar_opts, grains)


def _test_missing_env(pillar_opts, grains):
    data = _get_ext_pillar(
        "minion",
        pillar_opts,
        grains,
        {
            "https://github.com/saltstack/salt-test-pillar-gitfs.git": [
                {"env": "misssing"}
            ]
        },
    )
    assert data == {}


@skipif_no_gitpython
def test_gitpython_missing_env(gitpython_pillar_opts, grains):
    _test_missing_env(gitpython_pillar_opts, grains)


@skipif_no_pygit2
def test_pygit2_missing_env(pygit2_pillar_opts, grains):
    _test_missing_env(pygit2_pillar_opts, grains)


def _test_env(pillar_opts, grains):
    data = _get_ext_pillar(
        "minion",
        pillar_opts,
        grains,
        {
            "other https://github.com/saltstack/salt-test-pillar-gitfs-2.git": [
                {"env": "other_env"}
            ]
        },
    )
    assert data == {"other": "env"}


@skipif_no_gitpython
def test_gitpython_env(gitpython_pillar_opts, grains):
    _test_env(gitpython_pillar_opts, grains)


@skipif_no_pygit2
def test_pygit2_env(pygit2_pillar_opts, grains):
    _test_env(pygit2_pillar_opts, grains)


def _test_branch(pillar_opts, grains):
    data = _get_ext_pillar(
        "minion",
        pillar_opts,
        grains,
        "branch https://github.com/saltstack/salt-test-pillar-gitfs.git",
    )
    assert data == {"key": "data"}


@skipif_no_gitpython
def test_gitpython_branch(gitpython_pillar_opts, grains):
    _test_branch(gitpython_pillar_opts, grains)


@skipif_no_pygit2
def test_pygit2_branch(pygit2_pillar_opts, grains):
    _test_branch(pygit2_pillar_opts, grains)


def _test_simple_dynamic(pillar_opts, grains):
    data = _get_ext_pillar(
        "minion",
        pillar_opts,
        grains,
        "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git",
    )
    assert data == {"key": "value"}


@skipif_no_gitpython
def test_gitpython_simple_dynamic(gitpython_pillar_opts, grains):
    _test_simple_dynamic(gitpython_pillar_opts, grains)


@skipif_no_pygit2
def test_pygit2_simple_dynamic(pygit2_pillar_opts, grains):
    _test_simple_dynamic(pygit2_pillar_opts, grains)


def _test_missing_env_dynamic(pillar_opts, grains):
    data = _get_ext_pillar(
        "minion",
        pillar_opts,
        grains,
        {
            "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git": [
                {"env": "misssing"}
            ]
        },
    )
    assert data == {}


@skipif_no_gitpython
def test_gitpython_missing_env_dynamic(gitpython_pillar_opts, grains):
    _test_missing_env_dynamic(gitpython_pillar_opts, grains)


@skipif_no_pygit2
def test_pygit2_missing_env_dynamic(pygit2_pillar_opts, grains):
    _test_missing_env_dynamic(pygit2_pillar_opts, grains)


def _test_pillarenv_dynamic(pillar_opts, grains):
    pillar_opts["pillarenv"] = "branch"
    data = _get_ext_pillar(
        "minion",
        pillar_opts,
        grains,
        "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git",
    )
    assert data == {"key": "data"}


@skipif_no_gitpython
def test_gitpython_pillarenv_dynamic(gitpython_pillar_opts, grains):
    _test_pillarenv_dynamic(gitpython_pillar_opts, grains)


@skipif_no_pygit2
def test_pygit2_pillarenv_dynamic(pygit2_pillar_opts, grains):
    _test_pillarenv_dynamic(pygit2_pillar_opts, grains)


def _test_multiple(pillar_opts, grains):
    pillar_opts["pillarenv"] = "branch"
    data = _get_ext_pillar(
        "minion",
        pillar_opts,
        grains,
        "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "other https://github.com/saltstack/salt-test-pillar-gitfs-2.git",
    )
    assert data == {"key": "data"}


@skipif_no_gitpython
def test_gitpython_multiple(gitpython_pillar_opts, grains):
    _test_multiple(gitpython_pillar_opts, grains)


@skipif_no_pygit2
def test_pygit2_multiple(pygit2_pillar_opts, grains):
    _test_multiple(pygit2_pillar_opts, grains)


def _test_multiple_2(pillar_opts, grains):
    data = _get_ext_pillar(
        "minion",
        pillar_opts,
        grains,
        "https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "https://github.com/saltstack/salt-test-pillar-gitfs-2.git",
    )
    assert data == {
        "key": "value",
        "key1": "value1",
        "key2": "value2",
        "key4": "value4",
        "data1": "d",
        "data2": "d2",
    }


@skipif_no_gitpython
def test_gitpython_multiple_2(gitpython_pillar_opts, grains):
    _test_multiple_2(gitpython_pillar_opts, grains)


@skipif_no_pygit2
def test_pygit2_multiple_2(pygit2_pillar_opts, grains):
    _test_multiple_2(pygit2_pillar_opts, grains)


def _test_multiple_slash_in_branch_name(pillar_opts, grains):
    pillar_opts["pillarenv"] = "doggy/moggy"
    data = _get_ext_pillar(
        "minion",
        pillar_opts,
        grains,
        "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "other https://github.com/saltstack/salt-test-pillar-gitfs-2.git",
    )
    assert data == {
        "key": "data",
        "foo": OrderedDict(
            [
                ("animals", OrderedDict([("breed", "seadog")])),
                (
                    "feature/baz",
                    OrderedDict(
                        [("test1", "dog"), ("test2", "kat"), ("test3", "gerbil")]
                    ),
                ),
            ]
        ),
    }


@skipif_no_gitpython
def test_gitpython_multiple_slash_in_branch_name(gitpython_pillar_opts, grains):
    _test_multiple_slash_in_branch_name(gitpython_pillar_opts, grains)


@skipif_no_pygit2
def test_pygit2_multiple_slash_in_branch_name(pygit2_pillar_opts, grains):
    _test_multiple_slash_in_branch_name(pygit2_pillar_opts, grains)


# ---------------------------------------------------------------------------
# Issue #64199: ext_pillar ``git`` must accept a commit SHA (full or short) as
# the "branch" argument, matching the behavior of ``gitfs_remotes``.
# ---------------------------------------------------------------------------


@pytest.fixture
def git_pillar_sha_repo(tmp_path_factory):
    """
    Create a local git repository with two commits and a ``pillar/``
    directory. Yields a tuple of (``file://`` URL, first-commit SHA,
    second-commit SHA).
    """
    import subprocess

    repo_dir = tmp_path_factory.mktemp("64199-sha-repo")

    def _git(*args):
        return subprocess.run(
            ["git", "-C", str(repo_dir), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    _git("init", "-q", "-b", "master")
    _git("config", "user.email", "test@example.com")
    _git("config", "user.name", "test")
    pillar_dir = repo_dir / "pillar"
    pillar_dir.mkdir()
    (pillar_dir / "top.sls").write_text("base:\n  '*':\n    - data\n")
    (pillar_dir / "data.sls").write_text("key: v1\n")
    _git("add", "pillar")
    _git("commit", "-q", "-m", "initial")
    sha1 = _git("rev-parse", "HEAD").stdout.strip()
    (pillar_dir / "data.sls").write_text("key: v2\n")
    _git("add", "pillar")
    _git("commit", "-q", "-m", "update")
    sha2 = _git("rev-parse", "HEAD").stdout.strip()
    yield f"file://{repo_dir}", sha1, sha2


def _test_sha_branch(pillar_opts, grains, repo_info, ref):
    url, _sha1, _sha2 = repo_info
    data = _get_ext_pillar(
        "minion",
        pillar_opts,
        grains,
        {f"{ref} {url}": [{"root": "pillar"}, {"env": "base"}]},
    )
    return data


@skipif_no_gitpython
def test_gitpython_full_sha(gitpython_pillar_opts, grains, git_pillar_sha_repo):
    """
    A 40-char commit SHA used in place of a branch name resolves to that
    commit's tree.
    """
    _url, sha1, sha2 = git_pillar_sha_repo
    data = _test_sha_branch(gitpython_pillar_opts, grains, git_pillar_sha_repo, sha2)
    assert data == {"key": "v2"}
    # Also verify a different commit (not just HEAD).
    data = _test_sha_branch(gitpython_pillar_opts, grains, git_pillar_sha_repo, sha1)
    assert data == {"key": "v1"}


@skipif_no_gitpython
def test_gitpython_short_sha(gitpython_pillar_opts, grains, git_pillar_sha_repo):
    """
    A 7-char short SHA resolves the same way as the full SHA.
    """
    _url, _sha1, sha2 = git_pillar_sha_repo
    data = _test_sha_branch(
        gitpython_pillar_opts, grains, git_pillar_sha_repo, sha2[:7]
    )
    assert data == {"key": "v2"}


@skipif_no_gitpython
def test_gitpython_branch_still_works(
    gitpython_pillar_opts, grains, git_pillar_sha_repo
):
    """
    Regression guard: a plain branch name still resolves (fix must not
    change existing semantics).
    """
    data = _test_sha_branch(
        gitpython_pillar_opts, grains, git_pillar_sha_repo, "master"
    )
    assert data == {"key": "v2"}


@skipif_no_gitpython
def test_gitpython_nonexistent_sha(gitpython_pillar_opts, grains, git_pillar_sha_repo):
    """
    A SHA that doesn't exist in the repo fails cleanly (empty pillar, no
    uncaught traceback).
    """
    data = _test_sha_branch(
        gitpython_pillar_opts,
        grains,
        git_pillar_sha_repo,
        "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    )
    assert data == {}


@skipif_no_pygit2
def test_pygit2_full_sha(pygit2_pillar_opts, grains, git_pillar_sha_repo):
    _url, sha1, sha2 = git_pillar_sha_repo
    data = _test_sha_branch(pygit2_pillar_opts, grains, git_pillar_sha_repo, sha2)
    assert data == {"key": "v2"}
    data = _test_sha_branch(pygit2_pillar_opts, grains, git_pillar_sha_repo, sha1)
    assert data == {"key": "v1"}


@skipif_no_pygit2
def test_pygit2_short_sha(pygit2_pillar_opts, grains, git_pillar_sha_repo):
    _url, _sha1, sha2 = git_pillar_sha_repo
    data = _test_sha_branch(pygit2_pillar_opts, grains, git_pillar_sha_repo, sha2[:7])
    assert data == {"key": "v2"}


@skipif_no_pygit2
def test_pygit2_branch_still_works(pygit2_pillar_opts, grains, git_pillar_sha_repo):
    data = _test_sha_branch(pygit2_pillar_opts, grains, git_pillar_sha_repo, "master")
    assert data == {"key": "v2"}


@skipif_no_pygit2
def test_pygit2_nonexistent_sha(pygit2_pillar_opts, grains, git_pillar_sha_repo):
    data = _test_sha_branch(
        pygit2_pillar_opts,
        grains,
        git_pillar_sha_repo,
        "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    )
    assert data == {}
