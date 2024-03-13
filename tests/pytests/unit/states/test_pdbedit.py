import pytest

import salt.modules.pdbedit as pdbedit_mod
import salt.states.pdbedit as pdbedit
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pdbedit: {}, pdbedit_mod: {}}


def test_generate_absent():
    """
    Test salt.states.pdbedit.absent when
    user is already absent
    """
    name = "testname"
    cmd_ret = {"pid": 13172, "retcode": 0, "stdout": "", "stderr": ""}
    with patch.dict(pdbedit.__salt__, {"pdbedit.list": pdbedit_mod.list_users}):
        with patch.dict(
            pdbedit_mod.__salt__, {"cmd.run_all": MagicMock(return_value=cmd_ret)}
        ):
            ret = pdbedit.absent(name)
    assert ret["comment"] == f"account {name} is absent"
