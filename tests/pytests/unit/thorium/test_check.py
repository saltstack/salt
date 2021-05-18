import salt.thorium.check
from tests.support.mock import patch


def test_len_eq_should_be_equal_when_len_val_equal_to_value():
    expected_name = "fnord"
    expected_result = {
        "name": expected_name,
        "result": True,
        "comment": "",
        "changes": {},
    }
    with patch(
        "salt.thorium.check.__reg__", {expected_name: {"val": [0] * 42}}, create=True,
    ):
        result = salt.thorium.check.len_eq(expected_name, 42)
    assert result == expected_result


def test_len_eq_should_be_not_equal_when_name_not_in_reg():
    expected_name = "fnord"
    expected_result = {
        "name": expected_name,
        "result": False,
        "comment": "Value fnord not in register",
        "changes": {},
    }
    with patch(
        "salt.thorium.check.__reg__",
        {"not expected name": {"val": [0] * 42}},
        create=True,
    ):
        result = salt.thorium.check.len_eq(expected_name, 42)
    assert result == expected_result


def test_len_eq_should_be_not_equal_when_val_not_len_val_equal_to_value():
    expected_name = "fnord"
    expected_result = {
        "name": expected_name,
        "result": False,
        "comment": "",
        "changes": {},
    }
    with patch(
        "salt.thorium.check.__reg__", {expected_name: {"val": "42"}}, create=True,
    ):
        result = salt.thorium.check.len_eq(expected_name, "42")
    assert result == expected_result


def test_len_eq_should_be_not_equal_when_len_is_not_value():
    expected_name = "fnord"
    expected_result = {
        "name": expected_name,
        "result": False,
        "comment": "Value fnord not in register",
        "changes": {},
    }
    with patch(
        "salt.thorium.check.__reg__", {"not expected name": {"val": 42}}, create=True,
    ):
        result = salt.thorium.check.len_eq(expected_name, 42)
    assert result == expected_result
