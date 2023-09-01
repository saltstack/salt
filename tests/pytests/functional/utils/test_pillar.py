import os

import pytest

from salt.pillar.git_pillar import GLOBAL_ONLY, PER_REMOTE_ONLY, PER_REMOTE_OVERRIDES
from salt.utils.gitfs import GitPillar, GitPython, Pygit2
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
def pillar_opts(salt_factories, tmp_path):
    config_defaults = {"cachedir": str(tmp_path)}
    factory = salt_factories.salt_master_daemon(
        "pillar-functional-master", defaults=config_defaults
    )
    config_defaults = dict(factory.config)
    for key, item in config_defaults.items():
        if isinstance(item, ImmutableDict):
            config_defaults[key] = dict(item)
        elif isinstance(item, ImmutableList):
            config_defaults[key] = list(item)
    return config_defaults


@pytest.fixture
def gitpython_pillar_opts(pillar_opts):
    pillar_opts["verified_git_pillar_provider"] = "gitpython"
    return pillar_opts


@pytest.fixture
def pygit2_pillar_opts(pillar_opts):
    pillar_opts["verified_git_pillar_provider"] = "pygit2"
    return pillar_opts


def _get_pillar(opts, *remotes):
    return GitPillar(
        opts,
        remotes,
        per_remote_overrides=PER_REMOTE_OVERRIDES,
        per_remote_only=PER_REMOTE_ONLY,
        global_only=GLOBAL_ONLY,
    )


@skipif_no_gitpython
def test_gitpython_pillar_provider(gitpython_pillar_opts):
    p = _get_pillar(
        gitpython_pillar_opts, "https://github.com/saltstack/salt-test-pillar-gitfs.git"
    )
    assert len(p.remotes) == 1
    assert p.provider == "gitpython"
    assert isinstance(p.remotes[0], GitPython)


@skipif_no_pygit2
def test_pygit2_pillar_provider(pygit2_pillar_opts):
    p = _get_pillar(
        pygit2_pillar_opts, "https://github.com/saltstack/salt-test-pillar-gitfs.git"
    )
    assert len(p.remotes) == 1
    assert p.provider == "pygit2"
    assert isinstance(p.remotes[0], Pygit2)


def _test_env(opts):
    p = _get_pillar(
        opts, "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git"
    )
    assert len(p.remotes) == 1
    p.checkout()
    repo = p.remotes[0]
    # test that two different pillarenvs can exist at the same time
    files = set(os.listdir(repo.get_cachedir()))
    for f in (".gitignore", "README.md", "file.sls", "top.sls"):
        assert f in files
    opts["pillarenv"] = "main"
    p2 = _get_pillar(
        opts, "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git"
    )
    assert len(p.remotes) == 1
    p2.checkout()
    repo2 = p2.remotes[0]
    files = set(os.listdir(repo2.get_cachedir()))
    for f in (".gitignore", "README.md"):
        assert f in files
    for f in ("file.sls", "top.sls", "back.sls", "rooms.sls"):
        assert f not in files
    assert repo.get_cachedir() != repo2.get_cachedir()
    files = set(os.listdir(repo.get_cachedir()))
    for f in (".gitignore", "README.md", "file.sls", "top.sls"):
        assert f in files

    # double check cache paths
    assert (
        repo.get_cache_hash() == repo2.get_cache_hash()
    )  # __env__ repos share same hash
    assert repo.get_cache_basename() != repo2.get_cache_basename()
    assert repo.get_linkdir() != repo2.get_linkdir()
    assert repo.get_salt_working_dir() != repo2.get_salt_working_dir()
    assert repo.get_cache_basename() == "master"
    assert repo2.get_cache_basename() == "main"

    assert repo.get_cache_basename() in repo.get_cachedir()
    assert (
        os.path.join(repo.get_cache_basehash(), repo.get_cache_basename())
        == repo.get_cache_full_basename()
    )
    assert repo.get_linkdir() not in repo.get_cachedir()
    assert repo.get_salt_working_dir() not in repo.get_cachedir()


@skipif_no_gitpython
def test_gitpython_env(gitpython_pillar_opts):
    _test_env(gitpython_pillar_opts)


@skipif_no_pygit2
def test_pygit2_env(pygit2_pillar_opts):
    _test_env(pygit2_pillar_opts)


def _test_checkout_fetch_on_fail(opts):
    p = _get_pillar(opts, "https://github.com/saltstack/salt-test-pillar-gitfs.git")
    p.checkout(fetch_on_fail=False)  # TODO write me


@skipif_no_gitpython
def test_gitpython_checkout_fetch_on_fail(gitpython_pillar_opts):
    _test_checkout_fetch_on_fail(gitpython_pillar_opts)


@skipif_no_pygit2
def test_pygit2_checkout_fetch_on_fail(pygit2_pillar_opts):
    _test_checkout_fetch_on_fail(pygit2_pillar_opts)
