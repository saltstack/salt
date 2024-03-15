import logging

import pytest

import salt.modules.cmdmod as cmd
import salt.modules.win_file as win_file
import salt.modules.win_lgpo as win_lgpo
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
    pytest.mark.slow_test,
]


@pytest.fixture
def configure_loader_modules(tmp_path):
    cachedir = tmp_path / "__test_admx_policy_cache_dir"
    cachedir.mkdir(parents=True, exist_ok=True)
    return {
        win_lgpo: {
            "__salt__": {
                "cmd.run": cmd.run,
                "file.file_exists": win_file.file_exists,
                "file.remove": win_file.remove,
            },
            "__opts__": {
                "cachedir": str(cachedir),
            },
        },
    }


def test_load_secedit_data():
    result = win_lgpo._load_secedit_data()
    result = [x.strip() for x in result]
    assert "[Unicode]" in result
    assert "[System Access]" in result


def test_get_secedit_data():
    with patch.dict(win_lgpo.__context__, {}):
        result = win_lgpo._get_secedit_data()
    result = [x.strip() for x in result]
    assert "[Unicode]" in result
    assert "[System Access]" in result


def test_get_secedit_data_existing_context():
    mock_context = {"lgpo.secedit_data": ["spongebob", "squarepants"]}
    with patch.dict(win_lgpo.__context__, mock_context):
        result = win_lgpo._get_secedit_data()
    result = [x.strip() for x in result]
    assert "spongebob" in result
    assert "squarepants" in result


def test_get_secedit_value():
    result = win_lgpo._get_secedit_value("AuditDSAccess")
    assert result == "0"


def test_get_secedit_value_not_defined():
    result = win_lgpo._get_secedit_value("Spongebob")
    assert result == "Not Defined"


def test_write_secedit_data_import_fail(caplog):
    patch_cmd_retcode = patch.dict(
        win_lgpo.__salt__, {"cmd.retcode": MagicMock(return_value=1)}
    )
    with caplog.at_level(logging.DEBUG):
        with patch_cmd_retcode:
            assert win_lgpo._write_secedit_data("spongebob") is False
            assert "Secedit failed to import template data" in caplog.text


def test_write_secedit_data_configure_fail(caplog):
    patch_cmd_retcode = patch.dict(
        win_lgpo.__salt__, {"cmd.retcode": MagicMock(side_effect=[0, 1])}
    )
    with caplog.at_level(logging.DEBUG):
        with patch_cmd_retcode:
            assert win_lgpo._write_secedit_data("spongebob") is False
            assert "Secedit failed to apply security database" in caplog.text
