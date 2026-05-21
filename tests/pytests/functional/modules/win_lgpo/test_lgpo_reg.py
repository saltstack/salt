"""
Functional tests for salt.modules.win_lgpo_reg.delete_value covering all four
combinations of pol/registry state.
"""

import pytest

import salt.modules.win_lgpo_reg as lgpo_reg_mod
import salt.utils.win_reg

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
    pytest.mark.slow_test,
]

TEST_KEY = r"SOFTWARE\Salt\Testing\lgpo_reg"
TEST_NAME = "TestValue"
TEST_TYPE = "REG_SZ"
TEST_DATA = "salt_lgpo_reg_test"
POLICY_CLASS = "Machine"


def _pol_present():
    return bool(
        lgpo_reg_mod.get_value(
            key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
        )
    )


def _reg_present():
    result = salt.utils.win_reg.read_value(hive="HKLM", key=TEST_KEY, vname=TEST_NAME)
    return result["success"] and result["vdata"] is not None


def _set_pol_and_reg():
    """Write the value to both the pol file and the registry."""
    lgpo_reg_mod.set_value(
        key=TEST_KEY,
        v_name=TEST_NAME,
        v_data=TEST_DATA,
        v_type=TEST_TYPE,
        policy_class=POLICY_CLASS,
    )


def _set_reg_only():
    """Write the value directly to the registry, bypassing the pol file."""
    salt.utils.win_reg.set_value(
        hive="HKLM",
        key=TEST_KEY,
        vname=TEST_NAME,
        vdata=TEST_DATA,
        vtype=TEST_TYPE,
    )


def _cleanup():
    lgpo_reg_mod.delete_value(key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS)
    salt.utils.win_reg.delete_value(hive="HKLM", key=TEST_KEY, vname=TEST_NAME)


@pytest.fixture(autouse=True)
def clean_policy():
    _cleanup()
    yield
    _cleanup()


def test_delete_value_pol_absent_reg_absent():
    """
    Scenario 1: pol absent, reg absent -> nothing to do, returns None.
    """
    assert not _pol_present()
    assert not _reg_present()

    ret = lgpo_reg_mod.delete_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )

    assert ret is None
    assert not _pol_present()
    assert not _reg_present()


def test_delete_value_pol_absent_reg_present():
    """
    Scenario 2 (the bug): pol absent, reg present -> registry entry must be
    deleted even though pol had nothing to remove.
    """
    _set_reg_only()
    assert not _pol_present()
    assert _reg_present()

    ret = lgpo_reg_mod.delete_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )

    assert ret is True
    assert not _pol_present()
    assert not _reg_present()


def test_delete_value_pol_present_reg_present():
    """
    Scenario 3: pol present, reg present -> both removed, returns True.
    """
    _set_pol_and_reg()
    assert _pol_present()
    assert _reg_present()

    ret = lgpo_reg_mod.delete_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )

    assert ret is True
    assert not _pol_present()
    assert not _reg_present()


def test_delete_value_pol_present_reg_absent():
    """
    Scenario 4: pol present, reg absent -> pol entry removed even though
    registry value is already gone, returns True.
    """
    _set_pol_and_reg()
    salt.utils.win_reg.delete_value(hive="HKLM", key=TEST_KEY, vname=TEST_NAME)
    assert _pol_present()
    assert not _reg_present()

    ret = lgpo_reg_mod.delete_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )

    assert ret is True
    assert not _pol_present()
    assert not _reg_present()
