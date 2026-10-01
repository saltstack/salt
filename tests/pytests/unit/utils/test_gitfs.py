import importlib
import os
import time

import pytest

import salt.config
import salt.exceptions
import salt.fileserver.gitfs
import salt.utils.gitfs
from salt.exceptions import FileserverConfigError
from tests.support.helpers import patched_environ
from tests.support.mock import MagicMock, patch

try:
    HAS_PYGIT2 = (
        salt.utils.gitfs.PYGIT2_VERSION
        and salt.utils.gitfs.PYGIT2_VERSION >= salt.utils.gitfs.PYGIT2_MINVER
        and salt.utils.gitfs.LIBGIT2_VERSION
        and salt.utils.gitfs.LIBGIT2_VERSION >= salt.utils.gitfs.LIBGIT2_MINVER
    )
except AttributeError:
    HAS_PYGIT2 = False


if HAS_PYGIT2:
    import pygit2

    try:
        from pygit2.enums import ObjectType

        HAS_PYGIT2_ENUMS = True

    except ModuleNotFoundError:
        HAS_PYGIT2_ENUMS = False


@pytest.fixture
def minion_opts(tmp_path):
    """
    Default minion configuration with relative temporary paths to not require root permissions.
    """
    root_dir = tmp_path / "minion"
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["__role"] = "minion"
    opts["root_dir"] = str(root_dir)
    for name in ("cachedir", "pki_dir", "sock_dir", "conf_dir"):
        dirpath = root_dir / name
        dirpath.mkdir(parents=True)
        opts[name] = str(dirpath)
    opts["log_file"] = "logs/minion.log"
    return opts


@pytest.mark.parametrize(
    "role_name,role_class",
    (
        ("gitfs", salt.utils.gitfs.GitFS),
        ("git_pillar", salt.utils.gitfs.GitPillar),
        ("winrepo", salt.utils.gitfs.WinRepo),
    ),
)
def test_provider_case_insensitive_gitfs_provider(minion_opts, role_name, role_class):
    """
    Ensure that both lowercase and non-lowercase values are supported
    """
    provider = "GitPython"
    key = f"{role_name}_provider"
    with patch.object(role_class, "verify_gitpython", MagicMock(return_value=True)):
        with patch.object(role_class, "verify_pygit2", MagicMock(return_value=False)):
            args = [minion_opts, {}]
            kwargs = {"init_remotes": False}
            if role_name == "winrepo":
                kwargs["cache_root"] = "/tmp/winrepo-dir"
            with patch.dict(minion_opts, {key: provider}):
                # Try to create an instance with uppercase letters in
                # provider name. If it fails then a
                # FileserverConfigError will be raised, so no assert is
                # necessary.
                role_class(*args, **kwargs)
            # Now try to instantiate an instance with all lowercase
            # letters. Again, no need for an assert here.
            role_class(*args, **kwargs)


@pytest.mark.parametrize(
    "role_name,role_class",
    (
        ("gitfs", salt.utils.gitfs.GitFS),
        ("git_pillar", salt.utils.gitfs.GitPillar),
        ("winrepo", salt.utils.gitfs.WinRepo),
    ),
)
def test_valid_provider_gitfs_provider(minion_opts, role_name, role_class):
    """
    Ensure that an invalid provider is not accepted, raising a
    FileserverConfigError.
    """

    def _get_mock(verify, provider):
        """
        Return a MagicMock with the desired return value
        """
        return MagicMock(return_value=verify.endswith(provider))

    key = f"{role_name}_provider"
    for provider in salt.utils.gitfs.GIT_PROVIDERS:
        verify = "verify_gitpython"
        mock1 = _get_mock(verify, provider)
        with patch.object(role_class, verify, mock1):
            verify = "verify_pygit2"
            mock2 = _get_mock(verify, provider)
            with patch.object(role_class, verify, mock2):
                args = [minion_opts, {}]
                kwargs = {"init_remotes": False}
                if role_name == "winrepo":
                    kwargs["cache_root"] = "/tmp/winrepo-dir"
                with patch.dict(minion_opts, {key: provider}):
                    role_class(*args, **kwargs)
                with patch.dict(minion_opts, {key: "foo"}):
                    # Set the provider name to a known invalid provider
                    # and make sure it raises an exception.
                    with pytest.raises(FileserverConfigError):
                        role_class(*args, **kwargs)


