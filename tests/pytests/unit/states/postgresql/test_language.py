"""
    :codeauthor: Andrew Colin Kissa <andrew@topdog.za.net>
"""

import pytest

import salt.states.postgres_language as postgres_language
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {postgres_language: {}}


def test_present_existing():
    """
    Test present, language is already present in database
    """
    name = "plpgsql"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    mock_language_list = MagicMock(return_value={"plpgsql": name})
    with patch.dict(
        postgres_language.__salt__,
        {"postgres.language_list": mock_language_list},
    ):
        comt = f"Language {name} is already installed"
        ret.update({"comment": comt, "result": True})
        assert postgres_language.present(name, "testdb") == ret


def test_present_non_existing_pass():
    """
    Test present, language not present in database - pass
    """
    name = "plpgsql"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    mock_true = MagicMock(return_value=True)
    mock_empty_language_list = MagicMock(return_value={})
    with patch.dict(
        postgres_language.__salt__,
        {
            "postgres.language_list": mock_empty_language_list,
            "postgres.language_create": mock_true,
        },
    ):
        with patch.dict(postgres_language.__opts__, {"test": True}):
            comt = f"Language {name} is set to be installed"
            ret.update({"comment": comt, "result": None})
            assert postgres_language.present(name, "testdb") == ret

        with patch.dict(postgres_language.__opts__, {"test": False}):
            comt = f"Language {name} has been installed"
            ret.update(
                {"comment": comt, "result": True, "changes": {"plpgsql": "Present"}}
            )
            assert postgres_language.present(name, "testdb") == ret


def test_present_non_existing_fail():
    """
    Test present, language not present in database - fail
    """
    name = "plpgsql"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    mock_false = MagicMock(return_value=False)
    mock_empty_language_list = MagicMock(return_value={})
    with patch.dict(
        postgres_language.__salt__,
        {
            "postgres.language_list": mock_empty_language_list,
            "postgres.language_create": mock_false,
        },
    ):
        with patch.dict(postgres_language.__opts__, {"test": True}):
            comt = f"Language {name} is set to be installed"
            ret.update({"comment": comt, "result": None})
            assert postgres_language.present(name, "testdb") == ret

        with patch.dict(postgres_language.__opts__, {"test": False}):
            comt = f"Failed to install language {name}"
            ret.update({"comment": comt, "result": False})
            assert postgres_language.present(name, "testdb") == ret


def test_absent_existing():
    """
    Test absent, language present in database
    """
    name = "plpgsql"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    mock_true = MagicMock(return_value=True)
    with patch.dict(
        postgres_language.__salt__,
        {"postgres.language_exists": mock_true, "postgres.language_remove": mock_true},
    ):
        with patch.dict(postgres_language.__opts__, {"test": True}):
            comt = f"Language {name} is set to be removed"
            ret.update({"comment": comt, "result": None})
            assert postgres_language.absent(name, "testdb") == ret

        with patch.dict(postgres_language.__opts__, {"test": False}):
            comt = f"Language {name} has been removed"
            ret.update(
                {"comment": comt, "result": True, "changes": {"plpgsql": "Absent"}}
            )
            assert postgres_language.absent(name, "testdb") == ret


def test_absent_non_existing():
    """
    Test absent, language not present in database
    """
    name = "plpgsql"
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    mock_false = MagicMock(return_value=False)
    with patch.dict(
        postgres_language.__salt__, {"postgres.language_exists": mock_false}
    ):
        with patch.dict(postgres_language.__opts__, {"test": True}):
            comt = f"Language {name} is not present so it cannot be removed"
            ret.update({"comment": comt, "result": True})
            assert postgres_language.absent(name, "testdb") == ret
