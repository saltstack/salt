"""
Unit tests for ``salt._process_role``.
"""

import subprocess
import sys
import textwrap

import pytest

import salt._process_role


@pytest.fixture
def clean_role():
    """Save and restore the module-level ``_IS_CLI`` flag."""
    original = salt._process_role._IS_CLI
    salt._process_role._IS_CLI = False
    try:
        yield
    finally:
        salt._process_role._IS_CLI = original


def test_is_cli_default_false(clean_role):
    assert salt._process_role.is_cli() is False


def test_mark_as_cli_sets_flag(clean_role):
    salt._process_role.mark_as_cli()
    assert salt._process_role.is_cli() is True


def test_mark_as_cli_is_idempotent(clean_role):
    salt._process_role.mark_as_cli()
    salt._process_role.mark_as_cli()
    assert salt._process_role.is_cli() is True


def test_flag_defaults_false_in_fresh_interpreter():
    """
    A fresh Python process that imports the module without invoking a
    salt CLI entry point must observe ``is_cli() == False``.  This
    guards against anything module-level (imports, side effects) flipping
    the flag on for daemon processes.
    """
    code = textwrap.dedent(
        """
        import salt._process_role
        print("cli" if salt._process_role.is_cli() else "daemon")
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        check=True,
        text=True,
        timeout=60,
    )
    assert proc.stdout.strip() == "daemon"
