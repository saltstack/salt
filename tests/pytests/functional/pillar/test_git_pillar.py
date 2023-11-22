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
