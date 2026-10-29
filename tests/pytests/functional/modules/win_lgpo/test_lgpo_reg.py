"""
Functional tests for salt.modules.win_lgpo_reg covering delete_value,
disable_value, and set_value across the relevant pol/registry state combinations.
"""

import pytest

import salt.modules.win_lgpo_reg as lgpo_reg_mod
import salt.utils.win_functions
import salt.utils.win_lgpo_reg
import salt.utils.win_reg
from tests.support.mock import patch

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
TEST_DATA_ALT = "salt_lgpo_reg_test_updated"
POLICY_CLASS = "Machine"


# ---------------------------------------------------------------------------
# State inspection helpers
# ---------------------------------------------------------------------------


def _pol_active():
    """True when pol has an active (non-disabled) entry for the test value."""
    result = lgpo_reg_mod.get_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )
    return bool(result) and not str(result.get("data", "")).startswith("**del.")


def _pol_disabled():
    """True when pol has a **del. entry for the test value."""
    result = lgpo_reg_mod.get_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )
    return str(result.get("data", "")).startswith("**del.")


def _pol_data():
    """Return the pol data value, or None if absent."""
    result = lgpo_reg_mod.get_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )
    return result.get("data")


def _reg_present():
    result = salt.utils.win_reg.read_value(hive="HKLM", key=TEST_KEY, vname=TEST_NAME)
    return result["success"] and result["vdata"] is not None


def _reg_data():
    result = salt.utils.win_reg.read_value(hive="HKLM", key=TEST_KEY, vname=TEST_NAME)
    return result.get("vdata")


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


def _set_pol_and_reg(data=TEST_DATA):
    """Write an active value to both pol and registry."""
    lgpo_reg_mod.set_value(
        key=TEST_KEY,
        v_name=TEST_NAME,
        v_data=data,
        v_type=TEST_TYPE,
        policy_class=POLICY_CLASS,
    )


def _set_reg_only(data=TEST_DATA):
    """Write a value directly to the registry, bypassing pol."""
    salt.utils.win_reg.set_value(
        hive="HKLM",
        key=TEST_KEY,
        vname=TEST_NAME,
        vdata=data,
        vtype=TEST_TYPE,
    )


def _set_pol_disabled():
    """Write **del.name to pol and delete the registry value."""
    _set_pol_and_reg()
    lgpo_reg_mod.disable_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )


def _cleanup():
    lgpo_reg_mod.delete_value(key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS)
    salt.utils.win_reg.delete_value(hive="HKLM", key=TEST_KEY, vname=TEST_NAME)


@pytest.fixture(autouse=True)
def clean_policy():
    _cleanup()
    yield
    _cleanup()


# ---------------------------------------------------------------------------
# delete_value
# ---------------------------------------------------------------------------


def test_delete_value_pol_absent_reg_absent():
    """
    Scenario 1: pol absent, reg absent -> nothing to do, returns None.
    """
    assert not _pol_active()
    assert not _reg_present()

    ret = lgpo_reg_mod.delete_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )

    assert ret is None
    assert not _pol_active()
    assert not _reg_present()


def test_delete_value_pol_absent_reg_present():
    """
    Scenario 2 (the bug): pol absent, reg present -> registry entry must be
    deleted even though pol had nothing to remove.
    """
    _set_reg_only()
    assert not _pol_active()
    assert _reg_present()

    ret = lgpo_reg_mod.delete_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )

    assert ret is True
    assert not _pol_active()
    assert not _reg_present()


def test_delete_value_pol_present_reg_present():
    """
    Scenario 3: pol present, reg present -> both removed, returns True.
    """
    _set_pol_and_reg()
    assert _pol_active()
    assert _reg_present()

    ret = lgpo_reg_mod.delete_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )

    assert ret is True
    assert not _pol_active()
    assert not _reg_present()


def test_delete_value_pol_present_reg_absent():
    """
    Scenario 4: pol present, reg absent -> pol entry removed even though
    registry value is already gone, returns True.
    """
    _set_pol_and_reg()
    salt.utils.win_reg.delete_value(hive="HKLM", key=TEST_KEY, vname=TEST_NAME)
    assert _pol_active()
    assert not _reg_present()

    ret = lgpo_reg_mod.delete_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )

    assert ret is True
    assert not _pol_active()
    assert not _reg_present()


