"""Exercise GitCLI path resolution through the shared GitFS fileserver."""

import pathlib
import subprocess
import weakref

import pytest

from salt.fileserver.gitfs import PER_REMOTE_ONLY, PER_REMOTE_OVERRIDES
from salt.utils.gitfs import GitFS

pytestmark = [pytest.mark.skip_if_binaries_missing("git")]


@pytest.fixture(scope="module")
def remote_repo(tmp_path_factory):
    repo = tmp_path_factory.mktemp("gitcli-root")

    def git(*args, **kwargs):
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            **kwargs,
        )

    git("init", "-q", "-b", "main")
    git("config", "user.name", "Salt Test")
    git("config", "user.email", "salt-test@example.invalid")
    git("config", "commit.gpgsign", "false")
    for name, content in {
        "top.sls": "repository root\n",
        "salt/top.sls": "configured root\n",
        "salt/example/init.sls": "nested file\n",
        "salt/salt/top.sls": "wrong: root applied twice\n",
    }.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git("add", ".")
    # Commit a relative symlink without requiring filesystem symlink privileges.
    target_sha = git("hash-object", "-w", "--stdin", input=b"top.sls").stdout.strip()
    git(
        "update-index",
        "--add",
        "--cacheinfo",
        "120000",
        target_sha.decode(),
        "salt/link.sls",
    )
    git("commit", "-q", "-m", "Seed root resolution fixtures")
    return repo.as_uri()


@pytest.mark.parametrize("root_config", ["none", "global", "remote", "saltenv"])
@pytest.mark.parametrize("mountpoint", ["", "overlay"])
def test_find_file_with_root(
    master_opts, tmp_path, remote_repo, root_config, mountpoint, monkeypatch
):
    opts = master_opts.copy()
    opts.update(
        cachedir=str(tmp_path / "cache"),
        gitfs_provider="gitcli",
        gitfs_base="main",
        gitfs_root="salt" if root_config == "global" else "",
        gitfs_mountpoint=mountpoint,
        gitfs_saltenv=[],
    )
    remote_options = []
    if root_config == "remote":
        remote_options.append({"root": "salt"})
    elif root_config == "saltenv":
        remote_options.append({"saltenv": [{"base": [{"root": "salt"}]}]})
    remotes = [{remote_repo: remote_options}] if remote_options else [remote_repo]
    opts["gitfs_remotes"] = remotes
    # GitFS instances are cached per process; isolate each configuration.
    monkeypatch.setattr(GitFS, "instance_map", weakref.WeakKeyDictionary())
    gitfs = GitFS(
        opts,
        remotes,
        per_remote_overrides=PER_REMOTE_OVERRIDES,
        per_remote_only=PER_REMOTE_ONLY,
    )
    gitfs.update()

    rooted = root_config != "none"
    expected_files = {
        "top.sls": "configured root\n" if rooted else "repository root\n",
        "example/init.sls" if rooted else "salt/example/init.sls": "nested file\n",
        "link.sls" if rooted else "salt/link.sls": "configured root\n",
    }
    listed_files = gitfs.file_list({"saltenv": "base"})
    for name, expected in expected_files.items():
        path = f"{mountpoint}/{name}" if mountpoint else name
        assert path in listed_files
        found = gitfs.find_file(path, "base")
        assert found["rel"] == path
        assert found["path"], f"Listed file could not be resolved: {path}"
        assert pathlib.Path(found["path"]).read_text(encoding="utf-8") == expected

    if mountpoint:
        assert gitfs.find_file("top.sls", "base") == {"path": "", "rel": ""}
