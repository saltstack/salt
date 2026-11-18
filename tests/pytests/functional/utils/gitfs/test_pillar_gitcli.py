"""Check that git_pillar with the GitCLI provider gives the pillar compiler files on disk."""

import concurrent.futures
import pathlib
import subprocess

import pytest

from salt.utils.gitfs import GitPillar

pytestmark = [pytest.mark.skip_if_binaries_missing("git")]


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def remote_repo(tmp_path):
    repo = tmp_path / "remote"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Salt Test")
    _git(repo, "config", "user.email", "salt-test@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    for name, content in {
        "top.sls": "repository root\n",
        "old.sls": "removed later\n",
        "pillar/top.sls": "configured root\n",
    }.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "Seed pillar files")
    return repo


def _checkout(opts, remote_repo):
    pillar = GitPillar(opts, [f"main {remote_repo.as_uri()}"])
    pillar.fetch_remotes()
    pillar.checkout()
    assert list(pillar.pillar_dirs.values()) == ["base"]
    return pathlib.Path(next(iter(pillar.pillar_dirs)))


@pytest.fixture
def gitcli_opts(master_opts, tmp_path):
    opts = master_opts.copy()
    opts.update(
        cachedir=str(tmp_path / "cache"),
        git_pillar_provider="gitcli",
        git_pillar_base="main",
        git_pillar_branch="main",
        git_pillar_root="",
    )
    return opts


@pytest.mark.parametrize("root", ["", "pillar"])
def test_checkout_puts_pillar_files_on_disk(gitcli_opts, remote_repo, root):
    gitcli_opts["git_pillar_root"] = root
    pillar_dir = _checkout(gitcli_opts, remote_repo)
    expected = "configured root\n" if root else "repository root\n"
    assert (pillar_dir / "top.sls").read_text(encoding="utf-8") == expected


def test_checkout_follows_new_commits(gitcli_opts, remote_repo):
    pillar_dir = _checkout(gitcli_opts, remote_repo)
    assert (pillar_dir / "old.sls").exists()

    (remote_repo / "top.sls").write_text("updated\n", encoding="utf-8")
    _git(remote_repo, "rm", "-q", "old.sls")
    _git(remote_repo, "commit", "-q", "-am", "Update pillar files")

    pillar_dir = _checkout(gitcli_opts, remote_repo)
    assert (pillar_dir / "top.sls").read_text(encoding="utf-8") == "updated\n"
    assert not (pillar_dir / "old.sls").exists()


def test_mountpoint_links_to_the_checked_out_files(gitcli_opts, remote_repo):
    gitcli_opts["git_pillar_root"] = "pillar"
    remote = {f"main {remote_repo.as_uri()}": [{"mountpoint": "mnt/point"}]}
    pillar = GitPillar(gitcli_opts, [remote])
    pillar.fetch_remotes()
    pillar.checkout()
    assert list(pillar.pillar_dirs.values()) == ["base"]
    linkdir = pathlib.Path(next(iter(pillar.pillar_dirs)))
    top = linkdir / "mnt" / "point" / "top.sls"
    assert top.read_text(encoding="utf-8") == "configured root\n"


def test_concurrent_checkouts_all_get_the_pillar(gitcli_opts, remote_repo):
    remote = f"main {remote_repo.as_uri()}"
    pillars = [GitPillar(gitcli_opts, [remote]) for _ in range(8)]

    def checkout(pillar):
        pillar.checkout()
        return pillar.pillar_dirs

    with concurrent.futures.ThreadPoolExecutor(len(pillars)) as pool:
        for round_no in range(10):
            content = f"round {round_no}\n"
            (remote_repo / "top.sls").write_text(content, encoding="utf-8")
            _git(remote_repo, "commit", "-q", "-am", content)
            pillars[0].fetch_remotes()

            results = list(pool.map(checkout, pillars))
            assert all(len(dirs) == 1 for dirs in results)
            pillar_dir = pathlib.Path(next(iter(results[0])))
            assert (pillar_dir / "top.sls").read_text(encoding="utf-8") == content