# ---------------------------------------------------------------------------
# disable_value
# ---------------------------------------------------------------------------


def test_disable_value_already_disabled_reg_absent():
    """
    Scenario 1: pol already has **del. entry, reg absent -> nothing to do,
    returns None.
    """
    _set_pol_disabled()
    assert _pol_disabled()
    assert not _reg_present()

    ret = lgpo_reg_mod.disable_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )

    assert ret is None
    assert _pol_disabled()
    assert not _reg_present()


def test_disable_value_already_disabled_reg_present():
    """
    Scenario 2 (the bug): pol already has **del. entry, reg present ->
    registry entry must be deleted even though pol needed no change.
    """
    _set_pol_disabled()
    _set_reg_only()
    assert _pol_disabled()
    assert _reg_present()

    ret = lgpo_reg_mod.disable_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )

    assert ret is True
    assert _pol_disabled()
    assert not _reg_present()


def test_disable_value_pol_active_reg_present():
    """
    Scenario 3: pol has active entry, reg present -> pol converted to **del.,
    registry deleted, returns True.
    """
    _set_pol_and_reg()
    assert _pol_active()
    assert _reg_present()

    ret = lgpo_reg_mod.disable_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )

    assert ret is True
    assert _pol_disabled()
    assert not _reg_present()


def test_disable_value_pol_active_reg_absent():
    """
    Scenario 4: pol has active entry, reg absent -> pol converted to **del.,
    registry was already gone, returns True.
    """
    _set_pol_and_reg()
    salt.utils.win_reg.delete_value(hive="HKLM", key=TEST_KEY, vname=TEST_NAME)
    assert _pol_active()
    assert not _reg_present()

    ret = lgpo_reg_mod.disable_value(
        key=TEST_KEY, v_name=TEST_NAME, policy_class=POLICY_CLASS
    )

    assert ret is True
    assert _pol_disabled()
    assert not _reg_present()


# ---------------------------------------------------------------------------
# set_value
# ---------------------------------------------------------------------------


def test_set_value_pol_absent_reg_absent():
    """
    New value: creates entry in both pol and registry, returns True.
    """
    assert not _pol_active()
    assert not _reg_present()

    ret = lgpo_reg_mod.set_value(
        key=TEST_KEY,
        v_name=TEST_NAME,
        v_data=TEST_DATA,
        v_type=TEST_TYPE,
        policy_class=POLICY_CLASS,
    )

    assert ret is True
    assert _pol_active()
    assert _reg_data() == TEST_DATA


def test_set_value_update_existing():
    """
    Update: overwrites an existing pol and registry entry with new data,
    returns True.
    """
    _set_pol_and_reg(data=TEST_DATA)
    assert _pol_data() == TEST_DATA
    assert _reg_data() == TEST_DATA

    ret = lgpo_reg_mod.set_value(
        key=TEST_KEY,
        v_name=TEST_NAME,
        v_data=TEST_DATA_ALT,
        v_type=TEST_TYPE,
        policy_class=POLICY_CLASS,
    )

    assert ret is True
    assert _pol_data() == TEST_DATA_ALT
    assert _reg_data() == TEST_DATA_ALT


def test_set_value_enable_disabled():
    """
    Enable: converts a **del. pol entry back to an active entry and sets the
    registry value, returns True.
    """
    _set_pol_disabled()
    assert _pol_disabled()
    assert not _reg_present()

    ret = lgpo_reg_mod.set_value(
        key=TEST_KEY,
        v_name=TEST_NAME,
        v_data=TEST_DATA,
        v_type=TEST_TYPE,
        policy_class=POLICY_CLASS,
    )

    assert ret is True
    assert _pol_active()
    assert not _pol_disabled()
    assert _reg_data() == TEST_DATA


# ---------------------------------------------------------------------------
# set_value: write_registry
# ---------------------------------------------------------------------------


def test_set_value_write_registry_false_skips_registry():
    """write_registry=False: pol entry created, registry left untouched."""
    ret = lgpo_reg_mod.set_value(
        key=TEST_KEY,
        v_name=TEST_NAME,
        v_data=TEST_DATA,
        v_type=TEST_TYPE,
        policy_class=POLICY_CLASS,
        write_registry=False,
    )
    assert ret is True
    assert _pol_active()
    assert not _reg_present()


