import os
import time

import pytest

import salt.config
import salt.fileserver.gitfs
import salt.utils.gitfs
from salt.exceptions import FileserverConfigError
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
@pytest.mark.skipif(not HAS_PYGIT2, reason="This host lacks proper pygit2 support")
@pytest.mark.skip_on_windows(
    reason="Skip Pygit2 on windows, due to pygit2 access error on windows"
)
def test_get_cachedir_basename_pygit2(_prepare_provider):
    assert "_" == _prepare_provider.get_cache_basename()
