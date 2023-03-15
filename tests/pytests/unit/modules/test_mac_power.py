"""
mac_power tests
"""

import pytest

import salt.modules.mac_power as mac_power
from salt.exceptions import SaltInvocationError


@pytest.fixture
def configure_loader_modules():
    return {mac_power: {}}


def test_validate_sleep_valid_number():
    """
    test _validate_sleep function with valid number
    """
    assert mac_power._validate_sleep(179) == 179


def test_validate_sleep_invalid_number():
    """
    test _validate_sleep function with invalid number
    """
    pytest.raises(SaltInvocationError, mac_power._validate_sleep, 181)


def test_validate_sleep_valid_string():
    """
    test _validate_sleep function with valid string
    """
    assert mac_power._validate_sleep("never") == "Never"
    assert mac_power._validate_sleep("off") == "Never"


def test_validate_sleep_invalid_string():
    """
    test _validate_sleep function with invalid string
    """
    pytest.raises(SaltInvocationError, mac_power._validate_sleep, "bob")


def test_validate_sleep_bool_true():
    """
    test _validate_sleep function with True
    """
    pytest.raises(SaltInvocationError, mac_power._validate_sleep, True)


def test_validate_sleep_bool_false():
    """
    test _validate_sleep function with False
    """
    assert mac_power._validate_sleep(False) == "Never"


def test_validate_sleep_unexpected():
    """
    test _validate_sleep function with True
    """
    pytest.raises(SaltInvocationError, mac_power._validate_sleep, 172.7)
