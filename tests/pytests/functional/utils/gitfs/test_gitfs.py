import os.path

import pytest

from salt.fileserver.gitfs import PER_REMOTE_ONLY, PER_REMOTE_OVERRIDES
from salt.utils.gitfs import GitFS, GitPython, Pygit2
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
    GitFS.instance_map.clear()  # wipe instance_map object map for clean run
    return gitfs_opts


@pytest.fixture
def pygit2_gitfs_opts(gitfs_opts):
    gitfs_opts["verified_gitfs_provider"] = "pygit2"
    GitFS.instance_map.clear()  # wipe instance_map object map for clean run
    return gitfs_opts


def _get_gitfs(opts, *remotes):
    return GitFS(
        opts,
        remotes,
        per_remote_overrides=PER_REMOTE_OVERRIDES,
        per_remote_only=PER_REMOTE_ONLY,
    )


def _test_gitfs_simple(gitfs_opts):
    g = _get_gitfs(
        gitfs_opts,
        {"https://github.com/saltstack/salt-test-pillar-gitfs.git": [{"name": "bob"}]},
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
    g = _get_gitfs(
        gitfs_opts, "https://github.com/saltstack/salt-test-pillar-gitfs.git"
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
    g = _get_gitfs(
        gitpython_gitfs_opts, "https://github.com/saltstack/salt-test-pillar-gitfs.git"
    )
    assert len(g.remotes) == 1
    assert g.provider == "gitpython"
    assert isinstance(g.remotes[0], GitPython)


@skipif_no_pygit2
def test_pygit2_gitfs_provider(pygit2_gitfs_opts):
    g = _get_gitfs(
        pygit2_gitfs_opts, "https://github.com/saltstack/salt-test-pillar-gitfs.git"
    )
    assert len(g.remotes) == 1
    assert g.provider == "pygit2"
    assert isinstance(g.remotes[0], Pygit2)


def _test_gitfs_minion(gitfs_opts):
    gitfs_opts["__role"] = "minion"
    g = _get_gitfs(
        gitfs_opts, "https://github.com/saltstack/salt-test-pillar-gitfs.git"
    )
    g.fetch_remotes()
    assert len(g.remotes) == 1
    assert set(g.file_list({"saltenv": "base"})) == {
        ".gitignore",
        "README.md",
        "file.sls",
        "top.sls",
    }
    assert set(g.file_list({"saltenv": "main"})) == {".gitignore", "README.md"}


@skipif_no_gitpython
def test_gitpython_gitfs_minion(gitpython_gitfs_opts):
    _test_gitfs_minion(gitpython_gitfs_opts)


@skipif_no_pygit2
def test_pygit2_gitfs_minion(pygit2_gitfs_opts):
    _test_gitfs_minion(pygit2_gitfs_opts)


def _test_fetch_request_with_mountpoint(opts):
    mpoint = [{"mountpoint": "salt/m"}]
    p = _get_gitfs(
        opts,
        {"https://github.com/saltstack/salt-test-pillar-gitfs.git": mpoint},
    )
    p.fetch_remotes()
    assert len(p.remotes) == 1
    repo = p.remotes[0]
    assert repo.mountpoint("testmount") == "salt/m"
    assert set(p.file_list({"saltenv": "testmount"})) == {
        "salt/m/test_dir1/testfile3",
        "salt/m/test_dir1/test_dir2/testfile2",
        "salt/m/.gitignore",
        "salt/m/README.md",
        "salt/m/test_dir1/test_dir2/testfile1",
    }


@skipif_no_gitpython
def test_gitpython_fetch_request_with_mountpoint(gitpython_gitfs_opts):
    _test_fetch_request_with_mountpoint(gitpython_gitfs_opts)


@skipif_no_pygit2
def test_pygit2_fetch_request_with_mountpoint(pygit2_gitfs_opts):
    _test_fetch_request_with_mountpoint(pygit2_gitfs_opts)


def _test_name(opts):
    p = _get_gitfs(
        opts,
        {
            "https://github.com/saltstack/salt-test-pillar-gitfs.git": [
                {"name": "name1"}
            ]
        },
        {
            "https://github.com/saltstack/salt-test-pillar-gitfs.git": [
                {"name": "name2"}
            ]
        },
    )
    p.fetch_remotes()
    assert len(p.remotes) == 2
    repo = p.remotes[0]
    repo2 = p.remotes[1]
    assert repo.get_cache_basehash() == "name1"
    assert repo2.get_cache_basehash() == "name2"


@skipif_no_gitpython
def test_gitpython_name(gitpython_gitfs_opts):
    _test_name(gitpython_gitfs_opts)


@skipif_no_pygit2
def test_pygit2_name(pygit2_gitfs_opts):
    _test_name(pygit2_gitfs_opts)


def _test_remote_map(opts):
    p = _get_gitfs(
        opts,
        "https://github.com/saltstack/salt-test-pillar-gitfs.git",
    )
    p.fetch_remotes()
    assert len(p.remotes) == 1
    assert os.path.isfile(os.path.join(opts["cachedir"], "gitfs", "remote_map.txt"))


@skipif_no_gitpython
def test_gitpython_remote_map(gitpython_gitfs_opts):
    _test_remote_map(gitpython_gitfs_opts)


@skipif_no_pygit2
def test_pygit2_remote_map(pygit2_gitfs_opts):
    _test_remote_map(pygit2_gitfs_opts)


def _test_lock(opts):
    g = _get_gitfs(
        opts,
        "https://github.com/saltstack/salt-test-pillar-gitfs.git",
    )
    g.fetch_remotes()
    assert len(g.remotes) == 1
    repo = g.remotes[0]
    mach_id = _get_machine_identifier().get("machine_id", "no_machine_id_available")
    assert repo.get_salt_working_dir() in repo._get_lock_file()
    assert repo.lock() == (
        [
            (
                f"Set update lock for gitfs remote "
                f"'https://github.com/saltstack/salt-test-pillar-gitfs.git' on machine_id '{mach_id}'"
            )
        ],
        [],
    )
    assert os.path.isfile(repo._get_lock_file())
    assert repo.clear_lock() == (
        [
            (
                f"Removed update lock for gitfs remote "
                f"'https://github.com/saltstack/salt-test-pillar-gitfs.git' on machine_id '{mach_id}'"
            )
        ],
        [],
    )
    assert not os.path.isfile(repo._get_lock_file())


@skipif_no_gitpython
def test_gitpython_lock(gitpython_gitfs_opts):
    _test_lock(gitpython_gitfs_opts)


@skipif_no_pygit2
def test_pygit2_lock(pygit2_gitfs_opts):
    _test_lock(pygit2_gitfs_opts)
