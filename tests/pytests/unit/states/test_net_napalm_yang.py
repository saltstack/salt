"""
    :codeauthor: Anthony Shaw <anthonyshaw@apache.org>

    Test cases for salt.states.net_napalm_yang
"""

import pytest

import salt.states.net_napalm_yang as netyang
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {netyang: {}}


def test_managed():
    ret = {"changes": {}, "comment": "Loaded.", "name": "test", "result": False}
    parse = MagicMock(return_value="abcdef")
    temp_file = MagicMock(return_value="")
    compliance_report = MagicMock(return_value={"complies": False})
    load_config = MagicMock(return_value={"comment": "Loaded."})
    file_remove = MagicMock()

    with patch("salt.utils.files.fopen"):
        with patch.dict(
            netyang.__salt__,
            {
                "temp.file": temp_file,
                "napalm_yang.parse": parse,
                "napalm_yang.load_config": load_config,
                "napalm_yang.compliance_report": compliance_report,
                "file.remove": file_remove,
            },
        ):
            with patch.dict(netyang.__opts__, {"test": False}):
                assert netyang.managed("test", "test", models=("model1",)) == ret
                assert parse.called
                assert temp_file.called
                assert compliance_report.called
                assert load_config.called
                assert file_remove.called


def test_configured():
    ret = {"changes": {}, "comment": "Loaded.", "name": "test", "result": False}
    load_config = MagicMock(return_value={"comment": "Loaded."})

    with patch("salt.utils.files.fopen"):
        with patch.dict(netyang.__salt__, {"napalm_yang.load_config": load_config}):
            with patch.dict(netyang.__opts__, {"test": False}):
                assert netyang.configured("test", "test", models=("model1",)) == ret

                assert load_config.called