@pytest.fixture
def _prepare_remote_repository_pygit2(tmp_path):
    remote = os.path.join(tmp_path, "pygit2-repo")
    filecontent = "This is an empty README file"
    filename = "README"
    signature = pygit2.Signature(
        "Dummy Commiter", "dummy@dummy.com", int(time.time()), 0
    )
    repository = pygit2.init_repository(remote, False)
    builder = repository.TreeBuilder()
    tree = builder.write()
    commit = repository.create_commit(
        "HEAD", signature, signature, "Create master branch", tree, []
    )
    repository.create_reference("refs/tags/simple_tag", commit)
    with salt.utils.files.fopen(
        os.path.join(repository.workdir, filename), "w"
    ) as file:
        file.write(filecontent)
    blob = repository.create_blob_fromworkdir(filename)
    builder = repository.TreeBuilder()
    builder.insert(filename, blob, pygit2.GIT_FILEMODE_BLOB)
    tree = builder.write()
    repository.index.read()
    repository.index.add(filename)
    repository.index.write()
    commit = repository.create_commit(
        "HEAD",
        signature,
        signature,
        "Added a README",
        tree,
        [repository.head.target],
    )
    if HAS_PYGIT2_ENUMS:
        repository.create_tag(
            "annotated_tag", commit, ObjectType.COMMIT, signature, "some message"
        )
    else:
        repository.create_tag(
            "annotated_tag", commit, pygit2.GIT_OBJ_COMMIT, signature, "some message"
        )
    return remote


@pytest.fixture
def _prepare_provider(tmp_path, minion_opts, _prepare_remote_repository_pygit2):
    cache = tmp_path / "pygit2-repo-cache"
    minion_opts.update(
        {
            "cachedir": str(cache),
            "gitfs_disable_saltenv_mapping": False,
            "gitfs_base": "master",
            "gitfs_insecure_auth": False,
            "gitfs_mountpoint": "",
            "gitfs_passphrase": "",
            "gitfs_password": "",
            "gitfs_privkey": "",
            "gitfs_provider": "pygit2",
            "gitfs_pubkey": "",
            "gitfs_ref_types": ["branch", "tag", "sha"],
            "gitfs_refspecs": [
                "+refs/heads/*:refs/remotes/origin/*",
                "+refs/tags/*:refs/tags/*",
            ],
            "gitfs_root": "",
            "gitfs_saltenv_blacklist": [],
            "gitfs_saltenv_whitelist": [],
            "gitfs_ssl_verify": True,
            "gitfs_update_interval": 3,
            "gitfs_user": "",
            "verified_gitfs_provider": "pygit2",
        }
    )
    per_remote_defaults = {
        "base": "master",
        "disable_saltenv_mapping": False,
        "insecure_auth": False,
        "ref_types": ["branch", "tag", "sha"],
        "passphrase": "",
        "mountpoint": "",
        "password": "",
        "privkey": "",
        "pubkey": "",
        "refspecs": [
            "+refs/heads/*:refs/remotes/origin/*",
            "+refs/tags/*:refs/tags/*",
        ],
        "root": "",
        "saltenv_blacklist": [],
        "saltenv_whitelist": [],
        "ssl_verify": True,
        "update_interval": 60,
        "user": "",
    }
    per_remote_only = ("all_saltenvs", "name", "saltenv")
    override_params = tuple(per_remote_defaults)
    cache_root = cache / "gitfs"
    role = "gitfs"
    provider = salt.utils.gitfs.Pygit2(
        minion_opts,
        _prepare_remote_repository_pygit2,
        per_remote_defaults,
        per_remote_only,
        override_params,
        str(cache_root),
        role,
    )
    return provider


@pytest.mark.skipif(not HAS_PYGIT2, reason="This host lacks proper pygit2 support")
@pytest.mark.skip_on_windows(
    reason="Skip Pygit2 on windows, due to pygit2 access error on windows"
)
def test_checkout_pygit2(_prepare_provider):
    provider = _prepare_provider
    provider.remotecallbacks = None
    provider.credentials = None
    provider.init_remote()
    provider.fetch()
    provider.branch = "master"
    assert provider.get_cachedir() in provider.checkout()
    provider.branch = "simple_tag"
    assert provider.get_cachedir() in provider.checkout()
    provider.branch = "annotated_tag"
    assert provider.get_cachedir() in provider.checkout()
    provider.branch = "does_not_exist"
    assert provider.checkout() is None


