import pytest

from salt.fileserver.gitfs import PER_REMOTE_ONLY, PER_REMOTE_OVERRIDES
from salt.utils.gitfs import GitFS, GitPython, Pygit2
from salt.utils.immutabletypes import ImmutableDict, ImmutableList

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
def gitfs_opts(salt_factories, tmp_path):
    config_defaults = {"cachedir": str(tmp_path)}
    factory = salt_factories.salt_master_daemon(
        "gitfs-functional-master", defaults=config_defaults
    )
    config_defaults = dict(factory.config)
    for key, item in config_defaults.items():
        if isinstance(item, ImmutableDict):
            config_defaults[key] = dict(item)
        elif isinstance(item, ImmutableList):
            config_defaults[key] = list(item)
    return config_defaults


@pytest.fixture
def gitpython_gitfs_opts(gitfs_opts):
    gitfs_opts["verified_gitfs_provider"] = "gitpython"
    GitFS.instance_map.clear()
    return gitfs_opts


@pytest.fixture
def pygit2_gitfs_opts(gitfs_opts):
    gitfs_opts["verified_gitfs_provider"] = "pygit2"
    GitFS.instance_map.clear()
    return gitfs_opts


def _test_gitfs_simple(gitfs_opts):
    g = GitFS(
        gitfs_opts,
        ["https://github.com/saltstack/salt-test-pillar-gitfs.git"],
        per_remote_overrides=PER_REMOTE_OVERRIDES,
        per_remote_only=PER_REMOTE_ONLY,
    )
    g.fetch_remotes()
    assert len(g.remotes) == 1
    assert set(g.file_list({"saltenv": "main"})) == {".gitignore", "README.md"}


@skipif_no_gitpython
def test_gitpython_gitfs_simple(gitpython_gitfs_opts):
    _test_gitfs_simple(gitpython_gitfs_opts)


@skipif_no_pygit2
def test_pygit2_gitfs_simple(pygit2_gitfs_opts):
    _test_gitfs_simple(pygit2_gitfs_opts)


def _test_gitfs_simple_base(gitfs_opts):
    g = GitFS(
        gitfs_opts,
        ["https://github.com/saltstack/salt-test-pillar-gitfs.git"],
        per_remote_overrides=PER_REMOTE_OVERRIDES,
        per_remote_only=PER_REMOTE_ONLY,
    )
    g.fetch_remotes()
    assert len(g.remotes) == 1
    assert set(g.file_list({"saltenv": "base"})) == {
        ".gitignore",
        "README.md",
        "file.sls",
        "top.sls",
    }


@skipif_no_gitpython
def test_gitpython_gitfs_simple_base(gitpython_gitfs_opts):
    _test_gitfs_simple_base(gitpython_gitfs_opts)


@skipif_no_pygit2
def test_pygit2_gitfs_simple_base(pygit2_gitfs_opts):
    _test_gitfs_simple_base(pygit2_gitfs_opts)


@skipif_no_gitpython
def test_gitpython_gitfs_provider(gitpython_gitfs_opts):
    g = GitFS(
        gitpython_gitfs_opts,
        ["https://github.com/saltstack/salt-test-pillar-gitfs.git"],
        per_remote_overrides=PER_REMOTE_OVERRIDES,
        per_remote_only=PER_REMOTE_ONLY,
    )
    assert len(g.remotes) == 1
    assert g.provider == "gitpython"
    assert isinstance(g.remotes[0], GitPython)


@skipif_no_pygit2
def test_pygit2_gitfs_provider(pygit2_gitfs_opts):
    g = GitFS(
        pygit2_gitfs_opts,
        ["https://github.com/saltstack/salt-test-pillar-gitfs.git"],
        per_remote_overrides=PER_REMOTE_OVERRIDES,
        per_remote_only=PER_REMOTE_ONLY,
    )
    assert len(g.remotes) == 1
    assert g.provider == "pygit2"
    assert isinstance(g.remotes[0], Pygit2)
