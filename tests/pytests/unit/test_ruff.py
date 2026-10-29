"""Exercise incremental linting against real Git revisions and real Ruff output."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "tools" / "precommit" / "ruff.py"
CONFIG = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")


def environment() -> dict[str, str]:
    """Keep fixture repositories independent of the calling Git hook."""
    return {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }


def git(repo: Path, *args: str) -> str:
    """Run Git within a disposable repository."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=environment(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write(repo: Path, name: str, contents: str) -> None:
    """Write a fixture, including its parent directories."""
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def commit(repo: Path) -> str:
    """Create a local fixture revision without running user hooks or signing."""
    git(repo, "add", ".")
    git(
        repo,
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=.git/no-hooks",
        "commit",
        "--quiet",
        "-m",
        "test revision",
    )
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Create a baseline containing an existing unused import."""
    pytest.importorskip("ruff")
    git(tmp_path, "init", "--quiet")
    git(tmp_path, "config", "user.name", "Ruff test")
    git(tmp_path, "config", "user.email", "ruff-test@example.invalid")
    write(tmp_path, "pyproject.toml", CONFIG)
    write(tmp_path, "sample.py", "import os\n\nvalue = 1\n")
    commit(tmp_path)
    return tmp_path


def check(
    repo: Path, *args: str, base_env: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the hook as contributors and CI do, with an explicit environment."""
    env = environment()
    env.pop("RUFF_BASE_REF", None)
    if base_env is not None:
        env["RUFF_BASE_REF"] = base_env
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_existing_violation_survives_line_shifts(repo: Path) -> None:
    write(repo, "sample.py", "# New documentation\n\nimport os\n\nvalue = 2\n")
    result = check(repo)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "0 new violation(s)" in result.stdout


def test_new_violation_in_existing_file_is_blocking(repo: Path) -> None:
    write(repo, "sample.py", "import os\nimport sys\n\nvalue = 1\n")
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "F401 `sys` imported but unused" in result.stdout
    assert "F401 `os`" not in result.stdout


def test_removing_last_use_reports_unchanged_import_line(repo: Path) -> None:
    write(repo, "sample.py", "import os\n\nvalue = os.name\n")
    commit(repo)
    write(repo, "sample.py", "import os\n\nvalue = 'changed'\n")
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "sample.py:1:8: F401" in result.stdout


def test_new_file_and_filename_with_spaces(repo: Path) -> None:
    write(repo, "new module.py", "import sys\n")
    result = check(repo, "new module.py")
    assert result.returncode == 1, result.stderr + result.stdout
    assert "new module.py:1:8: F401" in result.stdout


def test_identical_new_violation_is_not_hidden(repo: Path) -> None:
    write(repo, "sample.py", "def old():\n    import os\n")
    commit(repo)
    write(repo, "sample.py", "def old():\n    import os\n\ndef new():\n    import os\n")
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert result.stdout.count("F401") == 1


def test_rename_preserves_baseline(repo: Path) -> None:
    git(repo, "mv", "sample.py", "renamed.py")
    result = check(repo)
    assert result.returncode == 0, result.stderr + result.stdout


def test_rename_with_new_violation(repo: Path) -> None:
    # Keep enough original content for Git's similarity-based rename detection.
    original = "import os\n\nvalue = 1\n" + "# Existing documentation\n" * 10
    write(repo, "sample.py", original)
    commit(repo)
    git(repo, "mv", "sample.py", "renamed.py")
    write(
        repo,
        "renamed.py",
        original + "\ndef new(items=[]):\n    return items\n",
    )
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "B006" in result.stdout
    assert "F401" not in result.stdout


def test_deleted_file_is_skipped(repo: Path) -> None:
    (repo / "sample.py").unlink()
    result = check(repo, "sample.py")
    assert result.returncode == 0, result.stderr + result.stdout


def test_missing_base_fails_closed(repo: Path) -> None:
    result = check(repo, "--base-ref", "missing-branch")
    assert result.returncode == 2
    assert "Ruff incremental check failed" in result.stderr


def test_explicit_filenames_restrict_check(repo: Path) -> None:
    write(repo, "clean.py", "value = 1\n")
    write(repo, "broken.py", "import sys\n")
    result = check(repo, "clean.py")
    assert result.returncode == 0, result.stderr + result.stdout


@pytest.mark.parametrize("directory", ["salt/ext", "templates"])
def test_vendored_and_template_files_are_excluded(repo: Path, directory: str) -> None:
    filename = f"{directory}/new.py"
    write(repo, filename, "import sys\n")
    result = check(repo, filename)
    assert result.returncode == 0, result.stderr + result.stdout


def test_ci_base_catches_committed_violations(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    write(repo, "sample.py", "import os\nimport sys\n\nvalue = 1\n")
    commit(repo)
    assert check(repo).returncode == 0
    result = check(repo, base_env=base)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "F401 `sys`" in result.stdout


def test_command_line_base_overrides_environment(repo: Path) -> None:
    result = check(repo, "--base-ref", "HEAD", base_env="missing-branch")
    assert result.returncode == 0, result.stderr + result.stdout


def test_staged_addition_is_checked(repo: Path) -> None:
    write(repo, "added.py", "import sys\n")
    git(repo, "add", "added.py")
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "added.py:1:8: F401" in result.stdout


def test_never_autofixes_files(repo: Path) -> None:
    write(
        repo,
        "pyproject.toml",
        CONFIG.replace("target-version", "fix = true\ntarget-version"),
    )
    source = "import sys\n"
    write(repo, "new.py", source)
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert (repo / "new.py").read_text(encoding="utf-8") == source


def test_invalid_ruff_config_fails_closed(repo: Path) -> None:
    write(repo, "pyproject.toml", '[tool.ruff.lint]\nselect = ["INVALID"]\n')
    write(repo, "new.py", "value = 1\n")
    result = check(repo)
    assert result.returncode == 2
    assert "Ruff incremental check failed" in result.stderr


def test_inherited_git_hook_environment_is_isolated(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Use invalid foreign paths so a regression fails without touching another repo.
    monkeypatch.setenv("GIT_DIR", str(repo / "foreign-git-dir"))
    monkeypatch.setenv("GIT_WORK_TREE", str(repo / "foreign-work-tree"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(repo / "foreign-index"))
    monkeypatch.setenv("GIT_CONFIG", str(repo / "foreign-config"))
    assert Path(git(repo, "rev-parse", "--show-toplevel")) == repo
    write(repo, "new.py", "import sys\n")
    base = git(repo, "rev-parse", "HEAD")
    commit(repo)
    result = check(repo, "--base-ref", base)
    assert result.returncode == 1, result.stderr + result.stdout
    assert "new.py:1:8: F401" in result.stdout


@pytest.mark.parametrize(
    "source, code",
    [
        ('message = f"plain text"\n', "F541"),
        ("assert (True, False)\n", "F631"),
        ("if (False, False):\n    pass\n", "F634"),
        (
            "callbacks = []\nfor index in range(3):\n    callbacks.append(lambda: index)\n",
            "B023",
        ),
    ],
)
def test_additional_rules_are_enforced(repo: Path, source: str, code: str) -> None:
    write(repo, "new.py", source)
    result = check(repo)
    assert result.returncode == 1, result.stderr + result.stdout
    assert code in result.stdout