@pytest.mark.skipif(not HAS_PYGIT2, reason="This host lacks proper pygit2 support")
@pytest.mark.skip_on_windows(
    reason="Skip Pygit2 on windows, due to pygit2 access error on windows"
)
def test_checkout_pygit2_with_home_env_unset(_prepare_provider):
    provider = _prepare_provider
    provider.remotecallbacks = None
    provider.credentials = None
    with patched_environ(__cleanup__=["HOME"]):
        assert "HOME" not in os.environ
        importlib.reload(salt.utils.gitfs)
        assert "HOME" in os.environ


@pytest.mark.skipif(not HAS_PYGIT2, reason="This host lacks proper pygit2 support")
@pytest.mark.skip_on_windows(
    reason="Skip Pygit2 on windows, due to pygit2 access error on windows"
)
@pytest.mark.skipif(not HAS_PYGIT2, reason="This host lacks proper pygit2 support")
@pytest.mark.skip_on_windows(
    reason="Skip Pygit2 on windows, due to pygit2 access error on windows"
)
def test_get_cachedir_basename_pygit2(_prepare_provider):
    assert "_" == _prepare_provider.get_cache_basename()


@pytest.mark.skipif(not HAS_PYGIT2, reason="This host lacks proper pygit2 support")
def test_find_file(tmp_path):
    opts = {
        "cachedir": f"{tmp_path / 'cache'}",
        "gitfs_user": "",
        "gitfs_password": "",
        "gitfs_pubkey": "",
        "gitfs_privkey": "",
        "gitfs_passphrase": "",
        "gitfs_insecure_auth": False,
        "gitfs_refspecs": salt.config._DFLT_REFSPECS,
        "gitfs_ssl_verify": True,
        "gitfs_branch": "master",
        "gitfs_base": "master",
        "gitfs_root": "",
        "gitfs_env": "",
        "gitfs_fallback": "",
    }
    remotes = []

    gitfs = salt.utils.gitfs.GitFS(opts, remotes)
    assert gitfs.find_file("asdf") == {"path": "", "rel": ""}


@pytest.mark.skipif(not HAS_PYGIT2, reason="This host lacks proper pygit2 support")
def test_find_file_bad_path(tmp_path):
    opts = {
        "cachedir": f"{tmp_path / 'cache'}",
        "gitfs_user": "",
        "gitfs_password": "",
        "gitfs_pubkey": "",
        "gitfs_privkey": "",
        "gitfs_passphrase": "",
        "gitfs_insecure_auth": False,
        "gitfs_refspecs": salt.config._DFLT_REFSPECS,
        "gitfs_ssl_verify": True,
        "gitfs_branch": "master",
        "gitfs_base": "master",
        "gitfs_root": "",
        "gitfs_env": "",
        "gitfs_fallback": "",
    }
    remotes = []

    gitfs = salt.utils.gitfs.GitFS(opts, remotes)
    with pytest.raises(salt.exceptions.SaltValidationError):
        gitfs.find_file("sdf/../../../asdf")


@pytest.mark.skipif(not HAS_PYGIT2, reason="This host lacks proper pygit2 support")
def test_find_file_bad_env(tmp_path):
    opts = {
        "cachedir": f"{tmp_path / 'cache'}",
        "gitfs_user": "",
        "gitfs_password": "",
        "gitfs_pubkey": "",
        "gitfs_privkey": "",
        "gitfs_passphrase": "",
        "gitfs_insecure_auth": False,
        "gitfs_refspecs": salt.config._DFLT_REFSPECS,
        "gitfs_ssl_verify": True,
        "gitfs_branch": "master",
        "gitfs_base": "master",
        "gitfs_root": "",
        "gitfs_env": "",
        "gitfs_fallback": "",
    }
    remotes = []

    gitfs = salt.utils.gitfs.GitFS(opts, remotes)
    with pytest.raises(salt.exceptions.SaltValidationError):
        gitfs.find_file("asdf", tgt_env="asd/../../../sdf")