def test_set_value_write_registry_false_preserves_existing_reg():
    """write_registry=False: pol updated, pre-existing registry value untouched."""
    _set_reg_only(data=TEST_DATA)
    ret = lgpo_reg_mod.set_value(
        key=TEST_KEY,
        v_name=TEST_NAME,
        v_data=TEST_DATA_ALT,
        v_type=TEST_TYPE,
        policy_class=POLICY_CLASS,
        write_registry=False,
    )
    assert ret is True
    assert _pol_active()
    assert _reg_data() == TEST_DATA  # old value preserved


def test_set_value_write_registry_none_non_dc_writes_registry():
    """write_registry=None on a non-DC: auto-detects and writes registry."""
    with patch.object(
        salt.utils.win_functions, "is_domain_controller", return_value=False
    ):
        ret = lgpo_reg_mod.set_value(
            key=TEST_KEY,
            v_name=TEST_NAME,
            v_data=TEST_DATA,
            v_type=TEST_TYPE,
            policy_class=POLICY_CLASS,
        )
    assert ret is True
    assert _pol_active()
    assert _reg_data() == TEST_DATA


def test_set_value_write_registry_none_dc_skips_registry():
    """write_registry=None on a DC: auto-detects and skips registry write."""
    with patch.object(
        salt.utils.win_functions, "is_domain_controller", return_value=True
    ):
        ret = lgpo_reg_mod.set_value(
            key=TEST_KEY,
            v_name=TEST_NAME,
            v_data=TEST_DATA,
            v_type=TEST_TYPE,
            policy_class=POLICY_CLASS,
        )
    assert ret is True
    assert _pol_active()
    assert not _reg_present()


# ---------------------------------------------------------------------------
# set_value: refresh_policy
# ---------------------------------------------------------------------------


def test_set_value_refresh_policy_calls_util():
    """refresh_policy=True: util refresh_policy() is invoked after pol write."""
    with patch.object(
        salt.utils.win_lgpo_reg, "refresh_policy", return_value=True
    ) as mock_refresh:
        lgpo_reg_mod.set_value(
            key=TEST_KEY,
            v_name=TEST_NAME,
            v_data=TEST_DATA,
            v_type=TEST_TYPE,
            policy_class=POLICY_CLASS,
            write_registry=True,
            refresh_policy=True,
        )
    mock_refresh.assert_called_once()


def test_set_value_refresh_policy_false_does_not_call_util():
    """refresh_policy=False (default): util refresh_policy() is never called."""
    with patch.object(
        salt.utils.win_lgpo_reg, "refresh_policy", return_value=True
    ) as mock_refresh:
        lgpo_reg_mod.set_value(
            key=TEST_KEY,
            v_name=TEST_NAME,
            v_data=TEST_DATA,
            v_type=TEST_TYPE,
            policy_class=POLICY_CLASS,
            write_registry=True,
        )
    mock_refresh.assert_not_called()


# ---------------------------------------------------------------------------
# disable_value / delete_value: write_registry
# ---------------------------------------------------------------------------


def test_disable_value_write_registry_false_preserves_registry():
    """disable_value write_registry=False: pol disabled, registry value preserved."""
    _set_pol_and_reg()
    ret = lgpo_reg_mod.disable_value(
        key=TEST_KEY,
        v_name=TEST_NAME,
        policy_class=POLICY_CLASS,
        write_registry=False,
    )
    assert ret is True
    assert _pol_disabled()
    assert _reg_present()  # registry must NOT be deleted


def test_delete_value_write_registry_false_preserves_registry():
    """delete_value write_registry=False: pol removed, registry value preserved."""
    _set_pol_and_reg()
    ret = lgpo_reg_mod.delete_value(
        key=TEST_KEY,
        v_name=TEST_NAME,
        policy_class=POLICY_CLASS,
        write_registry=False,
    )
    assert ret is True
    assert not _pol_active()
    assert _reg_present()  # registry must NOT be deleted


# ---------------------------------------------------------------------------
# standalone refresh_policy
# ---------------------------------------------------------------------------


def test_refresh_policy_module_function():
    """lgpo_reg.refresh_policy() delegates to util and returns bool."""
    with patch.object(
        salt.utils.win_lgpo_reg, "refresh_policy", return_value=True
    ) as mock_refresh:
        ret = lgpo_reg_mod.refresh_policy()
    assert ret is True
    mock_refresh.assert_called_once()
