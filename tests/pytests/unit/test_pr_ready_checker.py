"""
Tests for ``tools/check_pr_ready.py``.

The script is the pre-commit gate documented in
:ref:`contributing-what-a-pr-needs`. These tests assert that planted
violations are detected and that clean inputs pass.
"""

import importlib.util
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "tools" / "check_pr_ready.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("tools_check_pr_ready", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def checker():
    return _load_module()


# ---------------------------------------------------------------------------
# Changelog fragment check
# ---------------------------------------------------------------------------


def test_changelog_required_when_salt_source_changes(checker):
    errors = checker.check_changelog(["salt/modules/test.py"])
    assert errors
    assert "changelog" in errors[0].lower()


def test_changelog_skipped_when_no_salt_changes(checker):
    errors = checker.check_changelog(["doc/topics/development/contributing.rst"])
    assert errors == []


def test_changelog_accepts_valid_fragment(checker):
    errors = checker.check_changelog(
        ["salt/modules/test.py", "changelog/12345.fixed.md"]
    )
    assert errors == []


def test_changelog_accepts_cve_fragment(checker):
    errors = checker.check_changelog(
        ["salt/transport/zeromq.py", "changelog/cve-2025-1234.security.md"]
    )
    assert errors == []


def test_changelog_rejects_unknown_type(checker):
    errors = checker.check_changelog(
        ["salt/modules/test.py", "changelog/12345.improved.md"]
    )
    assert errors


# ---------------------------------------------------------------------------
# pytest.mark.skipif reason check
# ---------------------------------------------------------------------------


def test_skipif_with_todo_reason_rejected(tmp_path, checker):
    bad = tmp_path / "test_bad.py"
    bad.write_text(
        "import pytest\n"
        "@pytest.mark.skipif(True, reason='TODO: fix this flake')\n"
        "def test_thing():\n"
        "    assert True\n"
    )
    errors = checker.check_skipif([bad])
    assert errors
    assert "skipif" in errors[0]


def test_skipif_with_real_reason_accepted(tmp_path, checker):
    good = tmp_path / "test_good.py"
    good.write_text(
        "import pytest, sys\n"
        "@pytest.mark.skipif(sys.platform == 'win32', "
        "reason='Linux-only test')\n"
        "def test_thing():\n"
        "    assert True\n"
    )
    errors = checker.check_skipif([good])
    assert errors == []


def test_skipif_with_fixme_reason_rejected(tmp_path, checker):
    bad = tmp_path / "test_bad.py"
    bad.write_text(
        "import pytest\n"
        "@pytest.mark.skipif(True, reason='FIXME broken on macos')\n"
        "def test_thing():\n"
        "    assert True\n"
    )
    errors = checker.check_skipif([bad])
    assert errors


# ---------------------------------------------------------------------------
# print() debug check
# ---------------------------------------------------------------------------


def test_print_in_salt_source_rejected(tmp_path, monkeypatch, checker):
    salt_dir = tmp_path / "salt" / "modules"
    salt_dir.mkdir(parents=True)
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    bad = salt_dir / "naughty.py"
    bad.write_text(
        "def run():\n    print('debug here')\n    return True\n",
    )
    errors = checker.check_debug_prints([bad])
    assert errors
    assert "print()" in errors[0]


def test_print_under_main_guard_accepted(tmp_path, monkeypatch, checker):
    salt_dir = tmp_path / "salt"
    salt_dir.mkdir(parents=True)
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    ok = salt_dir / "ok.py"
    ok.write_text(
        "def main():\n"
        "    return True\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(main())\n"
    )
    errors = checker.check_debug_prints([ok])
    assert errors == []


def test_print_outside_salt_dir_ignored(tmp_path, monkeypatch, checker):
    other = tmp_path / "scripts"
    other.mkdir(parents=True)
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    f = other / "helper.py"
    f.write_text("print('hello')\n")
    errors = checker.check_debug_prints([f])
    assert errors == []


# ---------------------------------------------------------------------------
# Commit-message attribution check
# ---------------------------------------------------------------------------


def test_co_authored_by_rejected(checker):
    msg = (
        "Fix the thing\n\n"
        "Some explanation here.\n\n"
        "Co-Authored-By: Bot <bot@example.com>\n"
    )
    errors = checker.check_attribution(msg)
    assert errors


def test_lowercase_co_authored_rejected(checker):
    msg = "Fix the thing\n\nCo-authored-by: Bot <bot@example.com>\n"
    errors = checker.check_attribution(msg)
    assert errors


def test_claude_attribution_rejected(checker):
    msg = "Fix the thing\n\nGenerated with Claude Code\n"
    errors = checker.check_attribution(msg)
    assert errors


def test_clean_commit_message_accepted(checker):
    msg = (
        "Fix the thing\n\n"
        "The thing was broken because the other thing was wrong.\n"
        "This makes the test deterministic.\n"
    )
    errors = checker.check_attribution(msg)
    assert errors == []
