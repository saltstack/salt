import os

import pytest

from salt.pillar.git_pillar import GLOBAL_ONLY, PER_REMOTE_ONLY, PER_REMOTE_OVERRIDES
from salt.utils.gitfs import GitPillar, GitPython, Pygit2
from salt.utils.immutabletypes import ImmutableDict, ImmutableList
from salt.utils.platform import get_machine_identifier as _get_machine_identifier

pytestmark = [
    pytest.mark.windows_whitelisted,
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


def _test_multiple_repos(opts):
    p = _get_pillar(
        opts,
        "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "main https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "branch https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "__env__ https://github.com/saltstack/salt-test-pillar-gitfs-2.git",
        "other https://github.com/saltstack/salt-test-pillar-gitfs-2.git",
    )
    p.checkout()
    assert len(p.remotes) == 5
    # make sure all repos dont share cache and working dir
    assert len({r.get_cachedir() for r in p.remotes}) == 5
    assert len({r.get_salt_working_dir() for r in p.remotes}) == 5

    p2 = _get_pillar(
        opts,
        "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "main https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "branch https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "__env__ https://github.com/saltstack/salt-test-pillar-gitfs-2.git",
        "other https://github.com/saltstack/salt-test-pillar-gitfs-2.git",
    )
    p2.checkout()
    assert len(p2.remotes) == 5
    # make sure that repos are given same cache dir
    for repo, repo2 in zip(p.remotes, p2.remotes):
        assert repo.get_cachedir() == repo2.get_cachedir()
        assert repo.get_salt_working_dir() == repo2.get_salt_working_dir()
    opts["pillarenv"] = "main"
    p3 = _get_pillar(
        opts,
        "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "main https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "branch https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "__env__ https://github.com/saltstack/salt-test-pillar-gitfs-2.git",
        "other https://github.com/saltstack/salt-test-pillar-gitfs-2.git",
    )
    p3.checkout()
    # check that __env__ has different cache with different pillarenv
    assert p.remotes[0].get_cachedir() != p3.remotes[0].get_cachedir()
    assert p.remotes[1].get_cachedir() == p3.remotes[1].get_cachedir()
    assert p.remotes[2].get_cachedir() == p3.remotes[2].get_cachedir()
    assert p.remotes[3].get_cachedir() != p3.remotes[3].get_cachedir()
    assert p.remotes[4].get_cachedir() == p3.remotes[4].get_cachedir()

    # check that other branch data is in cache
    files = set(os.listdir(p.remotes[4].get_cachedir()))
    for f in (".gitignore", "README.md", "file.sls", "top.sls", "other_env.sls"):
        assert f in files


@skipif_no_gitpython
def test_gitpython_multiple_repos(gitpython_pillar_opts):
    _test_multiple_repos(gitpython_pillar_opts)


@skipif_no_pygit2
def test_pygit2_multiple_repos(pygit2_pillar_opts):
    _test_multiple_repos(pygit2_pillar_opts)


def _test_fetch_request(opts):
    p = _get_pillar(
        opts,
        "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "other https://github.com/saltstack/salt-test-pillar-gitfs-2.git",
    )
    frequest = os.path.join(p.remotes[0].get_salt_working_dir(), "fetch_request")
    frequest_other = os.path.join(p.remotes[1].get_salt_working_dir(), "fetch_request")
    opts["pillarenv"] = "main"
    p2 = _get_pillar(
        opts, "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git"
    )
    frequest2 = os.path.join(p2.remotes[0].get_salt_working_dir(), "fetch_request")
    assert frequest != frequest2
    assert os.path.isfile(frequest) is False
    assert os.path.isfile(frequest2) is False
    assert os.path.isfile(frequest_other) is False
    p.fetch_remotes()
    assert os.path.isfile(frequest) is False
    # fetch request was placed
    assert os.path.isfile(frequest2) is True
    p2.checkout()
    # fetch request was found
    assert os.path.isfile(frequest2) is False
    p2.fetch_remotes()
    assert os.path.isfile(frequest) is True
    assert os.path.isfile(frequest2) is False
    assert os.path.isfile(frequest_other) is False
    for _ in range(3):
        p2.fetch_remotes()
    assert os.path.isfile(frequest) is True
    assert os.path.isfile(frequest2) is False
    assert os.path.isfile(frequest_other) is False
    # fetch request should still be processed even on fetch_on_fail=False
    p.checkout(fetch_on_fail=False)
    assert os.path.isfile(frequest) is False
    assert os.path.isfile(frequest2) is False
    assert os.path.isfile(frequest_other) is False


@skipif_no_gitpython
def test_gitpython_fetch_request(gitpython_pillar_opts):
    _test_fetch_request(gitpython_pillar_opts)


@skipif_no_pygit2
def test_pygit2_fetch_request(pygit2_pillar_opts):
    _test_fetch_request(pygit2_pillar_opts)


def _test_clear_old_remotes(opts):
    p = _get_pillar(
        opts,
        "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git",
        "other https://github.com/saltstack/salt-test-pillar-gitfs-2.git",
    )
    repo = p.remotes[0]
    repo2 = p.remotes[1]
    opts["pillarenv"] = "main"
    p2 = _get_pillar(
        opts, "__env__ https://github.com/saltstack/salt-test-pillar-gitfs.git"
    )
    repo3 = p2.remotes[0]
    assert os.path.isdir(repo.get_cachedir()) is True
    assert os.path.isdir(repo2.get_cachedir()) is True
    assert os.path.isdir(repo3.get_cachedir()) is True
    p.clear_old_remotes()
    assert os.path.isdir(repo.get_cachedir()) is True
    assert os.path.isdir(repo2.get_cachedir()) is True
    assert os.path.isdir(repo3.get_cachedir()) is True
    p2.clear_old_remotes()
    assert os.path.isdir(repo.get_cachedir()) is True
    assert os.path.isdir(repo2.get_cachedir()) is False
    assert os.path.isdir(repo3.get_cachedir()) is True


@skipif_no_gitpython
def test_gitpython_clear_old_remotes(gitpython_pillar_opts):
    _test_clear_old_remotes(gitpython_pillar_opts)


@skipif_no_pygit2
def test_pygit2_clear_old_remotes(pygit2_pillar_opts):
    _test_clear_old_remotes(pygit2_pillar_opts)


def _test_remote_map(opts):
    p = _get_pillar(
        opts,
        "https://github.com/saltstack/salt-test-pillar-gitfs.git",
    )
    p.fetch_remotes()
    assert len(p.remotes) == 1
    assert os.path.isfile(
        os.path.join(opts["cachedir"], "git_pillar", "remote_map.txt")
    )


@skipif_no_gitpython
def test_gitpython_remote_map(gitpython_pillar_opts):
    _test_remote_map(gitpython_pillar_opts)


@skipif_no_pygit2
def test_pygit2_remote_map(pygit2_pillar_opts):
    _test_remote_map(pygit2_pillar_opts)


def _test_lock(opts):
    p = _get_pillar(
        opts,
        "https://github.com/saltstack/salt-test-pillar-gitfs.git",
    )
    p.fetch_remotes()
    assert len(p.remotes) == 1
    repo = p.remotes[0]
    mach_id = _get_machine_identifier().get("machine_id", "no_machine_id_available")
    assert repo.get_salt_working_dir() in repo._get_lock_file()
    assert repo.lock() == (
        [
            (
                f"Set update lock for git_pillar remote "
                f"'https://github.com/saltstack/salt-test-pillar-gitfs.git' on machine_id '{mach_id}'"
            )
        ],
        [],
    )
    assert os.path.isfile(repo._get_lock_file())
    assert repo.clear_lock() == (
        [
            (
                f"Removed update lock for git_pillar remote "
                f"'https://github.com/saltstack/salt-test-pillar-gitfs.git' on machine_id '{mach_id}'"
            )
        ],
        [],
    )
    assert not os.path.isfile(repo._get_lock_file())


@skipif_no_gitpython
def test_gitpython_lock(gitpython_pillar_opts):
    _test_lock(gitpython_pillar_opts)


@skipif_no_pygit2
def test_pygit2_lock(pygit2_pillar_opts):
    _test_lock(pygit2_pillar_opts)