@pytest.mark.parametrize(
    "remote,valid",
    [
        ("git@github.com:/saltstack/salt", True),
        ("git@github.com:saltstack/salt", True),
        ("git@github.com/saltstack/salt", False),
        ("ssh://git@github.com/saltstack/salt.git", True),
        ("ssh://git@github.com:22/saltstack/salt.git", True),
        ("https://github.com/salttack/salt.git", True),
        ("https://github.com/\nsaltstack/salt.git", False),
        ("https://git:mypassword@github.com/saltstack/salt.git", True),
        ("file:///srv/git/salt.git", True),
    ],
)
def test_remote_validation(remote, valid):
    assert salt.utils.gitfs.GitFS.validate_remote(remote) is valid


@pytest.mark.parametrize(
    "remote,result",
    [
        ("git@github.com:/saltstack/salt", "ssh://git@github.com/saltstack/salt"),
        ("git@github.com:saltstack/salt", "ssh://git@github.com/saltstack/salt"),
        (
            "ssh://git@github.com/saltstack/salt.git",
            "ssh://git@github.com/saltstack/salt.git",
        ),
        (
            "ssh://git@github.com:22/saltstack/salt.git",
            "ssh://git@github.com:22/saltstack/salt.git",
        ),
        (
            "https://github.com/salttack/salt.git",
            "https://github.com/salttack/salt.git",
        ),
        (
            "https://git:mypassword@github.com/saltstack/salt.git",
            "https://git:mypassword@github.com/saltstack/salt.git",
        ),
        ("file:///srv/git/salt.git", "file:///srv/git/salt.git"),
    ],
)
def test_remote_to_url(remote, result):
    assert salt.utils.gitfs.GitFS.remote_to_url(remote) == result


@pytest.mark.skipif(not HAS_PYGIT2, reason="This host lacks proper pygit2 support")
def test_find_file_subdir(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "refs").mkdir()
    (root / "refs" / "base").mkdir()
    opts = {
        "cachedir": f"{tmp_path / 'cache'}",
        "gitfs_user": "",
        "gitfs_password": "",
        "gitfs_pubkey": "",
        "gitfs_privkey": "",
        "gitfs_passphrase": "",
        "gitfs_insecure_auth": False,
        "gitfs_refspecs": salt.config._DFLT_REFSPECS,
        "gitfs_ssl_verify": True,
        "gitfs_branch": "master",
        "gitfs_base": "master",
        "gitfs_root": "",
        "gitfs_env": "",
        "gitfs_fallback": "",
    }
    remotes = []
    gitfs = salt.utils.gitfs.GitFS(opts, remotes)
    gitfs.cache_root = str(root)
    ret = gitfs.find_file("foo/init.sls")
    assert ret == {"path": "", "rel": ""}


@pytest.fixture
def _pygit2_file_list_repo(tmp_path):
    """
    Build a repository whose tree holds nested directories, regular files, an
    executable, an empty file, symlinks to a file and to a directory, an empty
    directory and a submodule (gitlink) entry whose commit is not in the repo.
    Returns the repository, the root tree and the ids of the trees and
    symlink blobs, which are the only objects file_list needs to load.
    """
    repo = pygit2.init_repository(str(tmp_path / "file-list-repo"))

    def _tree(*entries):
        builder = repo.TreeBuilder()
        for name, oid, mode in entries:
            builder.insert(name, oid, mode)
        return builder.write()

    blob_mode = pygit2.GIT_FILEMODE_BLOB
    link_mode = pygit2.GIT_FILEMODE_LINK
    tree_mode = pygit2.GIT_FILEMODE_TREE
    deep = _tree(("d.txt", repo.create_blob(b"d"), blob_mode))
    sub = _tree(
        ("c.txt", repo.create_blob(b"c"), blob_mode),
        ("deep", deep, tree_mode),
    )
    empty_dir = _tree()
    link_file = repo.create_blob(b"a.txt")
    link_dir = repo.create_blob(b"sub")
    root = _tree(
        ("a.txt", repo.create_blob(b"a"), blob_mode),
        ("run.sh", repo.create_blob(b"#!/bin/sh"), pygit2.GIT_FILEMODE_BLOB_EXECUTABLE),
        ("empty", repo.create_blob(b""), blob_mode),
        ("link_file", link_file, link_mode),
        ("link_dir", link_dir, link_mode),
        ("sub", sub, tree_mode),
        ("empty_dir", empty_dir, tree_mode),
        ("submodule", pygit2.Oid(hex="1" * 40), pygit2.GIT_FILEMODE_COMMIT),
    )
    return {
        "repo": repo,
        "tree": repo[root],
        "loadable": {deep, sub, empty_dir, link_file, link_dir},
    }


