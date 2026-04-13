import os
import subprocess
import pytest
import salt.utils.gitfs
from tests.support.mock import MagicMock, patch

@pytest.fixture
def minion_opts(tmp_path):
    opts = {
        "cachedir": str(tmp_path / "cache"),
        "gitfs_depth": 1,
        "gitfs_ssl_verify": True,
        "gitfs_refspecs": ["+refs/heads/*:refs/remotes/origin/*"],
        "gitfs_root": "",
        "gitfs_mountpoint": "",
        "gitfs_base": "master",
        "gitfs_fallback": "",
        "gitfs_saltenv": [],
        "gitfs_ref_types": ["branch", "tag", "sha"],
        "gitfs_update_interval": 60,
        "gitfs_disable_saltenv_mapping": False,
        "gitfs_saltenv_whitelist": [],
        "gitfs_saltenv_blacklist": [],
        "gitfs_insecure_auth": False,
        "hash_type": "sha256",
        "__role": "master",
        "sock_dir": str(tmp_path / "sock"),
    }
    for param in salt.utils.gitfs.AUTH_PARAMS:
        opts[f"gitfs_{param}"] = ""
    return opts

@pytest.fixture
def gitcli(minion_opts, tmp_path):
    remote = "https://github.com/saltstack/salt.git"
    per_remote_defaults = {
        "mountpoint": "",
        "root": "",
        "ssl_verify": True,
        "update_interval": 60,
        "refspecs": ["+refs/heads/*:refs/remotes/origin/*"],
        "base": "master",
        "fallback": "",
        "saltenv": {},
        "ref_types": ["branch", "tag", "sha"],
        "disable_saltenv_mapping": False,
        "saltenv_whitelist": [],
        "saltenv_blacklist": [],
        "insecure_auth": False,
        "user": "",
        "password": "",
        "pubkey": "",
        "privkey": "",
        "proxy": "",
    }
    per_remote_only = ("all_saltenvs", "name", "saltenv")
    override_params = tuple(per_remote_defaults)
    cache_root = str(tmp_path / "gitfs")
    
    # We mock init_remote to avoid actually running git during construction
    with patch("salt.utils.gitfs.GitCLI.init_remote", return_value=True):
        return salt.utils.gitfs.GitCLI(
            minion_opts,
            remote,
            per_remote_defaults,
            per_remote_only,
            override_params,
            cache_root,
        )

def test_init(gitcli):
    assert gitcli.provider == "gitcli"
    assert gitcli.depth == 1

def test_run_git(gitcli):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"out", stderr=b"")
        res = gitcli._run_git(["status"])
        assert res.returncode == 0
        mock_run.assert_called()
        # Verify env has no SSL_NO_VERIFY by default
        args, kwargs = mock_run.call_args
        assert "GIT_SSL_NO_VERIFY" not in kwargs["env"]

def test_run_git_no_ssl_verify(gitcli):
    gitcli.ssl_verify = False
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        gitcli._run_git(["status"])
        args, kwargs = mock_run.call_args
        assert kwargs["env"]["GIT_SSL_NO_VERIFY"] == "true"

def test_init_remote_new(gitcli, tmp_path):
    with patch.object(gitcli, "_run_git") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        # Mock empty directory to trigger 'new = True'
        with patch("os.listdir", return_value=[]):
            assert gitcli.init_remote() is True
        assert os.path.exists(gitcli._cachedir)
        assert mock_run.call_count >= 2 # init and remote add

def test_fetch(gitcli):
    with patch.object(gitcli, "_run_git") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert gitcli._fetch() is True
        args, _ = mock_run.call_args
        assert "--depth" in args[0]
        assert "1" in args[0]

def test_envs(gitcli):
    with patch.object(gitcli, "_run_git") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, 
            stdout=b"refs/remotes/origin/master\nrefs/remotes/origin/dev\nrefs/tags/v1.0\n"
        )
        envs = gitcli.envs()
        assert "base" in envs
        assert "dev" in envs
        assert "v1.0" in envs

def test_file_list(gitcli):
    with patch.object(gitcli, "_run_git") as mock_run:
        def side_effect(args, **kwargs):
            if "rev-parse" in args:
                return MagicMock(returncode=0)
            if "ls-tree" in args:
                return MagicMock(
                    returncode=0,
                    stdout=b"100644 blob sha1\tfile1.txt\n120000 blob sha2\tsymlink1\n"
                )
            if "show" in args:
                return MagicMock(returncode=0, stdout=b"target_file")
            return MagicMock(returncode=1)
        
        mock_run.side_effect = side_effect
        files, symlinks = gitcli.file_list("base")
        assert "file1.txt" in files
        assert "symlink1" in files
        assert symlinks["symlink1"] == "target_file"

def test_find_file(gitcli):
    with patch.object(gitcli, "_run_git") as mock_run:
        def side_effect(args, **kwargs):
            if "rev-parse" in args:
                return MagicMock(returncode=0)
            if "ls-tree" in args:
                return MagicMock(
                    returncode=0,
                    stdout=b"100644 blob sha1\tfile1.txt\n"
                )
            if "show" in args:
                return MagicMock(returncode=0, stdout=b"file content")
            return MagicMock(returncode=1)
        
        mock_run.side_effect = side_effect
        blob, sha, mode = gitcli.find_file("file1.txt", "base")
        assert blob.data == b"file content"
        assert sha == "sha1"
        assert mode == 0o100644

def test_dir_list(gitcli):
    with patch.object(gitcli, "_run_git") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0), # rev-parse
            MagicMock(returncode=0, stdout=b"040000 tree sha1\tsubdir1\n") # ls-tree
        ]
        dirs = gitcli.dir_list("base")
        assert "subdir1" in dirs

def test_checkout(gitcli):
    with patch.object(gitcli, "_run_git") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert gitcli.checkout() == gitcli.check_root()

def test_git_version_check_ok(minion_opts, tmp_path):
    remote = "https://github.com/saltstack/salt.git"
    with patch("salt.utils.gitfs.GitCLI._get_git_version", return_value=salt.utils.gitfs.Version("2.3.0")):
        with patch("salt.utils.gitfs.GitCLI.init_remote", return_value=True):
            cli = salt.utils.gitfs.GitCLI(
                minion_opts,
                remote,
                {},
                (),
                (),
                str(tmp_path / "gitfs"),
            )
            assert cli.git_version == "2.3.0"

def test_git_version_check_fail(minion_opts, tmp_path):
    remote = "https://github.com/saltstack/salt.git"
    with patch("salt.utils.gitfs.GitCLI._get_git_version", return_value=salt.utils.gitfs.Version("1.7.0")):
        with patch("salt.utils.gitfs.failhard") as mock_fail:
            salt.utils.gitfs.GitCLI(
                minion_opts,
                remote,
                {},
                (),
                (),
                str(tmp_path / "gitfs"),
            )
            assert mock_fail.called
