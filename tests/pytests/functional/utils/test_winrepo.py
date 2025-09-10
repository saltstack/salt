import os

import pytest

from salt.runners.winrepo import GLOBAL_ONLY, PER_REMOTE_ONLY, PER_REMOTE_OVERRIDES
from salt.utils.gitfs import GitPython, Pygit2, WinRepo
from salt.utils.immutabletypes import ImmutableDict, ImmutableList
from salt.utils.platform import get_machine_identifier as _get_machine_identifier

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
def winrepo_opts(salt_factories, tmp_path):
    config_defaults = {"cachedir": str(tmp_path)}
    factory = salt_factories.salt_master_daemon(
        "winrepo-functional-master", defaults=config_defaults
    )
    config_defaults = dict(factory.config)
    for key, item in config_defaults.items():
        if isinstance(item, ImmutableDict):
            config_defaults[key] = dict(item)
        elif isinstance(item, ImmutableList):
            config_defaults[key] = list(item)
    return config_defaults


@pytest.fixture
def gitpython_winrepo_opts(winrepo_opts):
    winrepo_opts["verified_winrepo_provider"] = "gitpython"
    return winrepo_opts


@pytest.fixture
def pygit2_winrepo_opts(winrepo_opts):
    winrepo_opts["verified_winrepo_provider"] = "pygit2"
    return winrepo_opts


def _get_winrepo(opts, *remotes):
    return WinRepo(
        opts,
        remotes,
        per_remote_overrides=PER_REMOTE_OVERRIDES,
        per_remote_only=PER_REMOTE_ONLY,
        global_only=GLOBAL_ONLY,
    )


@skipif_no_gitpython
def test_gitpython_winrepo_provider(gitpython_winrepo_opts):
    w = _get_winrepo(
        gitpython_winrepo_opts,
        "https://github.com/saltstack/salt-test-pillar-gitfs.git",
    )
    assert len(w.remotes) == 1
    assert w.provider == "gitpython"
    assert isinstance(w.remotes[0], GitPython)


@skipif_no_pygit2
def test_pygit2_winrepo_provider(pygit2_winrepo_opts):
    w = _get_winrepo(
        pygit2_winrepo_opts, "https://github.com/saltstack/salt-test-pillar-gitfs.git"
    )
    assert len(w.remotes) == 1
    assert w.provider == "pygit2"
    assert isinstance(w.remotes[0], Pygit2)


def _test_winrepo_simple(opts):
    w = _get_winrepo(opts, "https://github.com/saltstack/salt-test-pillar-gitfs.git")
    assert len(w.remotes) == 1
    w.checkout()
    repo = w.remotes[0]
    files = set(os.listdir(repo.get_cachedir()))
    for f in (".gitignore", "README.md", "file.sls", "top.sls"):
        assert f in files


@skipif_no_gitpython
def test_gitpython_winrepo_simple(gitpython_winrepo_opts):
    _test_winrepo_simple(gitpython_winrepo_opts)


@skipif_no_pygit2
def test_pygit2_winrepo_simple(pygit2_winrepo_opts):
    _test_winrepo_simple(pygit2_winrepo_opts)


def _test_remote_map(opts):
    p = _get_winrepo(
        opts,
        "https://github.com/saltstack/salt-test-pillar-gitfs.git",
    )
    p.fetch_remotes()
    assert len(p.remotes) == 1
    assert os.path.isfile(os.path.join(opts["cachedir"], "winrepo", "remote_map.txt"))


@skipif_no_gitpython
def test_gitpython_remote_map(gitpython_winrepo_opts):
    _test_remote_map(gitpython_winrepo_opts)


@skipif_no_pygit2
def test_pygit2_remote_map(pygit2_winrepo_opts):
    _test_remote_map(pygit2_winrepo_opts)


def _test_lock(opts):
    mach_id = _get_machine_identifier().get("machine_id", "no_machine_id_available")
    w = _get_winrepo(
        opts,
        "https://github.com/saltstack/salt-test-pillar-gitfs.git",
    )
    w.fetch_remotes()
    assert len(w.remotes) == 1
    repo = w.remotes[0]
    assert repo.get_salt_working_dir() in repo._get_lock_file()
    assert repo.lock() == (
        [
            (
                f"Set update lock for winrepo remote 'https://github.com/saltstack/salt-test-pillar-gitfs.git' on machine_id '{mach_id}'"
            )
        ],
        [],
    )
    assert os.path.isfile(repo._get_lock_file())
    assert repo.clear_lock() == (
        [
            (
                f"Removed update lock for winrepo remote 'https://github.com/saltstack/salt-test-pillar-gitfs.git' on machine_id '{mach_id}'"
            )
        ],
        [],
    )
    assert not os.path.isfile(repo._get_lock_file())


@skipif_no_gitpython
def test_gitpython_lock(gitpython_winrepo_opts):
    _test_lock(gitpython_winrepo_opts)


@skipif_no_pygit2
def test_pygit2_lock(pygit2_winrepo_opts):
    _test_lock(pygit2_winrepo_opts)