class _CountingRepo:
    """
    Wrap a pygit2 repository, recording the object ids looked up through it
    """

    def __init__(self, repo):
        self._repo = repo
        self.looked_up = []
        self.contains_calls = 0

    def __getitem__(self, oid):
        self.looked_up.append(oid)
        return self._repo[oid]

    def __contains__(self, oid):
        self.contains_calls += 1
        return oid in self._repo

    def __getattr__(self, name):
        return getattr(self._repo, name)


def _pygit2_file_list(provider, fixture, root="", mountpoint="", repo=None):
    provider.repo = repo if repo is not None else fixture["repo"]
    with patch.object(provider, "get_tree", return_value=fixture["tree"]):
        with patch.object(provider, "root", return_value=root):
            with patch.object(provider, "mountpoint", return_value=mountpoint):
                return provider.file_list("base")


@pytest.mark.skipif(not HAS_PYGIT2, reason="This host lacks proper pygit2 support")
@pytest.mark.skip_on_windows(
    reason="Skip Pygit2 on windows, due to pygit2 access error on windows"
)
@pytest.mark.parametrize(
    "root,mountpoint,files,symlinks",
    [
        (
            "",
            "",
            {
                "a.txt",
                "run.sh",
                "empty",
                "link_file",
                "link_dir",
                "sub/c.txt",
                "sub/deep/d.txt",
            },
            {"link_file": b"a.txt", "link_dir": b"sub"},
        ),
        (
            "",
            "mp",
            {
                "mp/a.txt",
                "mp/run.sh",
                "mp/empty",
                "mp/link_file",
                "mp/link_dir",
                "mp/sub/c.txt",
                "mp/sub/deep/d.txt",
            },
            {"mp/link_file": b"a.txt", "mp/link_dir": b"sub"},
        ),
        ("sub", "", {"c.txt", "deep/d.txt"}, {}),
        ("sub", "mp/x", {"mp/x/c.txt", "mp/x/deep/d.txt"}, {}),
        ("sub/deep", "", {"d.txt"}, {}),
        # A root that is missing, is a file, is a symlink or is a submodule
        # yields nothing
        ("missing", "", set(), {}),
        ("a.txt", "", set(), {}),
        ("link_dir", "", set(), {}),
        ("submodule", "", set(), {}),
    ],
)
def test_pygit2_file_list(
    _prepare_provider, _pygit2_file_list_repo, root, mountpoint, files, symlinks
):
    """
    Symlinks are listed as files and their (bytes) target is recorded, they are
    never followed. Empty directories add nothing and submodules are skipped.
    """
    ret = _pygit2_file_list(
        _prepare_provider, _pygit2_file_list_repo, root=root, mountpoint=mountpoint
    )
    assert ret == (files, symlinks)


@pytest.mark.skipif(not HAS_PYGIT2, reason="This host lacks proper pygit2 support")
@pytest.mark.skip_on_windows(
    reason="Skip Pygit2 on windows, due to pygit2 access error on windows"
)
def test_pygit2_file_list_no_tree(_prepare_provider, _pygit2_file_list_repo):
    _prepare_provider.repo = _pygit2_file_list_repo["repo"]
    with patch.object(_prepare_provider, "get_tree", return_value=None):
        assert _prepare_provider.file_list("base") == (set(), {})


@pytest.mark.skipif(not HAS_PYGIT2, reason="This host lacks proper pygit2 support")
@pytest.mark.skip_on_windows(
    reason="Skip Pygit2 on windows, due to pygit2 access error on windows"
)
def test_pygit2_file_list_only_loads_trees_and_symlinks(
    _prepare_provider, _pygit2_file_list_repo
):
    """
    Regular blobs must not be loaded from the object database while building
    the file list, that made refreshing the file list cache very slow for big
    repositories (issue #55419).
    """
    counting = _CountingRepo(_pygit2_file_list_repo["repo"])
    files, _ = _pygit2_file_list(
        _prepare_provider, _pygit2_file_list_repo, repo=counting
    )
    assert len(files) == 7
    assert counting.contains_calls == 0
    assert set(counting.looked_up) <= _pygit2_file_list_repo["loadable"]
