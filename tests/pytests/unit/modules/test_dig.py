import pytest

import salt.modules.cmdmod as cmdmod
import salt.modules.dig as dig
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        dig: {
            "__salt__": {
                "cmd.run_all": cmdmod.run_all,
            },
        }
    }


def test_dig_cname_found():
    dig_mock = MagicMock(
        return_value={
            "pid": 2018,
            "retcode": 0,
            "stderr": "",
            "stdout": "bellanotte1986.github.io.",
        }
    )
    with patch.dict(dig.__salt__, {"cmd.run_all": dig_mock}):
        assert dig.CNAME("www.eitr.tech") == "bellanotte1986.github.io."


def test_dig_cname_none_found():
    dig_mock = MagicMock(
        return_value={
            "pid": 2022,
            "retcode": 0,
            "stderr": "",
            "stdout": "",
        }
    )
    with patch.dict(dig.__salt__, {"cmd.run_all": dig_mock}):
        assert dig.CNAME("www.google.com") == ""
