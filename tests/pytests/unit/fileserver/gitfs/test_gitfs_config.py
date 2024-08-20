import textwrap

import pytest
import tornado.ioloop

import salt.fileserver.gitfs as gitfs
import salt.utils.files
import salt.utils.gitfs
import salt.utils.platform
import salt.utils.win_functions
import salt.utils.yaml
from salt.utils.gitfs import GITPYTHON_MINVER, GITPYTHON_VERSION
from tests.support.mock import patch

try:
    # pylint: disable=unused-import
    import git

    # We still need to use GitPython here for temp repo setup, so we do need to
    # actually import it. But we don't need import pygit2 in this module, we
    # can just use the Version instances imported along with
    # salt.utils.gitfs to check if we have a compatible version.
    HAS_GITPYTHON = GITPYTHON_VERSION >= GITPYTHON_MINVER
except (ImportError, AttributeError):
    HAS_GITPYTHON = False


pytestmark = [
    pytest.mark.skipif(
        not HAS_GITPYTHON, reason=f"GitPython >= {GITPYTHON_MINVER} required"
    )
]


@pytest.fixture
def configure_loader_modules(tmp_path):
    opts = {
        "sock_dir": str(tmp_path / "sock_dir"),
        "gitfs_remotes": ["file://" + str(tmp_path / "repo_dir")],
        "cachedir": str(tmp_path / "cache_dir"),
        "gitfs_root": "",
        "fileserver_backend": ["gitfs"],
        "gitfs_base": "master",
        "gitfs_fallback": "",
        "fileserver_events": True,
        "transport": "zeromq",
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
        "gitfs_ref_types": ["branch", "tag", "sha"],
        "gitfs_update_interval": 60,
        "__role": "master",
    }
    if salt.utils.platform.is_windows():
        opts["gitfs_remotes"][0] = opts["gitfs_remotes"][0].replace("\\", "/")

    return {gitfs: {"__opts__": opts}}


@pytest.fixture(scope="module", autouse=True)
def clear_instance_map():
    try:
        del salt.utils.gitfs.GitFS.instance_map[tornado.ioloop.IOLoop.current()]
    except KeyError:
        pass


def test_per_saltenv_config():
    opts_override = textwrap.dedent(
        """
        gitfs_root: salt

        gitfs_saltenv:
          - baz:
            # when loaded, the "salt://" prefix will be removed
            - mountpoint: salt://baz_mountpoint
            - ref: baz_branch
            - root: baz_root

        gitfs_remotes:

          - file://{0}tmp/repo1:
            - saltenv:
              - foo:
                - ref: foo_branch
                - root: foo_root

          - file://{0}tmp/repo2:
            - mountpoint: repo2
            - saltenv:
              - baz:
                - mountpoint: abc
    """.format(
            "/" if salt.utils.platform.is_windows() else ""
        )
    )
    with patch.dict(gitfs.__opts__, salt.utils.yaml.safe_load(opts_override)):
        git_fs = salt.utils.gitfs.GitFS(
            gitfs.__opts__,
            gitfs.__opts__["gitfs_remotes"],
            per_remote_overrides=gitfs.PER_REMOTE_OVERRIDES,
            per_remote_only=gitfs.PER_REMOTE_ONLY,
        )

    # repo1 (branch: foo)
    # The mountpoint should take the default (from gitfs_mountpoint), while
    # ref and root should take the per-saltenv params.
    assert git_fs.remotes[0].mountpoint("foo") == ""
    assert git_fs.remotes[0].ref("foo") == "foo_branch"
    assert git_fs.remotes[0].root("foo") == "foo_root"

    # repo1 (branch: bar)
    # The 'bar' branch does not have a per-saltenv configuration set, so
    # each of the below values should fall back to global values.
    assert git_fs.remotes[0].mountpoint("bar") == ""
    assert git_fs.remotes[0].ref("bar") == "bar"
    assert git_fs.remotes[0].root("bar") == "salt"

    # repo1 (branch: baz)
    # The 'baz' branch does not have a per-saltenv configuration set, but
    # it is defined in the gitfs_saltenv parameter, so the values
    # from that parameter should be returned.
    assert git_fs.remotes[0].mountpoint("baz") == "baz_mountpoint"
    assert git_fs.remotes[0].ref("baz") == "baz_branch"
    assert git_fs.remotes[0].root("baz") == "baz_root"

    # repo2 (branch: foo)
    # The mountpoint should take the per-remote mountpoint value of
    # 'repo2', while ref and root should fall back to global values.
    assert git_fs.remotes[1].mountpoint("foo") == "repo2"
    assert git_fs.remotes[1].ref("foo") == "foo"
    assert git_fs.remotes[1].root("foo") == "salt"

    # repo2 (branch: bar)
    # The 'bar' branch does not have a per-saltenv configuration set, so
    # the mountpoint should take the per-remote mountpoint value of
    # 'repo2', while ref and root should fall back to global values.
    assert git_fs.remotes[1].mountpoint("bar") == "repo2"
    assert git_fs.remotes[1].ref("bar") == "bar"
    assert git_fs.remotes[1].root("bar") == "salt"

    # repo2 (branch: baz)
    # The 'baz' branch has the mountpoint configured as a per-saltenv
    # parameter. The other two should take the values defined in
    # gitfs_saltenv.
    assert git_fs.remotes[1].mountpoint("baz") == "abc"
    assert git_fs.remotes[1].ref("baz") == "baz_branch"
    assert git_fs.remotes[1].root("baz") == "baz_root"
